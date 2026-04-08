"""Few-shot with 3 fixed hand-written examples."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

EXAMPLES = [
    {
        "text": "Preciso de voos de ida e volta GRU-JFK para Ana Silva e Bruno Costa, saindo 10/05/2026, voltando 15/05/2026, econômica. Hotel em NY nessas datas, 1 quarto.",
        "plan": {
            "trip_type": "round_trip",
            "travelers": [
                {"id": "t1", "name": "Ana Silva", "type": "adult"},
                {"id": "t2", "name": "Bruno Costa", "type": "adult"},
            ],
            "flights": [{"origin": "GRU", "destination": "JFK", "depart_date": "2026-05-10", "return_date": "2026-05-15", "traveler_ids": ["t1", "t2"], "cabin": "economy"}],
            "hotels": [{"city_iata": "JFK", "city_name": "New York", "check_in": "2026-05-10", "check_out": "2026-05-15", "traveler_ids": ["t1", "t2"], "rooms": 1}],
        },
    },
    {
        "text": "Multi-city trip for Carlos Mendes: São Paulo to Lisbon on June 3rd, then Lisbon to Madrid on June 7th, then Madrid back to São Paulo on June 12th. Book hotel in Lisbon Jun 3-7 and hotel in Madrid Jun 7-12. Business class.",
        "plan": {
            "trip_type": "multi_city",
            "travelers": [{"id": "t1", "name": "Carlos Mendes", "type": "adult"}],
            "flights": [
                {"origin": "GRU", "destination": "LIS", "depart_date": "2026-06-03", "return_date": None, "traveler_ids": ["t1"], "cabin": "business"},
                {"origin": "LIS", "destination": "MAD", "depart_date": "2026-06-07", "return_date": None, "traveler_ids": ["t1"], "cabin": "business"},
                {"origin": "MAD", "destination": "GRU", "depart_date": "2026-06-12", "return_date": None, "traveler_ids": ["t1"], "cabin": "business"},
            ],
            "hotels": [
                {"city_iata": "LIS", "city_name": "Lisbon", "check_in": "2026-06-03", "check_out": "2026-06-07", "traveler_ids": ["t1"], "rooms": 1},
                {"city_iata": "MAD", "city_name": "Madrid", "check_in": "2026-06-07", "check_out": "2026-06-12", "traveler_ids": ["t1"], "rooms": 1},
            ],
        },
    },
    {
        "text": "Team meeting in Miami July 10-13. Diana flies from São Paulo, Eduardo and Fernanda from Rio. All three stay at the same hotel, 2 rooms. Return same day July 13.",
        "plan": {
            "trip_type": "round_trip",
            "travelers": [
                {"id": "t1", "name": "Diana", "type": "adult"},
                {"id": "t2", "name": "Eduardo", "type": "adult"},
                {"id": "t3", "name": "Fernanda", "type": "adult"},
            ],
            "flights": [
                {"origin": "GRU", "destination": "MIA", "depart_date": "2026-07-10", "return_date": "2026-07-13", "traveler_ids": ["t1"], "cabin": "economy"},
                {"origin": "GIG", "destination": "MIA", "depart_date": "2026-07-10", "return_date": "2026-07-13", "traveler_ids": ["t2", "t3"], "cabin": "economy"},
            ],
            "hotels": [{"city_iata": "MIA", "city_name": "Miami", "check_in": "2026-07-10", "check_out": "2026-07-13", "traveler_ids": ["t1", "t2", "t3"], "rooms": 2}],
        },
    },
]


def _example_messages():
    msgs = []
    for ex in EXAMPLES:
        msgs.append({"role": "user", "content": user_prompt(ex["text"])})
        msgs.append({"role": "assistant", "content": json.dumps(ex["plan"], ensure_ascii=False)})
    return msgs


class A4FewshotFixed(Approach):
    name = "a4_fewshot_fixed"

    def predict(self, text):
        c = client()
        msgs = [{"role": "system", "content": SYSTEM_BASE}] + _example_messages() + [{"role": "user", "content": user_prompt(text)}]
        resp = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=msgs,
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(resp.choices[0].message.content)


approach = A4FewshotFixed()
