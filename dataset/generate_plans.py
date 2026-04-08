"""Generate synthetic ground-truth travel plans as ordered step lists.

Output format (per line, JSONL):

{
  "_id": "p0001",
  "case": "round_trip_simple",
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
        "departure_date": "2026-07-10",
        "passengers": 2,
        "traveler_ids": ["t1", "t2"]
      }
    },
    ...
  ]
}

Notes:
- Step ids are sequential integers starting at 0.
- depends_on is the previous step's id (linear chain). Empty for step 0.
- next_step is the following step id, or null for the last one.
- Hotels use city = destination IATA, number_of_nights and number_of_guests as STRINGS
  to match the live system output.
"""
import argparse
import json
import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset.iata_airports import CODES, CITY_BY_CODE

OUT = os.path.join(os.path.dirname(__file__), "out", "plans.jsonl")


def future_date(min_days=7, max_days=180):
    return date.today() + timedelta(days=random.randint(min_days, max_days))


def traveler_ids(n):
    return [f"t{i+1}" for i in range(n)]


def two_codes():
    return random.sample(CODES, 2)


# ── Step builders ─────────────────────────────────────────────────────────────


def flight_step(step_id, leg, frm, to, dep, tids):
    return {
        "step_id": step_id,
        "action": "quote_flight",
        "depends_on": [step_id - 1] if step_id > 0 else [],
        "enter_guard": "True",
        "next_step": None,  # filled at end
        "success_criteria": "len(result) > 0",
        "title": f"{frm} to {to} flight",
        "inputs": {
            "leg": leg,
            "from_airport_code": frm,
            "to_airport_code": to,
            "departure_date": dep,
            "passengers": len(tids),
            "traveler_ids": tids,
        },
    }


def hotel_step(step_id, city, check_in, nights, tids, area=None):
    city_name = CITY_BY_CODE.get(city, city)
    return {
        "step_id": step_id,
        "action": "quote_hotel",
        "depends_on": [step_id - 1] if step_id > 0 else [],
        "enter_guard": "True",
        "next_step": None,
        "success_criteria": "len(result) > 0",
        "title": f"{city_name} hotel {nights} nights ({len(tids)} guests)",
        "inputs": {
            "area": area,
            "check_in_date": check_in,
            "city": city_name,
            "number_of_guests": str(len(tids)),
            "number_of_nights": str(nights),
            "traveler_ids": tids,
        },
    }


def finalize(steps):
    """Set next_step based on order (linear chain)."""
    for i, s in enumerate(steps):
        s["next_step"] = (i + 1) if i + 1 < len(steps) else None
    return steps


# ── Case generators ───────────────────────────────────────────────────────────


def case_round_trip_simple():
    n = random.randint(1, 2)
    tids = traveler_ids(n)
    o, d = two_codes()
    dep = future_date()
    nights = random.randint(2, 7)
    ret = dep + timedelta(days=nights)
    steps = [
        flight_step(0, 0, o, d, dep.isoformat(), tids),
        flight_step(1, 1, d, o, ret.isoformat(), tids),
        hotel_step(2, d, dep.isoformat(), nights, tids),
    ]
    return "round_trip_simple", finalize(steps)


def case_one_way():
    n = random.randint(1, 2)
    tids = traveler_ids(n)
    o, d = two_codes()
    dep = future_date()
    return "one_way", finalize([flight_step(0, 0, o, d, dep.isoformat(), tids)])


def case_multi_city():
    n = random.randint(1, 3)
    tids = traveler_ids(n)
    a, b, c = random.sample(CODES, 3)
    d1 = future_date()
    n1 = random.randint(2, 5)
    d2 = d1 + timedelta(days=n1)
    n2 = random.randint(2, 5)
    d3 = d2 + timedelta(days=n2)
    steps = [
        flight_step(0, 0, a, b, d1.isoformat(), tids),
        flight_step(1, 1, b, c, d2.isoformat(), tids),
        flight_step(2, 2, c, a, d3.isoformat(), tids),
        hotel_step(3, b, d1.isoformat(), n1, tids),
        hotel_step(4, c, d2.isoformat(), n2, tids),
    ]
    return "multi_city", finalize(steps)


def case_hotel_only():
    n = random.randint(1, 3)
    tids = traveler_ids(n)
    city = random.choice(CODES)
    ci = future_date()
    nights = random.randint(1, 10)
    return "hotel_only", finalize([hotel_step(0, city, ci.isoformat(), nights, tids)])


def case_flight_only_rt():
    n = random.randint(1, 2)
    tids = traveler_ids(n)
    o, d = two_codes()
    dep = future_date()
    ret = dep + timedelta(days=random.randint(1, 5))
    steps = [
        flight_step(0, 0, o, d, dep.isoformat(), tids),
        flight_step(1, 1, d, o, ret.isoformat(), tids),
    ]
    return "flight_only_rt", finalize(steps)


