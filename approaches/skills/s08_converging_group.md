# Skill: converging_group

**When to use:** Travelers come from different origins and meet at the same destination, sharing one hotel there.

---

## Step-by-step

1. **List all travelers.** Assign stable ids. Note which origin each traveler (or subgroup) departs from.

2. **Group travelers by origin.** Example: Ana flies from São Paulo (GRU), Bruno and Carlos fly from Rio (GIG).

3. **Create one flight entry per origin group.**
   - Each leg: origin=that city's IATA, destination=shared meeting city IATA.
   - `depart_date`: the date each subgroup flies (they may differ by a day — use what the text says).
   - `return_date`: if they also return together, add it. If not, use null.
   - `traveler_ids`: only the travelers in that subgroup.
   - `cabin`: per leg (default `economy`).

4. **Create one shared hotel at the destination.**
   - `city_iata` = meeting city.
   - `check_in` = earliest arrival date among all subgroups.
   - `check_out` = the date everyone leaves.
   - `traveler_ids`: ALL travelers.
   - `rooms`: stated, or estimate `ceil(N/2)`.

5. **trip_type.** Use `"round_trip"` if they all return, `"one_way"` if not.

6. **Assemble.**
   - Multiple flight entries (one per origin group).
   - One hotel entry covering everyone.
