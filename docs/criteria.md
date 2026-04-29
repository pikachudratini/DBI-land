# Hard Criteria

A property must pass **every** gate to qualify. There are no soft trade-offs in this list — soft preferences belong in property notes, not here. The IDs (`G1`–`G9`) are referenced by the due-diligence checklist and the tracker tool.

| ID  | Gate                                       | Why it matters                                                                                                                                        |
| --- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | **≥ 1,000 contiguous acres**               | Below this size the center cannot be self-contained or buffered from neighbors. Non-contiguous parcels create access, taxation, and management problems. |
| G2  | **Entrance from north or east side**       | Stated requirement of the principal. A driveway or legal access easement on the south or west side fails this gate even if other access exists.       |
| G3  | **No major highway bordering the parcel**  | Highway frontage brings traffic noise, runoff, eminent-domain risk, and visibility that conflict with a retreat use. "Major highway" = U.S. route, Interstate, or state primary highway. |
| G4  | **No easements on the property**           | Any recorded easement (utility, access, conservation, pipeline, ingress/egress for neighbors) gives an outside party rights on the land. Even dormant easements are a fail. |
| G5  | **Full surface AND mineral rights**        | If minerals are severed, the mineral-estate owner can lease drilling/mining rights and access the surface to extract — overriding the surface owner. Severed minerals = fail. |
| G6  | **No zoning, no HOA, no deed restrictions**| Zoning, HOA covenants, and deed restrictions can prohibit agriculture, structures, group residency, religious use, water use, or animal keeping. Any of the three = fail. |
| G7  | **No high-voltage power lines**            | Transmission lines (≥ 69 kV) on or crossing the parcel bring utility easements (fails G4 anyway), EMF concerns, and visual intrusion. Distribution lines (lower voltage) serving the parcel itself are acceptable. |
| G8  | **Soil suitable for organic crop production** | Per USDA Web Soil Survey: at least one large block rated *prime farmland* or *farmland of statewide importance*, well-drained, with no contamination history. Prior land use must allow organic certification (3-year transition rule). |
| G9  | **Year-round springs originating on the land** | Springs that emerge **on the parcel** (not streams flowing in from upstream property). Must flow during the late-summer / early-fall dry season. Verified by site visit during dry season and ideally a hydrogeologist letter. |

## How the tracker scores these

For each candidate in `tracker/data.json`, every gate is recorded as one of:

- `"pass"` — verified and confirmed
- `"fail"` — verified and disqualifying
- `"unknown"` — not yet verified (treated as a blocker until checked, but not a permanent fail)

A candidate is **qualified** only when all 9 gates are `pass`. Any `fail` removes it from the running. `unknown` flags it for the next due-diligence step.

## Budget (separate from gates)

Budget is a constraint, not a gate, because it depends on negotiation:

- Asking price ≤ **$4,000,000**
- Effective $/acre ≤ **$4,000** at 1,000 acres (lower at higher acreage)
