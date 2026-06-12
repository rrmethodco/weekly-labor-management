"""Weekly Forecast Submission Scorecard service.

Workflow state lives in HELIXO_WEEKLY_FORECAST_SCORECARD (one row per
location × fiscal week). Revenue/labor budget and forecast figures are read
live from the Helixo operational tables; Ross's allowable labor guidance and
the TeamWork/Dolce scheduled labor dollars are stored on the workflow row.

Workflow (per the Weekly Labor Management SOP):
    DRAFT -> SUBMITTED -> TARGETS_ISSUED -> APPROVAL_REQUESTED
          -> APPROVED -> PUBLISHED
Rejections at the forecast stage return to DRAFT; rejections at the schedule
stage return to TARGETS_ISSUED.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from backend.services.helixo_snowflake_storage import (
    fetch_helixo_table_rows,
    fetch_helixo_table_rows_safe,
)
from backend.services.locations_storage import list_active_locations
from backend.snowflake import SnowflakeConnection

logger = logging.getLogger(__name__)

TABLE = "HELIXO_WEEKLY_FORECAST_SCORECARD"

FOH_POSITIONS = {"Server", "Bartender", "Host", "Barista", "Support", "Training"}
BOH_POSITIONS = {"Line Cooks", "Prep Cooks", "Pastry", "Dishwashers"}

FOH_BUDGET_COLS = [
    "server_budget",
    "bartender_budget",
    "host_budget",
    "barista_budget",
    "support_budget",
    "training_budget",
]
BOH_BUDGET_COLS = [
    "line_cooks_budget",
    "prep_cooks_budget",
    "pastry_budget",
    "dishwashers_budget",
]

STATUS_FLOW = [
    "DRAFT",
    "SUBMITTED",
    "TARGETS_ISSUED",
    "APPROVAL_REQUESTED",
    "APPROVED",
    "PUBLISHED",
]

# action -> (allowed source statuses, resulting status)
# Per the Weekly Labor Management SOP: GM + Directors submit the forecast
# (Helixo, Mon 10 AM); Ross approving it and issuing FOH/BOH targets is ONE
# step (Mon EOD); the GM builds the schedule in TeamWork and submitting the
# scheduled $ here IS the approval request (Tue); Ross approves (Wed); the GM
# publishes in TeamWork and confirms (Wed).
TRANSITIONS: dict[str, tuple[set[str], str]] = {
    "submit": ({"DRAFT"}, "SUBMITTED"),
    "issue_targets": ({"SUBMITTED", "TARGETS_ISSUED"}, "TARGETS_ISSUED"),
    "submit_schedule": ({"TARGETS_ISSUED", "APPROVAL_REQUESTED"}, "APPROVAL_REQUESTED"),
    "approve_schedule": ({"APPROVAL_REQUESTED"}, "APPROVED"),
    "publish": ({"APPROVED"}, "PUBLISHED"),
}

# statuses a rejection can be issued from -> status it falls back to
REJECT_FALLBACK = {
    "SUBMITTED": "DRAFT",
    "APPROVAL_REQUESTED": "TARGETS_ISSUED",
    "APPROVED": "TARGETS_ISSUED",
}


def week_dates(period: int, week: int, year: int) -> tuple[date, date]:
    fy_start = date(year - 1, 12, 29)
    p_start = fy_start + timedelta(days=(period - 1) * 28)
    w_start = p_start + timedelta(days=(week - 1) * 7)
    return w_start, w_start + timedelta(days=6)


def current_fiscal_week(today: date | None = None) -> tuple[int, int, int]:
    """(period, week, fiscal_year) containing ``today`` under the 13×28-day calendar."""
    t = today or date.today()
    fy = t.year + 1 if t >= date(t.year, 12, 29) else t.year
    diff = (t - date(fy - 1, 12, 29)).days
    period = min(13, diff // 28 + 1)
    week = min(4, (diff % 28) // 7 + 1)
    return period, week, fy


def _t(conn: SnowflakeConnection, name: str) -> str:
    return f"{conn.config.DATABASE}.{conn.config.SCHEMA}.{name}"


def _f(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        x = float(v)
        return 0.0 if x != x else x  # NaN guard
    except (TypeError, ValueError):
        return 0.0


def _opt_f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def _ts(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except (TypeError, ValueError):
            return None
    s = str(v)
    return s if s and s.lower() != "nat" else None


def _submission_dict(row: dict[str, Any]) -> dict[str, Any]:
    r = {str(k).lower(): v for k, v in row.items()}
    return {
        "id": str(r.get("id") or ""),
        "locationId": str(r.get("location_id") or ""),
        "fiscalYear": int(_f(r.get("fiscal_year"))),
        "period": int(_f(r.get("period"))),
        "week": int(_f(r.get("week"))),
        "weekStart": str(r.get("week_start") or ""),
        "weekEnd": str(r.get("week_end") or ""),
        "status": str(r.get("status") or "DRAFT"),
        "submittedForecastRevenue": _opt_f(r.get("submitted_forecast_revenue")),
        "submittedBy": r.get("submitted_by") or None,
        "submittedAt": _ts(r.get("submitted_at")),
        "guidanceFohLabor": _opt_f(r.get("guidance_foh_labor")),
        "guidanceBohLabor": _opt_f(r.get("guidance_boh_labor")),
        "guidanceNotes": r.get("guidance_notes") or None,
        "guidanceIssuedBy": r.get("guidance_issued_by") or None,
        "guidanceIssuedAt": _ts(r.get("guidance_issued_at")),
        "scheduledFohLabor": _opt_f(r.get("scheduled_foh_labor")),
        "scheduledBohLabor": _opt_f(r.get("scheduled_boh_labor")),
        "scheduleSource": r.get("schedule_source") or "TeamWork/Dolce",
        "scheduleNotes": r.get("schedule_notes") or None,
        "scheduleSubmittedBy": r.get("schedule_submitted_by") or None,
        "scheduleSubmittedAt": _ts(r.get("schedule_submitted_at")),
        "approvedBy": r.get("final_approved_by") or None,
        "approvedAt": _ts(r.get("final_approved_at")),
        "publishedBy": r.get("published_by") or None,
        "publishedAt": _ts(r.get("published_at")),
        "rejectedFromStatus": r.get("rejected_from_status") or None,
        "rejectionReason": r.get("rejection_reason") or None,
        "rejectedBy": r.get("rejected_by") or None,
        "rejectedAt": _ts(r.get("rejected_at")),
    }


def fetch_submissions(period: int, week: int, year: int) -> dict[str, dict[str, Any]]:
    """All workflow rows for a fiscal week keyed by lowercase location_id."""
    with SnowflakeConnection() as conn:
        df = conn.execute_query(
            f"""
            SELECT * FROM {_t(conn, TABLE)}
            WHERE fiscal_year = %(fy)s AND period = %(p)s AND week = %(w)s
            ORDER BY updated_at DESC
            """,
            {"fy": year, "p": period, "w": week},
        )
    if df is None or df.empty:
        return {}
    df.columns = df.columns.str.lower()
    out: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        sub = _submission_dict(row.to_dict())
        key = sub["locationId"].strip().lower()
        if key and key not in out:  # newest row wins
            out[key] = sub
    return out


def get_submission_by_id(submission_id: str) -> dict[str, Any] | None:
    with SnowflakeConnection() as conn:
        df = conn.execute_query(
            f"SELECT * FROM {_t(conn, TABLE)} WHERE id = %(id)s LIMIT 1",
            {"id": submission_id},
        )
    if df is None or df.empty:
        return None
    df.columns = df.columns.str.lower()
    return _submission_dict(df.iloc[0].to_dict())


def ensure_submission(location_id: str, period: int, week: int, year: int) -> dict[str, Any]:
    """Return the workflow row for a location/week, creating a DRAFT if missing."""
    existing = fetch_submissions(period, week, year).get(location_id.strip().lower())
    if existing:
        return existing
    w_start, w_end = week_dates(period, week, year)
    entry_id = str(uuid.uuid4())
    with SnowflakeConnection() as conn:
        conn.execute(
            f"""
            INSERT INTO {_t(conn, TABLE)}
                (id, location_id, fiscal_year, period, week, week_start, week_end, status)
            VALUES (%(id)s, %(loc)s, %(fy)s, %(p)s, %(w)s, %(ws)s, %(we)s, 'DRAFT')
            """,
            {
                "id": entry_id,
                "loc": location_id,
                "fy": year,
                "p": period,
                "w": week,
                "ws": w_start.isoformat(),
                "we": w_end.isoformat(),
            },
        )
    sub = get_submission_by_id(entry_id)
    if sub is None:
        raise RuntimeError("Failed to create forecast scorecard submission row")
    return sub


def apply_action(
    submission_id: str,
    action: str,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a workflow action; validates the transition and stamps the actor."""
    payload = payload or {}
    sub = get_submission_by_id(submission_id)
    if sub is None:
        raise ValueError("Submission not found")
    current = sub["status"]

    sets: list[str] = ["updated_at = CURRENT_TIMESTAMP()"]
    params: dict[str, Any] = {"id": submission_id, "actor": actor}

    if action == "reject":
        fallback = REJECT_FALLBACK.get(current)
        if not fallback:
            raise ValueError(f"Cannot reject from status {current}")
        sets += [
            "status = %(status)s",
            "rejected_from_status = %(from_status)s",
            "rejection_reason = %(reason)s",
            "rejected_by = %(actor)s",
            "rejected_at = CURRENT_TIMESTAMP()",
        ]
        params.update(
            {
                "status": fallback,
                "from_status": current,
                "reason": str(payload.get("reason") or "").strip() or None,
            }
        )
    else:
        transition = TRANSITIONS.get(action)
        if not transition:
            raise ValueError(f"Unknown action: {action}")
        allowed, new_status = transition
        if current not in allowed:
            raise ValueError(f"Action '{action}' not allowed from status {current}")
        sets.append("status = %(status)s")
        params["status"] = new_status

        if action == "submit":
            sets += [
                "submitted_forecast_revenue = %(fcst)s",
                "submitted_by = %(actor)s",
                "submitted_at = CURRENT_TIMESTAMP()",
                # clear the rejection trail on resubmit
                "rejected_from_status = NULL",
                "rejection_reason = NULL",
            ]
            params["fcst"] = _opt_f(payload.get("forecast_revenue"))
        elif action == "issue_targets":
            # Issuing targets IS the forecast approval (SOP step 2).
            sets += [
                "guidance_foh_labor = %(foh)s",
                "guidance_boh_labor = %(boh)s",
                "guidance_notes = %(notes)s",
                "guidance_issued_by = %(actor)s",
                "guidance_issued_at = CURRENT_TIMESTAMP()",
            ]
            params.update(
                {
                    "foh": _f(payload.get("target_foh_labor", payload.get("guidance_foh_labor"))),
                    "boh": _f(payload.get("target_boh_labor", payload.get("guidance_boh_labor"))),
                    "notes": str(payload.get("target_notes") or payload.get("guidance_notes") or "").strip() or None,
                }
            )
        elif action == "submit_schedule":
            # Entering the TeamWork scheduled $ IS the approval request (SOP step 4).
            sets += [
                "scheduled_foh_labor = %(foh)s",
                "scheduled_boh_labor = %(boh)s",
                "schedule_notes = %(notes)s",
                "schedule_submitted_by = %(actor)s",
                "schedule_submitted_at = CURRENT_TIMESTAMP()",
                "rejected_from_status = NULL",
                "rejection_reason = NULL",
            ]
            params.update(
                {
                    "foh": _f(payload.get("scheduled_foh_labor")),
                    "boh": _f(payload.get("scheduled_boh_labor")),
                    "notes": str(payload.get("schedule_notes") or "").strip() or None,
                }
            )
        elif action == "approve_schedule":
            sets += [
                "final_approved_by = %(actor)s",
                "final_approved_at = CURRENT_TIMESTAMP()",
            ]
        elif action == "publish":
            sets += [
                "published_by = %(actor)s",
                "published_at = CURRENT_TIMESTAMP()",
            ]

    with SnowflakeConnection() as conn:
        conn.execute(
            f"UPDATE {_t(conn, TABLE)} SET {', '.join(sets)} WHERE id = %(id)s",
            params,
        )
    updated = get_submission_by_id(submission_id)
    if updated is None:
        raise RuntimeError("Submission disappeared during update")
    return updated


