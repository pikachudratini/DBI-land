import json

from dbi_land.geocode import Geocoder
from dbi_land.models import Listing


class _FakeGeocoder(Geocoder):
    """Stub the network call so tests don't hit OSM."""

    def __init__(self, cache_path, lookups):
        super().__init__(cache_path=cache_path)
        self._lookups = lookups
        self._call_count = 0

    def _query(self, q: str):
        self._call_count += 1
        return self._lookups.get(q)


def _l(listing_id: str, lat=None, lon=None, county=None, state="MO") -> Listing:
    return Listing(
        listing_id=listing_id,
        source="t",
        url=f"http://x/{listing_id}",
        state=state,
        county=county,
        acres=100.0,
        price_usd=300_000.0,
        lat=lat,
        lon=lon,
    )


def test_enrich_fills_missing_coordinates(tmp_path):
    geo = _FakeGeocoder(
        cache_path=tmp_path / "cache.json",
        lookups={"Texas, MO, USA": (37.30, -92.0)},
    )
    out = geo.enrich([_l("a", county="Texas"), _l("b", lat=40.0, lon=-90.0)])
    assert out[0].lat == 37.30 and out[0].lon == -92.0
    assert out[1].lat == 40.0 and out[1].lon == -90.0


def test_cache_persists_across_instances(tmp_path):
    cache = tmp_path / "cache.json"
    geo1 = _FakeGeocoder(cache_path=cache, lookups={"Texas, MO, USA": (37.3, -92.0)})
    geo1.enrich([_l("a", county="Texas")])
    assert geo1._call_count == 1

    geo2 = _FakeGeocoder(cache_path=cache, lookups={})  # no lookups available
    out = geo2.enrich([_l("a2", county="Texas")])
    assert out[0].lat == 37.3
    assert geo2._call_count == 0  # served from cache


def test_negative_result_cached(tmp_path):
    cache = tmp_path / "cache.json"
    geo = _FakeGeocoder(cache_path=cache, lookups={})  # nothing matches
    geo.enrich([_l("a", county="Nowhere")])
    raw = json.loads(cache.read_text())
    assert raw == {"Nowhere, MO, USA": None}
