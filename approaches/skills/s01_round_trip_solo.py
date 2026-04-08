SKILL = {
    "name": "round_trip_solo",
    "when_to_use": "A single traveler going to one destination and back, possibly with a hotel for the same dates.",
    "prompt": """You are extracting a SOLO ROUND-TRIP corporate travel plan.
Focus on:
- Exactly one traveler.
- Exactly one outbound and one return flight (same origin/destination pair, swapped).
- Optionally one hotel at the destination matching the travel dates.
Set trip_type = "round_trip" (or "flight_only" if no hotel was requested).
Use 3-letter IATA codes. Dates ISO. cabin defaults to "economy".
""",
}
