"""Shared runtime-agent attribution helpers for CLI tools."""

from __future__ import annotations

import os
from collections.abc import Mapping


AGENT_ENV_VARS = ("AGENT_NAME", "BRIDGE_AGENT_NAME")


def default_agent_name(
    environ: Mapping[str, str] | None = None,
    *,
    fallback: str = "codex",
) -> str:
    env = environ if environ is not None else os.environ
    for key in AGENT_ENV_VARS:
        value = env.get(key, "").strip()
        if value:
            return value
    if env.get("CLAUDECODE", "").strip():
        return "claude"
    return fallback
