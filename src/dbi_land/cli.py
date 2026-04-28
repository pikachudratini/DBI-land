from __future__ import annotations

import sys
from pathlib import Path

import click

from dbi_land.config import Criteria
from dbi_land.digest import write_digest
from dbi_land.score import score_listings
from dbi_land.sources import CsvSource


@click.group()
def main() -> None:
    """DBI Land — farmland prospecting pipeline."""


@main.command()
@click.option("--criteria", "criteria_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--csv", "csv_paths", multiple=True, type=click.Path(exists=True, dir_okay=False),
              help="One or more CSV files of listings to ingest.")
@click.option("--out", "out_path", default="out/digest.html", show_default=True,
              type=click.Path(dir_okay=False))
@click.option("--all/--passing-only", default=False,
              help="Include listings that fail one or more criteria.")
def run(criteria_path: str, csv_paths: tuple[str, ...], out_path: str, all: bool) -> None:
    """Ingest listings, score them, and write an HTML digest."""
    if not csv_paths:
        click.echo("No --csv inputs provided.", err=True)
        sys.exit(2)
    criteria = Criteria.from_yaml(criteria_path)
    listings = []
    for p in csv_paths:
        listings.extend(CsvSource(p).fetch())
    click.echo(f"Loaded {len(listings)} listings from {len(csv_paths)} file(s).")
    scored = score_listings(listings, criteria, only_passing=not all)
    out = write_digest(scored, out_path)
    click.echo(f"Wrote {len(scored)} ranked listing(s) -> {out}")


@main.command()
@click.option("--criteria", "criteria_path", required=True, type=click.Path(exists=True, dir_okay=False))
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
