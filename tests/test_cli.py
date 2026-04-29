"""Smoke tests for CLI subcommands using click's test runner."""
from pathlib import Path

from click.testing import CliRunner

from dbi_land.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_show_criteria_runs():
    result = CliRunner().invoke(
        main, ["show-criteria", "--criteria", str(EXAMPLES / "criteria.yaml")]
    )
    assert result.exit_code == 0
    assert "States:" in result.output


def test_run_against_csv(tmp_path):
    runner = CliRunner()
    out = tmp_path / "out" / "digest.html"
    digested = tmp_path / "data" / "digested.txt"
    result = runner.invoke(
        main,
        [
            "run",
            "--criteria", str(EXAMPLES / "criteria.yaml"),
            "--csv", str(EXAMPLES / "sample_listings.csv"),
            "--out", str(out),
            "--digested", str(digested),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Wrote " in result.output
    assert out.exists()
    assert digested.exists()


def test_ingest_csv_then_run_new_only_filters(tmp_path):
    runner = CliRunner()
    store = tmp_path / "data" / "listings.jsonl"
    digested = tmp_path / "data" / "digested.txt"
    out = tmp_path / "out" / "digest.html"

    r1 = runner.invoke(
        main,
        ["ingest-csv", "--store", str(store), str(EXAMPLES / "sample_listings.csv")],
    )
    assert r1.exit_code == 0, r1.output
    assert "Ingested 7 new" in r1.output

    r2 = runner.invoke(
        main,
        [
            "run",
            "--criteria", str(EXAMPLES / "criteria.yaml"),
            "--store", str(store),
            "--new-only",
            "--out", str(out),
            "--digested", str(digested),
        ],
    )
    assert r2.exit_code == 0, r2.output
    assert "Wrote 4 ranked" in r2.output

    r3 = runner.invoke(
        main,
        [
            "run",
            "--criteria", str(EXAMPLES / "criteria.yaml"),
            "--store", str(store),
            "--new-only",
            "--out", str(out),
            "--digested", str(digested),
        ],
    )
    assert r3.exit_code == 0, r3.output
    # All passing listings were already digested in r2.
    assert "filtered 4" in r3.output
    assert "Wrote 0 ranked" in r3.output


def test_send_dry_run(tmp_path):
    html = tmp_path / "digest.html"
    html.write_text("<p>x</p>")
    result = CliRunner().invoke(main, ["send", "--html", str(html), "--dry-run"])
    assert result.exit_code == 0
    assert "would send" in result.output


def test_dashboard(tmp_path):
    runner = CliRunner()
    store = tmp_path / "data" / "listings.jsonl"
    out = tmp_path / "site" / "index.html"
    runner.invoke(
        main,
        ["ingest-csv", "--store", str(store), str(EXAMPLES / "sample_listings.csv")],
    )
    result = runner.invoke(
        main,
        [
            "dashboard",
            "--criteria", str(EXAMPLES / "criteria.yaml"),
            "--store", str(store),
            "--out", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    html = out.read_text()
    assert "DBI Land" in html
    assert 'data-state="MO"' in html
    assert 'data-state="WY"' in html  # all listings shown, not just passing
