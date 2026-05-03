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
GITHUB_TRIAGE_CLOSED_TERMS = (
    "all candidates triaged",
    "fully triaged",
    "triage complete",
    "zero untriaged candidates",
)
GITHUB_TRIAGE_NO_ACTION_TERMS = (
    "no public comment",
    "no public outreach",
    "no claim",
    "no pr",
    "no-go",
    "posted nothing",
)
NO_INVENTORY_ZERO_TERMS = (
    "0 reservation issues",
    "0 unread emails",
    "0 matching reservation emails",
    "0 matching bridge kit emails",
    "zero reservation issues",
    "zero bridge kit reservations",
    "zero unread emails",
    "zero unread mail",
    "zero matching reservation emails",
    "zero matching bridge kit emails",
    "keep the distribution hold",
)
BOUNTY_ZERO_TERMS = (
    "zero immediate candidates",
    "no immediately executable cash bounty",
    "no executable bounty candidate",
    "zero executable candidates",
    "zero higher-than-low candidates",
    "all reviewed priority candidates are saturated",
    "deferred-pipeline",
    "no compete-bump comment",
    "no maintainer review",
    "publish/claim hold",
    "watch/hold",
)
DEVTO_ZERO_TERMS = (
    "0/0/0",
    "0 reactions / 0 comments",
    "total reactions: 0",
    "total comments: 0",
)
CHANNEL_SCOUT_ZERO_TERMS = (
    "no public outbound",
    "no additional public outbound",
    "no public reply posted",
    "no farcaster cast/reply",
    "no farcaster cast",
    "decision: no reply",
    "no reply this wake",
    "zero qualified",
    "zero actionable",
    "no non-duplicative public action",
    "distribution hold",
)
PROTON_INBOX_ZERO_TERMS = (
    "zero unread",
    "0 unread",
    "result\n```json\n[]",
    "result:\n```json\n[]",
    "```json\n[]\n```",
    "empty inbox",
    "no inbound",
)
DEVTO_PUBLISHED_AT_RE = re.compile(
    r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)?"
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
    "please",
    "pls",
    "need you to",
)
FUNNEL_PATH_PREFIXES = ("playbook/", "longform/")
FUNNEL_SATURATION_COMMITS = 4
FUNNEL_SATURATION_WINDOW = timedelta(minutes=60)
PRODUCTIZED_REVIEW_FRESH_WINDOW = timedelta(minutes=90)
GITHUB_NONZERO_TRIAGE_WINDOW = timedelta(minutes=90)
FARCASTER_COOLDOWN = timedelta(minutes=30)
FARCASTER_REPLY_OBSERVE_WINDOW = timedelta(minutes=60)
GITHUB_FOLLOW_UP_WINDOW = timedelta(hours=72)
GITHUB_REPLY_CHECK_FRESH_WINDOW = timedelta(minutes=30)
CHANNEL_SCOUT_FRESH_WINDOW = timedelta(minutes=90)
DEVTO_ZERO_ARCHIVE_MIN_POST_AGE = timedelta(hours=24)
DEVTO_ZERO_ARCHIVE_POLL_COOLDOWN = timedelta(hours=6)
CHANNEL_UNLOCK_ASK_WINDOW = timedelta(hours=6)
PAGE_TRAFFIC_BOT_BASELINE_7D = 210
PAGE_TRAFFIC_MAX_AGE = timedelta(hours=36)
PAGE_TRAFFIC_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
LAUNCH_RESPONSE_WINDOW = timedelta(minutes=90)
LAUNCH_URL_RE = re.compile(r"https://[^\s)>]+")
LAUNCH_CLOSED_TERMS = (
    "status: closed",
    "status: inactive",
    "window: closed",
    "launch closed",
)


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
class DueFollowUp:
    label: str
    url: str
    last_agent_at: datetime
    due_at: datetime
    source_path: Path


@dataclass(frozen=True)
class LaunchWindow:
    path: Path
    at: datetime
    venue: str
    url: str | None = None


@dataclass(frozen=True)
class CooldownStatus:
    active: bool
    reason: str


@dataclass(frozen=True)
class PageTraffic:
    key: str
    label: str
    window_hits: int | None
    status: str


