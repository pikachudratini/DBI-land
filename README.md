# DBI Land Search

Centralized search for a second Divine Bliss International (DBI) center on rural land.

## What this repo is

A working set of documents and a small static tracker tool to evaluate candidate properties against a fixed set of hard requirements. There is no application server — every artifact is a markdown file you can read in any editor or a static HTML page you can open locally.

## How to use it

1. **Read the criteria.** Start with [`docs/criteria.md`](docs/criteria.md). These are the 9 hard PASS/FAIL gates. A property that fails any gate is disqualified.
2. **Understand the verification process.** [`docs/due-diligence-checklist.md`](docs/due-diligence-checklist.md) lists the concrete step required to confirm each criterion (title commitment, USDA soil survey, etc.).
3. **Look at where to search.** [`docs/search-methodology.md`](docs/search-methodology.md) covers brokers, listing sites, and the order of operations. [`docs/spring-geology-primer.md`](docs/spring-geology-primer.md) explains why certain regions reliably have year-round springs.
4. **Review the regional shortlist.** [`candidates/regions/`](candidates/regions/) has one file per priority region with land prices, zoning posture, mineral-rights risk, and active brokers.
5. **Track specific properties.** Copy [`candidates/properties/_template.md`](candidates/properties/_template.md) for each new listing. Add the same record to [`tracker/data.js`](tracker/data.js) so it shows up in the scoring tool.
6. **Score and compare.** Open [`tracker/index.html`](tracker/index.html) in a browser. Sort, filter, and see which candidates pass all gates. No build step or server required — the tracker is a single static page.

## Search parameters

- **Acreage**: ≥ 1,000 acres
- **Budget**: under $4,000,000 (≈ $4,000/acre ceiling at minimum size)
- **Geographic scope**: spring-rich regions of the U.S. — primarily the Ozark Plateau, Cumberland Plateau, central Appalachians, and Ouachita Mountains
- **Top priority**: year-round springs **originating on the parcel** (not streams flowing through from elsewhere)

## Branch

All work is on `claude/find-rural-land-wVLN8`.
