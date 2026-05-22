from __future__ import annotations

import sys
from pathlib import Path

import click

from dbi_land.config import Criteria
from dbi_land.dashboard import write_dashboard
from dbi_land.dedupe import dedupe_cross_source
from dbi_land.digest import write_digest
from dbi_land.elevation import ElevationEnricher
from dbi_land.email_sender import EmailConfig, send_digest
from dbi_land.freshness import LastSeenIndex
from dbi_land.geocode import Geocoder
from dbi_land.gis import (
    PowerProximity,
    TowerProximity,
    WaterProximity,
    score_power_proximity,
    score_tower_proximity,
    score_water_proximity,
)
from dbi_land.score import score_listings
from dbi_land.sources import (
    CsvSource,
    ImapConfig,
    ImapSource,
    LandSearchScraper,
    LandSearchScraperConfig,
    LandWatchScraper,
    LandWatchScraperConfig,
    LandAndFarmScraper,
    LandAndFarmScraperConfig,
)
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
@click.option("--dedupe/--no-dedupe", default=True,
              help="Collapse cross-source duplicates (same state/county/acres/price).")
@click.option("--max-stale-days", default=14, show_default=True, type=int,
              help="Drop listings not re-confirmed by a scrape within this window. "
                   "Set to 0 to disable freshness filtering.")
@click.option("--last-seen", "last_seen_path", default="data/last_seen.json",
              show_default=True, type=click.Path(dir_okay=False),
              help="Path to the LastSeenIndex JSON file written by scrape-* commands.")
@click.option("--power-geojson", default=None, type=click.Path(exists=True, dir_okay=False),
              help="Optional HIFLD-style transmission-line GeoJSON; enables the power score.")
@click.option("--tower-geojson", default=None, type=click.Path(exists=True, dir_okay=False),
              help="Optional FCC-ASR-style cell tower Point GeoJSON; enables the tower score.")
@click.option("--water-geojson", "water_geojsons", multiple=True,
              type=click.Path(exists=True, dir_okay=False),
              help="NHD GeoJSON (flowline and/or point/spring); pass multiple times to merge.")
@click.option("--geocode/--no-geocode", default=False,
              help="Geocode listings missing lat/lon via Nominatim.")
@click.option("--elevation/--no-elevation", "elevation", default=False,
              help="Enrich listings with USGS 3DEP ground elevation (meters).")
@click.option("--enrich-passing-only/--enrich-before-scoring", default=False,
              help="Run --geocode/--elevation AFTER scoring on the passing set only. "
                   "Much faster when most listings will fail other criteria.")
