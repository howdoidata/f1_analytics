"""Reusable Status Badge rendering primitive for any controlled status value.

Renders a status as a stable, upper-cased marker derived only from the
status's own value, never a separate label lookup, so it can never drift
into a synonym. When a caller supplies a reason, it is shown next to the
badge rather than silently dropped.

This module is deliberately stdlib-only and generic over any `Enum` or plain
string status value — it has no opinion on which controlled vocabulary a
status belongs to, so it can decorate any status-shaped field in the bundle
without importing or knowing about that field's vocabulary.
"""

from __future__ import annotations

from enum import Enum


def render_status_badge(status: object, *, reason: str | None = None) -> str:
    """Render one status value as a bracketed marker, with an optional reason.

    `status` may be an `Enum` member (its `.value` is used) or a plain string;
    either way the marker is `f"[{str(value).upper()}]"`, derived only from the
    status's own value. When `reason` is non-blank (a whitespace-only reason
    counts as absent), its stripped text is appended after an em dash;
    otherwise the bare marker is returned.
    """
    value = status.value if isinstance(status, Enum) else status
    marker = f"[{str(value).upper()}]"
    if reason is not None and reason.strip():
        return f"{marker} — {reason.strip()}"
    return marker


__all__ = ["render_status_badge"]