@dataclass(frozen=True)
class PageTrafficSnapshot:
    path: Path
    at: datetime
    window_days: int
    bot_baseline_7d: int
    pages: tuple[PageTraffic, ...]


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
    if name.startswith("github-candidate-triage-"):
        return "github_candidate_triage"
    if name.startswith("no-inventory-bridge-kit-signal-check-"):
        return "no_inventory"
    if (
        name.startswith("algora-bounty-check-")
        or name.startswith("archestra-bounty-label-watch-")
        or name.startswith("github-bounty-priority-scan-")
        or name.startswith("github-bounty-priority-triage-")
        or name.startswith("midnight-bounty-followup-")
        or name.startswith("opire-featured-bounty-check-")
        or name.startswith("paid-bounty-scout-")
    ):
        return "bounty"
    if name.startswith("devto-engagement-"):
        return "devto_engagement"
    if name.startswith("productized-asset-review-"):
        return "productized_review"
    if name.startswith("proton-inbox-scan-"):
        return "proton_inbox"
    if (
        name.startswith("channel-poverty-audit-")
        or name.startswith("farcaster-channel-deadness-")
        or name.startswith("farcaster-outbound-scout-")
        or name.startswith("founders-engagement-scout-")
    ):
        return "channel_scout"
    return None


def load_latest_pages_traffic(state_dir: Path) -> PageTrafficSnapshot | None:
    if not state_dir.exists():
        return None

    candidates: list[PageTrafficSnapshot] = []
    for path in state_dir.glob("pages-traffic-*.md"):
        at = parse_timestamp(path)
        if at is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        matches = PAGE_TRAFFIC_JSON_RE.findall(text)
        if not matches:
            continue
        try:
            payload = json.loads(matches[-1])
        except json.JSONDecodeError:
            continue
        pages_payload = payload.get("pages", [])
        if not isinstance(pages_payload, list):
            continue
        pages: list[PageTraffic] = []
        for item in pages_payload:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            label = item.get("label")
            status = item.get("status")
            window_hits = item.get("window_hits")
            if not isinstance(key, str) or not isinstance(label, str) or not isinstance(status, str):
                continue
            if not isinstance(window_hits, int):
                window_hits = None
            pages.append(PageTraffic(key, label, window_hits, status))
        candidates.append(
            PageTrafficSnapshot(
                path=path,
                at=at,
                window_days=payload.get("window_days")
                if isinstance(payload.get("window_days"), int)
                else 7,
                bot_baseline_7d=payload.get("bot_baseline_7d")
                if isinstance(payload.get("bot_baseline_7d"), int)
                else PAGE_TRAFFIC_BOT_BASELINE_7D,
                pages=tuple(pages),
            )
        )
    return max(candidates, key=lambda snapshot: snapshot.at) if candidates else None


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
    elif kind == "github_candidate_triage":
        zero_signal = has_any(lower, GITHUB_TRIAGE_CLOSED_TERMS)
    elif kind == "no_inventory":
        zero_signal = has_any(lower, NO_INVENTORY_ZERO_TERMS)
    elif kind == "bounty":
        zero_signal = has_any(lower, BOUNTY_ZERO_TERMS)
    elif kind == "devto_engagement":
        zero_signal = has_any(lower, DEVTO_ZERO_TERMS)
    elif kind == "channel_scout":
        zero_signal = has_any(lower, CHANNEL_SCOUT_ZERO_TERMS)
    elif kind == "proton_inbox":
        zero_signal = has_any(lower, PROTON_INBOX_ZERO_TERMS)

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


def launch_window_venue(path: Path) -> str | None:
    name = path.name.lower()
    if "launch-window-active" not in name:
        return None
    if "lobsters" in name or "lobste" in name:
        return "Lobsters"
    if "hn" in name or "hacker-news" in name:
        return "HN"
    return "HN/Lobsters"


def extract_launch_url(text: str) -> str | None:
    match = LAUNCH_URL_RE.search(text)
    return match.group(0).rstrip(".,;") if match else None


def load_active_launch_window(
    state_dir: Path,
    now: datetime,
    *,
    window: timedelta = LAUNCH_RESPONSE_WINDOW,
) -> LaunchWindow | None:
    if not state_dir.exists():
        return None

    windows: list[LaunchWindow] = []
    for path in state_dir.glob("*launch-window-active-*.md"):
        venue = launch_window_venue(path)
        at = parse_timestamp(path)
        if venue is None or at is None or at > now or now - at > window:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if has_any(text, LAUNCH_CLOSED_TERMS):
            continue
        windows.append(
            LaunchWindow(
                path=path,
                at=at,
                venue=venue,
                url=extract_launch_url(text),
            )
        )
    return max(windows, key=lambda launch: launch.at) if windows else None


def latest(events: list[StateEvent], kind: str) -> StateEvent | None:
    filtered = [event for event in events if event.kind == kind]
    return filtered[-1] if filtered else None


