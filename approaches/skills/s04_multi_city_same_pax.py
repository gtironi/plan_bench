SKILL = {
    "name": "multi_city_same_pax",
    "when_to_use": "Same travelers visiting 2+ cities in sequence (A -> B -> C -> A), with hotels in each city.",
    "prompt": """You are extracting a MULTI-CITY plan with the SAME group throughout.
Focus on:
- Sequential one-way legs (each with return_date = null) for the whole group.
- One hotel per intermediate stop, dates matching the leg-to-leg gap.
trip_type = "multi_city".
""",
}
