"""Slack notifications for the Weekly Labor Management workflow.

Best-effort: every stage change pings the configured Slack channel so the next
actor never has to poll the page. No-op unless both SLACK_BOT_TOKEN and
LABOR_WORKFLOW_SLACK_CHANNEL are set. Failures are logged, never raised — a
missed ping must not block an approval.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_API_BASE = "https://slack.com/api"
CHANNEL = (os.getenv("LABOR_WORKFLOW_SLACK_CHANNEL") or "").strip()
FRONTEND_BASE = (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
PAGE_PATH = "/performance/food-beverage/labor-management"


def _usd(v: Any) -> str:
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _message(sub: dict[str, Any], action: str, actor: str, location_name: str) -> str | None:
    week_tag = f"P{sub.get('period')} W{sub.get('week')} ({sub.get('weekStart')})"
    link = f"{FRONTEND_BASE}{PAGE_PATH}"
    status = sub.get("status")
    if action == "submit":
        return (
            f"📋 *{location_name}* {week_tag}: forecast {_usd(sub.get('submittedForecastRevenue'))} "
            f"set & submitted by {actor} — *Ross to approve & return labor targets* → {link}"
        )
    if action == "issue_targets":
        return (
            f"🎯 *{location_name}* {week_tag}: forecast approved & targets returned by {actor} — "
            f"FOH {_usd(sub.get('guidanceFohLabor'))} · BOH {_usd(sub.get('guidanceBohLabor'))} — "
            f"*GM to build the TeamWork schedule* → {link}"
        )
    if action == "submit_schedule":
        return (
            f"🗓 *{location_name}* {week_tag}: schedule built — {actor} requests approval — "
            f"FOH {_usd(sub.get('scheduledFohLabor'))} · BOH {_usd(sub.get('scheduledBohLabor'))} — "
            f"*Ross to approve* → {link}"
        )
    if action == "approve_schedule":
        return f"✅ *{location_name}* {week_tag}: schedule is approved by {actor} — *GM to publish in TeamWork* → {link}"
    if action == "publish":
        return f"📣 *{location_name}* {week_tag}: schedule *published* in TeamWork by {actor} — live to the team."
    if action == "reject":
        reason = sub.get("rejectionReason") or "no reason given"
        return (
            f"↩️ *{location_name}* {week_tag}: rejected by {actor} "
            f"(back to {status}) — “{reason}” → {link}"
        )
    return None


def notify_stage_change(sub: dict[str, Any], action: str, actor: str, location_name: str) -> None:
    """Post the stage change to Slack; silent no-op when unconfigured."""
    if not SLACK_BOT_TOKEN or not CHANNEL:
        return
    text = _message(sub, action, actor, location_name)
    if not text:
        return
    try:
        with httpx.Client(timeout=10) as client:
            res = client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"channel": CHANNEL, "text": text},
            )
            data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
            if not (res.status_code == 200 and data.get("ok")):
                logger.warning("labor workflow Slack post failed: %s %s", res.status_code, data)
    except Exception as e:
        logger.warning("labor workflow Slack post exception: %s", e)
