"""Gemini Flash wrapper for natural-language rationale generation.

Public surface: ``generate_rationale(context)``. Returns the generated text,
or ``None`` when the LLM is unavailable for any reason — the caller falls
back to the deterministic template in ``format_response_node``.

Design notes:
- Fail-closed: every code path that can't produce real LLM output returns None.
- Lazy init: importing this module never reaches out to the API; the genai
  client is configured on first call and reused thereafter.
- 60s in-memory cache keyed by SHA-256 of the JSON-serialised context.
  Single-process MVP — mirrors the slowapi single-worker stance from #88.
- The system prompt is closed: the model is instructed to use only the facts
  in the supplied context and not to invent lap numbers, drivers, or events.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in production
    pass


_logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 60
_cache: dict[str, tuple[float, str]] = {}

_genai_module = None  # set on first successful configure
_configured_key: str | None = None


_SYSTEM_PROMPT = (
    "You are a Formula 1 race engineer. Summarise the session context for a strategist "
    "in 1-2 short sentences. RULES: (1) Use only the numbers, drivers, events, and lap "
    "values supplied in the JSON context — do NOT invent or extrapolate. (2) If a value "
    "is missing, omit that detail rather than guess. (3) No markdown, no bullet points, "
    "no preamble like 'Here is the summary'. Just the engineer's call. "
    "(4) When the context contains a non-empty `citations` list, you MAY ground a "
    "regulation claim by quoting the citation's `title` or `section` verbatim — never "
    "paraphrase the regulation text or invent article numbers."
)


def _context_key(context: dict[str, Any], *, namespace: str = "rationale") -> str:
    payload = json.dumps({"_ns": namespace, **context}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_configured() -> Any | None:
    """Return the configured ``google.generativeai`` module, or None on failure."""
    global _genai_module, _configured_key

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    if _genai_module is not None and _configured_key == api_key:
        return _genai_module

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        _logger.warning("google-generativeai not installed; falling back to template")
        return None

    try:
        genai.configure(api_key=api_key)
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to configure Gemini client", exc_info=True)
        return None

    _genai_module = genai
    _configured_key = api_key
    return genai


def generate_rationale(context: dict[str, Any], *, model: str = "gemini-2.0-flash") -> str | None:
    """Generate a natural-language rationale, or return None to fall back to template."""
    cache_key = _context_key(context)
    cached = _cache.get(cache_key)
    if cached is not None:
        ts, text = cached
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return text

    genai = _ensure_configured()
    if genai is None:
        return None

    try:
        client = genai.GenerativeModel(model_name=model, system_instruction=_SYSTEM_PROMPT)
        prompt = f"Session context (JSON):\n{json.dumps(context, default=str, indent=2)}"
        response = client.generate_content(prompt)
        text = (getattr(response, "text", None) or "").strip()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Gemini call failed; falling back to template", exc_info=True)
        return None

    if not text:
        return None

    _cache[cache_key] = (time.time(), text)
    return text


def generate_structured(
    user_payload: dict[str, Any],
    *,
    system_prompt: str,
    model: str = "gemini-2.0-flash",
) -> dict[str, Any] | None:
    """Call Gemini and parse the response as JSON. Returns dict or None.

    Mirrors ``generate_rationale``'s fail-closed contract: missing API key,
    network error, JSON parse error, or empty completion all return None so
    the caller can fall back to a deterministic response. The cache is shared
    with ``generate_rationale`` but namespaced by the system prompt so a
    radio classification can't collide with a rationale string.
    """
    cache_key = _context_key(
        {"prompt": system_prompt, "payload": user_payload},
        namespace="structured",
    )
    cached = _cache.get(cache_key)
    if cached is not None:
        ts, text = cached
        if time.time() - ts < _CACHE_TTL_SECONDS:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Cache contained malformed JSON — drop it and fall through.
                _cache.pop(cache_key, None)

    genai = _ensure_configured()
    if genai is None:
        return None

    try:
        client = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        prompt = f"Input (JSON):\n{json.dumps(user_payload, default=str, indent=2)}"
        response = client.generate_content(prompt)
        text = (getattr(response, "text", None) or "").strip()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Gemini structured call failed; caller will fall back", exc_info=True)
        return None

    if not text:
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        _logger.warning("Gemini structured response was not valid JSON: %r", text[:200])
        return None

    if not isinstance(parsed, dict):
        return None

    _cache[cache_key] = (time.time(), text)
    return parsed


def _reset_cache_for_tests() -> None:
    """Drop the cache. Used by tests to keep runs deterministic."""
    _cache.clear()
