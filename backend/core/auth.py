"""Supabase JWT verification + FastAPI deps for optional/required user identity.

Public surface:
- ``verify_supabase_jwt(token)`` — decode and verify HS256 against SUPABASE_JWT_SECRET.
- ``get_optional_user_id(request)`` — FastAPI dep returning user id or None.
- ``get_required_user_id(request)`` — FastAPI dep raising 401 on missing/invalid token.

Design notes:
- Fail-closed mirrors ``core.llm``: any decode/verify error returns None for the
  optional path, so callers can keep serving anonymous requests.
- The required dep is reserved for endpoints that are themselves auth-gated
  (e.g. ``GET /analyze/history``). Core features stay anonymous-friendly.
- Reads ``SUPABASE_JWT_SECRET`` lazily on first call so importing this module
  never blows up when the secret is missing in dev/CI.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import jwt
from fastapi import HTTPException, Request, status

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in production
    pass


_logger = logging.getLogger(__name__)


def _get_jwt_secret() -> str | None:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    return secret or None


def verify_supabase_jwt(token: str) -> dict[str, Any] | None:
    """Verify a Supabase-issued HS256 JWT. Return claims dict or None on any failure."""
    if not token:
        return None
    secret = _get_jwt_secret()
    if not secret:
        return None
    try:
        # Supabase tokens are signed HS256 with the project's JWT secret. The
        # default ``aud`` claim is "authenticated"; pin it so a token minted for
        # another audience can't be used here.
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.debug("Supabase JWT verification failed", exc_info=True)
        return None
    if not isinstance(claims, dict) or not claims.get("sub"):
        return None
    return claims


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_optional_user_id(request: Request) -> str | None:
    """Return the verified ``sub`` claim, or None when no/invalid token is present.

    Use for endpoints that work anonymously and only need the user id when
    available (e.g. opt-in persistence on ``/analyze``).
    """
    token = _extract_bearer(request)
    if not token:
        return None
    claims = verify_supabase_jwt(token)
    if not claims:
        return None
    return str(claims["sub"])


def get_required_user_id(request: Request) -> str:
    """Return the verified ``sub`` claim or raise 401.

    Use for endpoints that are themselves auth-gated (e.g. history listing).
    """
    token = _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = verify_supabase_jwt(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(claims["sub"])
