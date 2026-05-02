#!/usr/bin/env python3
"""Suggest the next heartbeat lane from recent local state.

The script is intentionally read-only. It exists to stop heartbeat dispatches
from burning cycles on the same zero-signal GitHub scan when the local state
already says the next slot should move to productized validation, bounty
re-fetch, or funnel work.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


TIMESTAMP_RE = re.compile(
    r"(?P<date>20\d\d-\d\d-\d\d)(?:-[A-Za-z0-9]+)*-(?P<hhmm>\d{4})\.md$"
)
DEADLINE_RE = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\dZ")

ZERO_LEAD_TERMS = (
    "no candidates passed",
    "zero candidates",
    "0 actionable github leads",
)
NO_INVENTORY_ZERO_TERMS = (
    "0 reservation issues",
    "0 unread emails",
    "0 matching reservation emails",
    "keep the distribution hold",
)
BOUNTY_ZERO_TERMS = (
    "zero immediate candidates",
    "no immediately executable cash bounty",
    "zero executable candidates",
    "watch/hold",
)
DEVTO_ZERO_TERMS = (
    "0/0/0",
    "0 reactions / 0 comments",
    "total reactions: 0",
    "total comments: 0",
)


@dataclass(frozen=True)
class StateEvent:
    kind: str
    path: Path
    at: datetime
    zero_signal: bool
    reply_signal: bool = False


@dataclass(frozen=True)
class CooldownStatus:
    active: bool
    reason: str


@dataclass(frozen=True)
class Suggestion:
    decision: str
    reason: str
    next_steps: tuple[str, ...]
    cooldown: CooldownStatus
    latest_events: tuple[StateEvent, ...]


def parse_timestamp(path: Path) -> datetime | None:
    match = TIMESTAMP_RE.search(path.name)
    if not match:
        return None

    hhmm = match.group("hhmm")
    value = f"{match.group('date')}T{hhmm[:2]}:{hhmm[2:]}:00+00:00"
    return datetime.fromisoformat(value).astimezone(UTC)


def event_kind(path: Path) -> str | None:
    name = path.name
    if name.startswith("github-leads-"):
        return "github_leads"
    if name.startswith("github-replies-"):
        return "github_replies"
    if name.startswith("no-inventory-bridge-kit-signal-check-"):
        return "no_inventory"
    if (
        name.startswith("algora-bounty-check-")
        or name.startswith("opire-featured-bounty-check-")
        or name.startswith("paid-bounty-scout-")
    ):
        return "bounty"
    if name.startswith("devto-engagement-"):
        return "devto_engagement"
    return None


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def classify_event(path: Path) -> StateEvent | None:
    kind = event_kind(path)
    at = parse_timestamp(path)
    if kind is None or at is None:
        return None

    text = path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    zero_signal = False
    reply_signal = False
    if kind == "github_leads":
        zero_signal = has_any(lower, ZERO_LEAD_TERMS)
    elif kind == "github_replies":
        reply_signal = bool(re.search(r"(?m)^\|\s*reply\s*\|", lower))
        zero_signal = not reply_signal
    elif kind == "no_inventory":
        zero_signal = has_any(lower, NO_INVENTORY_ZERO_TERMS)
    elif kind == "bounty":
        zero_signal = has_any(lower, BOUNTY_ZERO_TERMS)
    elif kind == "devto_engagement":
        zero_signal = has_any(lower, DEVTO_ZERO_TERMS)

    return StateEvent(
        kind=kind,
        path=path,
        at=at,
        zero_signal=zero_signal,
        reply_signal=reply_signal,
    )


def load_events(state_dir: Path) -> list[StateEvent]:
    if not state_dir.exists():
        return []
    events = [
        event
        for path in state_dir.glob("*.md")
        if (event := classify_event(path)) is not None
    ]
    return sorted(events, key=lambda event: event.at)


def latest(events: list[StateEvent], kind: str) -> StateEvent | None:
    filtered = [event for event in events if event.kind == kind]
    return filtered[-1] if filtered else None


def github_cooldown_status(
    events: list[StateEvent],
    now: datetime,
    *,
    zero_pair_window: timedelta = timedelta(minutes=30),
    cooldown_window: timedelta = timedelta(minutes=45),
) -> CooldownStatus:
    lead_events = [event for event in events if event.kind == "github_leads"]
    if len(lead_events) < 2:
        return CooldownStatus(False, "Fewer than two timestamped GitHub lead scans.")

    first, second = lead_events[-2], lead_events[-1]
    if not first.zero_signal or not second.zero_signal:
        return CooldownStatus(False, "Latest GitHub lead scans were not both zero-signal.")
    if second.at - first.at > zero_pair_window:
        return CooldownStatus(False, "Latest zero lead scans were not inside 30 minutes.")
    if now - second.at > cooldown_window:
        return CooldownStatus(False, "Latest zero lead scan is outside the cooldown window.")

    reply_events = [
        event
        for event in events
        if event.kind == "github_replies"
        and first.at - timedelta(minutes=5) <= event.at <= second.at + timedelta(minutes=5)
    ]
    if any(event.reply_signal for event in reply_events):
        return CooldownStatus(False, "A reply signal appeared during the zero-scan window.")

    return CooldownStatus(
        True,
        (
            "Two consecutive GitHub lead scans inside 30 minutes were zero-signal "
            f"({stamp(first.at)} and {stamp(second.at)})."
        ),
    )


def parse_deadline(ops_dir: Path) -> datetime | None:
    lane_path = ops_dir / "no_inventory_validation_lane.md"
    if not lane_path.exists():
        return None

    text = lane_path.read_text(encoding="utf-8", errors="replace")
    matches = DEADLINE_RE.findall(text)
    if not matches:
        return None
    return max(
        datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        for value in matches
    )


def normalize_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def minutes_old(now: datetime, event: StateEvent | None) -> float | None:
    if event is None:
        return None
    return (now - event.at).total_seconds() / 60


def suggest_next_action(events: list[StateEvent], ops_dir: Path, now: datetime) -> Suggestion:
    cooldown = github_cooldown_status(events, now)
    latest_lead = latest(events, "github_leads")
    latest_reply = latest(events, "github_replies")
    latest_no_inventory = latest(events, "no_inventory")
    latest_bounty = latest(events, "bounty")
    latest_devto = latest(events, "devto_engagement")
    deadline = parse_deadline(ops_dir)
    latest_events = tuple(
        event
        for event in (
            latest_lead,
            latest_reply,
            latest_no_inventory,
            latest_bounty,
            latest_devto,
        )
        if event is not None
    )

    if deadline is not None and now >= deadline:
        return Suggestion(
            decision="park_or_scale_no_inventory_lane",
            reason=(
                f"The no-inventory review deadline has passed ({stamp(deadline)}). "
                "Do the promised park/scale decision before more validation checks."
            ),
            next_steps=(
                "Open ops/no_inventory_validation_lane.md and classify the lane as scale, park, or kill.",
                "If zero qualified signal remains, recycle useful checklist pieces into productized services.",
                "Append the decision to ops/revenue_pipeline.md and ops/improvements.md.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
        )

    if cooldown.active:
        no_inventory_age = minutes_old(now, latest_no_inventory)
        bounty_age = minutes_old(now, latest_bounty)
        devto_age = minutes_old(now, latest_devto)
        if no_inventory_age is None or no_inventory_age > 90:
            return Suggestion(
                decision="no_inventory_signal_check",
                reason=(
                    f"{cooldown.reason} The Agent Bridge Reliability Kit signal check "
                    "is stale or missing."
                ),
                next_steps=(
                    "Search GitHub reservation issues for the canonical source slug.",
                    "Check unread mail and Bridge Kit reservation mail.",
                    "Log the result in state/ and append the Signal Log only if a real check ran.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        if bounty_age is None or bounty_age > 240:
            return Suggestion(
                decision="stale_bounty_refetch",
                reason=(
                    f"{cooldown.reason} No-inventory was checked recently, "
                    "but bounty surfaces are stale enough to re-fetch."
                ),
                next_steps=(
                    "Re-fetch the most recent saturated/pending bounty leads.",
                    "Only promote a candidate with a canonical open issue and cash-like payout.",
                    "Log watch/hold decisions instead of posting public claims from stale cards.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        if devto_age is None or devto_age > 30:
            return Suggestion(
                decision="devto_engagement_pull",
                reason=(
                    f"{cooldown.reason} No-inventory and bounty checks are fresh, "
                    "but the dev.to engagement snapshot is stale or missing."
                ),
                next_steps=(
                    "Run tools/devto_engagement_check.py --state-dir state --agent codex.",
                    "Record per-post reactions/comments in state/devto-engagement-YYYY-MM-DD-codex-HHMM.md.",
                    "If 24h-old posts remain 0/0, treat dev.to as SEO-only until native-discovery work is chosen.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        return Suggestion(
            decision="funnel_or_productized_asset_review",
            reason=(
                f"{cooldown.reason} No-inventory and bounty checks are both fresh, "
                "so the next useful slot is conversion or reusable product/service packaging."
            ),
            next_steps=(
                "Audit one site/playbook/task-brief conversion path or one productized service artifact.",
                "Ship a small copy, link, or tooling improvement with focused validation.",
                "Record the post-mortem in ops/improvements.md.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
        )

    if latest_reply is None or minutes_old(now, latest_reply) is None or minutes_old(now, latest_reply) > 30:
        return Suggestion(
            decision="github_reply_check_then_lead_scan",
            reason="GitHub is not in cooldown and reply state is missing or older than 30 minutes.",
            next_steps=(
                "Run tools/github_reply_check.py before any public outbound.",
                "Run tools/github_lead_scan.py only after reply state is known.",
                "Do a manual code read before posting or claiming anything.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
        )

    return Suggestion(
        decision="github_lead_scan",
        reason="GitHub is not in cooldown and reply state is fresh.",
        next_steps=(
            "Run the read-only lead scan.",
            "Skip public outbound unless a candidate survives manual code review.",
            "If the scan is zero, update the pipeline so the next heartbeat can switch lanes.",
        ),
        cooldown=cooldown,
        latest_events=latest_events,
    )


def stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def format_event(event: StateEvent) -> str:
    signal = "reply" if event.reply_signal else ("zero" if event.zero_signal else "nonzero")
    return f"- {event.kind}: {stamp(event.at)} `{event.path.as_posix()}` ({signal})"


def format_suggestion(suggestion: Suggestion, now: datetime) -> str:
    lines = [
        f"# Heartbeat lane suggestion - {stamp(now)}",
        "",
        f"Decision: `{suggestion.decision}`",
        "",
        f"Reason: {suggestion.reason}",
        "",
        "Next steps:",
    ]
    lines.extend(f"- {step}" for step in suggestion.next_steps)
    if suggestion.latest_events:
        lines.extend(["", "Latest local signals:"])
        lines.extend(format_event(event) for event in suggestion.latest_events)
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--ops-dir", type=Path, default=Path("ops"))
    parser.add_argument(
        "--now",
        help="Override current UTC time for tests, for example 2026-05-02T09:17Z.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = normalize_now(args.now)
    events = load_events(args.state_dir)
    suggestion = suggest_next_action(events, args.ops_dir, now)
    print(format_suggestion(suggestion, now), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
