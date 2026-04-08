# Skill: round_trip_solo

**When to use:** A single traveler going to one destination and back, possibly with a hotel for the same dates.

---

## Step-by-step

1. **Identify the single traveler.** Find the full name. Assign id `t1`. Type = `adult` unless stated otherwise.

2. **Find the outbound leg.**
   - Origin: where the traveler is coming from. Map city name → IATA code (e.g. "São Paulo" → `GRU`, "New York" → `JFK`).
   - Destination: where they are going. Map to IATA.
   - `depart_date`: the departure date in ISO YYYY-MM-DD.

3. **Find the return leg.**
   - The return is the same pair reversed: destination → origin.
   - `return_date`: the date they come back. Write it in the same flight object as `return_date`.
   - If no return date is mentioned, stop and use skill `one_way` instead.

4. **Determine cabin class.** Default `economy` unless the traveler specifies business, first, or premium economy.

5. **Check if a hotel is needed.**
   - If the user mentions a hotel or accommodation: create one hotel entry with `city_iata` = destination, `check_in` = `depart_date`, `check_out` = `return_date`, `rooms` = 1.
   - If no hotel is mentioned: `hotels = []` and set `trip_type = "flight_only"`.
   - If hotel is present: `trip_type = "round_trip"`.

6. **Assemble the plan.**
   - `travelers`: one entry with `id`, `name`, `type`.
   - `flights`: one entry with `origin`, `destination`, `depart_date`, `return_date`, `traveler_ids: ["t1"]`, `cabin`.
   - `hotels`: zero or one entry.
