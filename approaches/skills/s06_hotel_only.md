# Skill: hotel_only

**When to use:** The user asks only for hotel/lodging — no flights are mentioned.

---

## Step-by-step

1. **List all travelers.** Assign stable ids. Note whether they share a room or need separate rooms.

2. **Identify the hotel stay.**
   - City → IATA code.
   - `check_in` date in ISO.
   - `check_out` date in ISO.
   - `rooms`: use what the user says. If not stated, default to 1.
   - `traveler_ids`: all travelers staying in this hotel.

3. **Check for multiple hotels.** If the user mentions stays in different cities or at different times, create one hotel entry per stay. Each entry gets the correct `city_iata`, dates, and traveler subset.

4. **Flights must be empty.** `flights = []`.

5. **Assemble.**
   - `trip_type = "hotel_only"`.
   - `flights = []`.
   - One or more hotel entries.
