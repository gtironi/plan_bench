"""Decomposed extractors: travelers, flights, hotels separately, then merge."""
import json
import sys, os
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from approaches.base import Approach
from schema import validate_plan

TRAVELERS_SCHEMA = {
    "name": "travelers", "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False, "required": ["travelers"],
        "properties": {"travelers": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "name", "type"],
            "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "type": {"type": "string", "enum": ["adult", "child", "infant"]}},
        }}},
    },
}

FLIGHTS_SCHEMA = {
    "name": "flights", "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False, "required": ["flights"],
        "properties": {
            "flights": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["leg", "from_airport_code", "to_airport_code", "departure_date", "passengers", "traveler_ids"],
                "properties": {
                    "leg": {"type": "integer"},
                    "from_airport_code": {"type": "string"},
                    "to_airport_code": {"type": "string"},
                    "departure_date": {"type": "string"},
                    "passengers": {"type": "integer"},
                    "traveler_ids": {"type": "array", "items": {"type": "string"}},
                },
            }},
        },
    },
}

HOTELS_SCHEMA = {
    "name": "hotels", "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False, "required": ["hotels"],
        "properties": {"hotels": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["city", "check_in_date", "number_of_nights", "number_of_guests", "traveler_ids"],
            "properties": {
                "city": {"type": "string"},
                "check_in_date": {"type": "string"},
                "number_of_nights": {"type": "string"},
                "number_of_guests": {"type": "string"},
                "traveler_ids": {"type": "array", "items": {"type": "string"}},
            },
        }}},
    },
}


def _call(c, system, user, schema):
    r = c.chat.completions.create(
        model=MODEL_MAIN,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": schema},
    )
    return json.loads(r.choices[0].message.content)


def _step(action: str, title: str, inputs: dict) -> dict:
    return {
        "step_id": 0,  # filled later
        "action": action,
        "depends_on": [],  # filled later
        "enter_guard": "True",
        "next_step": None,  # filled later
        "success_criteria": "len(result) > 0",
        "title": title,
        "inputs": inputs,
    }


def _relinearize_steps(steps):
    for i, s in enumerate(steps):
        s["step_id"] = i
        s["depends_on"] = [] if i == 0 else [i - 1]
        s["next_step"] = i + 1 if i < len(steps) - 1 else None
    return steps


class A9Decomposed(Approach):
    name = "a9_decomposed_tools"

    def predict(self, text):
        c = client()
        today = date.today().isoformat()
        travs = _call(
            c,
            "Extract every traveler mentioned.\n"
            f"TODAY: {today}\n"
            "Use stable ids t1, t2, ... in mention order.",
            text,
            TRAVELERS_SCHEMA,
        )
        ctx = f"REQUEST:\n{text}\n\nTRAVELERS:\n{json.dumps(travs, ensure_ascii=False)}"
        flights = _call(
            c,
            "Extract every flight leg.\n"
            f"TODAY: {today}\n"
            "- Use 3-letter IATA airport codes.\n"
            "- Output departure_date as YYYY-MM-DD.\n"
            "- All plan dates must be in the future relative to TODAY (if ambiguous, choose a future date).\n"
            "- passengers must equal len(traveler_ids).\n"
            "- leg is 0 for outbound/converging legs, 1 for return/diverging legs.\n"
            "- Reference traveler ids exactly as given.\n"
            "- If the request does NOT need flights, return flights=[] (empty array).\n",
            ctx,
            FLIGHTS_SCHEMA,
        )
        hotels = _call(
            c,
            "Extract every hotel stay.\n"
            f"TODAY: {today}\n"
            "- Output check_in_date as YYYY-MM-DD.\n"
            "- All plan dates must be in the future relative to TODAY (if ambiguous, choose a future date).\n"
            "- city must be a city name (e.g. 'Helsinki', 'Vienna') not an IATA code.\n"
            "- number_of_nights and number_of_guests must be strings.\n"
            "- Reference traveler ids exactly as given.\n"
            "- If the request does NOT need hotels, return hotels=[] (empty array).\n",
            ctx,
            HOTELS_SCHEMA,
        )

        steps = []
        for f in flights.get("flights") or []:
            frm = f["from_airport_code"]
            to = f["to_airport_code"]
            steps.append(
                _step(
                    "quote_flight",
                    f"{frm} to {to} flight",
                    {
                        "leg": int(f["leg"]),
                        "from_airport_code": frm,
                        "to_airport_code": to,
                        "departure_date": f["departure_date"],
                        "passengers": int(f["passengers"]),
                        "traveler_ids": f["traveler_ids"],
                    },
                )
            )

        for h in hotels.get("hotels") or []:
            city = h["city"]
            steps.append(
                _step(
                    "quote_hotel",
                    f"{city} hotel {h['number_of_nights']} nights ({h['number_of_guests']} guests)",
                    {
                        "area": None,
                        "city": city,
                        "check_in_date": h["check_in_date"],
                        "number_of_nights": h["number_of_nights"],
                        "number_of_guests": h["number_of_guests"],
                        "traveler_ids": h["traveler_ids"],
                    },
                )
            )

        _relinearize_steps(steps)
        plan = {"steps": steps}
        validate_plan(plan)
        return plan


approach = A9Decomposed()
