"""Decomposed extractors: travelers, flights, hotels separately, then merge."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from approaches.base import Approach

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
        "type": "object", "additionalProperties": False, "required": ["trip_type", "flights"],
        "properties": {
            "trip_type": {"type": "string", "enum": ["one_way", "round_trip", "multi_city", "hotel_only", "flight_only"]},
            "flights": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["origin", "destination", "depart_date", "return_date", "traveler_ids", "cabin"],
                "properties": {
                    "origin": {"type": "string"}, "destination": {"type": "string"},
                    "depart_date": {"type": "string"}, "return_date": {"type": ["string", "null"]},
                    "traveler_ids": {"type": "array", "items": {"type": "string"}},
                    "cabin": {"type": "string", "enum": ["economy", "premium_economy", "business", "first"]},
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
            "required": ["city_iata", "city_name", "check_in", "check_out", "traveler_ids", "rooms"],
            "properties": {
                "city_iata": {"type": "string"}, "city_name": {"type": "string"},
                "check_in": {"type": "string"}, "check_out": {"type": "string"},
                "traveler_ids": {"type": "array", "items": {"type": "string"}},
                "rooms": {"type": "integer"},
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


class A9Decomposed(Approach):
    name = "a9_decomposed_tools"

    def predict(self, text):
        c = client()
        travs = _call(c, "Extract every traveler mentioned. Use stable ids t1, t2, ... in mention order.", text, TRAVELERS_SCHEMA)
        ctx = f"REQUEST:\n{text}\n\nTRAVELERS:\n{json.dumps(travs, ensure_ascii=False)}"
        flights = _call(c, "Extract every flight leg. Use 3-letter IATA codes. Reference traveler ids exactly. Pick trip_type.", ctx, FLIGHTS_SCHEMA)
        hotels = _call(c, "Extract every hotel stay. Use 3-letter IATA city codes. Reference traveler ids exactly.", ctx, HOTELS_SCHEMA)
        return {
            "trip_type": flights["trip_type"],
            "travelers": travs["travelers"],
            "flights": flights["flights"],
            "hotels": hotels["hotels"],
        }


approach = A9Decomposed()
