# Due-Diligence Checklist

For every serious candidate, work through this checklist top to bottom. Each item maps to a gate in [`criteria.md`](criteria.md). A "verified" answer requires the document or source listed — anecdotal answers from sellers or brokers do not count.

## Phase 1 — Desk screen (free, ~1 hour)

Before contacting a broker, eliminate disqualified parcels with public data.

- [ ] **G1 Acreage** — Pull the parcel from the county GIS / parcel viewer. Confirm acreage and that the listing is one contiguous tax parcel (or a small group of contiguous parcels under common ownership). Multi-parcel listings spread across roads usually fail.
- [ ] **G2 Entrance side** — Open the parcel in a topo viewer (USGS topoView, CalTopo, or Google Earth with parcel overlay). Identify where the existing driveway / legal access meets a public road. Confirm it is on the **north or east** side. If access is via easement across a neighbor, that easement direction also counts.
- [ ] **G3 No major highway** — Check the FHWA National Highway System map plus the state DOT route map. The parcel must not border an Interstate, U.S. route, or state primary highway. County roads are acceptable.
- [ ] **G7 No HV power lines (initial check)** — Use the EIA HIFLD "Electric Power Transmission Lines" layer (open data) on the parcel. If a transmission line crosses, it is almost always paired with a recorded easement (also fails G4). Document any apparent crossing for the title check.
- [ ] **G8 Soil (initial check)** — USDA Web Soil Survey (`websoilsurvey.sc.egov.usda.gov`). Draw an Area of Interest over the parcel; pull the *Farmland Classification* and *Drainage Class* reports. Look for at least one large block of prime farmland or farmland of statewide importance with well-drained soil.
- [ ] **G9 Springs (initial check)** — USGS National Hydrography Dataset (NHD); state spring inventory if it exists (Arkansas, Missouri, Tennessee, and Florida all publish them). Springs symbolized **inside** the parcel boundary are necessary but not sufficient — flow during the dry season must still be confirmed.

If the parcel passes Phase 1, escalate to Phase 2.

## Phase 2 — Title and records (paid, ~2–3 weeks)

- [ ] **G4 No easements** — Order a title commitment from a licensed title company in the parcel's county. Read **Schedule B-II (Exceptions)** line by line. Anything more than the standard owner's policy exceptions is a red flag; recorded easements (utility, ingress/egress, conservation) fail this gate.
- [ ] **G5 Mineral rights** — Two steps:
  1. County recorder mineral severance search (the title company can include this; some states require a separate search).
  2. Order a **mineral title opinion** from a real-estate attorney who practices in the county. This is the only way to get a binding answer about whether minerals run with the surface.
- [ ] **G6 Zoning / HOA / deed restrictions** — Three sources:
  1. Letter from the county planning department confirming the parcel's zoning designation (or that the county is unzoned).
  2. Recorder's office search for recorded restrictive covenants tied to the parcel.
  3. Seller disclosure of any HOA or property-owners' association affiliation.

## Phase 3 — Site visit (during dry season — late Aug / early Sept)

Springs are easy to misjudge in spring or after a wet stretch. The site visit must happen during the local dry season.

- [ ] **G9 Springs (verified)** — Walk to each spring shown on NHD/state inventory. Confirm visible flow at the source (not just downstream). Photograph each. Measure approximate flow with a bucket and stopwatch (gallons per minute). A hydrogeologist's letter on year-round flow is the gold standard if budget allows.
- [ ] **G2 Entrance (verified)** — Drive the access road. Confirm it is the legal access (matches plat) and arrives at the parcel from the documented direction.
- [ ] **G3 Highway (verified)** — Drive the perimeter. Verify no major-highway frontage and note traffic noise.
- [ ] **G7 Power lines (verified)** — Walk or drive the perimeter and the interior. Photograph any towers or wood-pole lines. Distinguish distribution (lower voltage, single crossarms) from transmission (higher voltage, larger structures, multiple conductors per phase).
- [ ] **G8 Soil (verified)** — Soil cores from at least three locations on the proposed crop area, sent to the state cooperative-extension lab for fertility, pH, and contamination panel. Ask the seller for prior land-use history (3-year clean record is required for organic certification).

## Phase 4 — Offer and closing

- [ ] Negotiate purchase contract with explicit warranty that all 9 gates remain satisfied at closing.
- [ ] Final walkthrough.
- [ ] Closing with title insurance issued.

## Hard "do not skip" items

These three are the most common ways a property looks good on paper but fails after closing:

1. **Mineral title opinion** (G5) — A title commitment alone is not enough; minerals are a separate estate and require their own attorney opinion.
2. **Dry-season spring visit** (G9) — Spring flow in March tells you nothing about September.
3. **Schedule B-II read in full** (G4) — Recorded easements often hide here in plain language ("a 50-foot easement to Acme Pipeline recorded at Book X Page Y").
