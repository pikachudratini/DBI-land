from dbi_land.sources import CsvSource


def test_csv_source_loads_all_rows(sample_csv_path):
    listings = list(CsvSource(sample_csv_path).fetch())
    assert len(listings) == 7
    first = listings[0]
    assert first.state == "MO"
    assert first.acres == 120
    assert first.price_usd == 420000
    assert abs(first.price_per_acre - 3500) < 0.01


def test_csv_source_skips_rows_with_missing_numeric(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(
        "listing_id,url,state,acres,price_usd\n"
        "a,http://x,MO,,100000\n"
        "b,http://y,MO,40,200000\n",
        encoding="utf-8",
    )
    listings = list(CsvSource(p).fetch())
    assert [l.listing_id for l in listings] == ["b"]


def test_csv_source_rejects_missing_required_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("listing_id,url\nx,http://y\n", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError):
        list(CsvSource(p).fetch())
