from dbi_land.models import Listing
from dbi_land.score import score_listings
from dbi_land.score.criteria import (
    score_acreage,
    score_access,
    score_price,
    score_state,
    score_water,
)
from dbi_land.sources import CsvSource


def _l(**kw) -> Listing:
    base = dict(
        listing_id="t",
        source="test",
        url="http://x",
        state="MO",
        county=None,
        acres=120.0,
        price_usd=400_000.0,
        lat=None,
        lon=None,
    )
    base.update(kw)
    return Listing(**base)


def test_state_pass_and_fail(criteria):
    assert score_state(_l(state="MO"), criteria).score == 1.0
    assert score_state(_l(state="WY"), criteria).score == 0.0


def test_excluded_county_fails(criteria):
    c = criteria.__class__(
        states=criteria.states,
        acreage_bands=criteria.acreage_bands,
        price=criteria.price,
        weights=criteria.weights,
        excluded_counties=("Texas",),
    )
    assert score_state(_l(state="MO", county="Texas"), c).score == 0.0


def test_acreage_band_midpoint_scores_highest(criteria):
    # MO band 1 is 40-160; midpoint 100
    mid = score_acreage(_l(acres=100), criteria).score
    edge = score_acreage(_l(acres=40), criteria).score
    out = score_acreage(_l(acres=10), criteria).score
    assert mid > edge > 0
    assert out == 0.0


def test_acreage_above_top_band_scores_as_top(criteria):
    # Test fixture's top band is 321-640 with weight 0.65; sanity cap default 50k.
    # A 1500-ac parcel is above all bands but well under sanity cap.
    top = max(criteria.acreage_bands, key=lambda b: b.max_acres)
    s = score_acreage(_l(acres=1500), criteria)
    assert s.score > 0
    assert s.score == min(top.weight, 1.0)
    assert "above top band" in s.detail


def test_acreage_above_sanity_cap_hard_fails(criteria):
    # A 248k-ac parcel is real scraping garbage; default sanity cap is 50k.
    s = score_acreage(_l(acres=248_292), criteria)
    assert s.score == 0.0
    assert "sanity cap" in s.detail


def test_price_caps_hard_fail(criteria):
    over_total = _l(acres=400, price_usd=2_000_000)  # exceeds total cap
    over_ppa = _l(acres=10, price_usd=200_000)  # 20k/ac
    assert score_price(over_total, criteria).score == 0.0
    assert score_price(over_ppa, criteria).score == 0.0


def test_price_below_1000_treated_as_unknown(criteria):
    # "Call for Price" listings sometimes land in the store with price_usd=1.0.
    # They must hard-fail price, not score as the best deal in the digest.
    assert score_price(_l(acres=240, price_usd=1.0), criteria).score == 0.0
    assert score_price(_l(acres=240, price_usd=0.0), criteria).score == 0.0


def test_price_under_cap_has_positive_score(criteria):
    s = score_price(_l(acres=120, price_usd=400_000), criteria)
    assert 0 < s.score <= 1


def test_water_extras_floor(criteria):
    assert score_water(_l(extras={"water_score": 0.1}), criteria).score == 0.0
    assert score_water(_l(extras={"water_score": 0.5}), criteria).score == 0.5
    # missing data is neutral, not a fail
    assert score_water(_l(), criteria).score == 0.5


def test_access_neutral_without_extras(criteria):
    assert score_access(_l(), criteria).score == 0.5


def test_access_floor_failure(criteria):
    s = score_access(_l(extras={"road_access_score": 0.1}), criteria)
    assert s.score == 0.0


def test_score_listings_filters_and_ranks(sample_csv_path, criteria):
    listings = list(CsvSource(sample_csv_path).fetch())
    scored = score_listings(listings, criteria, only_passing=True)
    # WY out-of-state, NC over price cap, IA over per-acre cap (8000/ac > 6000)
    ids = [s.listing.listing_id for s in scored]
    assert "ls-0005" not in ids
    assert "ls-0007" not in ids
    assert "ls-0002" not in ids
    assert ids[0] in {"ls-0001", "ls-0004", "ls-0006", "ls-0003"}
    # ranked descending
    totals = [s.total for s in scored]
    assert totals == sorted(totals, reverse=True)
