SKILL = {
    "name": "converging_group",
    "when_to_use": "Travelers coming from DIFFERENT origins meeting at the same destination, sharing one hotel.",
    "prompt": """You are extracting a CONVERGING GROUP plan.
Focus on:
- Two or more flight legs with DIFFERENT origins but the SAME destination and same dates.
- Each leg has only the subgroup of traveler_ids that flies from that origin.
- One shared hotel at the destination listing ALL travelers.
trip_type = "round_trip".
""",
}