def run(
    criteria_path: str,
    csv_paths: tuple[str, ...],
    store_path: str | None,
    new_only: bool,
    digested_path: str,
    out_path: str,
    passing: bool,
    dedupe: bool,
    max_stale_days: int,
    last_seen_path: str,
    power_geojson: str | None,
    tower_geojson: str | None,
    water_geojsons: tuple[str, ...],
    geocode: bool,
    elevation: bool,
    enrich_passing_only: bool,
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

    if dedupe:
        listings, dropped = dedupe_cross_source(listings)
        if dropped:
            click.echo(f"Dedupe: collapsed {dropped} cross-source duplicate(s).")

    if max_stale_days > 0:
        idx = LastSeenIndex(last_seen_path)
        before_freshness = len(listings)
        listings, stale = idx.filter_active(listings, max_stale_days=max_stale_days)
        click.echo(
            f"Freshness: dropped {stale} listing(s) not re-seen in last "
            f"{max_stale_days} day(s); {len(listings)} active of {before_freshness}."
        )

    digested_file = Path(digested_path)
    if new_only:
        already = _load_digested(digested_file)
        before = len(listings)
        listings = [l for l in listings if f"{l.source}:{l.listing_id}" not in already]
        click.echo(f"--new-only: filtered {before - len(listings)} previously-digested listing(s).")

    def _apply_enrichment(listings_in):
        out = listings_in
        if geocode:
            before = sum(1 for l in out if l.lat is None or l.lon is None)
            out = Geocoder().enrich(out)
            click.echo(f"Geocoded {before} listing(s) without coordinates.")
        if elevation:
            before = sum(
                1 for l in out
                if l.lat is not None and l.lon is not None and "elevation_m" not in l.extras
            )
            out = ElevationEnricher().enrich(out)
            click.echo(f"Looked up elevation for up to {before} listing(s).")
        if power_geojson:
            out = score_power_proximity(out, PowerProximity.from_geojson(power_geojson))
        if tower_geojson:
            out = score_tower_proximity(out, TowerProximity.from_geojson(tower_geojson))
        if water_geojsons:
            from dbi_land.gis.water import listings_to_bboxes
            boxes = listings_to_bboxes(out)
            if not boxes:
                click.echo("water: no listings have coords yet; skipping water scoring.")
            else:
                wp = WaterProximity.from_paths(water_geojsons, listing_bboxes=boxes)
                click.echo(f"water: bbox-filtered to {len(wp.features)} feature(s) "
                           f"near {len(boxes)} listing(s).")
                out = score_water_proximity(out, wp)
        return out

    if not enrich_passing_only:
        listings = _apply_enrichment(listings)

    click.echo(f"Scoring {len(listings)} listing(s).")
    scored = score_listings(listings, criteria, only_passing=passing)

    if enrich_passing_only and (geocode or elevation or power_geojson or tower_geojson or water_geojsons):
        enriched = _apply_enrichment([s.listing for s in scored])
        from dataclasses import replace as _replace
        by_key = {(l.source, l.listing_id): l for l in enriched}
        scored = [
            _replace(s, listing=by_key.get((s.listing.source, s.listing.listing_id), s.listing))
            for s in scored
        ]

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


@main.command("scrape-landsearch")
@click.option("--criteria", "criteria_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--store", "store_path", default="data/listings.jsonl", show_default=True,
              type=click.Path(dir_okay=False))
@click.option("--max-pages", default=3, show_default=True, type=int,
              help="Max LandSearch result pages to scrape per state.")
@click.option("--states", default=None,
              help="Comma-separated state codes to scrape; defaults to criteria.yaml states.")
def scrape_landsearch(
    criteria_path: str, store_path: str, max_pages: int, states: str | None,
) -> None:
    """Scrape LandSearch via headless Chromium and append listings to the store."""
    criteria = Criteria.from_yaml(criteria_path)
    state_codes = (
        [s.strip().upper() for s in states.split(",") if s.strip()]
        if states else list(criteria.states)
    )
    cfg = LandSearchScraperConfig(max_pages_per_state=max_pages)
    scraper = LandSearchScraper(state_codes, config=cfg)
    store = ListingStore(store_path)
    fetched = list(scraper.fetch())
    new = store.upsert(fetched)
    LastSeenIndex("data/last_seen.json").touch(fetched)
    click.echo(
        f"Scraped {len(state_codes)} state(s); +{len(new)} new, "
        f"{len(fetched)} confirmed active -> {store_path}"
    )


@main.command("scrape-landandfarm")
@click.option("--criteria", "criteria_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--store", "store_path", default="data/listings.jsonl", show_default=True,
              type=click.Path(dir_okay=False))
@click.option("--max-pages", default=5, show_default=True, type=int,
              help="Max Land and Farm result pages to scrape per state.")
@click.option("--min-acres", default=None, type=int,
              help="Acreage floor used in URL filter; defaults to smallest acreage band in criteria.")
@click.option("--states", default=None,
              help="Comma-separated state codes to scrape; defaults to criteria.yaml states.")
def scrape_landandfarm(
    criteria_path: str, store_path: str, max_pages: int,
    min_acres: int | None, states: str | None,
) -> None:
    """Scrape Land and Farm via headless Chromium with URL-level acreage filter."""
    criteria = Criteria.from_yaml(criteria_path)
    state_codes = (
        [s.strip().upper() for s in states.split(",") if s.strip()]
        if states else list(criteria.states)
    )
    if min_acres is None:
        min_acres = int(min(b.min_acres for b in criteria.acreage_bands))
    cfg = LandAndFarmScraperConfig(min_acres=min_acres, max_pages_per_state=max_pages)
    scraper = LandAndFarmScraper(state_codes, config=cfg)
    store = ListingStore(store_path)
    fetched = list(scraper.fetch())
    new = store.upsert(fetched)
    LastSeenIndex("data/last_seen.json").touch(fetched)
    click.echo(
        f"Scraped {len(state_codes)} state(s) (min {min_acres} ac); "
        f"+{len(new)} new, {len(fetched)} confirmed active -> {store_path}"
    )


@main.command("scrape-landwatch")
@click.option("--criteria", "criteria_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--store", "store_path", default="data/listings.jsonl", show_default=True,
              type=click.Path(dir_okay=False))
@click.option("--max-pages", default=5, show_default=True, type=int,
              help="Max LandWatch result pages to scrape per state.")
@click.option("--min-acres", default=None, type=int,
              help="Acreage floor used in LandWatch URL filter; defaults to smallest acreage band in criteria.")
@click.option("--states", default=None,
              help="Comma-separated state codes to scrape; defaults to criteria.yaml states.")
def scrape_landwatch(
    criteria_path: str, store_path: str, max_pages: int,
    min_acres: int | None, states: str | None,
) -> None:
    """Scrape LandWatch via headless Chromium with URL-level acreage filter."""
    criteria = Criteria.from_yaml(criteria_path)
    state_codes = (
        [s.strip().upper() for s in states.split(",") if s.strip()]
        if states else list(criteria.states)
    )
    if min_acres is None:
        min_acres = int(min(b.min_acres for b in criteria.acreage_bands))
    cfg = LandWatchScraperConfig(min_acres=min_acres, max_pages_per_state=max_pages)
    scraper = LandWatchScraper(state_codes, config=cfg)
    store = ListingStore(store_path)
    fetched = list(scraper.fetch())
    new = store.upsert(fetched)
    LastSeenIndex("data/last_seen.json").touch(fetched)
    click.echo(
        f"Scraped {len(state_codes)} state(s) (min {min_acres} ac); "
        f"+{len(new)} new, {len(fetched)} confirmed active -> {store_path}"
    )


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


@main.command()
@click.option("--criteria", "criteria_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--store", "store_path", default="data/listings.jsonl", show_default=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_path", default="site/index.html", show_default=True,
              type=click.Path(dir_okay=False))
def dashboard(criteria_path: str, store_path: str, out_path: str) -> None:
    """Render a static history dashboard with client-side filters."""
    out = write_dashboard(store_path, criteria_path, out_path)
    click.echo(f"Wrote dashboard -> {out}")


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
