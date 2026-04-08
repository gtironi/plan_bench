SKILL = {
    "name": "round_trip_group",
    "when_to_use": "Multiple travelers (2+) all flying together to the same destination and back, sharing one hotel.",
    "prompt": """You are extracting a GROUP ROUND-TRIP plan.
Focus on:
- 2 or more travelers, all on the same flight legs.
- Single round-trip pair of flights covering everyone.
- One shared hotel; estimate rooms (~ ceil(N/2)) if not specified.
trip_type = "round_trip".
""",
}
