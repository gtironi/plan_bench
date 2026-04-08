# Skill: back_to_back_trips

**When to use:** Multiple independent trips are packed into one request — different people on different dates, possibly nothing shared between them.

---

## Step-by-step

1. **Segment the request.** Read through and separate each distinct trip. A trip boundary is typically a different person or a different travel window that doesn't overlap.

2. **List all travelers across all trips.** Assign unique ids globally: `t1`, `t2`, … Do not reuse ids.

3. **For each trip segment:**
   a. Identify the traveler(s) for this segment and their ids.
   b. Identify origin, destination, depart_date, return_date (or null).
   c. Create a flight entry with `traveler_ids` pointing only to this segment's travelers.
   d. If a hotel is mentioned for this segment, create a hotel entry with the matching dates and the same `traveler_ids`.

4. **Do not mix traveler_ids between unrelated trips.** Ana's flight should not list Bruno's id and vice versa.

5. **Determine trip_type.** Look at the dominant pattern:
   - All one-way → `"one_way"`.
   - All round-trip → `"round_trip"`.
   - Mixed or multiple destinations → `"multi_city"`.

6. **Assemble.**
   - All flight entries in one `flights` array.
   - All hotel entries in one `hotels` array.
   - Each entry has its own precise `traveler_ids`.
