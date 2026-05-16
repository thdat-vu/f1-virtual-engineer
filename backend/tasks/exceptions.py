"""Failure taxonomy for the async task pipeline (#139 PR2).

Two classes, one rule of thumb:

- ``TransientError`` — something we expect Celery to retry. Network
  blips, rate-limit hits, upstream timeouts. Listed in each task's
  ``autoretry_for`` tuple so retries happen automatically with
  exponential backoff.
- ``PermanentError`` — something that won't get better by waiting.
  Schema mismatch, malformed input, deterministic bug. Skips retry
  entirely and lands in the DLQ on the first failure so a human can
  look at it.

A bare ``Exception`` from a task is treated as permanent. Be explicit
when you mean transient.
"""

from __future__ import annotations


class TaskError(Exception):
    """Base class so callers can `except TaskError` if they want both."""


class TransientError(TaskError):
    """Signal: retry me with backoff, this is probably temporary."""


class PermanentError(TaskError):
    """Signal: do not retry. Send straight to the DLQ for inspection."""


__all__ = ["TaskError", "TransientError", "PermanentError"]