# ---------------------------------------------------------------------------
# Scorecard builders
# ---------------------------------------------------------------------------


def _sum_positions(rows: list[dict[str, Any]], loc_id: str, positions: set[str], field: str) -> float:
    return sum(
        _f(r.get(field))
        for r in rows
        if r.get("location_id") == loc_id and str(r.get("position") or r.get("mapped_position") or "") in positions
    )


def _sum_cols(rows: list[dict[str, Any]], loc_id: str, cols: list[str]) -> float:
    return sum(sum(_f(r.get(c)) for c in cols) for r in rows if r.get("location_id") == loc_id)


def _sum_field(rows: list[dict[str, Any]], loc_id: str, field: str) -> float:
    return sum(_f(r.get(field)) for r in rows if r.get("location_id") == loc_id)


def _forecast_revenue(rows: list[dict[str, Any]], loc_id: str) -> float:
    return sum(
        _f(r.get("manager_revenue")) or _f(r.get("ai_suggested_revenue"))
        for r in rows
        if r.get("location_id") == loc_id
    )


def _daily_target_spread(
    forecast_rows: list[dict[str, Any]],
    loc_id: str,
    w_start: date,
    target_foh: float | None,
    target_boh: float | None,
) -> list[dict[str, Any]]:
    """SOP step 2 artifact: Ross enters two week totals; Leonardo spreads them
    by day pro-rated to the daily forecast (busier days get more labor)."""
    if target_foh is None or target_boh is None:
        return []
    fcst_by_day: dict[str, float] = {}
    for r in forecast_rows:
        if r.get("location_id") != loc_id:
            continue
        d = str(r.get("business_date") or "")[:10]
        fcst_by_day[d] = fcst_by_day.get(d, 0.0) + (_f(r.get("manager_revenue")) or _f(r.get("ai_suggested_revenue")))
    total = sum(fcst_by_day.values())
    out = []
    for i in range(7):
        d = (w_start + timedelta(days=i)).isoformat()
        f = fcst_by_day.get(d, 0.0)
        share = (f / total) if total > 0 else 1.0 / 7.0
        foh, boh = target_foh * share, target_boh * share
        out.append(
            {
                "date": d,
                "forecastRevenue": f,
                "targetFoh": foh,
                "targetBoh": boh,
                "laborPct": ((foh + boh) / f) if f > 0 else None,
            }
        )
    return out


