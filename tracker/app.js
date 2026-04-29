(function () {
  "use strict";

  const GATE_KEYS = [
    "G1_acreage_1000plus",
    "G2_entrance_north_or_east",
    "G3_no_major_highway",
    "G4_no_easements",
    "G5_full_mineral_rights",
    "G6_no_zoning_hoa_restrictions",
    "G7_no_hv_power_lines",
    "G8_organic_capable_soil",
    "G9_year_round_springs_on_parcel"
  ];

  const GATE_LABELS = {
    G1_acreage_1000plus: "G1 ≥ 1,000 acres",
    G2_entrance_north_or_east: "G2 Entrance N/E",
    G3_no_major_highway: "G3 No major highway",
    G4_no_easements: "G4 No easements",
    G5_full_mineral_rights: "G5 Mineral rights",
    G6_no_zoning_hoa_restrictions: "G6 No zoning/HOA",
    G7_no_hv_power_lines: "G7 No HV power lines",
    G8_organic_capable_soil: "G8 Organic-capable soil",
    G9_year_round_springs_on_parcel: "G9 Year-round springs"
  };

  const REGION_LABELS = {
    "ozarks": "Ozarks",
    "cumberland": "Cumberland Plateau",
    "ouachita": "Ouachitas",
    "west-virginia": "West Virginia",
    "north-florida": "North Florida",
    "other": "Other"
  };

  const STATUS_ICON = { pass: "✓", fail: "✗", unknown: "?" };

  function deriveStatus(c) {
    let pass = 0, fail = 0, unknown = 0;
    for (const k of GATE_KEYS) {
      const g = c.gates && c.gates[k];
      const s = g ? g.status : "unknown";
      if (s === "pass") pass++;
      else if (s === "fail") fail++;
      else unknown++;
    }
    let status;
    if (fail > 0) status = "disqualified";
    else if (unknown === 0) status = "qualified";
    else status = "contender";
    return { pass, fail, unknown, status };
  }

  function fmtPrice(n) {
    if (n == null || isNaN(n)) return "—";
    if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
    if (n >= 1_000) return "$" + Math.round(n / 1_000) + "k";
    return "$" + n;
  }

  function fmtNum(n) {
    if (n == null || isNaN(n)) return "—";
    return n.toLocaleString();
  }

  let state = {
    sortKey: "passed",
    sortDir: "desc",
    selectedId: null,
    filters: { region: "", minAcres: null, maxPrice: null, status: "" }
  };

  function getRows() {
    const all = (window.CANDIDATES || []).map(c => {
      const d = deriveStatus(c);
      return Object.assign({}, c, {
        passed: d.pass,
        failed: d.fail,
        unknown_count: d.unknown,
        status: d.status
      });
    });

    const f = state.filters;
    return all.filter(c => {
      if (f.region && c.region !== f.region) return false;
      if (f.minAcres != null && (c.acres || 0) < f.minAcres) return false;
      if (f.maxPrice != null && (c.asking_price_usd || 0) > f.maxPrice) return false;
      if (f.status && c.status !== f.status) return false;
      return true;
    });
  }

  function compare(a, b, key, dir) {
    let av = a[key], bv = b[key];
    if (key === "county") { av = (a.county || "") + ", " + (a.state || ""); bv = (b.county || "") + ", " + (b.state || ""); }
    if (typeof av === "string" || typeof bv === "string") {
      av = (av || "").toString().toLowerCase();
      bv = (bv || "").toString().toLowerCase();
      return dir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    av = av == null ? -Infinity : av;
    bv = bv == null ? -Infinity : bv;
    return dir === "asc" ? av - bv : bv - av;
  }

  function render() {
    const rows = getRows().sort((a, b) => compare(a, b, state.sortKey, state.sortDir));

    document.querySelectorAll("th[data-sort]").forEach(th => {
      th.classList.remove("sorted-asc", "sorted-desc");
      if (th.dataset.sort === state.sortKey) {
        th.classList.add(state.sortDir === "asc" ? "sorted-asc" : "sorted-desc");
      }
    });

    const tbody = document.getElementById("rows");
    tbody.innerHTML = "";
    if (rows.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="8" class="empty">No candidates match the current filters.</td>';
      tbody.appendChild(tr);
    } else {
      for (const c of rows) {
        const tr = document.createElement("tr");
        tr.dataset.id = c.id;
        if (c.id === state.selectedId) tr.classList.add("selected");
        tr.innerHTML = [
          td(c.name || c.id),
          td(REGION_LABELS[c.region] || c.region || "—"),
          td(((c.county || "") + ", " + (c.state || "")).replace(/^, |, $/, "") || "—"),
          tdNum(fmtNum(c.acres)),
          tdNum(fmtPrice(c.asking_price_usd)),
          tdNum(fmtPrice(c.price_per_acre_usd)),
          td(c.passed + " / 9" + (c.failed ? " (" + c.failed + " fail)" : "")),
          '<td class="status-' + c.status + '">' + statusLabel(c.status) + '</td>'
        ].join("");
        tr.addEventListener("click", () => {
          state.selectedId = c.id;
          render();
          renderDetail(c);
        });
        tbody.appendChild(tr);
      }
    }

    renderSummary(rows);
  }

  function renderSummary(rows) {
    const total = (window.CANDIDATES || []).length;
    const shown = rows.length;
    const counts = { qualified: 0, contender: 0, disqualified: 0 };
    rows.forEach(r => counts[r.status]++);
    document.getElementById("summary").innerHTML =
      "<strong>" + shown + "</strong> of " + total + " candidates shown — " +
      '<span class="status-qualified">' + counts.qualified + " qualified</span>, " +
      '<span class="status-contender">' + counts.contender + " contender</span>, " +
      '<span class="status-disqualified">' + counts.disqualified + " disqualified</span>";
  }

  function renderDetail(c) {
    const el = document.getElementById("detail");
    el.hidden = false;
    const meta = [
      REGION_LABELS[c.region] || c.region,
      ((c.county || "") + ", " + (c.state || "")).replace(/^, |, $/, ""),
      fmtNum(c.acres) + " ac",
      fmtPrice(c.asking_price_usd),
      fmtPrice(c.price_per_acre_usd) + "/ac"
    ].filter(Boolean).join(" · ");

    const gateHtml = GATE_KEYS.map(k => {
      const g = (c.gates && c.gates[k]) || { status: "unknown", source: "" };
      const cls = "gate-" + g.status;
      return '<div class="gate-row">' +
        '<span class="icon ' + cls + '">' + STATUS_ICON[g.status] + '</span>' +
        '<span class="label">' + GATE_LABELS[k] + '</span>' +
        (g.source ? '<span class="source">' + escapeHtml(g.source) + "</span>" : "") +
        "</div>";
    }).join("");

    el.innerHTML =
      "<h2>" + escapeHtml(c.name || c.id) + "</h2>" +
      '<div class="meta">' + escapeHtml(meta) +
      (c.listing_url ? ' · <a href="' + encodeURI(c.listing_url) + '" target="_blank" rel="noopener">listing</a>' : "") +
      (c.broker ? " · broker: " + escapeHtml(c.broker) : "") +
      "</div>" +
      '<div class="gates-grid">' + gateHtml + "</div>" +
      (c.notes ? "<p>" + escapeHtml(c.notes) + "</p>" : "");
  }

  function td(text) { return "<td>" + escapeHtml(String(text)) + "</td>"; }
  function tdNum(text) { return '<td class="num">' + escapeHtml(String(text)) + "</td>"; }
  function statusLabel(s) {
    return s === "qualified" ? "Qualified" : s === "contender" ? "Contender" : "Disqualified";
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function attachEvents() {
    document.querySelectorAll("th[data-sort]").forEach(th => {
      th.addEventListener("click", () => {
        const k = th.dataset.sort;
        if (state.sortKey === k) {
          state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        } else {
          state.sortKey = k;
          state.sortDir = (k === "name" || k === "region" || k === "county" || k === "status") ? "asc" : "desc";
        }
        render();
      });
    });

    document.getElementById("filter-region").addEventListener("change", e => {
      state.filters.region = e.target.value;
      render();
    });
    document.getElementById("filter-min-acres").addEventListener("input", e => {
      const v = parseInt(e.target.value, 10);
      state.filters.minAcres = isNaN(v) ? null : v;
      render();
    });
    document.getElementById("filter-max-price").addEventListener("input", e => {
      const v = parseInt(e.target.value, 10);
      state.filters.maxPrice = isNaN(v) ? null : v;
      render();
    });
    document.getElementById("filter-status").addEventListener("change", e => {
      state.filters.status = e.target.value;
      render();
    });
    document.getElementById("reset-filters").addEventListener("click", () => {
      state.filters = { region: "", minAcres: null, maxPrice: null, status: "" };
      document.getElementById("filter-region").value = "";
      document.getElementById("filter-min-acres").value = "";
      document.getElementById("filter-max-price").value = "";
      document.getElementById("filter-status").value = "";
      render();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    attachEvents();
    render();
  });
})();
