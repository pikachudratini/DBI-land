import json

from dbi_land.gis import PowerProximity, score_power_proximity
from dbi_land.models import Listing


def _line_geojson(coords: list[list[float]], voltage: float = 230.0) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"VOLTAGE": voltage},
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        ],
    }


def _write(tmp_path, data) -> str:
    p = tmp_path / "lines.geojson"
    p.write_text(json.dumps(data))
    return str(p)


def test_far_listing_scores_one(tmp_path):
    # Line in Wyoming, listing in Missouri — no nearby line.
    path = _write(tmp_path, _line_geojson([[-104.8, 42.10], [-104.7, 42.10]]))
    pp = PowerProximity.from_geojson(path)
    score, distance = pp.score(37.0, -92.0)
    assert score == 1.0


def test_listing_on_line_scores_zero(tmp_path):
    path = _write(tmp_path, _line_geojson([[-92.001, 37.0], [-91.999, 37.0]]))
    pp = PowerProximity.from_geojson(path, min_setback_m=100, comfort_m=1500)
    score, _ = pp.score(37.0, -92.0)
    assert score == 0.0


def test_listing_in_ramp_zone(tmp_path):
    # Place listing ~800m north of an east-west line; ramp midpoint range.
    path = _write(tmp_path, _line_geojson([[-92.01, 37.0], [-91.99, 37.0]]))
    pp = PowerProximity.from_geojson(path, min_setback_m=100, comfort_m=1500)
    # 800m at MO latitude is ~0.0072 degrees of latitude
    score, distance = pp.score(37.0072, -92.0)
    assert 0.05 < score < 1.0
    assert 700 < distance < 900


def test_low_voltage_lines_filtered_out(tmp_path):
    path = _write(
        tmp_path,
        _line_geojson([[-92.001, 37.0], [-91.999, 37.0]], voltage=12.0),
    )
    pp = PowerProximity.from_geojson(path, min_voltage_kv=69.0)
    # The single low-voltage line was filtered, so no features remain.
    assert pp.features == []
    score, _ = pp.score(37.0, -92.0)
    assert score == 1.0


def test_score_power_proximity_writes_extras(tmp_path):
    path = _write(tmp_path, _line_geojson([[-92.001, 37.0], [-91.999, 37.0]]))
    pp = PowerProximity.from_geojson(path)
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
    [out] = score_power_proximity(listings, pp)
    assert out.extras["power_proximity_score"] == 0.0
    assert out.extras["power_distance_m"] is not None
