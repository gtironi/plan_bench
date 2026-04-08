"""Metrics for plan-vs-plan comparison.

Order-invariant. Each predicted step is greedily matched to the gold step of
the same action type that shares the most field values. The score for a step
is (matched_fields / relevant_fields), where relevant_fields are the action's
metric fields present in gold inputs after dropping nulls. The plan accuracy
is the average step score over max(len(pred), len(gold)) — extras and missings
count as 0.

Before scoring, plans are normalized: step metadata (step_id, depends_on,
enter_guard, next_step, success_criteria, title) is ignored, and inputs keys
with value None are removed so irrelevant nulls do not affect matching.
"""
import re
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema import validate_plan
from dataset.iata_airports import CODES

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

FLIGHT_FIELDS = ["from_airport_code", "to_airport_code", "departure_date", "passengers", "traveler_ids"]
HOTEL_FIELDS  = ["city", "check_in_date", "number_of_nights", "number_of_guests", "traveler_ids"]


def _strip_null_inputs(inputs):
    if not inputs:
        return {}
    return {k: v for k, v in inputs.items() if v is not None}


def normalize_plan_for_metrics(p):
    """Copy plan for scoring: only action + non-null inputs; metadata stripped."""
    out = []
    for s in p.get("steps", []) or []:
        if not isinstance(s, dict):
            continue
        out.append({
            "action": s.get("action"),
            "inputs": _strip_null_inputs(s.get("inputs") or {}),
        })
    return {"steps": out}


# ── Field comparison ──────────────────────────────────────────────────────────

def _norm(v):
    """Canonical form so trivial differences don't break equality."""
    if isinstance(v, list):
        return tuple(sorted(str(x) for x in v))
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, (int, float)):
        return str(v)
    return v


def _field_acc(pred_step, gold_step):
    """Fraction of relevant fields (present in gold after null-stripping) that match."""
    fields = FLIGHT_FIELDS if gold_step["action"] == "quote_flight" else HOTEL_FIELDS
    p_in = pred_step.get("inputs", {}) or {}
    g_in = gold_step.get("inputs", {}) or {}
    relevant = [f for f in fields if f in g_in]
    if not relevant:
        return 1.0
    matches = sum(1 for f in relevant if _norm(p_in.get(f)) == _norm(g_in.get(f)))
    return matches / len(relevant)


# ── Greedy matching ───────────────────────────────────────────────────────────

def _match_steps(pred_steps, gold_steps):
    """For each gold step, pick the unused pred step (same action) with the
    highest field overlap. Returns (pairs, extras) where pairs is a list of
    (pred|None, gold) and extras is the list of leftover pred steps."""
    available = list(range(len(pred_steps)))
    pairs = []
    for g in gold_steps:
        best_i = -1
        best_score = -1.0
        for i in available:
            p = pred_steps[i]
            if p.get("action") != g.get("action"):
                continue
            sc = _field_acc(p, g)
            if sc > best_score:
                best_score = sc
                best_i = i
        if best_i >= 0:
            available.remove(best_i)
            pairs.append((pred_steps[best_i], g))
        else:
            pairs.append((None, g))
    extras = [pred_steps[i] for i in available]
    return pairs, extras


# ── Aggregate accuracy metrics ────────────────────────────────────────────────

def _accuracy(pred_steps, gold_steps):
    pairs, extras = _match_steps(pred_steps, gold_steps)
    total = max(len(pred_steps), len(gold_steps))
    if total == 0:
        return 1.0
    accs = [_field_acc(p, g) if p else 0.0 for p, g in pairs]
    accs += [0.0] * len(extras)
    return sum(accs) / total


def _filter(steps, action):
    return [s for s in steps if s.get("action") == action]


# ── Schema / surface validity ─────────────────────────────────────────────────

def schema_valid(p):
    try:
        validate_plan(p)
        return 1.0
    except Exception:
        return 0.0


def iata_validity(p):
    """Fraction of from/to airport codes in pred flights that are real IATA codes."""
    codes = []
    for s in p.get("steps", []):
        if s.get("action") == "quote_flight":
            inp = s.get("inputs") or {}
            codes += [inp.get("from_airport_code"), inp.get("to_airport_code")]
    codes = [c for c in codes if c]
    if not codes:
        return 1.0
    return sum(1 for c in codes if str(c).upper() in CODES) / len(codes)