def _variance(value: float | None, base: float | None) -> dict[str, float | None]:
    if value is None or base is None:
        return {"dollars": None, "pct": None}
    return {
        "dollars": value - base,
        "pct": ((value - base) / base) if base else None,
    }


def build_week_scorecards(period: int, week: int, year: int) -> dict[str, Any]:
    """Forecast submission scorecard for every active location for one fiscal week."""
    w_start, w_end = week_dates(period, week, year)
    start, end = w_start.isoformat(), w_end.isoformat()

    locations = list_active_locations()
    location_ids = [loc["id"] for loc in locations]

    budget_cols = "location_id,business_date,budget_revenue," + ",".join(FOH_BUDGET_COLS + BOH_BUDGET_COLS)
    budgets = fetch_helixo_table_rows("daily_budget", location_ids, start_date=start, end_date=end, columns=budget_cols)
    forecasts = fetch_helixo_table_rows_safe(
        "daily_forecasts",
        location_ids,
        start_date=start,
        end_date=end,
        columns="location_id,business_date,manager_revenue,ai_suggested_revenue",
    )
    labor_targets = fetch_helixo_table_rows_safe(
        "daily_labor_targets",
        location_ids,
        start_date=start,
        end_date=end,
        columns="location_id,business_date,position,projected_labor_dollars",
    )
    submissions = fetch_submissions(period, week, year)

    scorecards = []
    for loc in locations:
        loc_id = loc["id"]
        sub = submissions.get(loc_id.strip().lower())

        budget_revenue = _sum_field(budgets, loc_id, "budget_revenue")
        forecast_revenue = _forecast_revenue(forecasts, loc_id)
        if sub and sub.get("submittedForecastRevenue") is not None:
            forecast_revenue = float(sub["submittedForecastRevenue"])

        budget_foh = _sum_cols(budgets, loc_id, FOH_BUDGET_COLS)
        budget_boh = _sum_cols(budgets, loc_id, BOH_BUDGET_COLS)
        helixo_foh = _sum_positions(labor_targets, loc_id, FOH_POSITIONS, "projected_labor_dollars")
        helixo_boh = _sum_positions(labor_targets, loc_id, BOH_POSITIONS, "projected_labor_dollars")

        guidance_foh = sub.get("guidanceFohLabor") if sub else None
        guidance_boh = sub.get("guidanceBohLabor") if sub else None
        scheduled_foh = sub.get("scheduledFohLabor") if sub else None
        scheduled_boh = sub.get("scheduledBohLabor") if sub else None

        guidance_total = (guidance_foh + guidance_boh) if guidance_foh is not None and guidance_boh is not None else None
        scheduled_total = (
            (scheduled_foh + scheduled_boh) if scheduled_foh is not None and scheduled_boh is not None else None
        )
        budget_labor_total = budget_foh + budget_boh

        scorecards.append(
            {
                "location": {
                    "id": loc_id,
                    "name": loc["name"],
                    "city": loc.get("city") or "",
                },
                "revenue": {
                    "budget": budget_revenue,
                    "forecast": forecast_revenue,
                    "variance": _variance(forecast_revenue, budget_revenue),
                },
                "labor": {
                    "foh": {
                        "budget": budget_foh,
                        "helixoTarget": helixo_foh,
                        "guidance": guidance_foh,
                        "scheduled": scheduled_foh,
                        "guidanceVsBudget": _variance(guidance_foh, budget_foh),
                        "scheduledVsGuidance": _variance(scheduled_foh, guidance_foh),
                    },
                    "boh": {
                        "budget": budget_boh,
                        "helixoTarget": helixo_boh,
                        "guidance": guidance_boh,
                        "scheduled": scheduled_boh,
                        "guidanceVsBudget": _variance(guidance_boh, budget_boh),
                        "scheduledVsGuidance": _variance(scheduled_boh, guidance_boh),
                    },
                    "total": {
                        "budget": budget_labor_total,
                        "helixoTarget": helixo_foh + helixo_boh,
                        "guidance": guidance_total,
                        "scheduled": scheduled_total,
                        "guidanceVsBudget": _variance(guidance_total, budget_labor_total),
                        "scheduledVsGuidance": _variance(scheduled_total, guidance_total),
                    },
                },
                "laborPct": {
                    "budget": (budget_labor_total / budget_revenue) if budget_revenue > 0 else None,
                    "guidance": (guidance_total / forecast_revenue)
                    if guidance_total is not None and forecast_revenue > 0
                    else None,
                    "scheduled": (scheduled_total / forecast_revenue)
                    if scheduled_total is not None and forecast_revenue > 0
                    else None,
                },
                "dailyTargets": _daily_target_spread(forecasts, loc_id, w_start, guidance_foh, guidance_boh),
                "submission": sub,
            }
        )

    scorecards.sort(key=lambda s: s["revenue"]["forecast"], reverse=True)
    status_counts: dict[str, int] = {}
    for s in scorecards:
        st = s["submission"]["status"] if s["submission"] else "NOT_STARTED"
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "meta": {
            "period": period,
            "week": week,
            "year": year,
            "weekStart": start,
            "weekEnd": end,
            "statusCounts": status_counts,
        },
        "scorecards": scorecards,
    }


