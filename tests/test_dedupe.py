from __future__ import annotations

from dbi_land.dedupe import dedupe_cross_source
from dbi_land.models import Listing


def _l(**kw) -> Listing:
    base = dict(
        listing_id="t",
        source="landsearch",
        url="http://x",
        state="MO",
        county="Texas",
        acres=240.0,
        price_usd=400_000.0,
        lat=None,
        lon=None,
        title="",
    )
    base.update(kw)
    return Listing(**base)


def test_same_parcel_two_sources_collapses_to_one():
    a = _l(source="landwatch", listing_id="lw-1", title="Berrien Center, MI", state="MI",
           county="Berrien", acres=245.0, price_usd=66_000.0)
    b = _l(source="landandfarm", listing_id="laf-1", title="Berrien Center, MI", state="MI",
           county="Berrien", acres=245.0, price_usd=66_000.0)
    out, dropped = dedupe_cross_source([a, b])
    assert dropped == 1
    assert len(out) == 1


def test_three_sources_same_parcel_collapse():
    a = _l(source="landsearch",  listing_id="ls-1", state="TX", county="Red River",
           acres=235.0, price_usd=1_495_000.0)
    b = _l(source="landwatch",   listing_id="lw-1", state="TX", county="Red River",
           acres=235.0, price_usd=1_495_000.0)
    c = _l(source="landandfarm", listing_id="laf-1", state="TX", county="Red River",
           acres=235.0, price_usd=1_495_000.0)
    out, dropped = dedupe_cross_source([a, b, c])
    assert dropped == 2
    assert len(out) == 1


def test_different_acres_not_merged():
    a = _l(source="landwatch", acres=240.0)
    b = _l(source="landandfarm", acres=241.0)
    out, dropped = dedupe_cross_source([a, b])
    assert dropped == 0
    assert len(out) == 2


def test_different_counties_not_merged():
    a = _l(source="landwatch", county="Texas")
    b = _l(source="landandfarm", county="Wayne")
    out, dropped = dedupe_cross_source([a, b])
    assert dropped == 0
    assert len(out) == 2


def test_representative_prefers_richest_metadata():
    bare = _l(source="landwatch", listing_id="lw-1", lat=None, lon=None, county="Berrien",
              title="")
    rich = _l(source="landandfarm", listing_id="laf-1", lat=41.94, lon=-86.36,
              county="Berrien", title="Berrien Center, MI, 49102")
    out, _ = dedupe_cross_source([bare, rich])
    assert len(out) == 1
    assert out[0].listing_id == "laf-1"  # rich entry wins


def test_first_appearance_order_is_preserved():
    a = _l(source="landwatch",   listing_id="lw-1", state="MI", acres=245.0)
    b = _l(source="landwatch",   listing_id="lw-2", state="WI", acres=264.0)
    a_dup = _l(source="landandfarm", listing_id="laf-1", state="MI", acres=245.0)
    out, _ = dedupe_cross_source([a, b, a_dup])
    assert [l.state for l in out] == ["MI", "WI"]


def test_empty_input():
    out, dropped = dedupe_cross_source([])
    assert out == []
    assert dropped == 0
