"""Static-HTML history dashboard: every tracked listing with client-side filters."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, select_autoescape

from dbi_land.config import Criteria
from dbi_land.models import ListingScore
from dbi_land.score import score_listings
from dbi_land.storage import ListingStore

_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>DBI Land — history</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; max-width: 1100px; margin: 1em auto; padding: 0 1em; color: #222; }
h1 { font-size: 1.4em; margin-bottom: 0.2em; }
.meta { color: #666; font-size: 0.9em; }
.controls { margin: 1em 0; padding: 0.7em; background: #f7f7f5; border-radius: 6px; }
.controls label { display: inline-block; margin-right: 1em; font-size: 0.9em; }
.controls input, .controls select { font: inherit; padding: 2px 4px; }
table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }
th { background: #fafafa; cursor: pointer; user-select: none; }
tr.fail { color: #999; }
tr.pass td:first-child { border-left: 3px solid #2a6f2a; }
.score { font-weight: bold; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 10px; font-size: 0.8em; background: #e8f4ff; color: #04527c; margin-right: 4px; }
.tag.fail { background: #fde6e6; color: #802; }
a { color: #1a5; text-decoration: none; }
.empty { color: #888; font-style: italic; }
</style></head><body>
<h1>DBI Land — history</h1>
<div class="meta">{{ generated }} &middot; {{ scored|length }} listing(s) tracked</div>

<div class="controls">
  <label>State: <input id="f-state" type="text" size="6" placeholder="MO,IA"></label>
  <label>Min acres: <input id="f-min-acres" type="number" min="0" step="10" size="5"></label>
  <label>Max $/ac: <input id="f-max-ppa" type="number" min="0" step="500" size="6"></label>
  <label>Status:
    <select id="f-status">
      <option value="all">all</option>
      <option value="pass" selected>passing</option>
      <option value="fail">failing</option>
    </select>
  </label>
  <span id="visible-count" style="float:right; color:#666;"></span>
</div>

<table id="listings">
<thead><tr>
<th data-key="total">Score</th>
<th data-key="state">State</th>
<th data-key="county">County</th>
<th data-key="acres">Acres</th>
<th data-key="price">Price</th>
<th data-key="ppa">$/ac</th>
<th data-key="source">Source</th>
<th data-key="title">Listing</th>
<th>Criteria</th>
</tr></thead>
<tbody>
{% for s in scored %}
<tr class="{{ 'pass' if s.passes else 'fail' }}"
    data-state="{{ s.listing.state }}"
    data-acres="{{ s.listing.acres }}"
    data-ppa="{{ s.listing.price_per_acre|round(0)|int }}"
    data-status="{{ 'pass' if s.passes else 'fail' }}"
    data-total="{{ '%.4f'|format(s.total) }}">
  <td class="score">{{ "%.2f"|format(s.total) }}</td>
  <td>{{ s.listing.state }}</td>
  <td>{{ s.listing.county or '' }}</td>
  <td>{{ "%.1f"|format(s.listing.acres) }}</td>
  <td>${{ "{:,.0f}".format(s.listing.price_usd) }}</td>
  <td>${{ "{:,.0f}".format(s.listing.price_per_acre) }}</td>
  <td>{{ s.listing.source }}</td>
  <td><a href="{{ s.listing.url }}">{{ s.listing.title or s.listing.listing_id }}</a></td>
  <td>
    {% for c in s.criteria %}
      <span class="tag {{ 'fail' if c.score == 0 else '' }}" title="{{ c.detail }}">{{ c.name }} {{ "%.2f"|format(c.score) }}</span>
    {% endfor %}
  </td>
</tr>
{% endfor %}
</tbody>
</table>

{% if not scored %}<p class="empty">No listings in store yet.</p>{% endif %}

<script>
(function () {
  const tbody = document.querySelector('#listings tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const fState = document.getElementById('f-state');
  const fMinAcres = document.getElementById('f-min-acres');
  const fMaxPpa = document.getElementById('f-max-ppa');
  const fStatus = document.getElementById('f-status');
  const visible = document.getElementById('visible-count');

  function apply() {
    const states = fState.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    const minAcres = parseFloat(fMinAcres.value);
    const maxPpa = parseFloat(fMaxPpa.value);
    const status = fStatus.value;
    let shown = 0;
    rows.forEach(r => {
      const ok =
        (!states.length || states.includes(r.dataset.state))
        && (isNaN(minAcres) || parseFloat(r.dataset.acres) >= minAcres)
        && (isNaN(maxPpa) || parseFloat(r.dataset.ppa) <= maxPpa)
        && (status === 'all' || r.dataset.status === status);
      r.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    visible.textContent = `${shown} visible`;
  }

  [fState, fMinAcres, fMaxPpa, fStatus].forEach(el => el.addEventListener('input', apply));

  document.querySelectorAll('th[data-key]').forEach(th => {
    let asc = false;
    th.addEventListener('click', () => {
      asc = !asc;
      const key = th.dataset.key;
      const sign = asc ? 1 : -1;
      const sorted = rows.slice().sort((a, b) => {
        const av = parseFloat(a.dataset[key]);
        const bv = parseFloat(b.dataset[key]);
        if (!isNaN(av) && !isNaN(bv)) return sign * (av - bv);
        return sign * String(a.dataset[key] || '').localeCompare(String(b.dataset[key] || ''));
      });
      sorted.forEach(r => tbody.appendChild(r));
    });
  });

  apply();
})();
</script>
</body></html>
"""


def render_dashboard(scored: Sequence[ListingScore]) -> str:
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_TEMPLATE)
    return template.render(scored=list(scored), generated=date.today().isoformat())


def write_dashboard(
    store_path: str | Path,
    criteria_path: str | Path,
    out_path: str | Path,
) -> Path:
    criteria = Criteria.from_yaml(criteria_path)
    listings = ListingStore(store_path).all_listings()
    scored = score_listings(listings, criteria, only_passing=False)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_dashboard(scored), encoding="utf-8")
    return out
