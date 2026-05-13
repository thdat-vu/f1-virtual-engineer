"""Supabase JWT verification + FastAPI deps for optional/required user identity.

Public surface:
- ``verify_supabase_jwt(token)`` — decode and verify the token. Supabase projects
  issue asymmetric (ES256/RS256) tokens signed by the project's JWT Signing Keys;
  legacy projects still emit HS256 tokens signed by ``SUPABASE_JWT_SECRET``. We
  try JWKS first, then fall back to the legacy symmetric secret when present.
- ``get_optional_user_id(request)`` — FastAPI dep returning user id or None.
- ``get_required_user_id(request)`` — FastAPI dep raising 401 on missing/invalid token.

Design notes:
- Fail-closed mirrors ``core.llm``: any decode/verify error returns None for the
  optional path, so callers can keep serving anonymous requests.
- The required dep is reserved for endpoints that are themselves auth-gated
  (e.g. ``GET /analyze/history``). Core features stay anonymous-friendly.
- JWKS is fetched lazily and cached by ``PyJWKClient`` — a Supabase key rotation
  is picked up on the next request once the cached entry expires.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in production
    pass


_logger = logging.getLogger(__name__)

# Cache the JWKS client per SUPABASE_URL so repeated verifies share the
# in-memory key cache. PyJWKClient caches fetched keys for an hour by
# default, which matches the access-token lifetime.
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwt_secret() -> str | None:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    return secret or None


def _get_supabase_url() -> str | None:
    url = os.environ.get("SUPABASE_URL")
    return url.rstrip("/") if url else None


def _get_jwks_client() -> PyJWKClient | None:
    """Return a cached PyJWKClient for the current SUPABASE_URL, or None when unset."""
    base_url = _get_supabase_url()
    if not base_url:
        return None
    client = _jwks_clients.get(base_url)
    if client is None:
        jwks_url = f"{base_url}/auth/v1/.well-known/jwks.json"
        client = PyJWKClient(jwks_url, cache_keys=True)
        _jwks_clients[base_url] = client
    return client


def _verify_via_jwks(token: str) -> dict[str, Any] | None:
    client = _get_jwks_client()
    if client is None:
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg not in {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"}:
            # Don't let the symmetric fallback path masquerade as an asymmetric verify.
            return None
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience="authenticated",
        )
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.debug("Supabase JWT verification via JWKS failed", exc_info=True)
        return None
    return claims if isinstance(claims, dict) and claims.get("sub") else None


def _verify_via_legacy_secret(token: str) -> dict[str, Any] | None:
    secret = _get_jwt_secret()
    if not secret:
        return None
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.debug("Supabase JWT verification via legacy HS256 failed", exc_info=True)
        return None
    return claims if isinstance(claims, dict) and claims.get("sub") else None


def verify_supabase_jwt(token: str) -> dict[str, Any] | None:
    """Verify a Supabase-issued JWT. Return claims dict or None on any failure.

    Tries JWKS (ES256/RS256 — the new JWT Signing Keys path) first, falls back
    to the legacy symmetric ``SUPABASE_JWT_SECRET`` (HS256) when JWKS is not
    configured or the token header specifies HS256.
    """
    if not token:
        return None
    # Fast path: inspect the header to decide which verifier to try first.
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except Exception:  # noqa: BLE001 — malformed token, treat as anonymous.
        return None
    if alg == "HS256":
        return _verify_via_legacy_secret(token)
    claims = _verify_via_jwks(token)
    if claims is not None:
        return claims
    return _verify_via_legacy_secret(token)


def _reset_clients_for_tests() -> None:
    """Drop the JWKS client cache — used by tests to keep runs isolated."""
    _jwks_clients.clear()


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
