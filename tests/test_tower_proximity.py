import json

from dbi_land.gis import TowerProximity, score_tower_proximity
from dbi_land.models import Listing


def _point_geojson(lon: float, lat: float, status: str = "C") -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"STATUS": status},
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        ],
    }


def _write(tmp_path, data) -> str:
    p = tmp_path / "towers.geojson"
    p.write_text(json.dumps(data))
    return str(p)


def test_listing_on_top_of_tower_scores_zero(tmp_path):
    path = _write(tmp_path, _point_geojson(-92.0, 37.0))
    tp = TowerProximity.from_geojson(path, min_setback_m=400, comfort_m=3000)
    score, distance = tp.score(37.0, -92.0)
    assert score == 0.0
    assert distance < 5


def test_far_listing_scores_one(tmp_path):
    path = _write(tmp_path, _point_geojson(-104.8, 42.10))
    tp = TowerProximity.from_geojson(path)
    score, _ = tp.score(37.0, -92.0)
    assert score == 1.0


def test_listing_in_ramp_zone(tmp_path):
    path = _write(tmp_path, _point_geojson(-92.0, 37.0))
    tp = TowerProximity.from_geojson(path, min_setback_m=400, comfort_m=3000)
    # ~1500m north
    score, distance = tp.score(37.0135, -92.0)
    assert 0.05 < score < 1.0
    assert 1400 < distance < 1600


def test_proposed_towers_filtered_out_by_default(tmp_path):
    path = _write(tmp_path, _point_geojson(-92.0, 37.0, status="G"))  # "granted" not "constructed"
    tp = TowerProximity.from_geojson(path)
    assert tp.features == []
    score, _ = tp.score(37.0, -92.0)
    assert score == 1.0


def test_missing_status_kept(tmp_path):
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [-92.0, 37.0]},
            }
        ],
    }
    path = _write(tmp_path, data)
    tp = TowerProximity.from_geojson(path)
    assert len(tp.features) == 1


def test_score_tower_proximity_writes_extras(tmp_path):
    path = _write(tmp_path, _point_geojson(-92.0, 37.0))
    tp = TowerProximity.from_geojson(path)
    listings = [
        Listing(
            listing_id="a", source="t", url="http://x",
            state="MO", county=None,
            acres=300.0, price_usd=900_000.0,
            lat=37.0, lon=-92.0,
        ),
    ]
    [out] = score_tower_proximity(listings, tp)
    assert out.extras["tower_proximity_score"] == 0.0
    assert out.extras["tower_distance_m"] is not None


def test_from_fcc_asr_csv_loads_constructed_only(tmp_path):
    csv_path = tmp_path / "asr.csv"
    csv_path.write_text(
        "STATUS_CODE,LAT_DEG_TOTAL,LONG_DEG_TOTAL\n"
        "C,37.0,-92.0\n"
        "G,38.0,-91.0\n"
    )
    tp = TowerProximity.from_fcc_asr_csv(str(csv_path))
    assert len(tp.features) == 1
    score, _ = tp.score(37.0, -92.0)
    assert score == 0.0
