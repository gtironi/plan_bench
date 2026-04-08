# Skill: flight_only

**When to use:** The user asks for flights only — no hotel is mentioned at all.

---

## Step-by-step

1. **List all travelers.** Assign stable ids.

2. **Determine if it is a round-trip or one-way.**
   - If both a departure date and a return date are present: it is a round-trip flight.
   - If only a departure date: it is one-way, set `return_date = null`.

3. **Build the flight entry.**
   - `origin` → IATA.
   - `destination` → IATA.
   - `depart_date` in ISO.
   - `return_date` in ISO or null.
   - `traveler_ids`: all travelers.
   - `cabin`: default `economy`.

4. **Hotels must be empty.** `hotels = []`.

5. **Assemble.**
   - `trip_type = "flight_only"`.
   - One flight entry.
   - `hotels = []`.
