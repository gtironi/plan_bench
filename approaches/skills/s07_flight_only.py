SKILL = {
    "name": "flight_only",
    "when_to_use": "User asks for flights with no hotel mention.",
    "prompt": """You are extracting a FLIGHT-ONLY plan (round-trip OR one-way).
Focus on:
- Flights only; hotels = [].
- If both depart and return dates exist, set trip_type = "flight_only".
- If only one date, you may still use "flight_only" with return_date = null.
""",
}