def triage_closes_lead_scan(
    triage: StateEvent | None,
    lead: StateEvent | None,
) -> bool:
    if triage is None or lead is None:
        return False
    if triage.kind != "github_candidate_triage" or lead.kind != "github_leads":
        return False
    if triage.at < lead.at or not triage.zero_signal:
        return False

    text = triage.path.read_text(encoding="utf-8", errors="replace").lower()
    lead_path = lead.path.as_posix().lower()
    return lead_path in text or lead.path.name.lower() in text


def triage_closed_without_action(triage: StateEvent | None) -> bool:
    if triage is None or triage.kind != "github_candidate_triage":
        return False

    text = triage.path.read_text(encoding="utf-8", errors="replace").lower()
    return has_any(text, GITHUB_TRIAGE_NO_ACTION_TERMS)


def github_cooldown_status(
    events: list[StateEvent],
    now: datetime,
    *,
    zero_pair_window: timedelta = timedelta(minutes=30),
    cooldown_window: timedelta = timedelta(minutes=45),
) -> CooldownStatus:
    lead_events = [event for event in events if event.kind == "github_leads"]
    if not lead_events:
        return CooldownStatus(False, "No timestamped GitHub lead scans.")

    if len(lead_events) >= 2:
        first, second = lead_events[-2], lead_events[-1]
        if first.zero_signal and second.zero_signal:
            if (
                second.at - first.at <= zero_pair_window
                and now - second.at <= cooldown_window
            ):
                reply_events = [
                    event
                    for event in events
                    if event.kind == "github_replies"
                    and first.at - timedelta(minutes=5)
                    <= event.at
                    <= second.at + timedelta(minutes=5)
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
        if not second.zero_signal:
            return CooldownStatus(False, "Latest GitHub lead scan was not zero-signal.")

    latest_lead = lead_events[-1]
    if not latest_lead.zero_signal:
        return CooldownStatus(False, "Latest GitHub lead scan was not zero-signal.")
    if latest_lead.at > now or now - latest_lead.at > cooldown_window:
        return CooldownStatus(False, "Latest zero lead scan is outside the cooldown window.")

    matching_replies = [
        event
        for event in events
        if event.kind == "github_replies"
        and latest_lead.at - timedelta(minutes=5)
        <= event.at
        <= latest_lead.at + timedelta(minutes=5)
    ]
    if any(event.reply_signal for event in matching_replies):
        return CooldownStatus(False, "A reply signal appeared in the latest GitHub scan pair.")
    if not matching_replies:
        return CooldownStatus(False, "Latest zero lead scan has no matching reply scan.")

    return CooldownStatus(
        True,
        (
            "Latest GitHub reply+lead scan pair was zero-signal "
            f"({stamp(latest_lead.at)})."
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


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def extract_github_label(value: str) -> tuple[str | None, str]:
    link_match = re.search(
        r"\[(?P<label>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\s+#\d+)\]\((?P<url>[^)]+)\)",
        value,
    )
    if link_match:
        return " ".join(link_match.group("label").split()), link_match.group("url")

    plain_match = re.search(
        r"(?P<label>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\s+#\d+)",
        value,
    )
    if plain_match:
        return " ".join(plain_match.group("label").split()), ""
    return None, ""


def parse_active_queue_followup_policy(ops_dir: Path) -> dict[str, str]:
    path = ops_dir / "outbound_pipeline.md"
    if not path.exists():
        return {}

    policies: dict[str, str] = {}
    in_queue = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## Active Non-Farcaster Target Queue"):
            in_queue = True
            continue
        if in_queue and line.startswith("## "):
            break
        if not in_queue or not line.startswith("|"):
            continue
        cells = split_markdown_row(line)
        if len(cells) < 4 or cells[0].lower() in {"lead", "---"}:
            continue
        label, _url = extract_github_label(cells[0])
        if label is None:
            continue
        policies[label.lower()] = " | ".join(cells[1:]).lower()
    return policies


def policy_allows_followup(policy: str) -> bool:
    if not policy:
        return False
    blocked_terms = (
        "single 72h follow-up posted",
        "follow-up posted",
        "no further bump",
        "do not bump",
        "watch-only",
        "watch only",
        "no paid cta",
        "closed_no_reply",
    )
    return not any(term in policy for term in blocked_terms)


def parse_latest_reply_waiting_rows(path: Path) -> tuple[DueFollowUp, ...]:
    rows: list[DueFollowUp] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("|"):
            continue
        cells = split_markdown_row(line)
        if len(cells) < 5:
            continue
        state = cells[0].strip().lower()
        if state in {"state", "---"} or state != "waiting":
            continue
        label, url = extract_github_label(cells[1])
        if label is None:
            continue
        last_agent_raw = cells[2].strip()
        if last_agent_raw == "-":
            continue
        try:
            last_agent_at = datetime.fromisoformat(
                last_agent_raw.replace("Z", "+00:00")
            ).astimezone(UTC)
        except ValueError:
            continue
        rows.append(
            DueFollowUp(
                label=label,
                url=url,
                last_agent_at=last_agent_at,
                due_at=last_agent_at + GITHUB_FOLLOW_UP_WINDOW,
                source_path=path,
            )
        )
    return tuple(rows)


def due_github_followups(
    latest_reply: StateEvent | None,
    ops_dir: Path,
    now: datetime,
) -> tuple[DueFollowUp, ...]:
    if latest_reply is None or latest_reply.kind != "github_replies":
        return ()

    policies = parse_active_queue_followup_policy(ops_dir)
    due = [
        row
        for row in parse_latest_reply_waiting_rows(latest_reply.path)
        if row.due_at <= now
        and policy_allows_followup(policies.get(row.label.lower(), ""))
    ]
    return tuple(sorted(due, key=lambda row: row.due_at))


def parse_devto_published_at(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_devto_published_times(path: Path) -> tuple[datetime, ...]:
    text = path.read_text(encoding="utf-8", errors="replace")
    values = []
    for match in DEVTO_PUBLISHED_AT_RE.findall(text):
        if parsed := parse_devto_published_at(match):
            values.append(parsed)
    return tuple(values)


def devto_archive_only_reason(
    event: StateEvent | None,
    now: datetime,
    *,
    min_post_age: timedelta = DEVTO_ZERO_ARCHIVE_MIN_POST_AGE,
    poll_cooldown: timedelta = DEVTO_ZERO_ARCHIVE_POLL_COOLDOWN,
) -> str | None:
    if event is None or not event.zero_signal:
        return None
    if event.at > now or now - event.at > poll_cooldown:
        return None

    oldest_zero_post = None
    for published_at in load_devto_published_times(event.path):
        if published_at > now:
            continue
        if now - published_at >= min_post_age:
            if oldest_zero_post is None or published_at < oldest_zero_post:
                oldest_zero_post = published_at

    if oldest_zero_post is None:
        return None

    return (
        "Latest dev.to snapshot is zero-signal and includes a post older than "
        f"{int(min_post_age.total_seconds() // 3600)}h "
        f"({stamp(oldest_zero_post)}). Treat dev.to as SEO/archive-only and "
        f"skip passive engagement pulls until {stamp(event.at + poll_cooldown)} "
        "unless the work is native-discovery or distribution."
    )


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


def low_pages_traffic_reason(
    snapshot: PageTrafficSnapshot | None,
    now: datetime,
    *,
    max_age: timedelta = PAGE_TRAFFIC_MAX_AGE,
) -> str | None:
    if snapshot is None:
        return None
    if snapshot.at > now or now - snapshot.at > max_age:
        return None

    measured_pages = [
        page
        for page in snapshot.pages
        if page.status == "ok" and page.window_hits is not None
    ]
    if not measured_pages:
        return None

    baseline = snapshot.bot_baseline_7d
    if any((page.window_hits or 0) > baseline for page in measured_pages):
        return None

    max_hits = max(page.window_hits or 0 for page in measured_pages)
    page_bits = ", ".join(
        f"{page.label}={page.window_hits or 0}" for page in measured_pages
    )
    return (
        f"Latest Pages traffic snapshot ({stamp(snapshot.at)}, "
        f"{snapshot.window_days}d window) has every measured page at or below "
        f"the bot baseline ({max_hits} <= {baseline}; {page_bits}). "
        "More funnel polish should wait for traffic generation."
    )


def pages_traffic_zero_signal(snapshot: PageTrafficSnapshot) -> bool:
    if not snapshot.pages:
        return False

    measured_pages = [
        page
        for page in snapshot.pages
        if page.status == "ok" and page.window_hits is not None
    ]
    if any((page.window_hits or 0) > snapshot.bot_baseline_7d for page in measured_pages):
        return False

    return all(page.status in ("ok", "missing") for page in snapshot.pages)


def pages_traffic_event(snapshot: PageTrafficSnapshot | None) -> StateEvent | None:
    if snapshot is None:
        return None
    return StateEvent(
        kind="pages_traffic",
        path=snapshot.path,
        at=snapshot.at,
        zero_signal=pages_traffic_zero_signal(snapshot),
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


def last_successful_farcaster_reply_time(log_path: Path) -> datetime | None:
    if not log_path.exists():
        return None

    times: list[datetime] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if " | reply -> " not in line or " | success " not in f"{line} ":
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


def recent_farcaster_reply_reason(
    last_reply_at: datetime | None,
    now: datetime,
    *,
    window: timedelta = FARCASTER_REPLY_OBSERVE_WINDOW,
) -> str | None:
    if last_reply_at is None:
        return None
    if last_reply_at > now:
        return None
    if now - last_reply_at > window:
        return None
    return (
        f"A Farcaster outbound reply was logged at {stamp(last_reply_at)}. "
        "Treat this as the current distribution action and verify/render-watch "
        "before scouting or posting another reply."
    )


def recent_channel_scout_reason(
    event: StateEvent | None,
    now: datetime,
    *,
    window: timedelta = CHANNEL_SCOUT_FRESH_WINDOW,
) -> str | None:
    if event is None:
        return None
    if event.at > now:
        return None
    if now - event.at > window:
        return None
    if event.path.name.startswith("channel-poverty-audit-"):
        return (
            "A recent channel-poverty audit already refreshed channel state "
            f"at {stamp(event.at)} (`{event.path.as_posix()}`). Treat the "
            "audit as fresh until a new inbound, target, or unlock signal appears."
        )
    if not event.zero_signal:
        return None
    return (
        "A recent channel scout already found no qualified public action "
        f"at {stamp(event.at)} (`{event.path.as_posix()}`). Treat the "
        "channel-poverty check as fresh until a new inbound, target, or "
        "unlock signal appears."
    )


def is_channel_unlock_ask(text: str) -> bool:
    lower = text.lower()
    segments = [segment.strip() for segment in re.split(r"[\r\n.!?;]+", lower)]
    return any(
        segment
        and has_any(segment, CHANNEL_UNLOCK_TERMS)
        and has_any(segment, CHANNEL_ASK_TERMS)
        for segment in segments
    )


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
    last_farcaster_reply_at: datetime | None = None,
    pages_traffic: PageTrafficSnapshot | None = None,
    active_launch: LaunchWindow | None = None,
) -> Suggestion:
    events = [event for event in events if event.at <= now]
    cooldown = github_cooldown_status(events, now)
    latest_lead = latest(events, "github_leads")
    latest_reply = latest(events, "github_replies")
    latest_no_inventory = latest(events, "no_inventory")
    latest_bounty = latest(events, "bounty")
    latest_devto = latest(events, "devto_engagement")
    latest_productized = latest(events, "productized_review")
    latest_channel_scout = latest(events, "channel_scout")
    latest_proton_inbox = latest(events, "proton_inbox")
    latest_candidate_triage = latest(events, "github_candidate_triage")
    latest_pages_traffic = pages_traffic_event(pages_traffic)
    deadline = parse_deadline(ops_dir)
    latest_events = tuple(
        event
        for event in (
            latest_lead,
            latest_reply,
            latest_candidate_triage,
            latest_no_inventory,
            latest_bounty,
            latest_devto,
            latest_productized,
            latest_channel_scout,
            latest_proton_inbox,
            latest_pages_traffic,
        )
        if event is not None
    )

    if active_launch is not None:
        url_note = f" Live URL: {active_launch.url}." if active_launch.url else ""
        return Suggestion(
            decision="post_launch_window_active",
            reason=(
                f"{active_launch.venue} launch-window marker "
                f"`{active_launch.path.as_posix()}` is active since "
                f"{stamp(active_launch.at)}. First-window reply latency beats "
                f"new content or GitHub scanning while the thread is live.{url_note}"
            ),
            next_steps=(
                "Open the live thread and read the newest comments before replying.",
                "Run `python wallet/balance.py` and `python tools/outbound_fact_check.py research/hn-launch-comment-pack.md` before using any canned number.",
                "Use `research/hn-launch-comment-pack.md` as adapted reply source; do not paste verbatim and do not start a new-content lane.",
                "After 90 minutes or when the thread cools, write fresh replies and log the launch result in ops/improvements.md.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
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

    due_followups = due_github_followups(latest_reply, ops_dir, now)
    if due_followups:
        target = due_followups[0]
        reply_age = minutes_old(now, latest_reply)
        reply_is_stale = (
            reply_age is None
            or reply_age > GITHUB_REPLY_CHECK_FRESH_WINDOW.total_seconds() / 60
        )
        url_note = f" {target.url}" if target.url else ""
        stale_note = (
            " The latest reply report is stale, so verify the thread before posting."
            if reply_is_stale
            else " The latest reply report is fresh enough to use as the gate."
        )
        return Suggestion(
            decision="github_due_followup_verify"
            if reply_is_stale
            else "github_due_followup",
            reason=(
                f"{target.label} reached its 72h no-reply follow-up window at "
                f"{stamp(target.due_at)} based on latest agent comment "
                f"{stamp(target.last_agent_at)} in `{target.source_path.as_posix()}`."
                f"{stale_note}"
            ),
            next_steps=(
                "Run `python tools/github_reply_check.py --state-dir state --agent codex` first if the latest reply report is stale; continue only if the target still shows `waiting`.",
                f"Draft exactly one short no-reply follow-up for {target.label}{url_note}; use one concrete debugging gate and no private-secret ask.",
                "Validate the draft through `ops.outbound_text_guard.validate_outbound_text(..., ascii_only=True)` before posting.",
                "After posting, update ops/outbound_pipeline.md and ops/revenue_pipeline.md to mark the lead no-further-bump/watch-only unless they reply.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
        )

    if cooldown.active:
        bounty_age = minutes_old(now, latest_bounty)
        if (
            latest_bounty is not None
            and latest_bounty.path.name.startswith("archestra-bounty-label-watch-")
            and not latest_bounty.zero_signal
            and bounty_age is not None
            and 0 <= bounty_age <= 240
        ):
            return Suggestion(
                decision="bounty_candidate_triage",
                reason=(
                    f"{cooldown.reason} Latest Archestra label-watch report "
                    f"`{latest_bounty.path.as_posix()}` is non-zero, so a "
                    "fresh unreserved bounty slot may be open."
                ),
                next_steps=(
                    "Open the latest Archestra watch report and the linked GitHub issue before any public action.",
                    "Verify the issue is still unreserved, unassigned, and above the cash floor.",
                    "Read the touched code and draft the failing-test path; only then post `/attempt` with the concrete plan.",
                    "Complete archestra.ai/contributor-onboard before interacting, and do not open a PR until the maintainer/Algora flow accepts the attempt.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )

        if (
            latest_bounty is not None
            and latest_bounty.path.name.startswith("github-bounty-priority-scan-")
            and not latest_bounty.zero_signal
            and bounty_age is not None
            and 0 <= bounty_age <= 240
        ):
            return Suggestion(
                decision="priority_bounty_gate_triage",
                reason=(
                    f"{cooldown.reason} Latest GitHub bounty priority scan "
                    f"`{latest_bounty.path.as_posix()}` found higher-than-low "
                    "priority candidates, so any new bounty-shopping should "
                    "triage priority before topic fit."
                ),
                next_steps=(
                    "Open the priority scan and inspect high-priority candidates before medium or low-priority work.",
                    "Re-verify the selected issue is still open, labeled bounty, and not already in-review/claimed.",
                    "Check project-specific publication or human-review gates before drafting or posting.",
                    "Only claim or submit after a manual code/doc read produces a concrete plan and no disqualifying AI-content rule applies.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )

        no_inventory_age = minutes_old(now, latest_no_inventory)
        devto_age = minutes_old(now, latest_devto)
        devto_archive_reason = devto_archive_only_reason(latest_devto, now)
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
                    "Run `python tools/archestra_bounty_watch.py --state-dir state --agent codex --min-amount 200` as the cheap label-removal watch.",
                    "Re-fetch the most recent saturated/pending bounty leads.",
                    "Only promote a candidate with a canonical open issue and cash-like payout.",
                    "Log watch/hold decisions instead of posting public claims from stale cards.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        if (devto_age is None or devto_age > 30) and devto_archive_reason is None:
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
        productized_age = minutes_old(now, latest_productized)
        if (
            productized_age is not None
            and 0 <= productized_age <= PRODUCTIZED_REVIEW_FRESH_WINDOW.total_seconds() / 60
        ):
            reason = (
                f"{cooldown.reason} A productized/service artifact review just "
                f"shipped at {stamp(latest_productized.at)} "
                f"(`{latest_productized.path.as_posix()}`). More conversion-copy "
                "polish should wait until the updated offer gets distribution or "
                "traffic signal."
            )
            poverty_reason = channel_poverty_reason(now, recent_unlock_asks, last_cast_at)
            reply_reason = recent_farcaster_reply_reason(last_farcaster_reply_at, now)
            scout_reason = recent_channel_scout_reason(latest_channel_scout, now)
            if reply_reason:
                return Suggestion(
                    decision="farcaster_reply_observe",
                    reason=f"{reason} {reply_reason}",
                    next_steps=(
                        "Do not post another Farcaster reply while the fresh outbound reply is in the observe window.",
                        "After roughly 30 minutes, re-fetch the parent permalink or check notifications to confirm whether the reply rendered.",
                        "If it rendered and no one responded, log the result and return to non-Farcaster lead work until a new target appears.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            if poverty_reason and scout_reason:
                return Suggestion(
                    decision="nonpublic_delivery_or_signal_work",
                    reason=f"{reason} {poverty_reason} {scout_reason}",
                    next_steps=(
                        "Do not repeat the channel-poverty audit or Farcaster scout while the channel state is fresh.",
                        "Spend this slot on nonpublic code, reply, delivery, or a new signal source that is not already in cooldown.",
                        "Log the artifact and the restraint in ops/improvements.md so the next heartbeat has durable input.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            if poverty_reason:
                return Suggestion(
                    decision="channel_poverty_audit",
                    reason=f"{reason} {poverty_reason}",
                    next_steps=(
                        "Do not make another productized copy edit while the review snapshot is fresh.",
                        "Check whether a non-duplicative distribution action is available outside current cooldowns.",
                        "If no channel is open, do read-only signal checks or delivery work and log the restraint.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            return Suggestion(
                decision="outbound_traffic_generation",
                reason=reason,
                next_steps=(
                    "Use the freshly aligned productized/playbook offer in one source-tagged distribution action if a channel is open.",
                    "Avoid another site/playbook/listing polish pass until traffic, replies, or a buyer question gives a new reason.",
                    "Refresh `python tools/pages_traffic_check.py --state-dir state --agent codex` after distribution so the next router tick has reach data.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        saturation_reason = funnel_saturation_reason(recent_commits, now)
        traffic_reason = low_pages_traffic_reason(pages_traffic, now)
        outbound_reason = " ".join(
            reason for reason in (saturation_reason, traffic_reason) if reason
        )
        if outbound_reason:
            poverty_reason = channel_poverty_reason(now, recent_unlock_asks, last_cast_at)
            reply_reason = recent_farcaster_reply_reason(last_farcaster_reply_at, now)
            scout_reason = recent_channel_scout_reason(latest_channel_scout, now)
            if reply_reason:
                return Suggestion(
                    decision="farcaster_reply_observe",
                    reason=f"{cooldown.reason} {outbound_reason} {reply_reason}",
                    next_steps=(
                        "Do not post another Farcaster reply while the fresh outbound reply is in the observe window.",
                        "After roughly 30 minutes, re-fetch the parent permalink or check notifications to confirm whether the reply rendered.",
                        "If it rendered and no one responded, log the result and return to non-Farcaster lead work until a new target appears.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            if poverty_reason and scout_reason:
                return Suggestion(
                    decision="nonpublic_delivery_or_signal_work",
                    reason=f"{cooldown.reason} {outbound_reason} {poverty_reason} {scout_reason}",
                    next_steps=(
                        "Do not repeat the channel-poverty audit or Farcaster scout while the channel state is fresh.",
                        "Spend this slot on nonpublic code, reply, delivery, or a new signal source that is not already in cooldown.",
                        "Log the artifact and the restraint in ops/improvements.md so the next heartbeat has durable input.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            if poverty_reason:
                return Suggestion(
                    decision="channel_poverty_audit",
                    reason=f"{cooldown.reason} {outbound_reason} {poverty_reason}",
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
                reason=f"{cooldown.reason} {outbound_reason}",
                next_steps=(
                    "Run a channel-poverty audit before another playbook, longform, or site-polish commit.",
                    "Use a distinct Farcaster, GitHub, dev.to, or HN angle with a source-tagged playbook/longform link only if the channel is open.",
                    "Refresh `python tools/pages_traffic_check.py --state-dir state --agent codex` after the outbound action so the next router tick has reach data.",
                    "If the best path needs Leon's human account, send one binary unlock ask and do not repeat it inside the cooldown window.",
                    "Log the channel, URL, and early engagement signal in ops/ or state/ for the next heartbeat.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        return Suggestion(
            decision="funnel_or_productized_asset_review",
            reason=(
                f"{cooldown.reason} No-inventory and bounty checks are both fresh. "
                f"{devto_archive_reason + ' ' if devto_archive_reason else ''}"
                "The next useful slot is conversion or reusable product/service packaging."
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
                "Run `python tools/github_reply_check.py --state-dir state --agent codex` before any public outbound.",
                "Run `python tools/github_lead_scan.py --state-dir state --agent codex` only after reply state is known.",
                "Do a manual code read before posting or claiming anything.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
        )

    latest_lead_age = minutes_old(now, latest_lead)
    if (
        latest_lead is not None
        and not latest_lead.zero_signal
        and latest_lead_age is not None
        and 0 <= latest_lead_age <= GITHUB_NONZERO_TRIAGE_WINDOW.total_seconds() / 60
    ):
        if triage_closes_lead_scan(latest_candidate_triage, latest_lead):
            if triage_closed_without_action(latest_candidate_triage):
                return Suggestion(
                    decision="github_candidate_closed",
                    reason=(
                        "The latest nonzero GitHub lead scan "
                        f"(`{latest_lead.path.as_posix()}` at {stamp(latest_lead.at)}) "
                        "has a fresh no-action triage closure "
                        f"(`{latest_candidate_triage.path.as_posix()}` at {stamp(latest_candidate_triage.at)}). "
                        "Do not rerun the same crowded or saturated scan."
                    ),
                    next_steps=(
                        "Do not rerun the GitHub lead scan until a reply arrives or the current nonzero scan is stale.",
                        "Use the next heartbeat on a different signal source, delivery task, or maintainer-watch item.",
                        "Only revisit the closed candidates if a maintainer asks for alternatives or the issue state materially changes.",
                    ),
                    cooldown=cooldown,
                    latest_events=latest_events,
                )
            return Suggestion(
                decision="github_candidate_watch",
                reason=(
                    "The latest nonzero GitHub lead scan "
                    f"(`{latest_lead.path.as_posix()}` at {stamp(latest_lead.at)}) "
                    "has a fresh triage closure "
                    f"(`{latest_candidate_triage.path.as_posix()}` at {stamp(latest_candidate_triage.at)}). "
                    "Watch the converted artifact instead of rerunning the same scan."
                ),
                next_steps=(
                    "Watch the logged PR/comment/watch item for maintainer signal before opening another same-repo PR.",
                    "Do not rerun the GitHub lead scan until a reply arrives or the current nonzero scan is stale.",
                    "Use the next heartbeat on a different signal source or delivery task if no maintainer signal appears.",
                ),
                cooldown=cooldown,
                latest_events=latest_events,
            )
        return Suggestion(
            decision="github_candidate_manual_triage",
            reason=(
                "GitHub reply state is fresh and the latest lead scan is nonzero "
                f"(`{latest_lead.path.as_posix()}` at {stamp(latest_lead.at)}). "
                "Do not rerun the same scan while candidate triage is still fresh."
            ),
            next_steps=(
                f"Open `{latest_lead.path.as_posix()}` and pick one candidate for manual code read, or log a no-go if all are saturated.",
                "If a candidate is pickup-ready, convert it into a small PR, precise comment, or tracked watch item.",
                "Only rerun `python tools/github_lead_scan.py --state-dir state --agent codex` after this nonzero scan is stale or all candidates are explicitly closed out.",
            ),
            cooldown=cooldown,
            latest_events=latest_events,
        )

    return Suggestion(
        decision="github_lead_scan",
        reason="GitHub is not in cooldown and reply state is fresh.",
        next_steps=(
            "Run `python tools/github_lead_scan.py --state-dir state --agent codex`.",
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
        "--traffic-baseline-7d",
        type=int,
        default=PAGE_TRAFFIC_BOT_BASELINE_7D,
        help="Override the low-traffic bot baseline for the latest Pages snapshot.",
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
    last_farcaster_reply_at = last_successful_farcaster_reply_time(
        args.ops_dir / "farcaster_reply_log.md"
    )
    pages_traffic = load_latest_pages_traffic(args.state_dir)
    active_launch = load_active_launch_window(args.state_dir, now)
    if pages_traffic is not None:
        pages_traffic = PageTrafficSnapshot(
            pages_traffic.path,
            pages_traffic.at,
            pages_traffic.window_days,
            args.traffic_baseline_7d,
            pages_traffic.pages,
        )
    suggestion = suggest_next_action(
        events,
        args.ops_dir,
        now,
        recent_commits,
        recent_unlock_asks,
        last_cast_at,
        last_farcaster_reply_at,
        pages_traffic,
        active_launch,
    )
    print(format_suggestion(suggestion, now), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
