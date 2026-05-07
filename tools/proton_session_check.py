#!/usr/bin/env python3
"""Detect when a blocked Proton session is holding due email follow-ups."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.agent_identity import default_agent_name  # noqa: E402
from tools.email_lead_watch import (  # noqa: E402
    DEFAULT_SUPPRESSION_LIST,
    EmailLeadStatus,
    classify_leads,
    load_suppressed_emails,
    md_escape,
    parse_email_leads,
    parse_now,
)

DEFAULT_PIPELINE = Path("ops/outbound_pipeline.md")
DEFAULT_STATE = Path("state/proton-session-check.json")
DEFAULT_BRIDGE_DB = Path(
    os.environ.get(
        "BRIDGE_DB",
        "C:/Users/leonv/assistant/projecten/agent-bridge/messages.db",
    )
)
DEFAULT_MIN_DUE = 2
DEFAULT_COOLDOWN_HOURS = 12.0
PROTON_NUDGE_CORE_TERMS = ("proton", "email_blocked")
PROTON_NUDGE_FOLLOWUP_TERMS = ("follow_up_due", "follow-up", "followup", "follow up")


@dataclass(frozen=True)
class EmailProbe:
    status: str
    returncode: int
    blocked: bool
    detail: str


@dataclass(frozen=True)
class ProtonSessionAssessment:
    generated_at: str
    probe_status: str
    due_count: int
    min_due: int
    due_signature: str
    nudge_needed: bool
    nudge_allowed: bool
    cooldown_source: str
    reason: str


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def run_email_probe(timeout_seconds: int = 60) -> EmailProbe:
    command = [
        sys.executable,
        str(ROOT / "ops" / "email_reader.py"),
        "--unread",
        "--exclude-noise",
        "--limit",
        "10",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return EmailProbe(
            status="timeout",
            returncode=124,
            blocked=False,
            detail=f"email_reader timed out after {exc.timeout}s",
        )
    except OSError as exc:
        return EmailProbe(
            status="error",
            returncode=127,
            blocked=False,
            detail=f"email_reader failed to start: {exc}",
        )

    combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    blocked = result.returncode == 2 and "EMAIL_BLOCKED" in combined
    if blocked:
        status = "blocked"
    elif result.returncode == 0:
        status = "ok"
    else:
        status = "error"
    detail = "EMAIL_BLOCKED detected" if blocked else combined[:240]
    return EmailProbe(
        status=status,
        returncode=result.returncode,
        blocked=blocked,
        detail=detail,
    )


def load_email_statuses(
    pipeline_path: Path,
    suppression_list: Path,
    now: datetime,
) -> list[EmailLeadStatus]:
    leads = parse_email_leads(pipeline_path.read_text(encoding="utf-8"))
    suppressed = load_suppressed_emails(suppression_list)
    return classify_leads(leads, now=now, suppressed_emails=suppressed)


def due_followups(statuses: Sequence[EmailLeadStatus]) -> list[EmailLeadStatus]:
    return [status for status in statuses if status.state == "follow_up_due"]


def due_signature(due: Sequence[EmailLeadStatus]) -> str:
    labels = sorted(f"{status.lead}|{status.cutoff_at}" for status in due)
    return "\n".join(labels)


def load_json_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def state_cooldown_active(
    state: dict,
    now: datetime,
    cooldown: timedelta,
    signature: str,
) -> bool:
    last = parse_utc_timestamp(state.get("last_nudge_ts"))
    if last is None or now - last >= cooldown:
        return False
    return state.get("last_due_signature") == signature


def bridge_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            body TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def latest_bridge_nudge_at(
    bridge_db: Path,
    now: datetime,
    cooldown: timedelta,
) -> datetime | None:
    if not bridge_db.exists():
        return None
    try:
        conn = sqlite3.connect(bridge_db)
    except sqlite3.Error:
        return None
    with conn:
        try:
            rows = conn.execute(
                """
                SELECT ts, body
                FROM messages
                WHERE to_agent='leon'
                ORDER BY id DESC
                LIMIT 80
                """
            ).fetchall()
        except sqlite3.Error:
            return None

    for ts_value, body in rows:
        text = (body or "").lower()
        if not all(term in text for term in PROTON_NUDGE_CORE_TERMS):
            continue
        if not any(term in text for term in PROTON_NUDGE_FOLLOWUP_TERMS):
            continue
        ts = parse_utc_timestamp(ts_value)
        if ts is not None and ts <= now and now - ts < cooldown:
            return ts
    return None


def assess(
    statuses: Sequence[EmailLeadStatus],
    probe: EmailProbe,
    *,
    now: datetime,
    min_due: int,
    cooldown: timedelta,
    state: dict | None = None,
    recent_bridge_nudge_at: datetime | None = None,
) -> ProtonSessionAssessment:
    due = due_followups(statuses)
    signature = due_signature(due)
    nudge_needed = probe.blocked and len(due) >= min_due
    cooldown_source = ""
    nudge_allowed = nudge_needed
    if nudge_needed and state_cooldown_active(state or {}, now, cooldown, signature):
        nudge_allowed = False
        cooldown_source = "state"
    if nudge_needed and recent_bridge_nudge_at is not None:
        nudge_allowed = False
        cooldown_source = "bridge"

    if probe.status == "ok":
        reason = "Proton inbox is readable; no session-refresh nudge needed."
    elif not probe.blocked:
        reason = f"Email probe returned {probe.status}; inspect without sending a Proton nudge."
    elif len(due) < min_due:
        reason = f"Proton is blocked, but only {len(due)} follow-up(s) are due."
    elif cooldown_source == "bridge":
        reason = "Recent bridge message to Leon already covered Proton follow_up_due blockage."
    elif cooldown_source == "state":
        reason = "Same due lead set was already nudged inside the cooldown window."
    else:
        reason = f"Proton is blocked while {len(due)} email follow-up(s) are due."

    return ProtonSessionAssessment(
        generated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        probe_status=probe.status,
        due_count=len(due),
        min_due=min_due,
        due_signature=signature,
        nudge_needed=nudge_needed,
        nudge_allowed=nudge_allowed,
        cooldown_source=cooldown_source,
        reason=reason,
    )


def format_timer(hours_to_cutoff: float | None) -> str:
    if hours_to_cutoff is None:
        return "-"
    if hours_to_cutoff >= 0:
        return f"{hours_to_cutoff:.1f}h remaining"
    return f"{abs(hours_to_cutoff):.1f}h overdue"


def render_report(
    assessment: ProtonSessionAssessment,
    statuses: Sequence[EmailLeadStatus],
    probe: EmailProbe,
) -> str:
    decision = "send_nudge" if assessment.nudge_allowed else "no_nudge"
    lines = [
        f"# Proton Session Check - {assessment.generated_at.replace('T', ' ').replace(':00Z', ' UTC')}",
        "",
        f"Decision: `{decision}`",
        f"Reason: {assessment.reason}",
        f"Probe: `{probe.status}` (return code {probe.returncode}; {probe.detail})",
        f"Due follow-ups: {assessment.due_count} (threshold {assessment.min_due})",
        "",
        "| State | Lead | Owner | 72h cutoff | Timer | Next action |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for status in statuses:
        if status.state not in {"follow_up_due", "watching", "suppressed"}:
            continue
        lines.append(
            "| {state} | {lead} | {owner} | {cutoff} | {timer} | {action} |".format(
                state=status.state,
                lead=md_escape(status.lead),
                owner=md_escape(status.owner),
                cutoff=status.cutoff_at,
                timer=format_timer(status.hours_to_cutoff),
                action=md_escape(status.next_action),
            )
        )
    return "\n".join(lines) + "\n"


def default_report_path(state_dir: Path, agent: str, now: datetime) -> Path:
    stamp = now.strftime("%Y-%m-%d")
    hhmmss = now.strftime("%H%M%S")
    return state_dir / f"proton-session-check-{stamp}-{agent}-{hhmmss}.md"


def build_bridge_body(
    assessment: ProtonSessionAssessment,
    due: Sequence[EmailLeadStatus],
    report_path: Path | None,
) -> str:
    report = report_path.as_posix() if report_path is not None else "(no report file)"
    lead_lines = "\n".join(f"- {status.lead}" for status in due[:8])
    if len(due) > 8:
        lead_lines += f"\n- ... plus {len(due) - 8} more"
    return (
        "Proton inbox-refresh nodig: "
        f"{assessment.due_count} email leads staan op follow_up_due, maar "
        "ops/email_reader.py geeft EMAIL_BLOCKED.\n\n"
        "Actie: refresh .secrets/proton_session.pickle via browser-backed "
        "Proton login. Daarna kunnen wij inbox checken en de follow-ups veilig "
        "sturen zonder blind te mailen.\n\n"
        f"State: {report}\n\n"
        f"Due leads:\n{lead_lines}"
    )


def send_bridge_message(
    bridge_db: Path,
    *,
    sender: str,
    recipient: str,
    body: str,
    now: datetime,
) -> int:
    bridge_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(bridge_db) as conn:
        bridge_schema(conn)
        cur = conn.execute(
            "INSERT INTO messages (ts, from_agent, to_agent, body, read) VALUES (?, ?, ?, ?, 0)",
            (now.isoformat(timespec="seconds"), sender, recipient, body),
        )
        return int(cur.lastrowid)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", type=Path, default=DEFAULT_PIPELINE)
    parser.add_argument("--suppression-list", type=Path, default=DEFAULT_SUPPRESSION_LIST)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--state-dir", type=Path, help="Write timestamped markdown report.")
    parser.add_argument("--write", type=Path, help="Write report to this exact path.")
    parser.add_argument("--bridge-db", type=Path, default=DEFAULT_BRIDGE_DB)
    parser.add_argument("--agent", default=default_agent_name())
    parser.add_argument("--sender", default="proton-session-check")
    parser.add_argument("--recipient", default="leon")
    parser.add_argument("--min-due", type=int, default=DEFAULT_MIN_DUE)
    parser.add_argument("--cooldown-hours", type=float, default=DEFAULT_COOLDOWN_HOURS)
    parser.add_argument("--email-timeout-seconds", type=int, default=60)
    parser.add_argument("--now", help="Override UTC timestamp, e.g. 2026-05-07T00:30Z.")
    parser.add_argument("--send", action="store_true", help="Send a deduped bridge nudge when needed.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        now = parse_now(args.now)
    except ValueError as exc:
        print(f"proton-session-check: invalid --now timestamp: {exc}", file=sys.stderr)
        return 2

    try:
        statuses = load_email_statuses(args.pipeline, args.suppression_list, now)
    except OSError as exc:
        print(f"proton-session-check: {exc}", file=sys.stderr)
        return 2

    cooldown = timedelta(hours=max(args.cooldown_hours, 0))
    state = load_json_state(args.state)
    probe = run_email_probe(timeout_seconds=args.email_timeout_seconds)
    recent_bridge = latest_bridge_nudge_at(args.bridge_db, now, cooldown)
    assessment = assess(
        statuses,
        probe,
        now=now,
        min_due=max(args.min_due, 1),
        cooldown=cooldown,
        state=state,
        recent_bridge_nudge_at=recent_bridge,
    )

    output_path = args.write
    if output_path is None and args.state_dir is not None:
        output_path = default_report_path(args.state_dir, args.agent, now)

    if args.json:
        payload = {
            "assessment": asdict(assessment),
            "probe": asdict(probe),
            "statuses": [asdict(status) for status in statuses],
        }
        output = json.dumps(payload, indent=2)
    else:
        output = render_report(assessment, statuses, probe)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + ("" if output.endswith("\n") else "\n"), encoding="utf-8")
        print(f"wrote {output_path}")
    else:
        print(output, end="")

    sent_id = None
    if args.send and assessment.nudge_allowed:
        body = build_bridge_body(assessment, due_followups(statuses), output_path)
        sent_id = send_bridge_message(
            args.bridge_db,
            sender=args.sender,
            recipient=args.recipient,
            body=body,
            now=now,
        )
        state.update(
            {
                "last_nudge_ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_due_signature": assessment.due_signature,
                "last_bridge_msg_id": sent_id,
                "last_report": output_path.as_posix() if output_path else "",
            }
        )
        save_json_state(args.state, state)

    if sent_id is not None:
        print(f"proton-session-check: sent bridge nudge #{sent_id}")
    else:
        print(f"proton-session-check: {assessment.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
