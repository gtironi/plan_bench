"""Run all approaches over the dataset and write results."""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from approaches import ALL, BY_NAME
from eval.metrics import score, METRIC_KEYS, diagnose_pred_vs_gold, strip_null_inputs_from_plan

DATASET = os.path.join(os.path.dirname(__file__), "..", "dataset", "out", "dataset.jsonl")
OUT_DIR = os.path.join(os.path.dirname(__file__), "out")
RESULTS = os.path.join(OUT_DIR, "results.csv")
SUMMARY = os.path.join(OUT_DIR, "summary.csv")

from pricing import PRICING
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
        p = PRICING.get(model, (2.00, None, 8.00))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--approaches", type=str, default=None, help="comma-separated names")
    ap.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    ap.add_argument("--budget", type=float, default=2.0, help="max USD to spend; stops when exceeded")
    args = ap.parse_args()

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
            p = PRICING.get(model, (2.00, None, 8.00))
            est_per_approach[a.name] = (
                (in_per_item * len(data) / 1_000_000 * p[0]) +
                (out_per_item * len(data) / 1_000_000 * p[2])
            )

    rows = []
    summary = {a.name: {k: [] for k in METRIC_KEYS} for a in approaches}

    os.makedirs(OUT_DIR, exist_ok=True)
    results_f = open(RESULTS, "w", newline="")
    results_w = csv.DictWriter(results_f, fieldnames=["approach"] + METRIC_KEYS)
    results_w.writeheader()

    # Per-approach prediction log: one JSONL per approach, append mode.
    def _log_pred(approach_name, text, pred, gold):
        path = os.path.join(OUT_DIR, f"{approach_name}_preds.jsonl")
        diagnostics = diagnose_pred_vs_gold(pred, gold)
        with open(path, "a") as f:
            f.write(
                json.dumps(
                    {"text": text, "pred": pred, "gold": gold, "diagnostics": diagnostics},
                    ensure_ascii=False,
                )
                + "\n"
            )

    try:
        for a in approaches:
            spent_before_approach = TRACKER.spent_usd
            print(f"\n{'─'*70}")
            est = est_per_approach.get(a.name)
            est_str = f"~${est:.4f}" if est is not None else "unknown"
            print(f"  APPROACH: {a.name}  |  estimated: {est_str}  |  total spent so far: ${TRACKER.spent_usd:.4f}")
            print(f"{'─'*70}")

            for item in data:
                text = item["text"]
                gold = item["plan"]
                if a.name == "a5_fewshot_retrieval":
                    pred = a.predict(text, exclude_id=item.get("id"))
                else:
                    pred = a.predict(text)
                pred = strip_null_inputs_from_plan(pred)

                _log_pred(a.name, text, pred, gold)
                s = score(pred, gold)
                row = {"approach": a.name, **s}
                rows.append(row)
                results_w.writerow(row)
                results_f.flush()
                for k in METRIC_KEYS:
                    summary[a.name][k].append(s[k])
                print(
                    f"  [{item.get('id','?')}] "
                    f"acc={s['accuracy']:.2f}  "
                    f"flights={s['flights_acc']:.2f}  "
                    f"hotels={s['hotels_acc']:.2f}  "
                    f"steps={s['step_count']}  "
                    f"| real=${TRACKER.spent_usd:.4f}  budget=${args.budget:.2f}"
                )

            real_this = TRACKER.spent_usd - spent_before_approach
            est_this = est_per_approach.get(a.name, 0)
            print(f"  ✓ {a.name} done  est=${est_this:.4f}  real=${real_this:.4f}  diff={real_this - est_this:+.4f}")

            # Flush summary CSV after each approach so partial results are saved.
            with open(SUMMARY, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["approach"] + METRIC_KEYS)
                w.writeheader()
                for name, vals in summary.items():
                    if vals[METRIC_KEYS[0]]:
                        w.writerow({"approach": name, **_avg_row(vals)})

    except BudgetExceeded as e:
        print(f"\n!! STOPPED: {e}")
    finally:
        results_f.close()

    TRACKER.print_summary()

    # Final summary CSV (complete).
    with open(SUMMARY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["approach"] + METRIC_KEYS)
        w.writeheader()
        for name, vals in summary.items():
            if vals[METRIC_KEYS[0]]:
                w.writerow({"approach": name, **_avg_row(vals)})

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
