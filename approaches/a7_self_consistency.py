"""Self-consistency: sample N plans, vote per field."""
import json
import sys, os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

N = 5


def _flight_key(f):
    return (f.get("origin"), f.get("destination"), f.get("depart_date"), f.get("return_date"), tuple(sorted(f.get("traveler_ids") or [])), f.get("cabin"))


def _hotel_key(h):
    return (h.get("city_iata"), h.get("check_in"), h.get("check_out"), tuple(sorted(h.get("traveler_ids") or [])), h.get("rooms"))


def _vote(samples):
    trip_type = Counter(s["trip_type"] for s in samples).most_common(1)[0][0]
    # Travelers: take the modal traveler set (by frozenset of names).
    trav_key = Counter(frozenset((t["name"] or "").strip().lower() for t in s["travelers"]) for s in samples).most_common(1)[0][0]
    # Pick the actual traveler list from the first sample whose names match.
    travelers = next(s["travelers"] for s in samples if frozenset((t["name"] or "").strip().lower() for t in s["travelers"]) == trav_key)

    # Flights / hotels: include any item that appears in >= ceil(N/2) samples.
    threshold = (len(samples) + 1) // 2
    fcnt = Counter()
    fmap = {}
    for s in samples:
        for f in s["flights"]:
            k = _flight_key(f)
            fcnt[k] += 1
            fmap.setdefault(k, f)
    flights = [fmap[k] for k, c in fcnt.items() if c >= threshold]

    hcnt = Counter()
    hmap = {}
    for s in samples:
        for h in s["hotels"]:
            k = _hotel_key(h)
            hcnt[k] += 1
            hmap.setdefault(k, h)
    hotels = [hmap[k] for k, c in hcnt.items() if c >= threshold]

    return {"trip_type": trip_type, "travelers": travelers, "flights": flights, "hotels": hotels}


class A7SelfConsistency(Approach):
    name = "a7_self_consistency"

    def predict(self, text):
        c = client()
        samples = []
        for _ in range(N):
            r = c.chat.completions.create(
                model=MODEL_MAIN,
                messages=[{"role": "system", "content": SYSTEM_BASE}, {"role": "user", "content": user_prompt(text)}],
                response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
                temperature=0.7,
            )
            samples.append(json.loads(r.choices[0].message.content))
        return _vote(samples)


approach = A7SelfConsistency()
