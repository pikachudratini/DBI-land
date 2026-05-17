import json

from dbi_land.gis import WaterProximity, score_water_proximity
from dbi_land.models import Listing


def _flowline_geojson(coords: list[list[float]], fcode: int = 46006) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"FCODE": fcode},
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        ],
    }


def _spring_geojson(lon: float, lat: float, fcode: int = 45800) -> dict:
    # 45800 is a generic NHD spring/seep code class
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"FCODE": fcode},
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        ],
    }


def _write(tmp_path, data, name="water.geojson") -> str:
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return str(p)


def test_listing_on_creek_is_ideal(tmp_path):
    path = _write(tmp_path, _flowline_geojson([[-92.001, 37.0], [-91.999, 37.0]]))
    wp = WaterProximity.from_geojson(path, ideal_m=200, max_m=3000)
    score, distance = wp.score(37.0, -92.0)
    assert score == 1.0
    assert distance < 5


def test_listing_far_from_water_fails(tmp_path):
    path = _write(tmp_path, _flowline_geojson([[-104.8, 42.10], [-104.7, 42.10]]))
    wp = WaterProximity.from_geojson(path, ideal_m=200, max_m=3000)
    score, _ = wp.score(37.0, -92.0)
    assert score == 0.0


def test_intermittent_streams_filtered_out_by_default(tmp_path):
    path = _write(
        tmp_path,
        _flowline_geojson([[-92.001, 37.0], [-91.999, 37.0]], fcode=46003),
    )
    wp = WaterProximity.from_geojson(path)
    assert wp.features == []


def test_intermittent_kept_when_fcode_allowed(tmp_path):
    path = _write(
        tmp_path,
        _flowline_geojson([[-92.001, 37.0], [-91.999, 37.0]], fcode=46003),
    )
    wp = WaterProximity.from_geojson(path, keep_fcodes=(46003,))
    assert len(wp.features) == 1


def test_score_water_proximity_writes_extras(tmp_path):
    path = _write(tmp_path, _flowline_geojson([[-92.001, 37.0], [-91.999, 37.0]]))
    wp = WaterProximity.from_geojson(path)
    listings = [
        Listing(
            listing_id="a",
            source="t",
            url="http://x",
            state="MO",
            county=None,
            acres=100.0,
            price_usd=300_000.0,
            lat=37.0,
            lon=-92.0,
        )
    ]
    [out] = score_water_proximity(listings, wp)
    assert out.extras["water_score"] == 1.0
    assert out.extras["water_distance_m"] is not None


def test_listing_in_ramp_zone(tmp_path):
    path = _write(tmp_path, _flowline_geojson([[-92.01, 37.0], [-91.99, 37.0]]))
    wp = WaterProximity.from_geojson(path, ideal_m=100, max_m=2000)
    # ~800m north of east-west creek
    score, distance = wp.score(37.0072, -92.0)
    assert 0.0 < score < 1.0
    assert 700 < distance < 900


def test_springs_kept_in_default_fcodes(tmp_path):
    path = _write(tmp_path, _spring_geojson(-92.0, 37.0))
    wp = WaterProximity.from_geojson(path)
    assert len(wp.features) == 1
    score, distance = wp.score(37.0, -92.0)
    assert score == 1.0
    assert distance < 5


def test_from_paths_merges_flowlines_and_springs(tmp_path):
    flow = _write(
        tmp_path,
        _flowline_geojson([[-110.0, 45.0], [-109.99, 45.0]]),  # far away
        name="flow.geojson",
    )
    springs = _write(tmp_path, _spring_geojson(-92.0, 37.0), name="springs.geojson")
    wp = WaterProximity.from_paths([flow, springs])
    assert len(wp.features) == 2
    # MO listing — only the spring is nearby
    score, _ = wp.score(37.0, -92.0)
    assert score == 1.0
