SKILL = {
    "name": "multi_city_split_pax",
    "when_to_use": "Different subgroups going to different destinations from the same origin (or vice versa) on the same dates.",
    "prompt": """You are extracting a SPLIT MULTI-CITY plan.
Focus on:
- Two or more flight legs leaving the same origin on the same date but going to DIFFERENT destinations.
- Each leg has its own subgroup of traveler_ids.
- A separate hotel per destination, each tied only to the matching subgroup.
trip_type = "multi_city".
""",
}
