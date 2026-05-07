#!/usr/bin/env python3
"""Summarize cold email lead follow-up windows from outbound_pipeline.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from tools.agent_identity import default_agent_name
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from agent_identity import default_agent_name


WATCH_HEADING = "## Active Email Lead Watch"
EXPECTED_FOLLOW_UP_HOURS = 72
DEFAULT_FOLLOW_UP_POLICY = "72h-bump"
DEFAULT_SUPPRESSION_LIST = Path("ops/email_suppression_list.md")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
POLICY_DURATION_RE = re.compile(
    r"(?P<amount>\d+)\s*(?P<unit>h|hr|hrs|hour|hours|d|day|days)\b",
    re.IGNORECASE,
)
NO_BUMP_POLICY_TERMS = (
    "if-reply-only",
    "reply-only",
    "no-bump",
    "no bump",
    "no-follow-up",
    "no follow-up",
)
CLOSED_NO_ACTION_TERMS = (
    "closed_no_action_needed",
    "closed-no-action-needed",
    "closed no action needed",
    "drift_close",
    "drift-close",
    "drift-closed",
)


@dataclass(frozen=True)
class EmailLead:
    lead: str
    sent_at: str
    cutoff_at: str
    owner: str
    anchor: str
    next_action: str
    policy: str = DEFAULT_FOLLOW_UP_POLICY


@dataclass(frozen=True)
class EmailLeadStatus:
    state: str
    lead: str
    owner: str
    sent_at: str
    cutoff_at: str
    hours_to_cutoff: float | None
    next_action: str
    policy: str = DEFAULT_FOLLOW_UP_POLICY
    note: str = ""


def strip_inline_code(value: str) -> str:
    return value.replace("`", "").strip()


def normalize_policy(value: str) -> str:
    value = strip_inline_code(value)
    return value or DEFAULT_FOLLOW_UP_POLICY


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_email_leads(markdown: str) -> list[EmailLead]:
    leads: list[EmailLead] = []
    in_watch = False
    for line in markdown.splitlines():
        if line.startswith(WATCH_HEADING):
            in_watch = True
            continue
        if in_watch and line.startswith("## "):
            break
        if not in_watch or not line.startswith("|"):
            continue

        cells = split_table_row(line)
        if len(cells) < 6:
            continue
        first = cells[0].lower()
        if first in {"lead", "---"} or set(first) == {"-"}:
            continue

        leads.append(
            EmailLead(
                lead=strip_inline_code(cells[0]),
                sent_at=strip_inline_code(cells[1]),
                cutoff_at=strip_inline_code(cells[2]),
                owner=strip_inline_code(cells[3]),
                anchor=strip_inline_code(cells[4]),
                next_action=strip_inline_code(cells[5]),
                policy=(
                    normalize_policy(cells[6])
                    if len(cells) >= 7
                    else DEFAULT_FOLLOW_UP_POLICY
                ),
            )
        )
    return leads


def parse_suppressed_emails(markdown: str) -> set[str]:
    return {match.group(0).lower() for match in EMAIL_RE.finditer(markdown)}


def load_suppressed_emails(path: Path) -> set[str]:
    try:
        return parse_suppressed_emails(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()


def lead_email(lead: str) -> str | None:
    match = EMAIL_RE.search(lead)
    if not match:
        return None
    return match.group(0).lower()


def parse_utc_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def policy_delta(policy: str) -> timedelta:
    match = POLICY_DURATION_RE.search(policy)
    if not match:
        return timedelta(hours=EXPECTED_FOLLOW_UP_HOURS)
    amount = int(match.group("amount"))
    unit = match.group("unit").lower()
    if unit.startswith("d"):
        return timedelta(days=amount)
    return timedelta(hours=amount)


def expected_cutoff(
    sent_at: datetime,
    policy: str = DEFAULT_FOLLOW_UP_POLICY,
) -> datetime:
    return sent_at + policy_delta(policy)


def policy_allows_follow_up(policy: str) -> bool:
    lowered = policy.lower()
    if "suppressed" in lowered:
        return False
    if any(term in lowered for term in CLOSED_NO_ACTION_TERMS):
        return False
    return not any(term in lowered for term in NO_BUMP_POLICY_TERMS)


def format_hours(hours: float | None) -> str:
    if hours is None:
        return "-"
    if hours >= 0:
        return f"{hours:.1f}h remaining"
    return f"{abs(hours):.1f}h overdue"


def md_escape(value: str) -> str:
    return value.replace("|", "\\|")


def classify_lead(
    lead: EmailLead,
    *,
    now: datetime,
    suppressed_emails: set[str] | None = None,
) -> EmailLeadStatus:
    try:
        sent_dt = parse_utc_timestamp(lead.sent_at)
    except ValueError:
        return EmailLeadStatus(
            state="invalid_sent",
            lead=lead.lead,
            owner=lead.owner,
            sent_at=lead.sent_at,
            cutoff_at=lead.cutoff_at,
            hours_to_cutoff=None,
            next_action=lead.next_action,
            policy=lead.policy,
            note="Sent timestamp is not ISO-8601 UTC.",
        )

    try:
        cutoff_dt = parse_utc_timestamp(lead.cutoff_at)
    except ValueError:
        return EmailLeadStatus(
            state="invalid_cutoff",
            lead=lead.lead,
            owner=lead.owner,
            sent_at=lead.sent_at,
            cutoff_at=lead.cutoff_at,
            hours_to_cutoff=None,
            next_action=lead.next_action,
            policy=lead.policy,
            note="Cutoff timestamp is not ISO-8601 UTC.",
        )

    expected = expected_cutoff(sent_dt, lead.policy)
    if cutoff_dt != expected:
        return EmailLeadStatus(
            state="cadence_mismatch",
            lead=lead.lead,
            owner=lead.owner,
            sent_at=lead.sent_at,
            cutoff_at=lead.cutoff_at,
            hours_to_cutoff=(cutoff_dt - now).total_seconds() / 3600,
            next_action=lead.next_action,
            policy=lead.policy,
            note=(
                f"Cutoff for policy {lead.policy} should be "
                f"{expected.strftime('%Y-%m-%dT%H:%MZ')}."
            ),
        )

    hours = (cutoff_dt - now).total_seconds() / 3600
    lowered_action = lead.next_action.lower()
    suppressed = lead_email(lead.lead) in (suppressed_emails or set()) or (
        "suppressed" in lead.policy.lower()
    )
    closed_no_action = any(
        term in lead.policy.lower() or term in lowered_action
        for term in CLOSED_NO_ACTION_TERMS
    )
    follow_up_allowed = policy_allows_follow_up(lead.policy)
    if suppressed:
        state = "suppressed"
        note = "Address is in email suppression list; no contact on any channel."
    elif closed_no_action:
        state = "closed_no_action_needed"
        note = "Cited work is closed or drifted; no follow-up should be sent."
    elif "cold_no_reply" in lowered_action:
        state = "closed"
        note = "Lead is already marked cold_no_reply."
    elif not follow_up_allowed:
        if hours <= 0:
            state = "closed"
            note = f"Policy {lead.policy} forbids a follow-up bump; close if no reply."
        else:
            state = "watching"
            note = f"Policy {lead.policy} is reply-only; no follow-up bump."
    elif hours <= 0:
        state = "follow_up_due"
        note = f"{lead.policy} no-reply follow-up window is open."
    else:
        state = "watching"
        note = "No follow-up before cutoff."

    return EmailLeadStatus(
        state=state,
        lead=lead.lead,
        owner=lead.owner,
        sent_at=lead.sent_at,
        cutoff_at=lead.cutoff_at,
        hours_to_cutoff=hours,
        next_action=lead.next_action,
        policy=lead.policy,
        note=note,
    )


def classify_leads(
    leads: list[EmailLead],
    *,
    now: datetime,
    suppressed_emails: set[str] | None = None,
) -> list[EmailLeadStatus]:
    return [
        classify_lead(lead, now=now, suppressed_emails=suppressed_emails)
        for lead in leads
    ]


def render_markdown(
    statuses: list[EmailLeadStatus],
    *,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        f"# Email Lead Watch - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| State | Lead | Owner | Sent | Cutoff | Timer | Policy | Next action | Note |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for status in statuses:
        lines.append(
            "| {state} | {lead} | {owner} | {sent} | {cutoff} | {timer} | {policy} | {action} | {note} |".format(
                state=status.state,
                lead=md_escape(status.lead),
                owner=md_escape(status.owner),
                sent=status.sent_at,
                cutoff=status.cutoff_at,
                timer=format_hours(status.hours_to_cutoff),
                policy=md_escape(status.policy),
                action=md_escape(status.next_action),
                note=md_escape(status.note or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def default_output_path(state_dir: Path, agent: str, generated_at: datetime) -> Path:
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d")
    hhmm = generated_at.astimezone(UTC).strftime("%H%M")
    return state_dir / f"email-lead-watch-{stamp}-{agent}-{hhmm}.md"


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return parse_utc_timestamp(value)


def has_validation_error(statuses: list[EmailLeadStatus]) -> bool:
    return any(
        status.state in {"invalid_sent", "invalid_cutoff", "cadence_mismatch"}
        for status in statuses
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipeline",
        type=Path,
        default=Path("ops/outbound_pipeline.md"),
        help="Markdown pipeline file with Active Email Lead Watch.",
    )
    parser.add_argument(
        "--suppression-list",
        type=Path,
        default=DEFAULT_SUPPRESSION_LIST,
        help="Markdown suppression list; matching addresses are never follow-up due.",
    )
    parser.add_argument("--state-dir", type=Path, help="Write timestamped report.")
    parser.add_argument("--write", type=Path, help="Write report to this exact path.")
    parser.add_argument("--agent", default=default_agent_name())
    parser.add_argument("--now", help="Override UTC timestamp, e.g. 2026-05-02T22:30Z.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on malformed timestamps or policy/cutoff cadence drift.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        markdown = args.pipeline.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"email-lead-watch: {exc}", file=sys.stderr)
        return 2

    leads = parse_email_leads(markdown)
    if not leads:
        print("email-lead-watch: no active email leads found", file=sys.stderr)
        return 1

    try:
        now = parse_now(args.now)
    except ValueError as exc:
        print(f"email-lead-watch: invalid --now timestamp: {exc}", file=sys.stderr)
        return 2

    suppressed_emails = load_suppressed_emails(args.suppression_list)
    statuses = classify_leads(leads, now=now, suppressed_emails=suppressed_emails)
    generated_at = datetime.now(UTC)
    if args.json:
        output = json.dumps([asdict(status) for status in statuses], indent=2)
    else:
        output = render_markdown(statuses, generated_at=generated_at)

    output_path = args.write
    if output_path is None and args.state_dir is not None:
        output_path = default_output_path(args.state_dir, args.agent, generated_at)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"wrote {output_path}")
    else:
        print(output, end="")

    if args.strict and has_validation_error(statuses):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
