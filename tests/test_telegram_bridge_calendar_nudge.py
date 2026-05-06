"""Tests for telegram_bridge calendar nudge hookup."""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = ROOT / "ops" / "telegram_bridge.py"


def load_telegram_bridge() -> ModuleType:
    if "secret_vault" not in sys.modules:
        secret_vault_stub = ModuleType("secret_vault")

        class SecretVault:  # pragma: no cover - only needed for import-time wiring
            pass

        secret_vault_stub.SecretVault = SecretVault
        sys.modules["secret_vault"] = secret_vault_stub

    spec = importlib.util.spec_from_file_location("telegram_bridge_under_test", BRIDGE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calendar_nudge_needs_log_for_fired_summary() -> None:
    bridge = load_telegram_bridge()
    assert bridge.calendar_nudge_needs_log("summary: fired=1 already_sent=0", "") is True


def test_calendar_nudge_needs_log_for_stderr() -> None:
    bridge = load_telegram_bridge()
    assert bridge.calendar_nudge_needs_log("summary: fired=0 already_sent=0", "!! send failed") is True


def test_calendar_nudge_suppresses_quiet_noop() -> None:
    bridge = load_telegram_bridge()
    assert bridge.calendar_nudge_needs_log("summary: fired=0 already_sent=0", "") is False


def test_calendar_to_telegram_runs_send_mode_and_logs_fired(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = load_telegram_bridge()
    now = datetime.datetime(2026, 5, 7, 14, 30, tzinfo=datetime.UTC)
    calls: list[tuple[Path, Path, datetime.datetime, bool]] = []

    def fake_run(schedule: Path, state: Path, run_now: datetime.datetime, send: bool) -> int:
        calls.append((schedule, state, run_now, send))
        print("--- T-30 for Louis ---")
        print("summary: fired=1 already_sent=0 inactive=0 out_of_window=0")
        return 0

    monkeypatch.setattr(bridge.calendar_nudge, "run", fake_run)

    assert bridge.calendar_to_telegram(now=now) == 0
    assert calls == [
        (
            bridge.calendar_nudge.DEFAULT_SCHEDULE,
            bridge.calendar_nudge.DEFAULT_STATE,
            now,
            True,
        )
    ]
    out = capsys.readouterr().out
    assert "[bridge] calendar_nudge output:" in out
    assert "T-30 for Louis" in out


def test_calendar_to_telegram_suppresses_noop_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = load_telegram_bridge()

    def fake_run(schedule: Path, state: Path, run_now: datetime.datetime, send: bool) -> int:
        print("summary: fired=0 already_sent=0 inactive=1 out_of_window=0")
        return 0

    monkeypatch.setattr(bridge.calendar_nudge, "run", fake_run)

    assert bridge.calendar_to_telegram() == 0
    assert capsys.readouterr().out == ""


def test_calendar_to_telegram_contains_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bridge = load_telegram_bridge()

    def fake_run(schedule: Path, state: Path, run_now: datetime.datetime, send: bool) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(bridge.calendar_nudge, "run", fake_run)

    assert bridge.calendar_to_telegram() == 0
    assert "calendar_nudge error: boom" in capsys.readouterr().out
