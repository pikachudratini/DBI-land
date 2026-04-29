from __future__ import annotations

import sys
from pathlib import Path

import click

from dbi_land.config import Criteria
from dbi_land.digest import write_digest
from dbi_land.email_sender import EmailConfig, send_digest
from dbi_land.gis import PowerProximity, score_power_proximity
from dbi_land.score import score_listings
from dbi_land.sources import CsvSource, ImapConfig, ImapSource
from dbi_land.storage import ListingStore


@click.group()
def main() -> None:
    """DBI Land — farmland prospecting pipeline."""


def _load_digested(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def _append_digested(path: Path, keys: list[str]) -> None:
    if not keys:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for k in keys:
            f.write(k + "\n")


@main.command()
@click.option("--criteria", "criteria_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--csv", "csv_paths", multiple=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--store", "store_path", default=None,
              type=click.Path(dir_okay=False),
              help="JSONL listing store; loaded for scoring if --csv not provided.")
@click.option("--new-only/--all-known", default=False,
              help="Only score listings not yet shown in a previous digest.")
@click.option("--digested", "digested_path", default="data/digested.txt", show_default=True,
              type=click.Path(dir_okay=False))
@click.option("--out", "out_path", default="out/digest.html", show_default=True,
              type=click.Path(dir_okay=False))
@click.option("--passing/--include-failing", default=True)
@click.option("--power-geojson", default=None, type=click.Path(exists=True, dir_okay=False),
              help="Optional HIFLD-style transmission-line GeoJSON; enables the power score.")
def run(
    criteria_path: str,
    csv_paths: tuple[str, ...],
    store_path: str | None,
    new_only: bool,
    digested_path: str,
    out_path: str,
    passing: bool,
    power_geojson: str | None,
) -> None:
    """Score listings (from --csv or --store) and write the HTML digest."""
    criteria = Criteria.from_yaml(criteria_path)
    listings = []
    for p in csv_paths:
        listings.extend(CsvSource(p).fetch())
    if store_path:
        listings.extend(ListingStore(store_path).all_listings())
    if not listings:
        click.echo("No listings to score (provide --csv or --store).", err=True)
        sys.exit(2)

    digested_file = Path(digested_path)
    if new_only:
        already = _load_digested(digested_file)
        before = len(listings)
        listings = [l for l in listings if f"{l.source}:{l.listing_id}" not in already]
        click.echo(f"--new-only: filtered {before - len(listings)} previously-digested listing(s).")

    if power_geojson:
        pp = PowerProximity.from_geojson(power_geojson)
        listings = score_power_proximity(listings, pp)

    click.echo(f"Scoring {len(listings)} listing(s).")
    scored = score_listings(listings, criteria, only_passing=passing)
    out = write_digest(scored, out_path)
    click.echo(f"Wrote {len(scored)} ranked listing(s) -> {out}")

    _append_digested(
        digested_file,
        [f"{s.listing.source}:{s.listing.listing_id}" for s in scored],
    )


@main.command("ingest-imap")
@click.option("--store", "store_path", default="data/listings.jsonl", show_default=True,
              type=click.Path(dir_okay=False))
def ingest_imap(store_path: str) -> None:
    """Pull alert emails via IMAP and append new listings to the store."""
    cfg = ImapConfig.from_env()
    src = ImapSource(cfg)
    store = ListingStore(store_path)
    new = store.upsert(src.fetch())
    click.echo(f"Ingested {len(new)} new listing(s) -> {store_path}")


@main.command("ingest-csv")
@click.option("--store", "store_path", default="data/listings.jsonl", show_default=True,
              type=click.Path(dir_okay=False))
@click.argument("csv_paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def ingest_csv(store_path: str, csv_paths: tuple[str, ...]) -> None:
    """Append listings from one or more CSV files into the JSONL store."""
    if not csv_paths:
        click.echo("Provide at least one CSV path.", err=True)
        sys.exit(2)
    store = ListingStore(store_path)
    total = 0
    for p in csv_paths:
        new = store.upsert(CsvSource(p).fetch())
        click.echo(f"  {p}: +{len(new)} new")
        total += len(new)
    click.echo(f"Ingested {total} new listing(s) -> {store_path}")


@main.command()
@click.option("--html", "html_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--subject", default="Daily land digest")
@click.option("--dry-run/--send", default=False,
              help="Print the payload instead of calling Resend.")
def send(html_path: str, subject: str, dry_run: bool) -> None:
    """Send a rendered digest HTML via Resend."""
    if dry_run:
        click.echo(f"[dry-run] would send {html_path} as '{subject}'")
        return
    cfg = EmailConfig.from_env()
    html = Path(html_path).read_text(encoding="utf-8")
    result = send_digest(cfg, subject=subject, html=html)
    click.echo(f"Resend status: {result.get('status')}")


@main.command("show-criteria")
@click.option("--criteria", "criteria_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
def show_criteria(criteria_path: str) -> None:
    """Print the loaded criteria for sanity-check."""
    c = Criteria.from_yaml(criteria_path)
    click.echo(f"States: {', '.join(c.states)}")
    for b in c.acreage_bands:
        click.echo(f"Band: {b.min_acres}-{b.max_acres} ac (weight {b.weight})")
    click.echo(
        f"Price cap: ${c.price.max_price_per_acre:,.0f}/ac, "
        f"${c.price.max_total_price:,.0f} total"
    )
    click.echo(f"Weights: {c.weights}")


if __name__ == "__main__":
    main()
