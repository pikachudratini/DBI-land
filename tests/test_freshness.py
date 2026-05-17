from __future__ import annotations

from datetime import date, timedelta

from dbi_land.freshness import LastSeenIndex
from dbi_land.models import Listing


def _l(listing_id="t", source="landwatch") -> Listing:
    return Listing(
        listing_id=listing_id,
        source=source,
        url="http://x",
        state="MO",
        county="Texas",
        acres=600.0,
        price_usd=1_000_000.0,
        lat=None,
        lon=None,
    )


def test_touch_then_last_seen_roundtrip(tmp_path):
    idx = LastSeenIndex(tmp_path / "ls.json")
    when = date(2026, 5, 13)
    idx.touch([_l("a")], when=when)
    assert idx.last_seen(_l("a")) == when


def test_touch_persists_across_instances(tmp_path):
    p = tmp_path / "ls.json"
    when = date(2026, 5, 13)
    LastSeenIndex(p).touch([_l("a"), _l("b")], when=when)

    idx2 = LastSeenIndex(p)
    assert idx2.last_seen(_l("a")) == when
    assert idx2.last_seen(_l("b")) == when


def test_filter_active_drops_stale_and_unknown(tmp_path):
    idx = LastSeenIndex(tmp_path / "ls.json")
    today = date(2026, 5, 13)
    idx.touch([_l("fresh")], when=today)
    idx.touch([_l("stale")], when=today - timedelta(days=30))
    # _l("unknown") was never touched

    active, dropped = idx.filter_active(
        [_l("fresh"), _l("stale"), _l("unknown")],
        max_stale_days=14,
        today=today,
    )
    assert [l.listing_id for l in active] == ["fresh"]
    assert dropped == 2


def test_filter_active_edge_at_cutoff(tmp_path):
    idx = LastSeenIndex(tmp_path / "ls.json")
    today = date(2026, 5, 13)
    cutoff = today - timedelta(days=14)
    idx.touch([_l("edge")], when=cutoff)
    active, dropped = idx.filter_active(
        [_l("edge")], max_stale_days=14, today=today,
    )
    assert len(active) == 1
    assert dropped == 0


def test_touch_overwrites_older_date(tmp_path):
    idx = LastSeenIndex(tmp_path / "ls.json")
    idx.touch([_l("a")], when=date(2026, 5, 1))
    idx.touch([_l("a")], when=date(2026, 5, 13))
    assert idx.last_seen(_l("a")) == date(2026, 5, 13)


def test_different_sources_tracked_independently(tmp_path):
    idx = LastSeenIndex(tmp_path / "ls.json")
    idx.touch([_l("123", source="landwatch")], when=date(2026, 5, 13))
    # Same listing_id but on a different source: separate entry.
    assert idx.last_seen(_l("123", source="landandfarm")) is None
    assert idx.last_seen(_l("123", source="landwatch")) == date(2026, 5, 13)
