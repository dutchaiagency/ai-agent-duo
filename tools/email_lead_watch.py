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


WATCH_HEADING = "## Active Email Lead Watch"
EXPECTED_FOLLOW_UP_HOURS = 72


@dataclass(frozen=True)
class EmailLead:
    lead: str
    sent_at: str
    cutoff_at: str
    owner: str
    anchor: str
    next_action: str


@dataclass(frozen=True)
class EmailLeadStatus:
    state: str
    lead: str
    owner: str
    sent_at: str
    cutoff_at: str
    hours_to_cutoff: float | None
    next_action: str
    note: str = ""


def strip_inline_code(value: str) -> str:
    return value.replace("`", "").strip()


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
            )
        )
    return leads


def parse_utc_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def expected_cutoff(sent_at: datetime) -> datetime:
    return sent_at + timedelta(hours=EXPECTED_FOLLOW_UP_HOURS)


def format_hours(hours: float | None) -> str:
    if hours is None:
        return "-"
    if hours >= 0:
        return f"{hours:.1f}h remaining"
    return f"{abs(hours):.1f}h overdue"


def md_escape(value: str) -> str:
    return value.replace("|", "\\|")


def classify_lead(lead: EmailLead, *, now: datetime) -> EmailLeadStatus:
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
            note="72h cutoff timestamp is not ISO-8601 UTC.",
        )

    expected = expected_cutoff(sent_dt)
    if cutoff_dt != expected:
        return EmailLeadStatus(
            state="cadence_mismatch",
            lead=lead.lead,
            owner=lead.owner,
            sent_at=lead.sent_at,
            cutoff_at=lead.cutoff_at,
            hours_to_cutoff=(cutoff_dt - now).total_seconds() / 3600,
            next_action=lead.next_action,
            note=f"Cutoff should be {expected.strftime('%Y-%m-%dT%H:%MZ')}.",
        )

    hours = (cutoff_dt - now).total_seconds() / 3600
    lowered_action = lead.next_action.lower()
    if "cold_no_reply" in lowered_action:
        state = "closed"
        note = "Lead is already marked cold_no_reply."
    elif hours <= 0:
        state = "follow_up_due"
        note = "72h no-reply follow-up window is open."
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
        note=note,
    )


def classify_leads(leads: list[EmailLead], *, now: datetime) -> list[EmailLeadStatus]:
    return [classify_lead(lead, now=now) for lead in leads]


def render_markdown(
    statuses: list[EmailLeadStatus],
    *,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        f"# Email Lead Watch - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| State | Lead | Owner | Sent | 72h cutoff | Timer | Next action | Note |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for status in statuses:
        lines.append(
            "| {state} | {lead} | {owner} | {sent} | {cutoff} | {timer} | {action} | {note} |".format(
                state=status.state,
                lead=md_escape(status.lead),
                owner=md_escape(status.owner),
                sent=status.sent_at,
                cutoff=status.cutoff_at,
                timer=format_hours(status.hours_to_cutoff),
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
    parser.add_argument("--state-dir", type=Path, help="Write timestamped report.")
    parser.add_argument("--write", type=Path, help="Write report to this exact path.")
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--now", help="Override UTC timestamp, e.g. 2026-05-02T22:30Z.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on malformed timestamps or non-72h cutoff cadence.",
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

    statuses = classify_leads(leads, now=now)
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
