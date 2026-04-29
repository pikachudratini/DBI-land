// Candidate data — this file is the single source of truth for the tracker.
// Add new candidates as objects in the array below. Field names must match
// exactly. Each gate is "pass", "fail", or "unknown".
//
// Mirror new entries in candidates/properties/<slug>.md.

window.CANDIDATES = [
  {
    id: "example-ozarks-stub",
    name: "EXAMPLE — Stone County AR 1,200ac",
    region: "ozarks",
    county: "Stone",
    state: "AR",
    listing_url: "",
    broker: "",
    broker_contact: "",
    acres: 1200,
    asking_price_usd: 3000000,
    price_per_acre_usd: 2500,
    gates: {
      G1_acreage_1000plus: { status: "pass", source: "Tax parcel records show 1,200 contiguous acres" },
      G2_entrance_north_or_east: { status: "unknown", source: "Need to verify — driveway location not confirmed" },
      G3_no_major_highway: { status: "pass", source: "Only county road frontage per FHWA NHS map" },
      G4_no_easements: { status: "unknown", source: "Title commitment not yet ordered" },
      G5_full_mineral_rights: { status: "unknown", source: "Mineral title opinion pending" },
      G6_no_zoning_hoa_restrictions: { status: "pass", source: "Stone County is unzoned per planning dept letter" },
      G7_no_hv_power_lines: { status: "pass", source: "No transmission lines per EIA HIFLD layer" },
      G8_organic_capable_soil: { status: "unknown", source: "WSS shows 200ac prime farmland; prior-use unverified" },
      G9_year_round_springs_on_parcel: { status: "unknown", source: "USGS NHD shows 2 springs on parcel; dry-season visit needed" }
    },
    notes: "This is a stub example demonstrating tracker usage. Replace with real candidates as they are identified."
  }
];
