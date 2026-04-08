# Skill: multi_city_same_pax

**When to use:** The same group of travelers visits 2+ cities in sequence (A → B → C → A), with a hotel in each intermediate city.

---

## Step-by-step

1. **List all travelers.** Assign stable ids. They all appear on every leg.

2. **Identify the sequence of cities.** Write them out in order: city1, city2, city3, … (and back to city1 if they return). Map each to an IATA code.

3. **Create one flight entry per leg.** For a sequence A → B → C → A:
   - Leg 1: origin=A, destination=B, `depart_date`=date of departure, `return_date=null`.
   - Leg 2: origin=B, destination=C, `depart_date`=date of departure from B, `return_date=null`.
   - Leg 3: origin=C, destination=A, `depart_date`=date of departure from C, `return_date=null`.
   - All legs share the same `traveler_ids` and `cabin`.

4. **Create one hotel per intermediate stop.** For each city the group stays in:
   - `check_in` = date of arrival (= `depart_date` of the inbound leg).
   - `check_out` = date of departure (= `depart_date` of the outbound leg from that city).
   - `city_iata` = that city's IATA.
   - `traveler_ids`: all travelers.
   - `rooms`: stated or estimate `ceil(N/2)`.

5. **Do not create a hotel for the origin city** (they live there; the first and last cities are typically the same).

6. **Assemble.**
   - `trip_type = "multi_city"`.
   - N flight entries (one per leg).
   - N-1 hotel entries (one per intermediate city).