def build_actuals_scorecard(location_id: str, period: int, week: int, year: int) -> dict[str, Any]:
    """In-week actuals scorecard: revenue + labor vs forecast with a moving target."""
    return build_actuals_scorecards([location_id], period, week, year)[location_id]


def build_actuals_scorecards(
    location_ids: list[str], period: int, week: int, year: int
) -> dict[str, dict[str, Any]]:
    """In-week actuals scorecards for many locations from one set of Helixo reads."""
    w_start, w_end = week_dates(period, week, year)
    start, end = w_start.isoformat(), w_end.isoformat()

    actuals = fetch_helixo_table_rows(
        "daily_actuals_rco",
        location_ids,
        start_date=start,
        end_date=end,
        columns="location_id,business_date,revenue",
    )
    labor = fetch_helixo_table_rows_safe(
        "daily_labor",
        location_ids,
        start_date=start,
        end_date=end,
        columns="location_id,business_date,mapped_position,labor_dollars",
    )
    forecasts = fetch_helixo_table_rows_safe(
        "daily_forecasts",
        location_ids,
        start_date=start,
        end_date=end,
        columns="location_id,business_date,manager_revenue,ai_suggested_revenue",
    )
    budgets = fetch_helixo_table_rows_safe(
        "daily_budget",
        location_ids,
        start_date=start,
        end_date=end,
        columns="location_id,business_date," + ",".join(FOH_BUDGET_COLS + BOH_BUDGET_COLS),
    )
    submissions = fetch_submissions(period, week, year)

    return {
        loc_id: _compute_actuals(
            loc_id,
            period,
            week,
            year,
            w_start,
            actuals,
            labor,
            forecasts,
            budgets,
            submissions.get(loc_id.strip().lower()),
        )
        for loc_id in location_ids
    }