def case_large_group():
    n = random.randint(4, 8)
    tids = traveler_ids(n)
    o, d = two_codes()
    dep = future_date()
    nights = random.randint(2, 6)
    ret = dep + timedelta(days=nights)
    steps = [
        flight_step(0, 0, o, d, dep.isoformat(), tids),
        flight_step(1, 1, d, o, ret.isoformat(), tids),
        hotel_step(2, d, dep.isoformat(), nights, tids),
    ]
    return "large_group", finalize(steps)


def case_converging_group():
    """Two subgroups from different origins meet at one destination, share hotel."""
    n = random.randint(3, 5)
    tids = traveler_ids(n)
    split = max(1, n // 2)
    g1, g2 = tids[:split], tids[split:]
    o1, o2, dest = random.sample(CODES, 3)
    dep = future_date()
    nights = random.randint(2, 5)
    ret = dep + timedelta(days=nights)
    steps = [
        flight_step(0, 0, o1, dest, dep.isoformat(), g1),
        flight_step(1, 0, o2, dest, dep.isoformat(), g2),
        flight_step(2, 1, dest, o1, ret.isoformat(), g1),
        flight_step(3, 1, dest, o2, ret.isoformat(), g2),
        hotel_step(4, dest, dep.isoformat(), nights, tids),
    ]
    return "converging_group", finalize(steps)


def case_multi_city_split_pax():
    n = random.randint(2, 4)
    tids = traveler_ids(n)
    split = max(1, n // 2)
    g1, g2 = tids[:split], tids[split:]
    a, b, c = random.sample(CODES, 3)
    d1 = future_date()
    nights = random.randint(2, 4)
    d2 = d1 + timedelta(days=nights)
    steps = [
        flight_step(0, 0, a, b, d1.isoformat(), g1),
        flight_step(1, 0, a, c, d1.isoformat(), g2),
        hotel_step(2, b, d1.isoformat(), nights, g1),
        hotel_step(3, c, d1.isoformat(), nights, g2),
    ]
    return "multi_city_split_pax", finalize(steps)


def case_converge_then_extend():
    """
    Two origin groups (A and B) fly to a shared meeting city C, stay together,
    then all return home. A mixed subset (some from A, some from B) then extends
    the trip to a new city D, stays there, and finally returns home (2 flights).

    Steps:
      0  A → C  (group_a, leg 0)
      1  B → C  (group_b, leg 0)
      2  C → A  (group_a return, leg 1)
      3  C → B  (group_b return, leg 1)
      4  hotel C  (everyone)
      5  C → D  (ext_a + ext_b, leg 2)
      6  hotel D  (extension group)
      7  D → A  (ext_a, leg 3)
      8  D → B  (ext_b, leg 3)
    """
    # At least 4 people total: 2 from each origin, so we can form extension sub-groups
    nx = random.randint(2, 3)   # people from origin A
    ny = random.randint(2, 3)   # people from origin B
    all_tids = traveler_ids(nx + ny)
    group_a = all_tids[:nx]
    group_b = all_tids[nx:]

    # Extension sub-groups: at least 1 from each origin group
    ext_a = group_a[:max(1, nx // 2)]
    ext_b = group_b[:max(1, ny // 2)]
    ext_all = ext_a + ext_b

    origin_a, origin_b, city_c, city_d = random.sample(CODES, 4)

    dep = future_date()
    nights_c = random.randint(2, 4)
    ret_c = dep + timedelta(days=nights_c)          # everyone returns from C on this date

    ext_dep = ret_c                                  # extension departs same day as C return
    nights_d = random.randint(2, 4)
    ret_d = ext_dep + timedelta(days=nights_d)

    steps = [
        flight_step(0, 0, origin_a, city_c, dep.isoformat(),     group_a),
        flight_step(1, 0, origin_b, city_c, dep.isoformat(),     group_b),
        flight_step(2, 1, city_c,   origin_a, ret_c.isoformat(), group_a),
        flight_step(3, 1, city_c,   origin_b, ret_c.isoformat(), group_b),
        hotel_step (4, city_c, dep.isoformat(), nights_c,        all_tids),
        flight_step(5, 2, city_c,   city_d,   ext_dep.isoformat(), ext_all),
        hotel_step (6, city_d, ext_dep.isoformat(), nights_d,    ext_all),
        flight_step(7, 3, city_d,   origin_a, ret_d.isoformat(), ext_a),
        flight_step(8, 3, city_d,   origin_b, ret_d.isoformat(), ext_b),
    ]
    return "converge_then_extend", finalize(steps)


DISTRIBUTION = [
    (0.22, case_round_trip_simple),
    (0.12, case_one_way),
    (0.12, case_multi_city),
    (0.09, case_hotel_only),
    (0.09, case_flight_only_rt),
    (0.09, case_large_group),
    (0.09, case_converging_group),
    (0.09, case_converge_then_extend),
    (0.09, case_multi_city_split_pax),
]


def sample_case():
    r = random.random()
    acc = 0.0
    for p, fn in DISTRIBUTION:
        acc += p
        if r <= acc:
            return fn()
    return DISTRIBUTION[-1][1]()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for i in range(args.n):
            case, steps = sample_case()
            row = {"_id": f"p{i:04d}", "case": case, "steps": steps}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {args.n} plans -> {OUT}")


if __name__ == "__main__":
    main()
