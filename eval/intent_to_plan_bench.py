"""
Converte intent PES (renglo.intent.v1) ou passos crus do handler em plano no formato
do plan_bench (case + steps), alinhado ao ouro do dataset.

Quando GeneratePlan devolve plan.steps vazio mas intent preenchido (estratégia
programmatic e validação do catálogo removeu os passos), reconstruímos a partir
do intent com a mesma lógica que ProposePlan._build_plan_from_intent — sem
importar ProposePlan (evita load_config / DynamoDB só para esta conversão).

Ver: noma_backend_local/.../pes_noma/handlers/propose_plan.py (~197–419).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple


def _code(v: Any) -> str:
    if isinstance(v, dict):
        return str(v.get("code") or "")
    return str(v) if v else ""


def _flight_step(
    step_id: int,
    o_code: str,
    d_code: str,
    dep: str,
    pax: Any,
    tids: List[str],
    leg: int,
) -> Dict[str, Any]:
    return {
        "step_id": step_id,
        "title": f"{o_code} to {d_code} flight",
        "action": "quote_flight",
        "inputs": {
            "leg": leg,
            "from_airport_code": o_code,
            "to_airport_code": d_code,
            "departure_date": dep,
            "passengers": pax,
            "traveler_ids": list(tids) if tids else [],
        },
        "enter_guard": "True",
        "success_criteria": "len(result) > 0",
        "depends_on": [],
        "next_step": None,
    }


def _hotel_step(
    step_id: int,
    loc: Any,
    ci: str,
    co: str,
    nights: int,
    n_guests: Any,
    tids: List[str],
) -> Dict[str, Any]:
    n_guests_str = str(int(n_guests)) if isinstance(n_guests, (int, float)) else str(n_guests)
    if isinstance(loc, dict):
        loc_str = _code(loc)
    else:
        loc_str = str(loc or "")
    return {
        "step_id": step_id,
        "title": f"{loc_str} hotel {nights} nights ({n_guests_str} guests)",
        "action": "quote_hotel",
        "inputs": {
            "area": None,
            "city": loc_str,
            "check_in_date": ci,
            "number_of_nights": str(nights),
            "number_of_guests": n_guests_str,
            "traveler_ids": list(tids) if tids else [],
        },
        "enter_guard": "True",
        "success_criteria": "len(result) > 0",
        "depends_on": [],
        "next_step": None,
    }


def _train_bus_as_flight_step(
    step_id: int,
    o_code: str,
    d_code: str,
    dep: str,
    pax: Any,
    tids: List[str],
    leg: int,
    mode: str,
) -> Dict[str, Any]:
    """plan_bench só avalia quote_flight / quote_hotel; mapeia trem/ônibus para voo com os mesmos códigos."""
    return {
        "step_id": step_id,
        "title": f"{o_code} to {d_code} {mode}",
        "action": "quote_flight",
        "inputs": {
            "leg": leg,
            "from_airport_code": o_code,
            "to_airport_code": d_code,
            "departure_date": dep,
            "passengers": pax,
            "traveler_ids": list(tids) if tids else [],
        },
        "enter_guard": "True",
        "success_criteria": "len(result) > 0",
        "depends_on": [],
        "next_step": None,
    }


def intent_to_plan_bench_plan(
    intent: Dict[str, Any],
    case_label: str = "from_pes_intent",
) -> Dict[str, Any]:
    """Intent → plano comparável ao gold (steps com quote_flight / quote_hotel)."""
    iti = intent.get("itinerary") or {}
    segs = iti.get("segments") or []
    lod = iti.get("lodging") or {}
    stays_list = list(lod.get("stays") or [])
    party = intent.get("party") or {}
    travelers = party.get("travelers") or {}
    default_pax = (
        int(travelers.get("adults", 0) or 0)
        + int(travelers.get("children", 0) or 0)
        + int(travelers.get("infants", 0) or 0)
    ) or 1

    dest_code = _code(segs[0].get("destination")) if segs else None
    last_dest = (stays_list[-1].get("location_code") if stays_list else None) or dest_code
    if isinstance(last_dest, dict):
        last_dest = last_dest.get("code") if last_dest else None
    last_dest = str(last_dest or "").upper() or (str(dest_code or "").upper() if dest_code else "")

    inbound: List[Dict] = []
    return_segs: List[Dict] = []
    intermediate: List[Dict] = []
    for seg in segs:
        d = _code(seg.get("destination"))
        o = _code(seg.get("origin"))
        if dest_code and d and str(d).upper() == str(dest_code).upper():
            inbound.append(seg)
        elif last_dest and o and str(o).upper() == str(last_dest).upper():
            return_segs.append(seg)
        else:
            intermediate.append(seg)
    if not inbound and not return_segs and segs:
        inbound = list(segs)

    steps: List[Dict[str, Any]] = []
    leg = 0

    for seg in inbound:
        o_code = _code(seg.get("origin"))
        d_code = _code(seg.get("destination"))
        dep = seg.get("depart_date")
        pax = seg.get("passengers", default_pax)
        tids = seg.get("traveler_ids") or []
        transport_mode = (seg.get("transport_mode") or "flight").lower()
        if o_code and d_code and dep:
            if transport_mode in ("train", "bus"):
                steps.append(
                    _train_bus_as_flight_step(
                        len(steps), o_code, d_code, dep, pax, tids, leg, transport_mode
                    )
                )
            else:
                steps.append(_flight_step(len(steps), o_code, d_code, dep, pax, tids, leg))
            leg += 1

    prev_stay_loc: Optional[str] = None
    for stay in stays_list:
        loc = stay.get("location_code") or dest_code
        loc_code = (
            (_code(loc) if isinstance(loc, dict) else str(loc or "").upper())
            or (str(dest_code or "").upper() if dest_code else "")
        )
        ci = stay.get("check_in")
        co = stay.get("check_out")
        n_guests = stay.get("number_of_guests", default_pax)
        tids = stay.get("traveler_ids") or []
        if not loc or not ci or not co:
            continue
        if prev_stay_loc and loc_code and str(loc_code).upper() != str(prev_stay_loc).upper():
            for seg in intermediate:
                o = _code(seg.get("origin"))
                d = _code(seg.get("destination"))
                if str(o).upper() == str(prev_stay_loc).upper() and str(d).upper() == str(
                    loc_code
                ).upper():
                    dep = seg.get("depart_date")
                    pax = seg.get("passengers", default_pax)
                    seg_tids = seg.get("traveler_ids") or []
                    seg_transport = (seg.get("transport_mode") or "flight").lower()
                    if o and d and dep:
                        if seg_transport in ("train", "bus"):
                            steps.append(
                                _train_bus_as_flight_step(
                                    len(steps), o, d, dep, pax, seg_tids, leg, seg_transport
                                )
                            )
                        else:
                            steps.append(_flight_step(len(steps), o, d, dep, pax, seg_tids, leg))
                        leg += 1
                    break
        prev_stay_loc = loc_code
        try:
            from datetime import datetime

            ci_dt = datetime.strptime(str(ci)[:10], "%Y-%m-%d")
            co_dt = datetime.strptime(str(co)[:10], "%Y-%m-%d")
            nights = max(1, (co_dt - ci_dt).days)
        except Exception:
            nights = 1
        steps.append(_hotel_step(len(steps), loc, str(ci)[:10], str(co)[:10], nights, n_guests, tids))

    for seg in return_segs:
        o_code = _code(seg.get("origin"))
        d_code = _code(seg.get("destination"))
        dep = seg.get("depart_date")
        pax = seg.get("passengers", default_pax)
        tids = seg.get("traveler_ids") or []
        transport_mode = (seg.get("transport_mode") or "flight").lower()
        if o_code and d_code and dep:
            if transport_mode in ("train", "bus"):
                steps.append(
                    _train_bus_as_flight_step(
                        len(steps), o_code, d_code, dep, pax, tids, leg, transport_mode
                    )
                )
            else:
                steps.append(_flight_step(len(steps), o_code, d_code, dep, pax, tids, leg))
            leg += 1

    for i, step in enumerate(steps):
        step["step_id"] = i
        step["next_step"] = None if i == len(steps) - 1 else i + 1
        step["depends_on"] = [i - 1] if i > 0 else []

    strategy = "programmatic_lodging_only" if (not segs and stays_list) else "programmatic"
    return {"case": case_label, "steps": steps, "meta": {"strategy": strategy}}


def _pes_step_to_bench_step(step: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    """Normaliza um passo já no formato PES (LLM) para o shape do dataset."""
    action = step.get("action")
    if action == "quote_flight":
        inp = dict(step.get("inputs") or {})
        return {
            "step_id": idx,
            "title": step.get("title", ""),
            "action": "quote_flight",
            "inputs": {
                "leg": inp.get("leg", idx),
                "from_airport_code": inp.get("from_airport_code"),
                "to_airport_code": inp.get("to_airport_code"),
                "departure_date": inp.get("departure_date"),
                "passengers": inp.get("passengers"),
                "traveler_ids": list(inp.get("traveler_ids") or []),
            },
            "enter_guard": step.get("enter_guard", "True"),
            "success_criteria": step.get("success_criteria", "len(result) > 0"),
            "depends_on": list(step.get("depends_on") or []),
            "next_step": step.get("next_step"),
        }
    if action == "quote_hotel":
        inp = dict(step.get("inputs") or {})
        ng = inp.get("number_of_guests")
        nn = inp.get("number_of_nights")
        return {
            "step_id": idx,
            "title": step.get("title", ""),
            "action": "quote_hotel",
            "inputs": {
                "area": inp.get("area"),
                "city": inp.get("city"),
                "check_in_date": inp.get("check_in_date"),
                "number_of_nights": str(nn) if nn is not None and not isinstance(nn, str) else nn,
                "number_of_guests": str(ng) if ng is not None and not isinstance(ng, str) else ng,
                "traveler_ids": list(inp.get("traveler_ids") or []),
            },
            "enter_guard": step.get("enter_guard", "True"),
            "success_criteria": step.get("success_criteria", "len(result) > 0"),
            "depends_on": list(step.get("depends_on") or []),
            "next_step": step.get("next_step"),
        }
    if action == "quote_train_bus":
        inp = dict(step.get("inputs") or {})
        return _train_bus_as_flight_step(
            idx,
            str(inp.get("departure_city") or ""),
            str(inp.get("arrival_city") or ""),
            str(inp.get("departure_date") or ""),
            inp.get("passengers", 1),
            list(inp.get("traveler_ids") or []),
            int(inp.get("leg", idx)),
            "train_bus",
        )
    return None


def normalize_pes_plan_steps_to_bench(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Passos vindos de output.plan (quando não vazios) → plano plan_bench."""
    out_steps: List[Dict[str, Any]] = []
    for i, s in enumerate(steps):
        conv = _pes_step_to_bench_step(s, len(out_steps))
        if conv is not None:
            conv["step_id"] = len(out_steps)
            out_steps.append(conv)
    for i, step in enumerate(out_steps):
        step["step_id"] = i
        step["next_step"] = None if i == len(out_steps) - 1 else i + 1
        step["depends_on"] = [i - 1] if i > 0 else []
    return {"case": "from_pes_plan_steps", "steps": out_steps}


