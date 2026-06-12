"""Signed share tokens for the public Forecast Scorecard live link.

A share token grants read-only access to the rendered scorecard page at
``GET /api/v1/forecast-scorecard/share/{token}`` without a Leonardo login.
Tokens are HS256 JWTs with a dedicated audience so they can never be used as
Leonardo session tokens (and vice versa — session tokens carry no ``aud``).
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
ISSUER = "leonardo"
AUDIENCE = "forecast-scorecard-share"

DEFAULT_TTL_DAYS = int(os.getenv("FORECAST_SCORECARD_SHARE_TTL_DAYS", "90"))
MAX_TTL_DAYS = 365


def _secret() -> str:
    s = os.getenv("FORECAST_SCORECARD_SHARE_SECRET", "").strip() or os.getenv("JWT_SECRET_KEY", "").strip()
    if not s or s == "your-secret-key-change-in-production":
        raise RuntimeError(
            "Set FORECAST_SCORECARD_SHARE_SECRET (or JWT_SECRET_KEY) to enable forecast scorecard share links"
        )
    return s


def create_share_token(
    created_by: str,
    location_id: str | None = None,
    expires_days: int | None = None,
) -> tuple[str, datetime]:
    """Mint a share token. ``location_id=None`` shares the full portfolio view."""
    ttl_days = min(int(expires_days or DEFAULT_TTL_DAYS), MAX_TTL_DAYS)
    now = datetime.now(UTC)
    exp = now + timedelta(days=max(ttl_days, 1))
    payload: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": exp,
        "created_by": (created_by or "").strip().lower(),
        "scope": "location" if location_id else "portfolio",
        "location_id": (location_id or "").strip() or None,
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM), exp


def verify_share_token(token: str) -> dict[str, Any] | None:
    """Decode a share token; None when invalid/expired."""
    try:
        return jwt.decode(
            token,
            _secret(),
            algorithms=[JWT_ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
        )
    except jwt.ExpiredSignatureError:
        logger.info("forecast scorecard share token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("invalid forecast scorecard share token: %s", e)
        return None
