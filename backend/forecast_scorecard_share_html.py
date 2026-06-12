"""Self-contained HTML for the public Forecast Scorecard live link.

Rendered in the Leonardo house Report Canvas: light body + dark navy hero
(dark mode toggle included), Cormorant Garamond display, DM Mono labels,
blue-only deltas with orange reserved for action-required figures. The page
auto-refreshes every 5 minutes so the link stays live through the week.
"""

from __future__ import annotations

import html as html_mod
from datetime import UTC, datetime
from typing import Any


def _esc(v: Any) -> str:
    return html_mod.escape(str(v if v is not None else ""))


def _usd(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "—"
    s = "+" if sign and v > 0 else "−" if v < 0 else ""
    return f"{s}${abs(v):,.0f}"


def _pct(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "—"
    s = "+" if sign and v > 0 else "−" if v < 0 else ""
    return f"{s}{abs(v) * 100:.1f}%"


def _delta(variance: dict[str, Any] | None) -> str:
    if not variance or (variance.get("dollars") is None and variance.get("pct") is None):
        return '<span class="muted">—</span>'
    d, p = variance.get("dollars"), variance.get("pct")
    txt = _usd(d, sign=True)
    if p is not None:
        txt += f" ({_pct(p, sign=True)})"
    return f'<span class="delta">{txt}</span>'

STATUS_LABELS = {
    "NOT_STARTED": "Not started",
    "DRAFT": "Forecast due",
    "SUBMITTED": "Awaiting targets (Ross)",
    "TARGETS_ISSUED": "Schedule due (TeamWork)",
    "APPROVAL_REQUESTED": "Awaiting approval (Ross)",
    "APPROVED": "Approved — publish",
    "PUBLISHED": "Published",
}

_CSS = """
:root{
  --canvas:#f7f8fc; --card:#ffffff; --card-alt:#f4f7fd;
  --border:#e2e8f4; --divider:#edf0f7;
  --text:#0f1b2d; --text-2:#4a5568; --text-3:#8a9ab0;
  --accent:#2563b0; --accent-bright:#4187d4; --alert:#ea580c;
  --hero:#0c1526; --hero-text:#e2eaf6; --hero-dim:#8aa5c4; --hero-faint:#4a6480;
}
.report.dark{
  --canvas:#0c1526; --card:#111d30; --card-alt:#162035;
  --border:#1e3050; --divider:#162035;
  --text:#e2eaf6; --text-2:#8aa5c4; --text-3:#4a6480;
  --accent:#4187d4; --alert:#fb923c;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--canvas);color:var(--text);font-family:'Inter','DM Sans',sans-serif;
  font-size:13.5px;line-height:1.6;transition:background .2s}
.wrap{max-width:1060px;margin:0 auto;padding:26px 22px 80px}
.hero{background:var(--hero);color:var(--hero-text);border-radius:14px;padding:34px 40px;position:relative;overflow:hidden}
.hero .edge{position:absolute;left:8px;top:40px;writing-mode:vertical-rl;
  font-family:'DM Mono',monospace;font-size:8px;letter-spacing:.3em;color:var(--hero-faint)}
.hero .crumb{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--accent-bright);margin-bottom:14px}
.hero h1{font-family:'Cormorant Garamond',Georgia,serif;font-weight:300;font-size:48px;line-height:1.0;letter-spacing:-.01em}
.hero h1 em{font-style:italic;font-weight:400;color:#7a9dc4}
.hero .lede{font-style:italic;color:rgba(255,255,255,.65);margin-top:12px;max-width:720px}
.hero .lede strong{color:rgba(255,255,255,.92)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
.meta-chip{border:1px solid rgba(226,234,246,.18);border-radius:5px;padding:5px 9px;
  font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--hero-dim)}
.toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:18px 0 30px;flex-wrap:wrap}
.weeknav{display:flex;gap:8px;align-items:center}
.weeknav a,.toolbar button{font-family:'DM Sans',sans-serif;font-weight:500;font-size:12px;
  height:28px;padding:0 10px;display:inline-flex;align-items:center;border:1px solid var(--border);
  border-radius:6px;background:var(--card);color:var(--text);text-decoration:none;cursor:pointer}
.weeknav .label{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3)}
section{margin-bottom:44px}
.eyebrow{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--accent-bright);margin-bottom:6px}
h2{font-family:'Cormorant Garamond',Georgia,serif;font-weight:300;font-size:28px;margin-bottom:6px}
h2 em{font-style:italic;color:#6d84ad}
.hint{font-size:12px;color:var(--text-2);max-width:760px;margin-bottom:14px}
.panel{background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.panel + .panel{margin-top:14px}
.panel-head{padding:14px 16px 6px}
.panel-head .ttl{font-family:'Cormorant Garamond',serif;font-weight:600;font-size:18px}
.panel-head .sub{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{font-family:'DM Mono',monospace;font-weight:400;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--text-3);text-align:right;padding:8px 12px;border-bottom:1px solid var(--divider)}
th:first-child{text-align:left}
td{font-family:'DM Sans',sans-serif;font-weight:600;font-size:12px;color:var(--text);
  text-align:right;padding:8px 12px;border-bottom:1px solid var(--divider);font-variant-numeric:tabular-nums}
td:first-child{font-weight:400;color:var(--text-2);text-align:left}
tr:last-child td{border-bottom:0}
td .sub{display:block;font-weight:400;font-size:10.5px;color:var(--text-3)}
.delta{color:var(--accent);font-weight:600}
.alert{color:var(--alert);font-weight:600}
.muted{color:var(--text-3);font-weight:400}
.badge{display:inline-block;font-family:'DM Sans',sans-serif;font-weight:500;font-size:11px;
  padding:2px 8px;border:1px solid var(--border);border-radius:6px;color:var(--text)}
.badge.done{background:var(--accent);border-color:var(--accent);color:#fff}
.badge.alert{border-color:var(--alert);color:var(--alert)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.kpi .label{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3)}
.kpi .value{font-family:'Cormorant Garamond',serif;font-weight:300;font-size:28px;line-height:1.15;color:#445e7e}
.report.dark .kpi .value{color:#8aa5c4}
.kpi .value.alert{color:var(--alert)}
.kpi .sub{font-size:11px;color:var(--text-3)}
.kpi .deltachip{font-family:'Inter',sans-serif;font-weight:700;font-size:12px;color:var(--accent)}
.sugg{padding:4px 16px 12px}
.sugg p{font-size:12px;margin:6px 0;color:var(--text-2)}
.sugg p.alert{color:var(--alert);font-weight:500}
.stamp{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--text-3);margin-top:30px}
@media print{.toolbar{display:none}}
"""

_SCRIPT = """
(function(){
  var KEY='fsc-share-theme';
  var root=document.getElementById('report-root');
  function apply(t){ if(t==='dark'){root.classList.add('dark');}else{root.classList.remove('dark');}
    var b=document.getElementById('theme-toggle'); if(b){b.textContent = t==='dark' ? 'Light mode' : 'Dark mode';} }
  var saved=null; try{ saved=localStorage.getItem(KEY);}catch(e){}
  apply(saved==='dark'?'dark':'light');
  var btn=document.getElementById('theme-toggle');
  if(btn){btn.addEventListener('click',function(){
    var t=root.classList.contains('dark')?'light':'dark';
    try{localStorage.setItem(KEY,t);}catch(e){}
    apply(t);
  });}
})();
"""


def _status_badge(status: str) -> str:
    label = STATUS_LABELS.get(status, status)
    cls = "badge done" if status in ("APPROVED", "PUBLISHED") else "badge"
    return f'<span class="{cls}">{_esc(label)}</span>'


def _group_pct(line: dict[str, Any], target_revenue: float) -> float | None:
    """% of Target revenue using the Scheduled $ once entered, else the Target $."""
    v = line.get("scheduled") if line.get("scheduled") is not None else line.get("guidance")
    if v is None or target_revenue <= 0:
        return None
    return float(v) / target_revenue


def _scorecard_rows(cards: list[dict[str, Any]]) -> str:
    rows = []
    for s in cards:
        sub = s.get("submission") or {}
        status = sub.get("status") or "NOT_STARTED"
        rev = s["revenue"]
        foh, boh = s["labor"]["foh"], s["labor"]["boh"]
        foh_pct = _group_pct(foh, rev["forecast"])
        boh_pct = _group_pct(boh, rev["forecast"])
        tot_pct = (foh_pct + boh_pct) if foh_pct is not None and boh_pct is not None else None
        rows.append(
            "<tr>"
            f'<td>{_esc(s["location"]["name"])}<span class="sub">{_esc(s["location"]["city"])}</span></td>'
            f"<td>{_status_badge(status)}</td>"
            f'<td>{_usd(rev["budget"])}</td>'
            f'<td>{_usd(rev["forecast"])}</td>'
            f'<td>{_delta(rev["variance"])}</td>'
            f'<td>{_usd(foh["guidance"])}</td><td>{_usd(foh["scheduled"])}</td><td>{_pct(foh_pct)}</td>'
            f'<td>{_usd(boh["guidance"])}</td><td>{_usd(boh["scheduled"])}</td><td>{_pct(boh_pct)}</td>'
            f"<td>{_pct(tot_pct)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _detail_grid(s: dict[str, Any]) -> str:
    rev = s["revenue"]
    rev_b, rev_t = float(rev["budget"]), float(rev["forecast"])
    body = (
        "<tr><td>Revenue</td>"
        f'<td>{_usd(rev_b)}</td><td>{_usd(rev_t)}</td>'
        f'<td>{_usd(rev_t)}<span class="sub">= Target</span></td>'
        f'<td>{_delta(rev["variance"])}</td><td class="muted">—</td></tr>'
    )
    for label, line in (
        ("FOH Labor", s["labor"]["foh"]),
        ("BOH Labor", s["labor"]["boh"]),
        ("Total Labor", s["labor"]["total"]),
    ):
        gd, sc = line["guidance"], line["scheduled"]
        body += (
            f"<tr><td>{_esc(label)}</td>"
            f'<td>{_usd(line["budget"])}</td><td>{_usd(gd)}</td><td>{_usd(sc)}</td>'
            f'<td>{_delta(line["guidanceVsBudget"])}</td><td>{_delta(line["scheduledVsGuidance"])}</td></tr>'
        )
        body += (
            f'<tr><td style="padding-left:24px" class="muted">{_esc(label)} % of Revenue</td>'
            f'<td class="muted">{_pct(line["budget"] / rev_b if rev_b > 0 else None)}</td>'
            f'<td class="muted">{_pct(gd / rev_t if gd is not None and rev_t > 0 else None)}</td>'
            f'<td class="muted">{_pct(sc / rev_t if sc is not None and rev_t > 0 else None)}</td>'
            '<td class="muted">—</td><td class="muted">—</td></tr>'
        )
    return (
        "<table><thead><tr><th>Line</th><th>Budget</th><th>Target (Ross)</th>"
        "<th>Scheduled (TeamWork)</th><th>Δ Target vs Budget</th>"
        "<th>Δ Sched vs Target</th></tr></thead><tbody>" + body + "</tbody></table>"
    )


def _actuals_kpis(a: dict[str, Any]) -> str:
    wtd, mt = a["wtd"], a["movingTarget"]
    behind = (
        mt["requiredRevenuePerDay"] is not None
        and mt["forecastRemainingPerDay"] is not None
        and mt["requiredRevenuePerDay"] > mt["forecastRemainingPerDay"]
    )
    labor_over = (mt["laborRemaining"] or 0) < 0
    rev_delta = wtd["revenueVariance"].get("dollars")
    arrow = "↗" if (rev_delta or 0) >= 0 else "↘"
    req = (
        f"{_usd(max(mt['requiredRevenuePerDay'], 0))}/day" if mt["requiredRevenuePerDay"] is not None else "—"
    )
    per_day = (
        f"≈ {_usd(max(mt['laborPerDayRemaining'], 0))}/day"
        if mt["laborPerDayRemaining"] is not None
        else "no guidance on file"
    )
    return f"""
<div class="kpis">
  <div class="kpi"><div class="label">WTD Revenue</div>
    <div class="value">{_usd(wtd["revenueActual"])}</div>
    <div class="deltachip">{arrow} {_usd(rev_delta, sign=True)}</div>
    <div class="sub">vs {_usd(wtd["revenueForecastToDate"])} forecast-to-date</div></div>
  <div class="kpi"><div class="label">WTD Labor</div>
    <div class="value">{_usd(wtd["laborDollars"])}</div>
    <div class="sub">FOH {_usd(wtd["fohLabor"])} · BOH {_usd(wtd["bohLabor"])} · {_pct(wtd["laborPct"])} of revenue</div></div>
  <div class="kpi"><div class="label">Required Pace</div>
    <div class="value{" alert" if behind else ""}">{req}</div>
    <div class="sub">to land the {_usd(mt["weekForecastRevenue"])} week forecast</div></div>
  <div class="kpi"><div class="label">Labor Remaining</div>
    <div class="value{" alert" if labor_over else ""}">{_usd(mt["laborRemaining"])}</div>
    <div class="sub">of {_usd(mt["weekLaborAllowance"])} allowance · {per_day}</div></div>
</div>"""


def _suggestions_html(a: dict[str, Any]) -> str:
    items = a.get("suggestions") or []
    if not items:
        return '<div class="sugg"><p class="muted">The week is complete — no remaining days to manage.</p></div>'
    ps = "".join(
        f'<p class="{"alert" if s.get("alert") else ""}">{_esc(s.get("text"))}</p>' for s in items
    )
    mt = a["movingTarget"]
    extra = (
        f'<p class="muted">FOH remaining {_usd(mt["fohRemaining"])} of {_usd(mt["fohAllowance"])} · '
        f'BOH remaining {_usd(mt["bohRemaining"])} of {_usd(mt["bohAllowance"])} · '
        f'projected week labor {_pct(mt["projectedWeekLaborPct"])} vs {_pct(mt["targetLaborPct"])} target</p>'
    )
    return f'<div class="sugg">{ps}{extra}</div>'


def _day_table(a: dict[str, Any]) -> str:
    rows = []
    for d in a["days"]:
        iso = d["date"]
        try:
            label = datetime.fromisoformat(iso).strftime("%a %-m/%-d")
        except ValueError:
            label = iso
        if d["elapsed"]:
            rows.append(
                f"<tr><td>{_esc(label)}</td>"
                f'<td>{_usd(d["actualRevenue"])}</td><td>{_usd(d["forecastRevenue"])}</td>'
                f'<td>{_delta(d["revenueVariance"])}</td>'
                f'<td>{_usd(d["fohLabor"])}</td><td>{_usd(d["bohLabor"])}</td>'
                f'<td>{_usd(d["laborDollars"])}</td><td>{_pct(d["laborPct"])}</td></tr>'
            )
        else:
            rows.append(
                f'<tr><td class="muted">{_esc(label)} · ahead</td>'
                f'<td class="muted">—</td><td class="muted">{_usd(d["forecastRevenue"])}</td>'
                '<td class="muted">—</td><td class="muted">—</td><td class="muted">—</td>'
                '<td class="muted">—</td><td class="muted">—</td></tr>'
            )
    return (
        "<table><thead><tr><th>Day</th><th>Actual Rev</th><th>Forecast Rev</th><th>Δ</th>"
        "<th>FOH $</th><th>BOH $</th><th>Total Labor</th><th>Labor %</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _remaining_plan_table(a: dict[str, Any]) -> str:
    plan = a.get("remainingPlan") or []
    if not plan:
        return ""
    rows = []
    for p in plan:
        try:
            label = datetime.fromisoformat(p["date"]).strftime("%a %-m/%-d")
        except ValueError:
            label = p["date"]
        rows.append(
            f"<tr><td>{_esc(label)}</td><td>{_usd(p['forecastRevenue'])}</td>"
            f'<td class="muted">{_pct(p["share"])}</td>'
            f"<td>{_usd(p['suggestedFoh'])}</td><td>{_usd(p['suggestedBoh'])}</td>"
            f"<td>{_usd(p['suggestedTotal'])}</td><td>{_pct(p['impliedLaborPct'])}</td></tr>"
        )
    return (
        '<div class="panel" style="margin-top:14px"><div class="panel-head">'
        '<div class="sub">REMAINING ALLOWANCE PRO-RATED BY TARGET REVENUE</div>'
        '<div class="ttl">Remaining-Day Plan</div></div>'
        '<div style="overflow-x:auto;padding:0 4px 8px"><table>'
        "<thead><tr><th>Day</th><th>Target Rev</th><th>Share</th><th>Sugg FOH $</th>"
        "<th>Sugg BOH $</th><th>Sugg Total</th><th>Implied Labor %</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></div></div>"
    )


def _portfolio_actuals_table(cards: list[dict[str, Any]], actuals: dict[str, dict[str, Any]]) -> str:
    rows = []
    for s in cards:
        a = actuals.get(s["location"]["id"])
        if not a:
            continue
        wtd, mt = a["wtd"], a["movingTarget"]
        labor_over = (mt["laborRemaining"] or 0) < 0
        target = mt["targetLaborPct"]
        pct_cls = "alert" if (wtd["laborPct"] is not None and target is not None and wtd["laborPct"] > target + 0.005) else ""
        rows.append(
            "<tr>"
            f'<td>{_esc(s["location"]["name"])}<span class="sub">{_esc(s["location"]["city"])}</span></td>'
            f'<td>{_usd(wtd["revenueActual"])}</td>'
            f'<td>{_delta(wtd["revenueVariance"])}</td>'
            f'<td>{_usd(wtd["laborDollars"])}</td>'
            f'<td class="{pct_cls}">{_pct(wtd["laborPct"])}</td>'
            f"<td>{_pct(target)}</td>"
            f'<td class="{"alert" if labor_over else ""}">{_usd(mt["laborRemaining"])}</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Location</th><th>WTD Revenue</th><th>Δ vs Fcst-to-date</th>"
        "<th>WTD Labor</th><th>Labor %</th><th>Target %</th><th>Labor Remaining</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_share_page(
    *,
    scope_label: str,
    cards: list[dict[str, Any]],
    actuals: dict[str, dict[str, Any]],
    meta: dict[str, Any],
    base_path: str,
    single_location: bool,
) -> str:
    period, week, year = int(meta["period"]), int(meta["week"]), int(meta["year"])
    week_label = f"WEEK OF {meta['weekStart']} – {meta['weekEnd']}"
    now_stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_fcst = sum(s["revenue"]["forecast"] for s in cards)
    total_bud = sum(s["revenue"]["budget"] for s in cards)
    approved = sum(1 for s in cards if (s.get("submission") or {}).get("status") in ("APPROVED", "PUBLISHED"))

    def nav(p: int, w: int, y: int) -> str:
        if w < 1:
            p, w = p - 1, 4
        if w > 4:
            p, w = p + 1, 1
        if p < 1:
            p, w, y = 13, 4, y - 1
        if p > 13:
            p, w, y = 1, 1, y + 1
        # Query-only href: resolves against the current path, so the page works
        # both directly off the API host and proxied behind the Vercel domain.
        return f"?period={p}&week={w}&year={y}"

    week_in_progress = any(a["meta"]["elapsedDays"] > 0 for a in actuals.values()) if actuals else False

    # Section 01 — submission scorecard
    sec1 = f"""
<section>
  <div class="eyebrow">01 — WEEKLY PLAN</div>
  <h2>Weekly <em>Plan</em></h2>
  <p class="hint">Revenue budget and Target, with Target (Ross-provided allowable) and Scheduled
  (manually entered from TeamWork·Dolce) FOH and BOH labor dollars. Labor % is over Target revenue.
  Deltas are blue; the sign carries the direction.</p>
  <div class="panel"><div style="overflow-x:auto">
    <table><thead><tr><th>Location</th><th>Stage</th><th>Rev Budget</th><th>Rev Target</th><th>Δ Bud</th>
    <th>FOH Target</th><th>FOH Sched</th><th>FOH %</th><th>BOH Target</th><th>BOH Sched</th><th>BOH %</th>
    <th>Total %</th></tr></thead><tbody>{_scorecard_rows(cards)}</tbody></table>
  </div></div>
</section>"""

    # Per-location detail grids (always for single location; collapsed for portfolio)
    details = []
    for s in cards:
        sub = s.get("submission") or {}
        head = (
            f'<div class="panel-head"><div class="sub">{_esc(s["location"]["city"])} · '
            f'{_esc(STATUS_LABELS.get(sub.get("status") or "NOT_STARTED", ""))}</div>'
            f'<div class="ttl">{_esc(s["location"]["name"])}</div></div>'
        )
        grid = f'<div style="overflow-x:auto;padding:0 4px 8px">{_detail_grid(s)}</div>'
        notes = ""
        if sub.get("guidanceNotes"):
            notes = f'<div class="sugg"><p class="muted">Guidance: {_esc(sub["guidanceNotes"])}</p></div>'
        details.append(f'<div class="panel">{head}{grid}{notes}</div>')
    sec2 = f"""
<section>
  <div class="eyebrow">02 — PLAN DETAIL</div>
  <h2>Labor <em>Lines</em></h2>
  <p class="hint">Budget, Ross's Target, and the TeamWork/Dolce scheduled dollars for each labor line,
  with FOH and BOH labor % of revenue.</p>
  {"".join(details)}
</section>"""

    # Section 03 — in-week actuals
    if week_in_progress:
        if single_location and cards:
            a = actuals.get(cards[0]["location"]["id"])
            sec3_body = (
                _actuals_kpis(a)
                + f'<div class="panel"><div class="panel-head"><div class="sub">MOVING TARGET</div>'
                f'<div class="ttl">Labor Suggestions</div></div>{_suggestions_html(a)}</div>'
                + _remaining_plan_table(a)
                + f'<div class="panel" style="margin-top:14px"><div class="panel-head"><div class="sub">DAILY ACTUALS VS TARGET</div>'
                f'<div class="ttl">Day by Day</div></div><div style="overflow-x:auto;padding:0 4px 8px">{_day_table(a)}</div></div>'
            )
        else:
            alert_blocks = []
            for s in cards:
                a = actuals.get(s["location"]["id"])
                if not a:
                    continue
                alerts = [x for x in (a.get("suggestions") or []) if x.get("alert")]
                if alerts:
                    ps = "".join(f'<p class="alert">{_esc(x["text"])}</p>' for x in alerts)
                    alert_blocks.append(
                        f'<div class="panel"><div class="panel-head"><div class="ttl">{_esc(s["location"]["name"])}</div></div>'
                        f'<div class="sugg">{ps}</div></div>'
                    )
            sec3_body = (
                f'<div class="panel"><div style="overflow-x:auto">{_portfolio_actuals_table(cards, actuals)}</div></div>'
                + ("".join(alert_blocks) if alert_blocks else "")
            )
        sec3 = f"""
<section>
  <div class="eyebrow">03 — IN-WEEK ACTUALS</div>
  <h2>Moving <em>Target</em></h2>
  <p class="hint">Week-to-date actuals against the approved forecast, with the pace required on the remaining
  days to stay on target. Orange means act.</p>
  {sec3_body}
</section>"""
    else:
        sec3 = """
<section>
  <div class="eyebrow">03 — IN-WEEK ACTUALS</div>
  <h2>Moving <em>Target</em></h2>
  <p class="hint">The week has not started — actuals, the moving target, and labor suggestions will appear
  here from day one.</p>
</section>"""

    title_em = scope_label.split(" ")[-1]
    title_plain = scope_label[: -len(title_em)].strip() if scope_label.endswith(title_em) else scope_label
    hero_title = (
        f"{_esc(title_plain)} <em>{_esc(title_em)}</em>" if title_plain else f"<em>{_esc(title_em)}</em>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta http-equiv="refresh" content="300">
<title>Weekly Labor Management — {_esc(scope_label)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Sans:wght@400;500;600&family=Inter:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{_CSS}</style>
</head>
<body>
<div class="report" id="report-root">
<div class="wrap">
  <div class="hero">
    <div class="edge">WEEKLY LABOR MANAGEMENT WORKFLOW</div>
    <div class="crumb">REPORTS / F&amp;B / FORECAST SCORECARD</div>
    <h1>{hero_title}</h1>
    <p class="lede">Portfolio forecast of <strong>{_usd(total_fcst)}</strong> against a
      <strong>{_usd(total_bud)}</strong> budget — <strong>{approved}/{len(cards)}</strong> location(s)
      approved/published for the week.</p>
    <div class="chips">
      <span class="meta-chip">{_esc(week_label)}</span>
      <span class="meta-chip">PERIOD {period} · WEEK {week} · FY {year}</span>
      <span class="meta-chip">{_esc(scope_label.upper())}</span>
      <span class="meta-chip">LIVE · {now_stamp}</span>
    </div>
  </div>

  <div class="toolbar">
    <div class="weeknav">
      <a href="{nav(period, week - 1, year)}">‹ Prev week</a>
      <span class="label">P{period} W{week} · {_esc(str(meta["weekStart"]))} → {_esc(str(meta["weekEnd"]))}</span>
      <a href="{nav(period, week + 1, year)}">Next week ›</a>
    </div>
    <button id="theme-toggle" type="button">Dark mode</button>
  </div>

  {sec1}
  {sec2}
  {sec3}

  <div class="stamp">Leonardo · Weekly Labor Management Workflow · live feed · refreshes every 5 minutes · {now_stamp}</div>
</div>
</div>
<script>{_SCRIPT}</script>
</body>
</html>"""


def render_invalid_link_page() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow"><title>Link expired</title>
<style>body{background:#0c1526;color:#e2eaf6;font-family:Georgia,serif;display:grid;place-items:center;min-height:100vh;margin:0}
.box{text-align:center}.box h1{font-weight:300;font-size:34px}.box p{color:#8aa5c4;font-size:14px;font-family:sans-serif}</style>
</head><body><div class="box"><h1>This link has expired</h1>
<p>Ask your Leonardo administrator for a fresh Forecast Scorecard live link.</p></div></body></html>"""
