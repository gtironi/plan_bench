# Skill: multi_city_split_pax

**When to use:** Different subgroups leave the same origin on the same date but go to different destinations (or vice versa — they converge but split accommodation).

---

## Step-by-step

1. **List all travelers.** Assign stable ids `t1`, `t2`, …

2. **Identify the split.** Determine which travelers go to which destination. Form groups: group A → city X, group B → city Y.

3. **Create one flight entry per group.**
   - Leg for group A: origin=shared origin, destination=X, `depart_date`=same date, `return_date=null`, `traveler_ids`=[ids in group A].
   - Leg for group B: origin=shared origin, destination=Y, `depart_date`=same date, `return_date=null`, `traveler_ids`=[ids in group B].
   - Use the same `cabin` for both unless stated otherwise.

4. **Create one hotel per destination.**
   - Hotel X: `city_iata`=X, `check_in`=arrival date, `check_out`=departure date, `traveler_ids`=[group A ids], `rooms`=stated or 1.
   - Hotel Y: `city_iata`=Y, `check_in`=arrival date, `check_out`=departure date, `traveler_ids`=[group B ids], `rooms`=stated or 1.

5. **Do NOT mix traveler_ids between hotels** — each hotel only lists the travelers staying there.

6. **Assemble.**
   - `trip_type = "multi_city"`.
   - 2+ flight entries.
   - 2+ hotel entries, one per destination group.