def _compute_actuals(
    location_id: str,
    period: int,
    week: int,
    year: int,
    w_start: date,
    actuals: list[dict[str, Any]],
    labor: list[dict[str, Any]],
    forecasts: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    sub: dict[str, Any] | None,
) -> dict[str, Any]:
    today = date.today()
    start, end = w_start.isoformat(), (w_start + timedelta(days=6)).isoformat()

    rev_by_day: dict[str, float] = {}
    for r in actuals:
        if r.get("location_id") != location_id:
            continue
        d = str(r.get("business_date") or "")[:10]
        rev_by_day[d] = rev_by_day.get(d, 0.0) + _f(r.get("revenue"))

    fcst_by_day: dict[str, float] = {}
    for r in forecasts:
        if r.get("location_id") != location_id:
            continue
        d = str(r.get("business_date") or "")[:10]
        fcst_by_day[d] = fcst_by_day.get(d, 0.0) + (_f(r.get("manager_revenue")) or _f(r.get("ai_suggested_revenue")))

    foh_by_day: dict[str, float] = {}
    boh_by_day: dict[str, float] = {}
    other_by_day: dict[str, float] = {}
    for r in labor:
        if r.get("location_id") != location_id:
            continue
        d = str(r.get("business_date") or "")[:10]
        pos = str(r.get("mapped_position") or "")
        dollars = _f(r.get("labor_dollars"))
        if pos in FOH_POSITIONS:
            foh_by_day[d] = foh_by_day.get(d, 0.0) + dollars
        elif pos in BOH_POSITIONS:
            boh_by_day[d] = boh_by_day.get(d, 0.0) + dollars
        else:
            other_by_day[d] = other_by_day.get(d, 0.0) + dollars

    days = []
    wtd_revenue = wtd_forecast = wtd_foh = wtd_boh = wtd_other = 0.0
    elapsed_days = 0
    remaining_forecast = 0.0
    for i in range(7):
        d = (w_start + timedelta(days=i)).isoformat()
        actual_rev = rev_by_day.get(d, 0.0)
        fcst_rev = fcst_by_day.get(d, 0.0)
        foh = foh_by_day.get(d, 0.0)
        boh = boh_by_day.get(d, 0.0)
        other = other_by_day.get(d, 0.0)
        is_elapsed = date.fromisoformat(d) < today or actual_rev > 0
        labor_total = foh + boh + other
        days.append(
            {
                "date": d,
                "elapsed": is_elapsed,
                "actualRevenue": actual_rev,
                "forecastRevenue": fcst_rev,
                "revenueVariance": _variance(actual_rev, fcst_rev) if is_elapsed else {"dollars": None, "pct": None},
                "fohLabor": foh,
                "bohLabor": boh,
                "laborDollars": labor_total,
                "laborPct": (labor_total / actual_rev) if actual_rev > 0 else None,
            }
        )
        if is_elapsed:
            elapsed_days += 1
            wtd_revenue += actual_rev
            wtd_forecast += fcst_rev
            wtd_foh += foh
            wtd_boh += boh
            wtd_other += other
        else:
            remaining_forecast += fcst_rev

    week_forecast = wtd_forecast + remaining_forecast
    remaining_days = 7 - elapsed_days
    wtd_labor = wtd_foh + wtd_boh + wtd_other

    guidance_foh = sub.get("guidanceFohLabor") if sub else None
    guidance_boh = sub.get("guidanceBohLabor") if sub else None
    has_guidance = guidance_foh is not None and guidance_boh is not None
    week_labor_allowance = (guidance_foh + guidance_boh) if has_guidance else None
    target_labor_pct = (week_labor_allowance / week_forecast) if has_guidance and week_forecast > 0 else None

    # Moving targets: what the remaining days must average to land the week
    # on the approved forecast revenue and inside the labor allowance.
    revenue_gap = week_forecast - wtd_revenue
    required_revenue_per_day = (revenue_gap / remaining_days) if remaining_days > 0 else None
    forecast_remaining_per_day = (remaining_forecast / remaining_days) if remaining_days > 0 else None

    foh_remaining = (guidance_foh - wtd_foh) if guidance_foh is not None else None
    boh_remaining = (guidance_boh - wtd_boh) if guidance_boh is not None else None
    labor_remaining = (week_labor_allowance - wtd_labor) if week_labor_allowance is not None else None
    labor_per_day_remaining = (
        (labor_remaining / remaining_days) if labor_remaining is not None and remaining_days > 0 else None
    )

    wtd_labor_pct = (wtd_labor / wtd_revenue) if wtd_revenue > 0 else None
    # If the remaining days spend the remaining allowance (never negative) and
    # revenue lands on forecast, the week closes at this labor %.
    projected_week_labor_pct = None
    if week_forecast > 0 and labor_remaining is not None:
        projected_week_labor_pct = (wtd_labor + max(labor_remaining, 0.0)) / week_forecast

    suggestions: list[dict[str, Any]] = []
    if remaining_days > 0:
        if required_revenue_per_day is not None and forecast_remaining_per_day is not None:
            delta_per_day = required_revenue_per_day - forecast_remaining_per_day
            if delta_per_day > 0.005 * max(forecast_remaining_per_day, 1.0):
                suggestions.append(
                    {
                        "kind": "revenue_pace",
                        "alert": True,
                        "text": (
                            f"Revenue is ${revenue_gap - remaining_forecast:,.0f} behind forecast pace — the "
                            f"remaining {remaining_days} day(s) must average ${required_revenue_per_day:,.0f}/day "
                            f"(forecast called for ${forecast_remaining_per_day:,.0f}/day) to land the week on target."
                        ),
                    }
                )
            else:
                suggestions.append(
                    {
                        "kind": "revenue_pace",
                        "alert": False,
                        "text": (
                            f"Revenue is on/ahead of forecast pace — hold ${max(required_revenue_per_day, 0):,.0f}/day "
                            f"across the remaining {remaining_days} day(s) to close the week at "
                            f"${week_forecast:,.0f}."
                        ),
                    }
                )
        if has_guidance and target_labor_pct is not None and wtd_labor_pct is not None:
            if wtd_labor_pct > target_labor_pct + 0.005:
                overspend = wtd_labor - (target_labor_pct * wtd_revenue)
                suggestions.append(
                    {
                        "kind": "labor_pace",
                        "alert": True,
                        "text": (
                            f"Labor is running {wtd_labor_pct:.1%} vs the {target_labor_pct:.1%} allowable — "
                            f"about ${overspend:,.0f} hot. Trim roughly ${overspend / remaining_days:,.0f}/day "
                            f"from upcoming shifts to finish inside the ${week_labor_allowance:,.0f} allowance."
                        ),
                    }
                )
            else:
                suggestions.append(
                    {
                        "kind": "labor_pace",
                        "alert": False,
                        "text": (
                            f"Labor is pacing at {wtd_labor_pct:.1%} against a {target_labor_pct:.1%} allowable — "
                            f"${labor_remaining:,.0f} remains for the final {remaining_days} day(s) "
                            f"(≈ ${labor_per_day_remaining:,.0f}/day)."
                        ),
                    }
                )
        if foh_remaining is not None and foh_remaining < 0:
            suggestions.append(
                {
                    "kind": "foh_over",
                    "alert": True,
                    "text": (
                        f"FOH has exceeded its ${guidance_foh:,.0f} allowance by ${-foh_remaining:,.0f} — "
                        "cut FOH shifts before BOH; BOH still has "
                        f"${max(boh_remaining or 0, 0):,.0f} of room."
                    ),
                }
            )
        if boh_remaining is not None and boh_remaining < 0:
            suggestions.append(
                {
                    "kind": "boh_over",
                    "alert": True,
                    "text": (
                        f"BOH has exceeded its ${guidance_boh:,.0f} allowance by ${-boh_remaining:,.0f} — "
                        "review prep/dish coverage on the remaining days."
                    ),
                }
            )
        if not has_guidance:
            suggestions.append(
                {
                    "kind": "no_guidance",
                    "alert": True,
                    "text": (
                        "No approved labor guidance is on file for this week — moving labor targets are "
                        "unavailable until the forecast scorecard is approved."
                    ),
                }
            )

    return {
        "meta": {
            "locationId": location_id,
            "period": period,
            "week": week,
            "year": year,
            "weekStart": start,
            "weekEnd": end,
            "elapsedDays": elapsed_days,
            "remainingDays": remaining_days,
        },
        "days": days,
        "wtd": {
            "revenueActual": wtd_revenue,
            "revenueForecastToDate": wtd_forecast,
            "revenueVariance": _variance(wtd_revenue, wtd_forecast),
            "fohLabor": wtd_foh,
            "bohLabor": wtd_boh,
            "otherLabor": wtd_other,
            "laborDollars": wtd_labor,
            "laborPct": wtd_labor_pct,
        },
        "movingTarget": {
            "weekForecastRevenue": week_forecast,
            "remainingForecastRevenue": remaining_forecast,
            "requiredRevenuePerDay": required_revenue_per_day,
            "forecastRemainingPerDay": forecast_remaining_per_day,
            "weekLaborAllowance": week_labor_allowance,
            "targetLaborPct": target_labor_pct,
            "projectedWeekLaborPct": projected_week_labor_pct,
            "laborRemaining": labor_remaining,
            "laborPerDayRemaining": labor_per_day_remaining,
            "fohAllowance": guidance_foh,
            "fohRemaining": foh_remaining,
            "bohAllowance": guidance_boh,
            "bohRemaining": boh_remaining,
        },
        "remainingPlan": _remaining_day_plan(days, foh_remaining, boh_remaining),
        "varianceSheet": _variance_sheet(
            location_id, w_start, days, budgets, fcst_by_day, foh_by_day, boh_by_day, sub
        ),
        "suggestions": suggestions,
        "submission": sub,
    }


