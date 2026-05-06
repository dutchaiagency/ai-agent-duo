"""Tests for tools/calendar_nudge.py."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import calendar_nudge as cn


def write_schedule(tmp_path: Path, rows: list[tuple[str, int, str, str, str]]) -> Path:
    schedule = tmp_path / "upcoming_calls.md"
    body = [
        "# Upcoming Calls (UTC)",
        "",
        "| start_utc | duration_min | counterparty | url | status |",
        "|-----------|--------------|--------------|-----|--------|",
    ]
    for start, dur, cp, url, status in rows:
        body.append(f"| {start} | {dur} | {cp} | {url} | {status} |")
    schedule.write_text("\n".join(body), encoding="utf-8")
    return schedule


def test_parse_schedule_skips_header_and_separator(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "Louis", "https://meet.jit.si/x", "confirmed")],
    )
    calls = cn.parse_schedule(schedule)
    assert len(calls) == 1
    assert calls[0].counterparty == "Louis"
    assert calls[0].duration_min == 20
    assert calls[0].status == "confirmed"
    assert calls[0].start_utc == datetime(2026, 5, 7, 15, 0, tzinfo=UTC)


def test_parse_schedule_lowercases_status(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "X", "https://x.invalid", "Confirmed")],
    )
    calls = cn.parse_schedule(schedule)
    assert calls[0].status == "confirmed"


def test_parse_schedule_skips_malformed_rows(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schedule = write_schedule(
        tmp_path,
        [
            ("2026-05-07T15:00:00Z", 20, "Good", "https://x.invalid", "confirmed"),
            ("not-a-date", 20, "Bad", "https://x.invalid", "confirmed"),
        ],
    )
    calls = cn.parse_schedule(schedule)
    assert len(calls) == 1
    assert calls[0].counterparty == "Good"


def test_parse_schedule_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        cn.parse_schedule(tmp_path / "nope.md")


def test_due_nudges_far_future(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "X", "https://x.invalid", "confirmed")],
    )
    call = cn.parse_schedule(schedule)[0]
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)  # 3h before
    assert cn.due_nudges(call, now) == []


def test_due_nudges_T30_window(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "X", "https://x.invalid", "confirmed")],
    )
    call = cn.parse_schedule(schedule)[0]
    # 30 min before exactly
    now = call.start_utc - timedelta(minutes=30)
    assert "T-30" in cn.due_nudges(call, now)
    # 27 min before still in window (25-35)
    now = call.start_utc - timedelta(minutes=27)
    assert "T-30" in cn.due_nudges(call, now)
    # 24 min before falls into the gap between T-30 and T-5
    now = call.start_utc - timedelta(minutes=24)
    assert cn.due_nudges(call, now) == []


def test_due_nudges_T5_window(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "X", "https://x.invalid", "confirmed")],
    )
    call = cn.parse_schedule(schedule)[0]
    now = call.start_utc - timedelta(minutes=5)
    assert "T-5" in cn.due_nudges(call, now)
    now = call.start_utc - timedelta(minutes=2)
    assert "T-5" in cn.due_nudges(call, now)


def test_due_nudges_inactive_status(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "X", "https://x.invalid", "missed")],
    )
    call = cn.parse_schedule(schedule)[0]
    now = call.start_utc - timedelta(minutes=30)
    # missed status -> no nudge even if in window
    assert cn.due_nudges(call, now) == []


def test_due_nudges_after_call(tmp_path: Path) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-05T14:00:00Z", 20, "X", "https://x.invalid", "confirmed")],
    )
    call = cn.parse_schedule(schedule)[0]
    now = datetime(2026, 5, 6, 9, 0, tzinfo=UTC)  # 19h later
    assert cn.due_nudges(call, now) == []


def test_run_idempotent_within_window(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "Louis", "https://meet.jit.si/x", "confirmed")],
    )
    state_path = tmp_path / "state.json"
    now = datetime(2026, 5, 7, 14, 30, tzinfo=UTC)  # T-30
    # First run in dry-run: prints, but does not persist state to disk
    cn.run(schedule, state_path, now, send=False)
    out = capsys.readouterr().out
    assert "T-30 for Louis" in out
    # Second dry-run: same output, state still unwritten
    cn.run(schedule, state_path, now, send=False)
    out = capsys.readouterr().out
    assert "T-30 for Louis" in out
    assert not state_path.exists()


def test_run_marks_sent_after_real_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "Louis", "https://meet.jit.si/x", "confirmed")],
    )
    state_path = tmp_path / "state.json"
    now = datetime(2026, 5, 7, 14, 30, tzinfo=UTC)
    sent_calls: list[str] = []

    def fake_send(text: str) -> tuple[bool, str]:
        sent_calls.append(text)
        return True, '{"message_id": 42}'

    monkeypatch.setattr(cn, "send_via_telegram", fake_send)
    cn.run(schedule, state_path, now, send=True)
    assert len(sent_calls) == 1
    assert "T-30 reminder" in sent_calls[0]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert any("T-30" in entry for entry in state["sent"])
    # Re-run: idempotent, no new send
    cn.run(schedule, state_path, now, send=True)
    assert len(sent_calls) == 1


def test_run_does_not_mark_sent_on_relay_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schedule = write_schedule(
        tmp_path,
        [("2026-05-07T15:00:00Z", 20, "Louis", "https://meet.jit.si/x", "confirmed")],
    )
    state_path = tmp_path / "state.json"
    now = datetime(2026, 5, 7, 14, 30, tzinfo=UTC)

    def failing_send(text: str) -> tuple[bool, str]:
        return False, "telegram exit 1: boom"

    monkeypatch.setattr(cn, "send_via_telegram", failing_send)
    cn.run(schedule, state_path, now, send=True)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state.get("sent") == []  # nothing marked


def test_build_nudge_text_contains_key_fields() -> None:
    call = cn.Call(
        start_utc=datetime(2026, 5, 7, 15, 0, tzinfo=UTC),
        duration_min=20,
        counterparty="Louis",
        url="https://meet.jit.si/x",
        status="confirmed",
        raw="(test)",
    )
    now = call.start_utc - timedelta(minutes=30)
    text = cn.build_nudge_text(call, "T-30", now)
    assert "T-30 reminder" in text
    assert "Louis" in text
    assert "https://meet.jit.si/x" in text
    assert "20 min" in text  # duration
    assert "2026-05-07 15:00" in text


def test_main_dry_run_with_real_schedule_file() -> None:
    """Smoke-test: real ops/upcoming_calls.md parses cleanly."""
    schedule = ROOT / "ops" / "upcoming_calls.md"
    if not schedule.exists():
        pytest.skip("ops/upcoming_calls.md not present in repo")
    calls = cn.parse_schedule(schedule)
    # At least the missed Wetware row should parse.
    assert any("Louis" in c.counterparty for c in calls)
