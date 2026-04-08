# Skill: round_trip_group

**When to use:** Multiple travelers (2+) all flying together to the same destination and back, sharing one hotel.

---

## Step-by-step

1. **List all travelers.** Give each a stable id: `t1`, `t2`, `t3`, … in the order they appear in the text. Type = `adult` unless stated otherwise.

2. **Confirm they all share the same itinerary.** If any traveler has a different origin, different destination, or different dates, stop — use skill `converging_group` or `multi_city_split_pax` instead.

3. **Find the outbound leg.**
   - Origin: shared departure city → IATA.
   - Destination: shared arrival city → IATA.
   - `depart_date` in ISO.
   - `traveler_ids`: list ALL traveler ids.

4. **Find the return date.** Put it in the same flight entry as `return_date`.

5. **Determine cabin class.** One cabin for all. Default `economy`.

6. **Hotel.**
   - `city_iata` = destination.
   - `check_in` = `depart_date`, `check_out` = `return_date`.
   - `traveler_ids`: all travelers.
   - `rooms`: use what the user says. If not specified, estimate `ceil(N / 2)` where N = number of travelers.

7. **Assemble.**
   - `trip_type = "round_trip"`.
   - One flight entry for the whole group.
   - One hotel entry (unless explicitly no hotel was requested → `hotels = []`, `trip_type = "flight_only"`).
