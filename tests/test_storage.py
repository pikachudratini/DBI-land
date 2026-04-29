from datetime import date

from dbi_land.models import Listing
from dbi_land.storage import ListingStore


def _l(listing_id: str, source: str = "test", state: str = "MO") -> Listing:
    return Listing(
        listing_id=listing_id,
        source=source,
        url=f"http://x/{listing_id}",
        state=state,
        county=None,
        acres=100.0,
        price_usd=300_000.0,
        lat=37.0,
        lon=-92.0,
        listed_on=date(2026, 4, 20),
        extras={"k": 1},
    )


def test_upsert_dedupes_across_runs(tmp_path):
    store = ListingStore(tmp_path / "store.jsonl")
    new1 = store.upsert([_l("a"), _l("b")])
    assert {l.listing_id for l in new1} == {"a", "b"}
    new2 = store.upsert([_l("a"), _l("c")])
    assert {l.listing_id for l in new2} == {"c"}
    assert len(store.all_listings()) == 3


def test_round_trip_preserves_fields(tmp_path):
    store = ListingStore(tmp_path / "store.jsonl")
    store.upsert([_l("a")])
    [round_tripped] = store.all_listings()
    assert round_tripped.listing_id == "a"
    assert round_tripped.listed_on == date(2026, 4, 20)
    assert round_tripped.extras == {"k": 1}
