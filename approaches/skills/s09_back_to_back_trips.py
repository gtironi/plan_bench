SKILL = {
    "name": "back_to_back_trips",
    "when_to_use": "Multiple separate trips on consecutive days for different people, possibly sharing nothing.",
    "prompt": """You are extracting BACK-TO-BACK independent trips packed into one request.
Focus on:
- Treat each person/trip as its own set of legs and hotels.
- Different traveler_ids per leg.
- Pick trip_type that best describes the dominant trip; if mixed, prefer "multi_city".
""",
}