def _variance_sheet(
    location_id: str,
    w_start: date,
    days: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    fcst_by_day: dict[str, float],
    foh_by_day: dict[str, float],
    boh_by_day: dict[str, float],
    sub: dict[str, Any] | None,
) -> dict[str, Any]:
    """End-of-Week Variance (SOP sheet 3): Budget vs Scheduled vs Actual by day
    for FOH and BOH. Daily Scheduled is the approved weekly TeamWork total
    pro-rated by each day's forecast share until a TeamWork API sync provides
    real daily schedule data."""
    bud_foh_by_day: dict[str, float] = {}
    bud_boh_by_day: dict[str, float] = {}
    for r in budgets:
        if r.get("location_id") != location_id:
            continue
        d = str(r.get("business_date") or "")[:10]
        bud_foh_by_day[d] = bud_foh_by_day.get(d, 0.0) + sum(_f(r.get(c)) for c in FOH_BUDGET_COLS)
        bud_boh_by_day[d] = bud_boh_by_day.get(d, 0.0) + sum(_f(r.get(c)) for c in BOH_BUDGET_COLS)

    sched_foh = sub.get("scheduledFohLabor") if sub else None
    sched_boh = sub.get("scheduledBohLabor") if sub else None
    week_fcst = sum(fcst_by_day.values())

    rows = []
    for i in range(7):
        d = (w_start + timedelta(days=i)).isoformat()
        elapsed = days[i]["elapsed"]
        share = (fcst_by_day.get(d, 0.0) / week_fcst) if week_fcst > 0 else 1.0 / 7.0
        rows.append(
            {
                "date": d,
                "elapsed": elapsed,
                "foh": {
                    "budget": bud_foh_by_day.get(d, 0.0),
                    "scheduled": (sched_foh * share) if sched_foh is not None else None,
                    "actual": foh_by_day.get(d, 0.0) if elapsed else None,
                },
                "boh": {
                    "budget": bud_boh_by_day.get(d, 0.0),
                    "scheduled": (sched_boh * share) if sched_boh is not None else None,
                    "actual": boh_by_day.get(d, 0.0) if elapsed else None,
                },
            }
        )

    def _tot(group: str, field: str) -> float | None:
        vals = [r[group][field] for r in rows if r[group][field] is not None]
        return sum(vals) if vals else None

    return {
        "rows": rows,
        "totals": {
            "foh": {"budget": _tot("foh", "budget"), "scheduled": _tot("foh", "scheduled"), "actual": _tot("foh", "actual")},
            "boh": {"budget": _tot("boh", "budget"), "scheduled": _tot("boh", "scheduled"), "actual": _tot("boh", "actual")},
        },
        "scheduledIsProRated": True,
    }


