#!/usr/bin/env python3
"""
Reaplica eval.metrics sobre pes_generate_plan_baseline_preds.jsonl usando um plano
comparável derivado de handler_raw (intent → passos, quando plan.steps veio vazio).

O *_rescored.jsonl de saída contém por linha: text, gold, pred_comparable,
diagnostics_rescored (sem handler_raw). Métricas agregadas ficam nos CSVs.

Uso (na raiz plan_bench):

  python3 eval/rescore_pes_baseline_preds.py

  python3 eval/rescore_pes_baseline_preds.py --preds eval/out/outro.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_EVAL = Path(__file__).resolve().parent
_PLAN_BENCH = _EVAL.parent
sys.path.insert(0, str(_PLAN_BENCH))

from eval.intent_to_plan_bench import handler_raw_to_plan_bench
from eval.metrics import METRIC_KEYS, diagnose_pred_vs_gold, score


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--preds",
        type=Path,
        default=_PLAN_BENCH / "eval" / "out" / "pes_generate_plan_baseline_preds.jsonl",
    )
    ap.add_argument(
        "--out-jsonl",
        type=Path,
        default=None,
        help="default: <preds_stem>_rescored.jsonl",
    )
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=None,
        help="default: eval/out/pes_generate_plan_baseline_rescored_results.csv",
    )
    ap.add_argument(
        "--out-summary",
        type=Path,
        default=None,
        help="default: eval/out/pes_generate_plan_baseline_rescored_summary.csv",
    )
    args = ap.parse_args()

    preds_path = args.preds.resolve()
    if not preds_path.is_file():
        raise SystemExit(f"Arquivo não encontrado: {preds_path}")

    out_jsonl = args.out_jsonl or preds_path.with_name(
        preds_path.stem + "_rescored.jsonl"
    )
    out_dir = _PLAN_BENCH / "eval" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.out_csv or (out_dir / "pes_generate_plan_baseline_rescored_results.csv")
    out_summary = args.out_summary or (out_dir / "pes_generate_plan_baseline_rescored_summary.csv")

    summary = {k: [] for k in METRIC_KEYS}

    with open(preds_path, encoding="utf-8") as fin, open(
        out_jsonl, "w", encoding="utf-8"
    ) as fj, open(out_csv, "w", newline="", encoding="utf-8") as fc:
        cw = csv.DictWriter(
            fc, fieldnames=["approach", "id", "sample_index"] + METRIC_KEYS
        )
        cw.writeheader()

        for line_no, line in enumerate(fin):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            handler_raw = rec.get("handler_raw") or {}
            gold = rec.get("gold") or {}
            pred_comparable = handler_raw_to_plan_bench(handler_raw)

            pred_for_metrics = {
                "steps": pred_comparable.get("steps") or [],
            }
            metrics = score(pred_for_metrics, gold)
            diagnostics = diagnose_pred_vs_gold(pred_for_metrics, gold)

            out_rec = {
                "text": rec.get("text", ""),
                "gold": gold,
                "pred_comparable": pred_comparable,
                "diagnostics_rescored": diagnostics,
            }
            fj.write(json.dumps(out_rec, ensure_ascii=False, default=str) + "\n")

            cw.writerow(
                {
                    "approach": "pes_generate_plan_rescored",
                    "id": rec.get("id", ""),
                    "sample_index": rec.get("sample_index", line_no),
                    **metrics,
                }
            )

            for k in METRIC_KEYS:
                summary[k].append(metrics[k])

    with open(out_summary, "w", newline="", encoding="utf-8") as sf:
        sw = csv.DictWriter(sf, fieldnames=["approach"] + METRIC_KEYS)
        sw.writeheader()
        sw.writerow(
            {"approach": "pes_generate_plan_rescored", **_avg_row(summary)}
        )

    print(f"JSONL:  {out_jsonl}")
    print(f"CSV:    {out_csv}")
    print(f"Resumo: {out_summary}")
    print("Médias:", json.dumps(_avg_row(summary), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
