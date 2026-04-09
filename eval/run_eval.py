"""Run all approaches over the dataset and write results."""
import argparse
import csv
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from approaches import ALL, BY_NAME
from eval.metrics import score, METRIC_KEYS, diagnose_pred_vs_gold, strip_null_inputs_from_plan

DATASET = os.path.join(os.path.dirname(__file__), "..", "dataset", "out", "dataset.jsonl")
A5_EMBED_INDEX = os.path.join(os.path.dirname(__file__), "..", "dataset", "out", "embeddings.npz")
OUT_DIR = os.path.join(os.path.dirname(__file__), "out")
RESULTS = os.path.join(OUT_DIR, "results.csv")
SUMMARY = os.path.join(OUT_DIR, "summary.csv")
COST_CSV = os.path.join(OUT_DIR, "cost.csv")
PER_REQUEST_CSV = os.path.join(OUT_DIR, "per_request.csv")
PER_REQUEST_FIELDS = ["approach", "item_key", "cost_usd", "latency_seconds", "spent_cumulative_usd"]

from pricing import PRICING, PRICING_FALLBACK
from config import MODEL_MAIN, MODEL_REASONING
from tracker import TRACKER, BudgetExceeded

# Estimated LLM calls and output tokens per approach per sample.
# model is read from config — no hardcoding.
APPROACH_PROFILE = {
    #                          model            calls  in_extra  out_tok
    "a1_structured":    (MODEL_MAIN,                1,       0,   300),
    "a2_reasoning":     (MODEL_REASONING,           1,       0,   300),
    "a3_cot":           (MODEL_MAIN,                1,       0,   600),   # CoT reasoning before JSON
    "a4_fewshot_fixed": (MODEL_MAIN,                1,    1200,   300),   # 3 examples ≈ 1200 tok extra
    "a5_fewshot_retrieval": (MODEL_MAIN,            1,    1200,   300),
    "a6_two_stage":     (MODEL_MAIN,                2,       0,   350),   # 2 calls
    "a7_self_consistency": (MODEL_MAIN,             5,       0,   300),   # 5 samples
    "a8_critic_revise": (MODEL_MAIN,                3,       0,   400),   # generate + critic + revise
    "a9_decomposed_tools": (MODEL_MAIN,             3,       0,   150),   # 3 focused extractors
    "a10_reflexion":    (MODEL_MAIN,                3,       0,   450),   # up to 3 iters
    "a11_skills_agent": (MODEL_MAIN,                2,     600,   300),   # router + extraction
}


