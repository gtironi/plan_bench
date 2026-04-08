SKILL = {
    "name": "one_way",
    "when_to_use": "Travelers going to a destination with no explicit return flight.",
    "prompt": """You are extracting a ONE-WAY plan.
Focus on:
- Single flight leg with return_date = null.
- Hotels are unusual for one-way; only include if explicitly requested.
trip_type = "one_way".
""",
}