def _remaining_day_plan(
    days: list[dict[str, Any]],
    foh_remaining: float | None,
    boh_remaining: float | None,
) -> list[dict[str, Any]]:
    """Allocate the remaining FOH/BOH allowance across the unplayed days,
    pro-rated by each day's share of the remaining forecast revenue."""
    remaining = [d for d in days if not d["elapsed"]]
    pool_total = sum(d["forecastRevenue"] for d in remaining)
    foh_pool = max(foh_remaining, 0.0) if foh_remaining is not None else None
    boh_pool = max(boh_remaining, 0.0) if boh_remaining is not None else None
    plan = []
    for d in remaining:
        share = (d["forecastRevenue"] / pool_total) if pool_total > 0 else (1.0 / len(remaining))
        foh = foh_pool * share if foh_pool is not None else None
        boh = boh_pool * share if boh_pool is not None else None
        total = (foh + boh) if foh is not None and boh is not None else None
        plan.append(
            {
                "date": d["date"],
                "forecastRevenue": d["forecastRevenue"],
                "share": share,
                "suggestedFoh": foh,
                "suggestedBoh": boh,
                "suggestedTotal": total,
                "impliedLaborPct": (total / d["forecastRevenue"])
                if total is not None and d["forecastRevenue"] > 0
                else None,
            }
        )
    return plan
