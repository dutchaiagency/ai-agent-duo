#!/usr/bin/env python3
"""Suggest the next heartbeat lane from recent local state.

The script is intentionally read-only. It exists to stop heartbeat dispatches
from burning cycles on the same zero-signal GitHub scan when the local state
already says the next slot should move to productized validation, bounty
re-fetch, or funnel work.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from os import environ
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
CHANNEL_UNLOCK_TERMS = (
    "account unlock",
    "unlock",
    "human account",
    "show hn",
    "hacker news",
    "hn /show",
    "reddit",
    "lobsters",
    "product hunt",
    "x account",
    "twitter",
    "linkedin",
    "captcha",
    "phone",
    "kyc",
)
CHANNEL_ASK_TERMS = (
    "wil je",
    "kun je",
    "can you",
    "could you",
    "ask",
    "nodig",
    "vereist",
    "gated",
    "blocked",
    "blokker",
    "submit",
)
FUNNEL_PATH_PREFIXES = ("playbook/", "longform/")
FUNNEL_SATURATION_COMMITS = 4
FUNNEL_SATURATION_WINDOW = timedelta(minutes=60)
FARCASTER_COOLDOWN = timedelta(minutes=30)
CHANNEL_UNLOCK_ASK_WINDOW = timedelta(hours=6)


@dataclass(frozen=True)
class CommitTouch:
    at: datetime
    files: tuple[str, ...]


@dataclass(frozen=True)
class StateEvent:
    kind: str
    path: Path
    at: datetime
    zero_signal: bool
    reply_signal: bool = False


@dataclass(frozen=True)
class BridgeAsk:
    at: datetime
    from_agent: str
    excerpt: str


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


def parse_bridge_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def minutes_old(now: datetime, event: StateEvent | None) -> float | None:
    if event is None:
        return None
    return (now - event.at).total_seconds() / 60


def normalize_commit_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def parse_git_log(output: str) -> tuple[CommitTouch, ...]:
    commits: list[CommitTouch] = []
    current_at: datetime | None = None
    current_files: list[str] = []

    def flush() -> None:
        nonlocal current_at, current_files
        if current_at is not None:
            commits.append(
                CommitTouch(
                    at=current_at,
                    files=tuple(
                        path
                        for path in (normalize_commit_path(item) for item in current_files)
                        if path
                    ),
                )
            )
        current_at = None
        current_files = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("COMMIT "):
            flush()
            try:
                current_at = datetime.fromtimestamp(int(line.removeprefix("COMMIT ")), UTC)
            except ValueError:
                current_at = None
            continue
        if current_at is not None and line:
            current_files.append(line)
    flush()
    return tuple(commits)


def load_recent_commits(
    repo_dir: Path,
    *,
    count: int = FUNNEL_SATURATION_COMMITS,
) -> tuple[CommitTouch, ...]:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "log",
                f"-n{count}",
                "--name-only",
                "--pretty=format:COMMIT %ct",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ()
    return parse_git_log(result.stdout)


def funnel_saturation_reason(
    recent_commits: tuple[CommitTouch, ...],
    now: datetime,
    *,
    count: int = FUNNEL_SATURATION_COMMITS,
    window: timedelta = FUNNEL_SATURATION_WINDOW,
) -> str | None:
    inspected = recent_commits[:count]
    if len(inspected) < count:
        return None
    if any(now - commit.at > window or commit.at > now for commit in inspected):
        return None
    if not all(
        any(path.startswith(FUNNEL_PATH_PREFIXES) for path in commit.files)
        for commit in inspected
    ):
        return None

    oldest = inspected[-1].at
    minutes = int((now - oldest).total_seconds() // 60)
    return (
        f"The last {count} commits inside {minutes} minutes all touched "
        "playbook/ or longform/, so more funnel polish is saturated until "
        "fresh traffic or engagement arrives."
    )


def parse_cast_log_time(line: str) -> datetime | None:
    timestamp = line.split("|", 1)[0].strip()
    try:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def last_successful_cast_time(log_path: Path) -> datetime | None:
    if not log_path.exists():
        return None

    times: list[datetime] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if " | success " not in f"{line} " and " | success |" not in line:
            continue
        if parsed := parse_cast_log_time(line):
            times.append(parsed)
    return max(times) if times else None


def farcaster_cooldown_reason(last_cast_at: datetime | None, now: datetime) -> str | None:
    if last_cast_at is None:
        return None
    remaining = FARCASTER_COOLDOWN - (now - last_cast_at)
    if remaining <= timedelta(0):
        return None
    wait_minutes = max(1, int((remaining.total_seconds() + 59) // 60))
    return (
        f"Farcaster cooldown remains active for ~{wait_minutes}m "
        f"(last cast {stamp(last_cast_at)})."
    )


def is_channel_unlock_ask(text: str) -> bool:
    lower = text.lower()
    return has_any(lower, CHANNEL_UNLOCK_TERMS) and has_any(lower, CHANNEL_ASK_TERMS)


def bridge_ask_excerpt(text: str, max_chars: int = 180) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def resolve_bridge_db(repo_dir: Path) -> Path | None:
    if value := environ.get("BRIDGE_DB"):
        return Path(value)

    config_path = repo_dir / ".mcp.json"
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    servers = config.get("mcpServers", {})
    if not isinstance(servers, dict):
        return None
    for server in servers.values():
        if not isinstance(server, dict):
            continue
        env = server.get("env", {})
        if isinstance(env, dict) and isinstance(env.get("BRIDGE_DB"), str):
            return Path(env["BRIDGE_DB"])
    return None


def load_recent_bridge_unlock_asks(
    bridge_db: Path | None,
    now: datetime,
    *,
    window: timedelta = CHANNEL_UNLOCK_ASK_WINDOW,
    query_limit: int = 80,
) -> tuple[BridgeAsk, ...]:
    if bridge_db is None or not bridge_db.exists():
        return ()

    try:
        con = sqlite3.connect(f"{bridge_db.resolve().as_uri()}?mode=ro", uri=True)
        rows = con.execute(
            """
            SELECT ts, from_agent, body
            FROM messages
            WHERE to_agent = 'leon'
            ORDER BY id DESC
            LIMIT ?
            """,
            (query_limit,),
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return ()

    asks: list[BridgeAsk] = []
    for ts, from_agent, body in rows:
        at = parse_bridge_timestamp(str(ts))
        text = str(body)
        if at is None or now - at > window or at > now:
            continue
        if not is_channel_unlock_ask(text):
            continue
        asks.append(
            BridgeAsk(
                at=at,
                from_agent=str(from_agent),
                excerpt=bridge_ask_excerpt(text),
            )
        )
    return tuple(sorted(asks, key=lambda ask: ask.at, reverse=True))


def channel_poverty_reason(
    now: datetime,
    recent_unlock_asks: tuple[BridgeAsk, ...],
    last_cast_at: datetime | None,
) -> str | None:
    recent_unlock_ask = recent_unlock_asks[0] if recent_unlock_asks else None
    cooldown_reason = farcaster_cooldown_reason(last_cast_at, now)

    if recent_unlock_ask is None and cooldown_reason is None:
        return None

    parts: list[str] = []
    if cooldown_reason:
        parts.append(cooldown_reason)
    if recent_unlock_ask:
        parts.append(
            "Recent Leon channel-unlock ask is still pending "
            f"({recent_unlock_ask.from_agent} at {stamp(recent_unlock_ask.at)}: "
            f"{recent_unlock_ask.excerpt!r})."
        )
    return " ".join(parts)


def suggest_next_action(
    events: list[StateEvent],
    ops_dir: Path,
    now: datetime,
    recent_commits: tuple[CommitTouch, ...] = (),
    recent_unlock_asks: tuple[BridgeAsk, ...] = (),
    last_cast_at: datetime | None = None,
) -> Suggestion:
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
        saturation_reason = funnel_saturation_reason(recent_commits, now)
        if saturation_reason:
            poverty_reason = channel_poverty_reason(now, recent_unlock_asks, last_cast_at)
            if poverty_reason:
                return Suggestion(
                    decision="channel_poverty_audit",
                    reason=f"{cooldown.reason} {saturation_reason} {poverty_reason}",
                    next_steps=(
                        "Do not send another Leon account-unlock ask while a recent one is pending.",
                        "Check whether Farcaster has genuinely new information and is outside cooldown before casting.",
                        "If no non-duplicative public action exists, spend the slot on nonpublic code, reply, or delivery work and log why.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            return Suggestion(
                decision="outbound_traffic_generation",
                reason=f"{cooldown.reason} {saturation_reason}",
                next_steps=(
                    "Run a channel-poverty audit before another playbook or longform polish commit.",
                    "Use a distinct Farcaster, GitHub, dev.to, or HN angle with a source-tagged playbook/longform link only if the channel is open.",
                    "If the best path needs Leon's human account, send one binary unlock ask and do not repeat it inside the cooldown window.",
                    "Log the channel, URL, and early engagement signal in ops/ or state/ for the next heartbeat.",
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
    parser.add_argument("--repo-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--bridge-db",
        type=Path,
        help="Optional agent-bridge SQLite DB path for recent Leon unlock asks.",
    )
    parser.add_argument(
        "--now",
        help="Override current UTC time for tests, for example 2026-05-02T09:17Z.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = normalize_now(args.now)
    events = load_events(args.state_dir)
    recent_commits = load_recent_commits(args.repo_dir)
    bridge_db = args.bridge_db or resolve_bridge_db(args.repo_dir)
    recent_unlock_asks = load_recent_bridge_unlock_asks(bridge_db, now)
    last_cast_at = last_successful_cast_time(args.ops_dir / "farcaster_cast_log.md")
    suggestion = suggest_next_action(
        events,
        args.ops_dir,
        now,
        recent_commits,
        recent_unlock_asks,
        last_cast_at,
    )
    print(format_suggestion(suggestion, now), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
