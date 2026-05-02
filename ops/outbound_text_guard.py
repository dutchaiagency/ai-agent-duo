"""Shared guards for text that will be sent to public outbound surfaces."""

from __future__ import annotations

SUSPICIOUS_ESCAPE_MARKERS = (
    "\\00",
    "\\0",
    "\\/",
    "</" + "content>",
    "</" + "invoke>",
    "</" + "parameter>",
)


def validate_outbound_text(
    text: str,
    *,
    label: str = "outbound text",
    ascii_only: bool = False,
    allow_empty: bool = False,
) -> str | None:
    if not isinstance(text, str):
        return f"{label} must be text."
    if not allow_empty and not text.strip():
        return f"{label} is empty."
    for marker in SUSPICIOUS_ESCAPE_MARKERS:
        if marker in text:
            return f"Suspicious escape marker found in {label}: {marker}"
    if ascii_only:
        try:
            text.encode("ascii")
        except UnicodeEncodeError:
            return f"{label} contains non-ASCII characters; use plain ASCII for predictable browser input."
    return None
