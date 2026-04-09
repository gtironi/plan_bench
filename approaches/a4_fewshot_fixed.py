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
            "steps": [
                {
                    "step_id": 0,
                    "action": "quote_flight",
                    "depends_on": [],
                    "enter_guard": "True",
                    "next_step": 1,
                    "success_criteria": "len(result) > 0",
                    "title": "GRU to JFK flight",
                    "inputs": {
                        "leg": 0,
                        "from_airport_code": "GRU",
                        "to_airport_code": "JFK",
                        "departure_date": "2026-05-10",
                        "passengers": 2,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1", "t2"],
                    },
                },
                {
                    "step_id": 1,
                    "action": "quote_flight",
                    "depends_on": [0],
                    "enter_guard": "True",
                    "next_step": 2,
                    "success_criteria": "len(result) > 0",
                    "title": "JFK to GRU flight",
                    "inputs": {
                        "leg": 1,
                        "from_airport_code": "JFK",
                        "to_airport_code": "GRU",
                        "departure_date": "2026-05-15",
                        "passengers": 2,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1", "t2"],
                    },
                },
                {
                    "step_id": 2,
                    "action": "quote_hotel",
                    "depends_on": [1],
                    "enter_guard": "True",
                    "next_step": None,
                    "success_criteria": "len(result) > 0",
                    "title": "New York hotel 5 nights (2 guests)",
                    "inputs": {
                        "leg": None,
                        "from_airport_code": None,
                        "to_airport_code": None,
                        "departure_date": None,
                        "passengers": None,
                        "city": "New York",
                        "check_in_date": "2026-05-10",
                        "number_of_nights": "5",
                        "number_of_guests": "2",
                        "area": None,
                        "traveler_ids": ["t1", "t2"],
                    },
                },
            ]
        },
    },
    {
        "text": "Multi-city trip for Carlos Mendes: São Paulo to Lisbon on June 3rd, then Lisbon to Madrid on June 7th, then Madrid back to São Paulo on June 12th. Book hotel in Lisbon Jun 3-7 and hotel in Madrid Jun 7-12. Business class.",
        "plan": {
            "steps": [
                {
                    "step_id": 0,
                    "action": "quote_flight",
                    "depends_on": [],
                    "enter_guard": "True",
                    "next_step": 1,
                    "success_criteria": "len(result) > 0",
                    "title": "GRU to LIS flight",
                    "inputs": {
                        "leg": 0,
                        "from_airport_code": "GRU",
                        "to_airport_code": "LIS",
                        "departure_date": "2026-06-03",
                        "passengers": 1,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
                {
                    "step_id": 1,
                    "action": "quote_flight",
                    "depends_on": [0],
                    "enter_guard": "True",
                    "next_step": 2,
                    "success_criteria": "len(result) > 0",
                    "title": "LIS to MAD flight",
                    "inputs": {
                        "leg": 1,
                        "from_airport_code": "LIS",
                        "to_airport_code": "MAD",
                        "departure_date": "2026-06-07",
                        "passengers": 1,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
                {
                    "step_id": 2,
                    "action": "quote_flight",
                    "depends_on": [1],
                    "enter_guard": "True",
                    "next_step": 3,
                    "success_criteria": "len(result) > 0",
                    "title": "MAD to GRU flight",
                    "inputs": {
                        "leg": 2,
                        "from_airport_code": "MAD",
                        "to_airport_code": "GRU",
                        "departure_date": "2026-06-12",
                        "passengers": 1,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
                {
                    "step_id": 3,
                    "action": "quote_hotel",
                    "depends_on": [2],
                    "enter_guard": "True",
                    "next_step": 4,
                    "success_criteria": "len(result) > 0",
                    "title": "Lisbon hotel 4 nights (1 guests)",
                    "inputs": {
                        "leg": None,
                        "from_airport_code": None,
                        "to_airport_code": None,
                        "departure_date": None,
                        "passengers": None,
                        "city": "Lisbon",
                        "check_in_date": "2026-06-03",
                        "number_of_nights": "4",
                        "number_of_guests": "1",
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
                {
                    "step_id": 4,
                    "action": "quote_hotel",
                    "depends_on": [3],
                    "enter_guard": "True",
                    "next_step": None,
                    "success_criteria": "len(result) > 0",
                    "title": "Madrid hotel 5 nights (1 guests)",
                    "inputs": {
                        "leg": None,
                        "from_airport_code": None,
                        "to_airport_code": None,
                        "departure_date": None,
                        "passengers": None,
                        "city": "Madrid",
                        "check_in_date": "2026-06-07",
                        "number_of_nights": "5",
                        "number_of_guests": "1",
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
            ]
        },
    },
    {
        "text": "Team meeting in Miami July 10-13. Diana flies from São Paulo, Eduardo and Fernanda from Rio. All three stay at the same hotel, 2 rooms. Return same day July 13.",
        "plan": {
            "steps": [
                {
                    "step_id": 0,
                    "action": "quote_flight",
                    "depends_on": [],
                    "enter_guard": "True",
                    "next_step": 1,
                    "success_criteria": "len(result) > 0",
                    "title": "GRU to MIA flight",
                    "inputs": {
                        "leg": 0,
                        "from_airport_code": "GRU",
                        "to_airport_code": "MIA",
                        "departure_date": "2026-07-10",
                        "passengers": 1,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
                {
                    "step_id": 1,
                    "action": "quote_flight",
                    "depends_on": [0],
                    "enter_guard": "True",
                    "next_step": 2,
                    "success_criteria": "len(result) > 0",
                    "title": "GIG to MIA flight",
                    "inputs": {
                        "leg": 0,
                        "from_airport_code": "GIG",
                        "to_airport_code": "MIA",
                        "departure_date": "2026-07-10",
                        "passengers": 2,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t2", "t3"],
                    },
                },
                {
                    "step_id": 2,
                    "action": "quote_flight",
                    "depends_on": [1],
                    "enter_guard": "True",
                    "next_step": 3,
                    "success_criteria": "len(result) > 0",
                    "title": "MIA to GRU flight",
                    "inputs": {
                        "leg": 1,
                        "from_airport_code": "MIA",
                        "to_airport_code": "GRU",
                        "departure_date": "2026-07-13",
                        "passengers": 1,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t1"],
                    },
                },
                {
                    "step_id": 3,
                    "action": "quote_flight",
                    "depends_on": [2],
                    "enter_guard": "True",
                    "next_step": 4,
                    "success_criteria": "len(result) > 0",
                    "title": "MIA to GIG flight",
                    "inputs": {
                        "leg": 1,
                        "from_airport_code": "MIA",
                        "to_airport_code": "GIG",
                        "departure_date": "2026-07-13",
                        "passengers": 2,
                        "city": None,
                        "check_in_date": None,
                        "number_of_nights": None,
                        "number_of_guests": None,
                        "area": None,
                        "traveler_ids": ["t2", "t3"],
                    },
                },
                {
                    "step_id": 4,
                    "action": "quote_hotel",
                    "depends_on": [3],
                    "enter_guard": "True",
                    "next_step": None,
                    "success_criteria": "len(result) > 0",
                    "title": "Miami hotel 3 nights (3 guests)",
                    "inputs": {
                        "leg": None,
                        "from_airport_code": None,
                        "to_airport_code": None,
                        "departure_date": None,
                        "passengers": None,
                        "city": "Miami",
                        "check_in_date": "2026-07-10",
                        "number_of_nights": "3",
                        "number_of_guests": "3",
                        "area": None,
                        "traveler_ids": ["t1", "t2", "t3"],
                    },
                },
            ]
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
