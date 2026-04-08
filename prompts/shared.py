"""Shared prompt fragments used across approaches."""
from schema import SCHEMA_TEXT

SYSTEM_BASE = f"""You convert free-form corporate travel requests into an ordered list of executable plan steps.

A plan is a JSON object with one key: "steps". Each step is one of two actions:

- quote_flight: a single flight leg between two airports on one date for a set of travelers.
- quote_hotel: a single hotel stay in one city for a check-in date and a number of nights.

Output MUST conform to this JSON schema exactly:

{SCHEMA_TEXT}

Rules:
- step_id is a sequential integer starting at 0.
- depends_on is a list with the previous step_id (linear chain). The first step has [].
- next_step is the following step_id, or null for the last step.
- enter_guard is always the literal string "True".
- success_criteria is always the literal string "len(result) > 0".
- For quote_flight: set leg=0 for outbound, leg=1 for return; for multi-city, increment leg per leg of the same group. Set city, check_in_date, number_of_nights, number_of_guests, area to null. from_airport_code and to_airport_code are 3-letter UPPERCASE IATA codes (e.g. "São Paulo"->"GRU", "New York"->"JFK", "London"->"LHR"). departure_date is ISO YYYY-MM-DD. passengers is the integer count of traveler_ids.
- For quote_hotel: set city to the destination IATA code, check_in_date as ISO date, number_of_nights and number_of_guests as STRINGS (e.g. "3", "2"). Set leg, from_airport_code, to_airport_code, departure_date, passengers to null. area is usually null.
- traveler_ids are short stable strings like "t1", "t2", "t3". Use t1..tN in the order travelers appear in the text.
- title for flights: "<FROM> to <TO> flight". For hotels: "<CITY> hotel <N> nights (<G> guests)".
- Emit a hotel step for every accommodation mentioned. Emit a flight step for every distinct leg. If a subgroup flies separately, emit a separate flight step for that subgroup with only their traveler_ids.
- Never invent extra steps. Never omit required fields (use null where allowed).
"""


def user_prompt(text):
    return f"Extract the travel plan from this request:\n\n<<<\n{text}\n>>>"
