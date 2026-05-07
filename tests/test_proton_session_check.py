from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools.email_lead_watch import EmailLeadStatus
from tools.proton_session_check import (
    EmailProbe,
    assess,
    build_bridge_body,
    default_report_path,
    due_followups,
    latest_bridge_nudge_at,
    render_report,
    send_bridge_message,
)


NOW = datetime(2026, 5, 7, 0, 35, tzinfo=UTC)


def _status(
    state: str,
    lead: str,
    cutoff: str = "2026-05-06T12:00Z",
    policy: str = "72h-bump",
) -> EmailLeadStatus:
    return EmailLeadStatus(
        state=state,
        lead=lead,
        owner="codex",
        sent_at="2026-05-03T12:00Z",
        cutoff_at=cutoff,
        hours_to_cutoff=-12.5,
        next_action="Check inbox before follow-up.",
        policy=policy,
        note="",
    )


def _blocked_probe() -> EmailProbe:
    return EmailProbe(
        status="blocked",
        returncode=2,
        blocked=True,
        detail="EMAIL_BLOCKED detected",
    )


def test_assess_allows_nudge_when_blocked_and_two_followups_due() -> None:
    statuses = [
        _status("follow_up_due", "lead A"),
        _status("follow_up_due", "lead B"),
        _status("watching", "lead C"),
    ]

    assessment = assess(
        statuses,
        _blocked_probe(),
        now=NOW,
        min_due=2,
        cooldown=timedelta(hours=12),
        state={},
    )

    assert assessment.nudge_needed is True
    assert assessment.nudge_allowed is True
    assert assessment.due_count == 2
    assert "lead A" in assessment.due_signature


def test_assess_suppresses_same_due_set_inside_state_cooldown() -> None:
    statuses = [_status("follow_up_due", "lead A"), _status("follow_up_due", "lead B")]
    first = assess(
        statuses,
        _blocked_probe(),
        now=NOW,
        min_due=2,
        cooldown=timedelta(hours=12),
        state={},
    )

    assessment = assess(
        statuses,
        _blocked_probe(),
        now=NOW + timedelta(hours=1),
        min_due=2,
        cooldown=timedelta(hours=12),
        state={
            "last_nudge_ts": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_due_signature": first.due_signature,
        },
    )

    assert assessment.nudge_needed is True
    assert assessment.nudge_allowed is False
    assert assessment.cooldown_source == "state"


def test_latest_bridge_nudge_detects_recent_proton_followup_ping(tmp_path: Path) -> None:
    db = tmp_path / "messages.db"
    sent_at = NOW - timedelta(hours=2)
    send_bridge_message(
        db,
        sender="claude",
        recipient="leon",
        body="Proton inbox refresh: EMAIL_BLOCKED while follow-up-window has 6 leads.",
        now=sent_at,
    )

    latest = latest_bridge_nudge_at(db, NOW, timedelta(hours=12))

    assert latest == sent_at


def test_latest_bridge_nudge_ignores_unrelated_bridge_messages(tmp_path: Path) -> None:
    db = tmp_path / "messages.db"
    send_bridge_message(
        db,
        sender="codex",
        recipient="leon",
        body="GitHub PR watch found no actionable review.",
        now=NOW - timedelta(hours=1),
    )

    assert latest_bridge_nudge_at(db, NOW, timedelta(hours=12)) is None


def test_send_bridge_message_inserts_unread_row(tmp_path: Path) -> None:
    db = tmp_path / "messages.db"
    msg_id = send_bridge_message(
        db,
        sender="proton-session-check",
        recipient="leon",
        body="Proton EMAIL_BLOCKED follow_up_due.",
        now=NOW,
    )

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT id, from_agent, to_agent, body, read FROM messages"
        ).fetchone()

    assert row == (msg_id, "proton-session-check", "leon", "Proton EMAIL_BLOCKED follow_up_due.", 0)


def test_bridge_body_lists_due_leads_and_report_path() -> None:
    statuses = [_status("follow_up_due", "lead A"), _status("follow_up_due", "lead B")]
    assessment = assess(
        statuses,
        _blocked_probe(),
        now=NOW,
        min_due=2,
        cooldown=timedelta(hours=12),
        state={},
    )

    body = build_bridge_body(assessment, due_followups(statuses), Path("state/report.md"))

    assert "2 email leads" in body
    assert "state/report.md" in body
    assert "lead A (72h-bump)" in body


def test_render_report_surfaces_policy_column() -> None:
    statuses = [
        _status("follow_up_due", "lead A", policy="72h-bump"),
        _status("watching", "lead B", cutoff="2026-05-10T12:00Z", policy="7d-if-reply-only"),
    ]
    assessment = assess(
        statuses,
        _blocked_probe(),
        now=NOW,
        min_due=2,
        cooldown=timedelta(hours=12),
        state={},
    )

    report = render_report(assessment, statuses, _blocked_probe())

    assert "| State | Lead | Owner | Cutoff | Timer | Policy | Next action |" in report
    assert "7d-if-reply-only" in report


def test_default_report_path_uses_seconds_to_avoid_same_minute_overwrite(tmp_path: Path) -> None:
    path = default_report_path(tmp_path, "codex", datetime(2026, 5, 7, 7, 38, 15, tzinfo=UTC))

    assert path.name == "proton-session-check-2026-05-07-codex-073815.md"
