"""Weekly Labor Management Workflow endpoints.

Pre-week submission scorecard (budget vs forecast vs scheduled labor with the
GM -> Director -> Ross approval workflow) and the in-week actuals scorecard
with moving revenue/labor targets.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.services import forecast_scorecard_service as svc
from backend.services.forecast_scorecard_share_html import (
    render_invalid_link_page,
    render_share_page,
)
from backend.services.forecast_scorecard_share_service import (
    create_share_token,
    verify_share_token,
)
from backend.services.labor_workflow_notify_service import notify_stage_change
from backend.services.locations_storage import get_location_by_id

logger = logging.getLogger(__name__)
router = APIRouter()


def _validate_week(period: int, week: int, year: int) -> None:
    if not (1 <= period <= 13):
        raise HTTPException(status_code=422, detail="period must be 1-13")
    if not (1 <= week <= 4):
        raise HTTPException(status_code=422, detail="week must be 1-4")
    if not (2020 <= year <= 2100):
        raise HTTPException(status_code=422, detail="year out of range")


@router.get("/week")
def get_week_scorecards(
    period: int = Query(...),
    week: int = Query(...),
    year: int = Query(default_factory=lambda: datetime.now().year),
):
    _validate_week(period, week, year)
    try:
        return svc.build_week_scorecards(period, week, year)
    except Exception as e:
        logger.exception("forecast scorecard week build failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build forecast scorecard") from e


@router.get("/actuals")
def get_actuals_scorecard(
    location_id: str = Query(...),
    period: int = Query(...),
    week: int = Query(...),
    year: int = Query(default_factory=lambda: datetime.now().year),
):
    _validate_week(period, week, year)
    if not location_id.strip():
        raise HTTPException(status_code=422, detail="location_id is required")
    try:
        return svc.build_actuals_scorecard(location_id.strip(), period, week, year)
    except Exception as e:
        logger.exception("actuals scorecard build failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build actuals scorecard") from e


class EnsureSubmissionBody(BaseModel):
    location_id: str
    period: int
    week: int
    year: int


@router.post("/submissions/ensure")
def ensure_submission(body: EnsureSubmissionBody):
    _validate_week(body.period, body.week, body.year)
    if not body.location_id.strip():
        raise HTTPException(status_code=422, detail="location_id is required")
    try:
        return svc.ensure_submission(body.location_id.strip(), body.period, body.week, body.year)
    except Exception as e:
        logger.exception("ensure submission failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create submission") from e


class ActionBody(BaseModel):
    action: str
    actor: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ShareBody(BaseModel):
    location_id: str | None = None
    expires_days: int | None = None


@router.post("/share")
def create_share_link(body: ShareBody, request: Request):
    """Mint a public live-link token (authenticated; actor from the session user)."""
    user = getattr(request.state, "user", None) or {}
    created_by = str(user.get("email") or user.get("id") or "unknown")
    location_id = (body.location_id or "").strip() or None
    if location_id and get_location_by_id(location_id) is None:
        raise HTTPException(status_code=404, detail="Unknown location_id")
    try:
        token, exp = create_share_token(created_by, location_id, body.expires_days)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {
        "token": token,
        "path": f"/api/v1/forecast-scorecard/share/{token}",
        "scope": "location" if location_id else "portfolio",
        "locationId": location_id,
        "expiresAt": exp.isoformat(),
    }


@router.get("/share/{token}", response_class=HTMLResponse)
def view_share_page(
    token: str,
    period: int | None = Query(default=None),
    week: int | None = Query(default=None),
    year: int | None = Query(default=None),
):
    """Public live scorecard page; access is granted by the signed token alone."""
    claims = verify_share_token(token)
    if claims is None:
        return HTMLResponse(render_invalid_link_page(), status_code=403)

    cur_p, cur_w, cur_y = svc.current_fiscal_week()
    p = period if period and 1 <= period <= 13 else cur_p
    w = week if week and 1 <= week <= 4 else cur_w
    y = year if year and 2020 <= year <= 2100 else cur_y

    try:
        payload = svc.build_week_scorecards(p, w, y)
        cards = payload["scorecards"]
        scope_label = "Weekly Labor Management"
        single = False
        if claims.get("scope") == "location" and claims.get("location_id"):
            loc_id = str(claims["location_id"])
            cards = [c for c in cards if c["location"]["id"] == loc_id]
            if not cards:
                return HTMLResponse(render_invalid_link_page(), status_code=404)
            scope_label = cards[0]["location"]["name"]
            single = True
        actuals = svc.build_actuals_scorecards([c["location"]["id"] for c in cards], p, w, y)
        html = render_share_page(
            scope_label=scope_label,
            cards=cards,
            actuals=actuals,
            meta=payload["meta"],
            base_path=f"/api/v1/forecast-scorecard/share/{token}",
            single_location=single,
        )
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})
    except Exception as e:
        logger.exception("share page render failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to render scorecard") from e


@router.post("/submissions/{submission_id}/action")
def apply_submission_action(submission_id: str, body: ActionBody):
    if not body.actor.strip():
        raise HTTPException(status_code=422, detail="actor is required")
    try:
        updated = svc.apply_action(submission_id, body.action, body.actor.strip(), body.payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("submission action failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to apply action") from e

    # Ping the next actor on Slack (best-effort; never blocks the action).
    try:
        loc = get_location_by_id(updated.get("locationId") or "")
        notify_stage_change(updated, body.action, body.actor.strip(), (loc or {}).get("name") or updated.get("locationId") or "")
    except Exception as e:
        logger.warning("labor workflow notification failed: %s", e)
    return updated