def handler_raw_to_plan_bench(handler_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai do retorno completo do GeneratePlan um dict {case, steps} comparável ao gold.

    Prioridade:
    1) output.plan.steps não vazio → normaliza para quote_flight / quote_hotel;
    2) senão → reconstrói a partir de output.intent.
    """
    if not handler_raw.get("success"):
        return {"case": "handler_failed", "steps": []}
    out = handler_raw.get("output") or {}
    intent = out.get("intent") or {}
    plan = out.get("plan") or {}
    raw_steps = plan.get("steps")

    if isinstance(raw_steps, list) and len(raw_steps) > 0:
        normalized = normalize_pes_plan_steps_to_bench(raw_steps)
        meta = plan.get("meta") or {}
        normalized["meta"] = {**meta, "source": "plan_steps"}
        return normalized

    case = "from_pes_intent"
    meta = plan.get("meta") or {}
    if isinstance(meta.get("strategy"), str):
        case = meta["strategy"]
    built = intent_to_plan_bench_plan(intent, case_label=case)
    built["meta"] = {**meta, "source": "intent_rebuild"}
    return built


def dataclass_plan_to_dict(plan_obj: Any) -> Dict[str, Any]:
    """Se plan_obj for dataclass Plan (pes_noma), serializa para dict."""
    try:
        return asdict(plan_obj)
    except Exception:
        return {}
