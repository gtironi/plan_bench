# Skill: one_way

**When to use:** Traveler(s) going to a destination with no explicit return flight mentioned.

---

## Step-by-step

1. **List all travelers.** Assign stable ids `t1`, `t2`, … Type = `adult` unless stated.

2. **Find the single flight leg.**
   - Origin → IATA.
   - Destination → IATA.
   - `depart_date` in ISO.
   - `return_date = null` (no return was requested).
   - `traveler_ids`: all travelers who take this leg.
   - `cabin`: default `economy`.

3. **Hotel.** One-way trips usually have no hotel, but include one if the user explicitly asks.
   - If hotel is requested: set `check_in`, `check_out`, `city_iata` = destination.
   - If not: `hotels = []`.

4. **Assemble.**
   - `trip_type = "one_way"`.
   - One flight entry.
   - Zero or one hotel.
