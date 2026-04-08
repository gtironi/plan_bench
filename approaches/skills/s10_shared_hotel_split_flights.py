SKILL = {
    "name": "shared_hotel_split_flights",
    "when_to_use": "Travelers arriving/leaving on different flights/dates but sharing the same hotel for an overlapping window.",
    "prompt": """You are extracting a SHARED HOTEL / SPLIT FLIGHTS plan.
Focus on:
- Multiple flight legs with different traveler_ids and possibly different dates.
- ONE hotel covering the union date range, listing all travelers.
trip_type = "round_trip".
""",
}
