SKILL = {
    "name": "hotel_only",
    "when_to_use": "User asks only for hotel/lodging, no flights.",
    "prompt": """You are extracting a HOTEL-ONLY plan.
Focus on:
- No flights.
- One or more hotel stays with check_in / check_out and traveler_ids.
trip_type = "hotel_only".
""",
}
