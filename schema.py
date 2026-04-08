"""Plan schema: ordered list of step actions (quote_flight / quote_hotel)."""
import json

ACTIONS = {"quote_flight", "quote_hotel"}


def empty_plan():
    return {"steps": []}


def validate_plan(p):
    assert isinstance(p, dict)
    steps = p["steps"]
    assert isinstance(steps, list)
    seen_ids = set()
    for s in steps:
        assert s["action"] in ACTIONS, f"bad action: {s.get('action')}"
        assert isinstance(s["step_id"], int)
        assert s["step_id"] not in seen_ids, f"duplicate step_id {s['step_id']}"
        seen_ids.add(s["step_id"])
        assert isinstance(s["depends_on"], list)
        assert "next_step" in s
        assert "title" in s
        inputs = s["inputs"]
        if s["action"] == "quote_flight":
            for k in ("from_airport_code", "to_airport_code", "departure_date", "passengers", "traveler_ids", "leg"):
                assert k in inputs, f"flight missing {k}"
            assert len(inputs["from_airport_code"]) == 3
            assert len(inputs["to_airport_code"]) == 3
        else:
            for k in ("city", "check_in_date", "number_of_nights", "number_of_guests", "traveler_ids"):
                assert k in inputs, f"hotel missing {k}"


def _step_key(s):
    """Order-independent canonical key for a step."""
    inp = s.get("inputs", {})
    if s["action"] == "quote_flight":
        return (
            "F",
            inp.get("from_airport_code"),
            inp.get("to_airport_code"),
            inp.get("departure_date"),
            int(inp.get("passengers") or 0),
            tuple(sorted(inp.get("traveler_ids") or [])),
        )
    return (
        "H",
        inp.get("city"),
        inp.get("check_in_date"),
        str(inp.get("number_of_nights")),
        str(inp.get("number_of_guests")),
        tuple(sorted(inp.get("traveler_ids") or [])),
    )


def normalize_plan(p):
    """Return canonical step set keyed by content (order/ids stripped)."""
    return {"steps": sorted([_step_key(s) for s in p.get("steps", [])])}


# JSON schema for OpenAI structured output (strict mode).
PLAN_JSON_SCHEMA = {
    "name": "travel_plan_steps",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["steps"],
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "step_id", "action", "depends_on", "enter_guard",
                        "next_step", "success_criteria", "title", "inputs",
                    ],
                    "properties": {
                        "step_id": {"type": "integer"},
                        "action": {"type": "string", "enum": ["quote_flight", "quote_hotel"]},
                        "depends_on": {"type": "array", "items": {"type": "integer"}},
                        "enter_guard": {"type": "string"},
                        "next_step": {"type": ["integer", "null"]},
                        "success_criteria": {"type": "string"},
                        "title": {"type": "string"},
                        "inputs": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "leg", "from_airport_code", "to_airport_code",
                                "departure_date", "passengers", "city",
                                "check_in_date", "number_of_nights",
                                "number_of_guests", "area", "traveler_ids",
                            ],
                            "properties": {
                                "leg": {"type": ["integer", "null"]},
                                "from_airport_code": {"type": ["string", "null"]},
                                "to_airport_code": {"type": ["string", "null"]},
                                "departure_date": {"type": ["string", "null"]},
                                "passengers": {"type": ["integer", "null"]},
                                "city": {"type": ["string", "null"]},
                                "check_in_date": {"type": ["string", "null"]},
                                "number_of_nights": {"type": ["string", "null"]},
                                "number_of_guests": {"type": ["string", "null"]},
                                "area": {"type": ["string", "null"]},
                                "traveler_ids": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        },
    },
}

SCHEMA_TEXT = json.dumps(PLAN_JSON_SCHEMA["schema"], indent=2)
