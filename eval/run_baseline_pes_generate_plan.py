#!/usr/bin/env python3
"""
Baseline: mesmo fluxo que o handler GeneratePlan (pes_noma), aplicado ao dataset
plan_bench (ex.: dataset_full.jsonl), com métricas alinhadas ao run_eval.

O arquivo *_preds.jsonl não é apagado: amostras cujo ``sample_index`` já aparecem
no JSONL são puladas (sem nova chamada ao handler). O CSV de resultados é reescrito
com todas as linhas do lote atual, na ordem do dataset.

Requisitos (como o handler “no estado atual”):
- Repositório noma_backend_local com system/env_config.py (DynamoDB, OpenAI, etc.)
- Executar de forma que load_config() encontre as tabelas (cwd = raiz do backend).

Uso típico (a partir da raiz do repo noma):

  cd noma_backend_local
  python3 ../plan_bench/eval/run_baseline_pes_generate_plan.py \\
    --portfolio P --org O --case-group nome_do_case_group

Ou, com caminho absoluto ao backend:

  python3 plan_bench/eval/run_baseline_pes_generate_plan.py \\
    --backend-root /caminho/para/noma_backend_local \\
    --portfolio P --org O --case-group nome_do_case_group
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# plan_bench root (parent of eval/)
_PLAN_BENCH_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PLAN_BENCH_ROOT.parent

_DEFAULT_DATASET = _PLAN_BENCH_ROOT / "dataset" / "out" / "dataset_full.jsonl"
_DEFAULT_OUT = _PLAN_BENCH_ROOT / "eval" / "out"


def _load_existing_preds_by_index(preds_path: Path) -> dict[int, dict]:
    """Última linha por sample_index vence (JSONL pode ter sido editado)."""
    by_idx: dict[int, dict] = {}
    if not preds_path.is_file():
        return by_idx
    with open(preds_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            si = rec.get("sample_index")
            if si is None:
                continue
            by_idx[int(si)] = rec
    return by_idx


def _avg_row(vals: dict) -> dict:
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


def _setup_import_paths(backend_root: Path) -> None:
    """renglo → pes_noma → noma (prompts), na ordem esperada pelos imports."""
    renglo_lib = backend_root / "dev" / "renglo-lib"
    pes_pkg = backend_root / "extensions" / "pes_noma" / "package"
    noma_pkg = backend_root / "extensions" / "noma" / "package"
    for p in (renglo_lib, pes_pkg, noma_pkg):
        p = p.resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"Caminho obrigatório não encontrado: {p}")
        sys.path.insert(0, str(p))


def main() -> None:
    ap = argparse.ArgumentParser(description="Baseline GeneratePlan vs plan_bench dataset")
    ap.add_argument(
        "--backend-root",
        type=Path,
        default=None,
        help="Raiz noma_backend_local (default: irmão de noma/plan_bench ou $NOMA_BACKEND_ROOT)",
    )
    ap.add_argument(
        "--dataset",
        type=Path,
        default=_DEFAULT_DATASET,
        help="JSONL com campos text + plan (gold)",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--portfolio", required=True)
    ap.add_argument("--org", required=True)
    ap.add_argument("--case-group", required=True, dest="case_group")
    ap.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    ap.add_argument(
        "--init",
        type=str,
        default="",
        help='JSON opcional para payload _init (ex.: \'{"plan_actions":["quote_flight","quote_hotel"]}\')',
    )
    args = ap.parse_args()

    backend_root = args.backend_root
    if backend_root is None:
        env = os.environ.get("NOMA_BACKEND_ROOT")
        backend_root = Path(env) if env else (_REPO_ROOT / "noma_backend_local")
    backend_root = backend_root.resolve()

    if not (backend_root / "system" / "env_config.py").is_file():
        print(
            f"Aviso: não achei system/env_config.py em {backend_root}. "
            "load_config() pode falhar ou exigir só variáveis de ambiente.",
            file=sys.stderr,
        )

    os.chdir(backend_root)
    _setup_import_paths(backend_root)

    sys.path.insert(0, str(_PLAN_BENCH_ROOT))
    from eval.intent_to_plan_bench import handler_raw_to_plan_bench
    from eval.metrics import METRIC_KEYS, diagnose_pred_vs_gold, score

    from pes_noma.handlers.generate_plan import GeneratePlan

    dataset_path = args.dataset.resolve()
    if not dataset_path.is_file():
        raise SystemExit(f"Dataset não encontrado: {dataset_path}")

    init_obj = json.loads(args.init) if args.init.strip() else {}

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    approach_name = "pes_generate_plan_baseline"
    preds_path = out_dir / f"{approach_name}_preds.jsonl"
    results_path = out_dir / f"{approach_name}_results.csv"

    existing_preds = _load_existing_preds_by_index(preds_path)
    done_indices = set(existing_preds.keys())
    if done_indices:
        print(f"  Retomando: {len(done_indices)} amostra(s) já em {preds_path.name} (pulando API)")

    with open(dataset_path, encoding="utf-8") as f:
        lines = f.readlines()
    if args.limit:
        lines = lines[: args.limit]

    entries: list[tuple[int, dict]] = []
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        entries.append((idx, json.loads(line)))

    handler = GeneratePlan()
    rows_by_index: dict[int, dict] = {}

    with open(preds_path, "a", encoding="utf-8") as preds_append:
        for idx, item in entries:
            text = item["text"]
            gold = item["plan"]
            sample_id = item.get("id", "")

            if idx in done_indices:
                rec = existing_preds[idx]
                pred_plan = rec.get("pred") or {"steps": []}
                gold_eval = rec.get("gold") if isinstance(rec.get("gold"), dict) else gold
                metrics = score(pred_plan, gold_eval)
                row_id = rec.get("id", sample_id)
                print(
                    f"  [{row_id or idx}] pular (já em preds) "
                    f"acc={metrics['accuracy']:.2f} steps={metrics['step_count']}"
                )
            else:
                row_id = sample_id
                payload = {
                    "portfolio": args.portfolio,
                    "org": args.org,
                    "case_group": args.case_group,
                    "message": text,
                    "_init": json.dumps(init_obj) if init_obj else {},
                    "_entity_type": "plan_bench_baseline",
                    "_entity_id": sample_id or f"sample_{idx}",
                    "_thread": "plan_bench_baseline",
                }
                result = handler.run(payload)
                pred_plan = handler_raw_to_plan_bench(result)
                diagnostics = diagnose_pred_vs_gold(pred_plan, gold)
                metrics = score(pred_plan, gold)
                log_record = {
                    "id": sample_id,
                    "sample_index": idx,
                    "text": text,
                    "pred": pred_plan,
                    "gold": gold,
                    "handler_success": bool(result.get("success")),
                    "handler_raw": result,
                    "diagnostics": diagnostics,
                }
                preds_append.write(
                    json.dumps(log_record, ensure_ascii=False, default=str) + "\n"
                )
                preds_append.flush()
                existing_preds[idx] = log_record
                done_indices.add(idx)
                print(
                    f"  [{sample_id or idx}] success={result.get('success')} "
                    f"acc={metrics['accuracy']:.2f} flights={metrics['flights_acc']:.2f} "
                    f"hotels={metrics['hotels_acc']:.2f} steps={metrics['step_count']}"
                )

            rows_by_index[idx] = {
                "approach": approach_name,
                "id": row_id,
                "sample_index": idx,
                **metrics,
            }

    fieldnames = ["approach", "id", "sample_index"] + METRIC_KEYS
    with open(results_path, "w", newline="", encoding="utf-8") as results_f:
        w = csv.DictWriter(results_f, fieldnames=fieldnames)
        w.writeheader()
        for idx, _item in entries:
            w.writerow(rows_by_index[idx])

    summary = {k: [] for k in METRIC_KEYS}
    for idx, _item in entries:
        row = rows_by_index[idx]
        for k in METRIC_KEYS:
            summary[k].append(row[k])

    summary_path = out_dir / f"{approach_name}_summary.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as sf:
        sw = csv.DictWriter(sf, fieldnames=["approach"] + METRIC_KEYS)
        sw.writeheader()
        sw.writerow({"approach": approach_name, **_avg_row(summary)})

    print("\n=== BASELINE PES GeneratePlan ===")
    print(f"  Preds:   {preds_path}")
    print(f"  Results: {results_path}")
    print(f"  Summary: {summary_path}")
    avg = _avg_row(summary)
    for k in METRIC_KEYS:
        print(f"  {k}: {avg[k]}")


if __name__ == "__main__":
    main()