def date_acc(pred_steps, gold_steps):
    """Among matched step pairs, fraction of date fields that exactly match gold."""
    pairs, _ = _match_steps(pred_steps, gold_steps)
    total = 0
    correct = 0
    for p, g in pairs:
        date_fields = ["departure_date"] if g.get("action") == "quote_flight" else ["check_in_date"]
        for f in date_fields:
            gv = (g.get("inputs") or {}).get(f)
            if not gv:
                continue
            total += 1
            if p is not None and (p.get("inputs") or {}).get(f) == gv:
                correct += 1
    return correct / total if total else 1.0


# ── Per-example diagnostics (for logging / debugging) ─────────────────────────

def diagnose_pred_vs_gold(pred_raw, gold_raw):
    """Structured diff vs gold using the same normalization and matching as metrics.

    Returns a JSON-serializable dict: schema_error, per_gold_step (field-level
    mismatches or missing pred), extra_pred_steps, and optional iata_issues on pred.
    """
    pred_n = normalize_plan_for_metrics(pred_raw)
    gold_n = normalize_plan_for_metrics(gold_raw)
    pred_steps = pred_n.get("steps", []) or []
    gold_steps = gold_n.get("steps", []) or []

    schema_error = None
    try:
        validate_plan(pred_raw)
    except Exception as e:
        schema_error = str(e)

    pairs, extras = _match_steps(pred_steps, gold_steps)

    per_gold_step = []
    for gi, (p, g) in enumerate(pairs):
        action = g.get("action")
        entry = {"gold_step_index": gi, "action": action}
        if p is None:
            entry["problem"] = "no_matching_pred_step"
            entry["field_mismatches"] = []
            per_gold_step.append(entry)
            continue
        g_in = g.get("inputs") or {}
        p_in = p.get("inputs") or {}
        fields = FLIGHT_FIELDS if action == "quote_flight" else HOTEL_FIELDS
        mismatches = []
        for f in fields:
            if f not in g_in:
                continue
            if _norm(p_in.get(f)) != _norm(g_in.get(f)):
                mismatches.append({"field": f, "gold": g_in.get(f), "pred": p_in.get(f)})
        entry["field_mismatches"] = mismatches
        entry["problem"] = "field_mismatches" if mismatches else None
        per_gold_step.append(entry)

    extra_pred_steps = []
    for p in extras:
        extra_pred_steps.append({
            "problem": "extra_pred_step",
            "action": p.get("action"),
            "inputs": p.get("inputs") or {},
        })

    iata_issues = []
    for si, s in enumerate(pred_steps):
        if s.get("action") != "quote_flight":
            continue
        inp = s.get("inputs") or {}
        for fld in ("from_airport_code", "to_airport_code"):
            c = inp.get(fld)
            if not c:
                continue
            if str(c).upper() not in CODES:
                iata_issues.append(
                    {"pred_step_index": si, "field": fld, "code": c, "problem": "unknown_iata_code"}
                )

    return {
        "schema_error": schema_error,
        "per_gold_step": per_gold_step,
        "extra_pred_steps": extra_pred_steps,
        "iata_issues": iata_issues,
    }


# ── Main scoring function ─────────────────────────────────────────────────────

def score(pred_raw, gold_raw):
    pred_n = normalize_plan_for_metrics(pred_raw)
    gold_n = normalize_plan_for_metrics(gold_raw)
    pred_steps = pred_n.get("steps", []) or []
    gold_steps = gold_n.get("steps", []) or []

    pred_flights = _filter(pred_steps, "quote_flight")
    pred_hotels  = _filter(pred_steps, "quote_hotel")
    gold_flights = _filter(gold_steps, "quote_flight")
    gold_hotels  = _filter(gold_steps, "quote_hotel")

    return {
        "accuracy":     round(_accuracy(pred_steps, gold_steps), 4),
        "flights_acc":  round(_accuracy(pred_flights, gold_flights), 4),
        "hotels_acc":   round(_accuracy(pred_hotels, gold_hotels), 4),
        "step_count":   f"{len(pred_raw.get('steps', []) or [])}/{len(gold_raw.get('steps', []) or [])}",
        "iata_validity": round(iata_validity(pred_n), 4),
        "date_acc":     round(date_acc(pred_steps, gold_steps), 4),
        "schema_valid": schema_valid(pred_raw),
    }


METRIC_KEYS = [
    "accuracy", "flights_acc", "hotels_acc",
    "step_count", "iata_validity", "date_acc", "schema_valid",
]
