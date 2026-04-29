# Candidates

This directory holds the regional shortlist and per-property writeups.

## Subdirectories

- [`regions/`](regions/) — One file per priority region. Documents geology, typical land cost per acre, zoning posture at the county level, mineral-rights climate, and active brokers. Read these to decide where to focus.
- [`properties/`](properties/) — One file per specific listing being evaluated. Use [`properties/_template.md`](properties/_template.md) to start a new one.

## Regional shortlist (priority order)

1. **[Ozark Plateau (N. Arkansas, S. Missouri)](regions/ozarks-ar-mo.md)** — Strongest fit. Karst springs, low land prices, many counties unzoned.
2. **[Cumberland Plateau (E. Tennessee, E. Kentucky)](regions/cumberland-plateau-tn.md)** — Mild climate, sandstone-over-limestone springs, mostly unzoned at county level.
3. **[Ouachita Mountains (W. Arkansas, SE Oklahoma)](regions/ouachita-mountains.md)** — Springs, low cost, lighter regulation.
4. **[West Virginia / SW Virginia Appalachians](regions/west-virginia.md)** — Cheapest land, springs widespread, but severed minerals (coal, gas) disqualify many parcels.
5. **[North Florida / Panhandle](regions/north-florida.md)** — World-class springs, but typically over budget at 1,000 acres. Stretch goal.

## Adding a new property

1. Copy `properties/_template.md` to `properties/<short-slug>.md` (e.g. `properties/madison-co-ar-1200ac.md`).
2. Fill in everything you know. Mark unverified items as `unknown`, not as guesses.
3. Add the same record as an object to `tracker/data.js` so it appears in the scoring tool.
4. Commit.
