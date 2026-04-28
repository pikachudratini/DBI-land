from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, select_autoescape

from dbi_land.models import ListingScore

_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>DBI Land digest — {{ today }}</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; max-width: 780px; margin: 2em auto; color: #222; }
h1 { font-size: 1.4em; }
.listing { border: 1px solid #ddd; border-radius: 6px; padding: 1em; margin-bottom: 1em; }
.listing h2 { font-size: 1.1em; margin: 0 0 0.3em; }
.meta { color: #555; font-size: 0.9em; }
.score { float: right; font-weight: bold; color: #2a6f2a; }
.crit { font-size: 0.85em; color: #444; margin-top: 0.5em; }
.crit span { display: inline-block; margin-right: 0.8em; }
a { color: #1a5; text-decoration: none; }
.empty { color: #888; font-style: italic; }
</style></head><body>
<h1>DBI Land — {{ today }}</h1>
<p>{{ scored|length }} listing{{ '' if scored|length == 1 else 's' }} passed all criteria.</p>
{% if not scored %}
<p class="empty">No matches today.</p>
{% endif %}
{% for s in scored %}
<div class="listing">
  <span class="score">{{ "%.2f"|format(s.total) }}</span>
  <h2><a href="{{ s.listing.url }}">{{ s.listing.title or s.listing.listing_id }}</a></h2>
  <div class="meta">
    {{ s.listing.state }}{% if s.listing.county %}, {{ s.listing.county }}{% endif %}
    &middot; {{ "%.1f"|format(s.listing.acres) }} ac
    &middot; ${{ "{:,.0f}".format(s.listing.price_usd) }}
    &middot; ${{ "{:,.0f}".format(s.listing.price_per_acre) }}/ac
    &middot; <em>{{ s.listing.source }}</em>
  </div>
  <div class="crit">
    {% for c in s.criteria %}
      <span><b>{{ c.name }}</b>: {{ "%.2f"|format(c.score) }} — {{ c.detail }}</span>
    {% endfor %}
  </div>
</div>
{% endfor %}
</body></html>
"""


def render_digest(scored: Sequence[ListingScore], *, today: date | None = None) -> str:
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_TEMPLATE)
    return template.render(scored=list(scored), today=(today or date.today()).isoformat())


def write_digest(scored: Sequence[ListingScore], path: str | Path, *, today: date | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_digest(scored, today=today), encoding="utf-8")
    return out
