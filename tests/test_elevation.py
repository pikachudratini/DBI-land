import json

from dbi_land.elevation import ElevationEnricher
from dbi_land.models import Listing


class _FakeElevation(ElevationEnricher):
    """Stub the network call so tests don't hit USGS."""

    def __init__(self, cache_path, lookups):
        super().__init__(cache_path=cache_path)
        self._lookups = lookups
        self._call_count = 0

    def _query(self, lat: float, lon: float):
        self._call_count += 1
        return self._lookups.get((round(lat, 5), round(lon, 5)))


def _l(listing_id: str, lat=37.0, lon=-92.0, extras=None) -> Listing:
    return Listing(
        listing_id=listing_id,
        source="t",
        url=f"http://x/{listing_id}",
        state="MO",
        county=None,
        acres=300.0,
        price_usd=900_000.0,
        lat=lat,
        lon=lon,
        extras=extras or {},
    )


def test_enrich_writes_elevation_to_extras(tmp_path):
    enr = _FakeElevation(
        cache_path=tmp_path / "cache.json",
        lookups={(37.0, -92.0): 354.7},
    )
    [out] = enr.enrich([_l("a")])
    assert out.extras["elevation_m"] == 354.7


def test_enrich_skips_listings_without_coordinates(tmp_path):
    enr = _FakeElevation(cache_path=tmp_path / "cache.json", lookups={})
    [out] = enr.enrich([_l("a", lat=None, lon=None)])
    assert "elevation_m" not in out.extras
    assert enr._call_count == 0


def test_enrich_skips_already_enriched(tmp_path):
    enr = _FakeElevation(cache_path=tmp_path / "cache.json", lookups={})
    [out] = enr.enrich([_l("a", extras={"elevation_m": 500.0})])
    assert out.extras["elevation_m"] == 500.0
    assert enr._call_count == 0


def test_cache_persists_across_instances(tmp_path):
    cache = tmp_path / "cache.json"
    e1 = _FakeElevation(cache_path=cache, lookups={(37.0, -92.0): 354.7})
    e1.enrich([_l("a")])
    assert e1._call_count == 1
    e2 = _FakeElevation(cache_path=cache, lookups={})
    [out] = e2.enrich([_l("b")])  # same coords
    assert out.extras["elevation_m"] == 354.7
    assert e2._call_count == 0


def test_nodata_sentinel_treated_as_missing(tmp_path):
    enr = _FakeElevation(
        cache_path=tmp_path / "cache.json",
        lookups={(37.0, -92.0): None},  # _query returned None for sentinel
    )
    [out] = enr.enrich([_l("a")])
    assert "elevation_m" not in out.extras


def test_real_query_parses_nodata_sentinel(tmp_path, monkeypatch):
    """Direct _query test: EPQS returns -1000000 for out-of-coverage points."""
    enr = ElevationEnricher(cache_path=tmp_path / "cache.json")

    class _Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return self.body

    def _fake_urlopen(req, timeout):
        return _Resp(json.dumps({"value": "-1000000"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    assert enr._query(0.0, 0.0) is None


def test_real_query_parses_value(tmp_path, monkeypatch):
    enr = ElevationEnricher(cache_path=tmp_path / "cache.json")

    class _Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return self.body

    def _fake_urlopen(req, timeout):
        return _Resp(json.dumps({"value": "354.7"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    assert enr._query(37.0, -92.0) == 354.7