def _tok(s: str) -> int:
    """Very rough token count: ~4 chars per token."""
    return max(1, len(s) // 4)


def _avg_row(vals):
    """Average each metric column. Numeric → mean. String → last value (e.g. step_count "3/4")."""
    out = {}
    for k, v in vals.items():
        if not v:
            out[k] = ""
            continue
        if isinstance(v[0], (int, float)):
            out[k] = round(sum(v) / len(v), 4)
        else:
            out[k] = v[-1]
    return out


def append_summary_csv(summary_dict: dict):
    """Acrescenta uma linha por approach (métricas agregadas desta execução). Não apaga histórico."""
    fields = ["approach"] + METRIC_KEYS
    path = SUMMARY
    new_file = not os.path.isfile(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        for name, vals in summary_dict.items():
            if not vals[METRIC_KEYS[0]]:
                continue
            w.writerow({"approach": name, **_avg_row(vals)})


def estimate(approaches, data, base_system_tokens, avg_user_tokens):
    """Print token/cost estimate and ask for confirmation."""
    print("\n" + "=" * 70)
    print("TOKEN ESTIMATE (before running)")
    print("=" * 70)
    print(f"  dataset size : {len(data)} items")
    print(f"  approaches   : {len(approaches)}")
    print(f"  base system  : ~{base_system_tokens} tokens")
    print(f"  avg user msg : ~{avg_user_tokens} tokens")
    print()
    print(f"  {'approach':<26} {'model':<18} {'calls/item':>10} {'in tok/item':>12} {'out tok/item':>13}")
    print(f"  {'-'*26} {'-'*18} {'-'*10} {'-'*12} {'-'*13}")

    grand_cost = 0.0
    for a in approaches:
        prof = APPROACH_PROFILE.get(a.name)
        if not prof:
            print(f"  {a.name:<26} (no profile — skipped from estimate)")
            continue
        model, calls, in_extra, out_tok = prof
        in_per_call = base_system_tokens + avg_user_tokens + in_extra
        in_total_per_item = in_per_call * calls
        out_total_per_item = out_tok * calls
        in_total = in_total_per_item * len(data)
        out_total = out_total_per_item * len(data)
        p = PRICING.get(model, PRICING_FALLBACK)
        ip, op = p[0], p[2]  # input and output price per 1M tokens
        cost = (in_total / 1_000_000 * ip) + (out_total / 1_000_000 * op)
        grand_cost += cost
        print(f"  {a.name:<26} {model:<18} {calls:>10} {in_total_per_item:>12,} {out_total_per_item:>13,}")

    print()
    print(f"  Estimated total API cost: ~${grand_cost:.2f} USD")
    print("=" * 70)
    ans = input("\nContinuar? [s/N] ").strip().lower()
    if ans not in ("s", "sim", "y", "yes"):
        print("Abortado.")
        sys.exit(0)
    print()


def load_dataset():
    with open(DATASET) as f:
        return [json.loads(l) for l in f]


def _item_key(item: dict) -> str:
    """Stable id for resume: dataset id, or sha256 of request text."""
    iid = item.get("id")
    if iid is not None and str(iid) != "":
        return f"id:{iid}"
    h = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
    return f"h:{h}"


def _preds_jsonl_path(approach_name: str) -> str:
    return os.path.join(OUT_DIR, f"{approach_name}_preds.jsonl")


def load_preds_checkpoint(approach_name: str) -> dict:
    """Last line wins per item_key. Supports legacy rows without item_key (hash of text)."""
    path = _preds_jsonl_path(approach_name)
    by_key = {}
    if not os.path.isfile(path):
        return by_key
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = row.get("item_key")
            if not key:
                key = f"h:{hashlib.sha256(row['text'].encode('utf-8')).hexdigest()}"
            by_key[key] = row
    return by_key


def _read_results_csv_rows():
    if not os.path.isfile(RESULTS):
        return []
    with open(RESULTS, newline="") as f:
        return list(csv.DictReader(f))


def write_merged_results(selected_approaches, data, resume: bool):
    """Rewrite results.csv: recomputed rows for selected approaches (from jsonl) + untouched rows for others."""
    fieldnames = ["approach", "item_key"] + METRIC_KEYS
    item_by_key = {_item_key(it): it for it in data}
    key_order = [_item_key(it) for it in data]
    key_index = {k: i for i, k in enumerate(key_order)}
    skip_approaches = {a.name for a in selected_approaches}

    merged = []
    for a in selected_approaches:
        ckpt = load_preds_checkpoint(a.name)
        for key in key_order:
            if key not in ckpt:
                continue
            it = item_by_key[key]
            gold = it["plan"]
            pred = strip_null_inputs_from_plan(ckpt[key]["pred"])
            s = score(pred, gold)
            merged.append({"approach": a.name, "item_key": key, **s})

    if resume:
        for row in _read_results_csv_rows():
            if row.get("approach") not in skip_approaches:
                merged.append(row)

    merged.sort(key=lambda r: (r["approach"], key_index.get(r.get("item_key") or "", 10**9)))

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(RESULTS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in merged:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--approaches", type=str, default=None, help="comma-separated names")
    ap.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    ap.add_argument("--budget", type=float, default=2.0, help="max USD to spend; stops when exceeded")
    ap.add_argument(
        "--no-resume",
        action="store_true",
        help="ignore *_preds.jsonl checkpoints (re-call API); truncate preds jsonl for each approach",
    )
    args = ap.parse_args()
    resume = not args.no_resume

    TRACKER.set_budget(args.budget)

    if args.approaches:
        names = [n.strip() for n in args.approaches.split(",")]
        approaches = []
        for n in names:
            if n in BY_NAME:
                approaches.append(BY_NAME[n])
            else:
                # prefix match: "a1" matches "a1_structured"
                matches = [a for a in ALL if a.name == n or a.name.startswith(n + "_")]
                if not matches and n in ("a5", "a5_fewshot", "a5_fewshot_retrieval"):
                    assert False, (
                        f"a5_fewshot_retrieval não está registado — falta o índice de embeddings:\n"
                        f"  {A5_EMBED_INDEX}\n"
                        f"Gera com:\n"
                        f"  python approaches/a5_fewshot_retrieval.py --build-index\n"
                        f"Approaches disponíveis agora: {list(BY_NAME)}"
                    )
                assert matches, f"no approach found for '{n}'. available: {list(BY_NAME)}"
                approaches.extend(matches)
    else:
        approaches = ALL

    data = load_dataset()
    if args.limit:
        data = data[: args.limit]

    # ── Estimate ──────────────────────────────────────────────────────────────
    from prompts.shared import SYSTEM_BASE
    base_system_tokens = _tok(SYSTEM_BASE)
    avg_user_tokens = sum(_tok(item["text"]) for item in data) // max(len(data), 1) + 50

    if not args.yes:
        estimate(approaches, data, base_system_tokens, avg_user_tokens)

    # ── Run ───────────────────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)

    # Tell a5 which ids are in the eval split so it never retrieves them.
    eval_ids = [item.get("id") for item in data if item.get("id")]
    for a in approaches:
        if hasattr(a, "set_eval_ids"):
            a.set_eval_ids(eval_ids)

    # Pre-compute estimated cost per approach for comparison during run.
    est_per_approach = {}
    for a in approaches:
        prof = APPROACH_PROFILE.get(a.name)
        if prof:
            model, calls, in_extra, out_tok = prof
            in_per_item = (base_system_tokens + avg_user_tokens + in_extra) * calls
            out_per_item = out_tok * calls
            p = PRICING.get(model, PRICING_FALLBACK)
            est_per_approach[a.name] = (
                (in_per_item * len(data) / 1_000_000 * p[0]) +
                (out_per_item * len(data) / 1_000_000 * p[2])
            )

    summary = {a.name: {k: [] for k in METRIC_KEYS} for a in approaches}
    cost_per_request = {a.name: [] for a in approaches}  # real USD per request
    time_per_request = {a.name: [] for a in approaches}  # wall time per predict() (all LLM calls)
    os.makedirs(OUT_DIR, exist_ok=True)
    if not resume and os.path.isfile(COST_CSV):
        os.remove(COST_CSV)
    if not resume and os.path.isfile(PER_REQUEST_CSV):
        os.remove(PER_REQUEST_CSV)

    def _append_per_request_row(approach_name, item_key, cost_usd: float, latency_seconds: float, spent_cumulative: float):
        path = PER_REQUEST_CSV
        new_file = not os.path.isfile(path) or os.path.getsize(path) == 0
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=PER_REQUEST_FIELDS)
            if new_file:
                w.writeheader()
            w.writerow(
                {
                    "approach": approach_name,
                    "item_key": item_key,
                    "cost_usd": round(cost_usd, 6),
                    "latency_seconds": round(latency_seconds, 6),
                    "spent_cumulative_usd": round(spent_cumulative, 6),
                }
            )

    # Per-approach prediction log: one JSONL per approach, append mode.
    def _log_pred(approach_name, item_key, text, pred, gold, scores: dict):
        path = _preds_jsonl_path(approach_name)
        diagnostics = diagnose_pred_vs_gold(pred, gold)
        diagnostics["accuracy"] = scores["accuracy"]
        diagnostics["flights_acc"] = scores["flights_acc"]
        diagnostics["hotels_acc"] = scores["hotels_acc"]
        with open(path, "a") as f:
            f.write(
                json.dumps(
                    {
                        "item_key": item_key,
                        "text": text,
                        "pred": pred,
                        "gold": gold,
                        "diagnostics": diagnostics,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _upsert_cost_csv(approach_name, mean_price, mean_seconds):
        cost_rows = []
        if os.path.isfile(COST_CSV):
            with open(COST_CSV, newline="") as f:
                for r in csv.DictReader(f):
                    cost_rows.append(
                        {
                            "approach": r.get("approach"),
                            "mean_cost_usd": r.get("mean_cost_usd", r.get("mean_price", "")),
                            "mean_latency_seconds": r.get(
                                "mean_latency_seconds", r.get("mean_seconds", "")
                            ),
                        }
                    )
        cost_rows = [r for r in cost_rows if r.get("approach") != approach_name]
        cost_rows.append(
            {
                "approach": approach_name,
                "mean_cost_usd": round(mean_price, 6),
                "mean_latency_seconds": round(mean_seconds, 6),
            }
        )
        with open(COST_CSV, "w", newline="") as cf:
            cw = csv.DictWriter(cf, fieldnames=["approach", "mean_cost_usd", "mean_latency_seconds"])
            cw.writeheader()
            cw.writerows(cost_rows)

    try:
        for a in approaches:
            spent_before_approach = TRACKER.spent_usd
            if args.no_resume:
                pj = _preds_jsonl_path(a.name)
                if os.path.isfile(pj):
                    os.remove(pj)
            ckpt = {} if args.no_resume else load_preds_checkpoint(a.name)
            n_skipped = sum(1 for item in data if _item_key(item) in ckpt)
            if n_skipped:
                print(f"  (resume) {n_skipped}/{len(data)} itens já em {a.name}_preds.jsonl — a pular API")

            print(f"\n{'─'*70}")
            est = est_per_approach.get(a.name)
            est_str = f"~${est:.4f}" if est is not None else "unknown"
            print(f"  APPROACH: {a.name}  |  estimated: {est_str}  |  total spent so far: ${TRACKER.spent_usd:.4f}")
            print(f"{'─'*70}")

            for item in data:
                text = item["text"]
                gold = item["plan"]
                ik = _item_key(item)
                row_tag = item.get("id") if item.get("id") is not None else ik[:12]

                if ik in ckpt:
                    pred = strip_null_inputs_from_plan(ckpt[ik]["pred"])
                    s = score(pred, gold)
                    for k in METRIC_KEYS:
                        summary[a.name][k].append(s[k])
                    print(
                        f"  [{row_tag}] (resume) "
                        f"acc={s['accuracy']:.2f}  "
                        f"flights={s['flights_acc']:.2f}  "
                        f"hotels={s['hotels_acc']:.2f}  "
                        f"steps={s['step_count']}  "
                        f"| req=—  —s | cum=${TRACKER.spent_usd:.4f}  budget=${args.budget:.2f}"
                    )
                else:
                    spent_before_request = TRACKER.spent_usd
                    t0 = time.perf_counter()
                    if a.name == "a5_fewshot_retrieval":
                        pred = a.predict(text, exclude_id=item.get("id"))
                    else:
                        pred = a.predict(text)
                    elapsed = time.perf_counter() - t0
                    req_cost = TRACKER.spent_usd - spent_before_request
                    time_per_request[a.name].append(elapsed)
                    cost_per_request[a.name].append(req_cost)
                    _append_per_request_row(a.name, ik, req_cost, elapsed, TRACKER.spent_usd)
                    pred = strip_null_inputs_from_plan(pred)

                    s = score(pred, gold)
                    _log_pred(a.name, ik, text, pred, gold, s)
                    ckpt[ik] = {"pred": pred, "text": text, "item_key": ik}
                    for k in METRIC_KEYS:
                        summary[a.name][k].append(s[k])
                    print(
                        f"  [{row_tag}] "
                        f"acc={s['accuracy']:.2f}  "
                        f"flights={s['flights_acc']:.2f}  "
                        f"hotels={s['hotels_acc']:.2f}  "
                        f"steps={s['step_count']}  "
                        f"| req=${req_cost:.4f}  {elapsed:>6.2f}s | cum=${TRACKER.spent_usd:.4f}  budget=${args.budget:.2f}"
                    )

                # Grava results.csv a cada item (crash / budget stop preserva o que já correu).
                write_merged_results(approaches, data, resume)

            real_this = TRACKER.spent_usd - spent_before_approach
            est_this = est_per_approach.get(a.name, 0)
            print(f"  ✓ {a.name} done  est=${est_this:.4f}  real=${real_this:.4f}  diff={real_this - est_this:+.4f}")

            reqs = cost_per_request[a.name]
            treqs = time_per_request[a.name]
            mean_price = sum(reqs) / len(reqs) if reqs else 0.0
            mean_seconds = sum(treqs) / len(treqs) if treqs else 0.0
            if reqs:
                _upsert_cost_csv(a.name, mean_price, mean_seconds)

            # Print cost / latency summary so far
            print(f"\n  {'─'*40}")
            print(f"  COST & LATENCY (média só sobre chamadas novas nesta run — US$, s)")
            for name, reqs_ in cost_per_request.items():
                if reqs_:
                    ts = time_per_request[name]
                    tmean = sum(ts) / len(ts) if ts else 0.0
                    print(
                        f"    {name:<26}  mean_cost=${sum(reqs_)/len(reqs_):.6f}  mean_lat={tmean:>8.3f}s"
                    )
            print(f"  {'─'*40}\n")

    except BudgetExceeded as e:
        print(f"\n!! STOPPED: {e}")
    finally:
        try:
            write_merged_results(approaches, data, resume)
        except Exception as ex:
            print(f"(aviso: não foi possível atualizar {RESULTS}: {ex})")
        try:
            append_summary_csv(summary)
        except Exception as ex:
            print(f"(aviso: não foi possível atualizar {SUMMARY}: {ex})")

    TRACKER.print_summary()

    print("\n=== FINAL SUMMARY ===")
    header = f"  {'approach':<26}" + "".join(f"{k:>14}" for k in METRIC_KEYS)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, vals in summary.items():
        if not vals[METRIC_KEYS[0]]:
            continue
        row = _avg_row(vals)
        cells = []
        for k in METRIC_KEYS:
            v = row[k]
            cells.append(f"{v:>14.3f}" if isinstance(v, (int, float)) else f"{str(v):>14}")
        print(f"  {name:<26}" + "".join(cells))


if __name__ == "__main__":
    main()
