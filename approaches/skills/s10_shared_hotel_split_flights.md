# Skill: shared_hotel_split_flights

**When to use:** Travelers arrive or depart on different flights/dates but share the same hotel for an overlapping window.

---

## Step-by-step

1. **List all travelers.** Assign stable ids.

2. **Map each traveler's flights separately.**
   - Traveler A: flight A-in (origin, destination, depart_date) and maybe flight A-out (return_date or separate leg).
   - Traveler B: flight B-in with possibly different origin or different date.
   - Create a separate flight entry for each distinct (traveler subset, origin, date) combination.

3. **Identify the shared hotel window.**
   - `check_in` = the earliest date any traveler checks in (or arrives at the hotel city).
   - `check_out` = the latest date any traveler checks out.
   - If the text gives explicit check-in/check-out dates for the shared hotel, use those directly.
   - `city_iata` = the hotel city.
   - `traveler_ids` = ALL travelers staying there.
   - `rooms` = stated, or estimate `ceil(N/2)`.

4. **Only one hotel entry** even though flights differ. The hotel serves the whole group.

5. **trip_type.** Use `"round_trip"` if everyone returns. If the stays overlap but departures differ, still use `"round_trip"` as the dominant type.

6. **Assemble.**
   - Multiple flight entries (one per distinct traveler subgroup + date/origin combination).
   - One shared hotel entry covering the full window and all travelers.
