#!/usr/bin/env python3
"""Read-only Farcaster reply render/notification observer.

The heartbeat router can select `farcaster_reply_observe` shortly after a peer
posts a reply. This tool makes the follow-up repeatable: it reads successful
replies from `ops/farcaster_reply_log.md`, waits for the observe window to
mature, then checks notifications plus reply permalinks without posting.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLY_LOG = ROOT / "ops" / "farcaster_reply_log.md"
DEFAULT_PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "dutchaiagency"
NOTIFICATIONS_URL = "https://farcaster.xyz/~/notifications"
AGENT_ENV_VARS = ("AGENT_NAME", "BRIDGE_AGENT_NAME")


@dataclass(frozen=True)
class FarcasterReply:
    at: datetime
    agent: str
    url: str
    preview: str
    status: str
    reason: str


@dataclass(frozen=True)
class FarcasterVerification:
    at: datetime
    agent: str
    url: str
    note: str


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_reply_log(text: str) -> tuple[FarcasterReply, ...]:
    replies: list[FarcasterReply] = []
    for raw_line in text.splitlines():
        if " | reply -> " not in raw_line:
            continue
        parts = [part.strip() for part in raw_line.split(" | ", 5)]
        if len(parts) < 6:
            continue
        timestamp, agent, action, preview, status, reason = parts
        if not action.startswith("reply -> "):
            continue
        try:
            at = parse_timestamp(timestamp)
        except ValueError:
            continue
        replies.append(
            FarcasterReply(
                at=at,
                agent=agent,
                url=action.removeprefix("reply -> ").strip(),
                preview=preview,
                status=status.lower(),
                reason=reason,
            )
        )
    return tuple(replies)


def parse_verification_log(text: str) -> tuple[FarcasterVerification, ...]:
    verifications: list[FarcasterVerification] = []
    for raw_line in text.splitlines():
        if " | verify -> " not in raw_line:
            continue
        parts = [part.strip() for part in raw_line.split(" | ", 4)]
        if len(parts) < 4:
            continue
        timestamp, agent, action = parts[:3]
        if not action.startswith("verify -> "):
            continue
        try:
            at = parse_timestamp(timestamp)
        except ValueError:
            continue
        note = " | ".join(parts[3:])
        verifications.append(
            FarcasterVerification(
                at=at,
                agent=agent,
                url=action.removeprefix("verify -> ").strip(),
                note=note,
            )
        )
    return tuple(verifications)


def dedupe_replies(replies: tuple[FarcasterReply, ...]) -> tuple[FarcasterReply, ...]:
    by_key: dict[tuple[datetime, str], FarcasterReply] = {}
    for reply in replies:
        key = (reply.at, reply.url)
        previous = by_key.get(key)
        if previous is None or len(reply.preview) > len(previous.preview):
            by_key[key] = reply
    return tuple(sorted(by_key.values(), key=lambda reply: (reply.at, reply.url)))


def successful_replies(log_path: Path) -> tuple[FarcasterReply, ...]:
    if not log_path.exists():
        return ()
    replies = [
        reply
        for reply in parse_reply_log(log_path.read_text(encoding="utf-8", errors="replace"))
        if reply.status == "success"
    ]
    return dedupe_replies(tuple(replies))


def latest_successful_reply(log_path: Path) -> FarcasterReply | None:
    replies = successful_replies(log_path)
    return max(replies, key=lambda reply: reply.at) if replies else None


def latest_successful_reply_for_url(log_path: Path, url: str) -> FarcasterReply | None:
    replies = [reply for reply in successful_replies(log_path) if reply.url == url]
    return max(replies, key=lambda reply: reply.at) if replies else None


def normalize_match_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def contains_normalized_phrase(haystack: str, needle: str) -> bool:
    normalized_haystack = normalize_match_text(haystack)
    normalized_needle = normalize_match_text(needle)
    if not normalized_needle:
        return False
    return f" {normalized_needle} " in f" {normalized_haystack} "


def quoted_fragments(value: str) -> tuple[str, ...]:
    fragments: list[str] = []
    for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", value):
        fragment = match.group(1) or match.group(2)
        fragment = fragment.strip()
        if fragment:
            fragments.append(fragment)
    return tuple(fragments)


def verification_note_matches_reply(reply: FarcasterReply, note: str) -> bool:
    if contains_normalized_phrase(note, default_needle(reply.preview)):
        return True
    for fragment in quoted_fragments(note):
        if len(normalize_match_text(fragment).split()) < 2:
            continue
        if contains_normalized_phrase(reply.preview, fragment):
            return True
    return False


def reply_has_later_verification(
    reply: FarcasterReply,
    verifications: tuple[FarcasterVerification, ...],
    *,
    require_needle: bool = False,
) -> bool:
    return (
        latest_later_verification(
            reply,
            verifications,
            require_needle=require_needle,
        )
        is not None
    )


def latest_later_verification(
    reply: FarcasterReply,
    verifications: tuple[FarcasterVerification, ...],
    *,
    require_needle: bool = False,
) -> FarcasterVerification | None:
    latest: FarcasterVerification | None = None
    for verification in verifications:
        if verification.url != reply.url or verification.at < reply.at:
            continue
        if require_needle and not verification_note_matches_reply(reply, verification.note):
            continue
        if latest is None or verification.at > latest.at:
            latest = verification
    return latest


def unobserved_recent_successful_replies(
    log_path: Path,
    *,
    now: datetime,
    since: timedelta,
    stale_verified_urls: tuple[str, ...] = (),
    stale_after: timedelta | None = None,
) -> tuple[FarcasterReply, ...]:
    if not log_path.exists():
        return ()
    text = log_path.read_text(encoding="utf-8", errors="replace")
    now_utc = now.astimezone(UTC)
    cutoff = now_utc - since
    watched_urls = set(stale_verified_urls)
    verifications = parse_verification_log(text)
    all_replies = dedupe_replies(
        tuple(reply for reply in parse_reply_log(text) if reply.status == "success")
    )
    latest_verification_by_url: dict[str, FarcasterVerification] = {}
    for verification in verifications:
        previous = latest_verification_by_url.get(verification.url)
        if previous is None or verification.at > previous.at:
            latest_verification_by_url[verification.url] = verification
    url_counts: dict[str, int] = {}
    for reply in all_replies:
        url_counts[reply.url] = url_counts.get(reply.url, 0) + 1
    replies = []
    for reply in all_replies:
        if reply.at < cutoff:
            continue
        latest_verification = latest_later_verification(
            reply,
            verifications,
            require_needle=url_counts.get(reply.url, 0) > 1,
        )
        if latest_verification is None:
            replies.append(reply)
            continue
        if (
            stale_after is not None
            and reply.url in watched_urls
        ):
            latest_url_verification = latest_verification_by_url.get(reply.url)
            latest_observed_at = (
                latest_url_verification.at
                if latest_url_verification is not None
                else latest_verification.at
            )
            if now_utc - latest_observed_at >= stale_after:
                replies.append(reply)
            continue
    if watched_urls:
        latest_watched_by_url: dict[str, FarcasterReply] = {}
        collapsed: list[FarcasterReply] = []
        for reply in replies:
            if reply.url not in watched_urls:
                collapsed.append(reply)
                continue
            previous = latest_watched_by_url.get(reply.url)
            if previous is None or reply.at > previous.at:
                latest_watched_by_url[reply.url] = reply
        replies = collapsed + list(latest_watched_by_url.values())
    return tuple(sorted(replies, key=lambda reply: (reply.at, reply.url)))


def default_needle(preview: str) -> str:
    clean = re.sub(r"\s*\(\d+\s+chars\)\s*$", "", preview).strip()
    clean = clean.replace("...", " ")
    words = clean.split()
    return " ".join(words[:8])


def normalize_agent(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"


def default_agent_name(environ: dict[str, str] | None = None) -> str:
    environ = environ if environ is not None else os.environ
    for key in AGENT_ENV_VARS:
        value = environ.get(key, "").strip()
        if value:
            return value
    return "codex"


def state_snapshot_path(state_dir: Path, agent: str, now: datetime) -> Path:
    stamp = now.astimezone(UTC)
    return state_dir / (
        f"farcaster-reply-observe-{stamp.strftime('%Y-%m-%d')}-"
        f"{normalize_agent(agent)}-{stamp.strftime('%H%M')}.md"
    )


def sweep_state_snapshot_path(state_dir: Path, agent: str, now: datetime) -> Path:
    stamp = now.astimezone(UTC)
    return state_dir / (
        f"farcaster-reply-observe-sweep-{stamp.strftime('%Y-%m-%d')}-"
        f"{normalize_agent(agent)}-{stamp.strftime('%H%M')}.md"
    )


def summarize_text(text: str, *, limit: int = 500) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:limit].rstrip()


def collect_browser_text(
    url: str,
    *,
    profile_dir: Path,
    wait_seconds: float,
    timeout_ms: int,
) -> tuple[str, str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=True,
            viewport={"width": 1440, "height": 900},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(NOTIFICATIONS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(wait_seconds)
            notifications = page.inner_text("body")

            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(wait_seconds)
            permalink = page.inner_text("body")
        finally:
            ctx.close()
    return notifications, permalink


def heading(level: int, title: str) -> str:
    return f"{'#' * level} {title}"


def render_target_lines(
    reply: FarcasterReply,
    *,
    now: datetime,
    min_age: timedelta,
    needle: str,
    notifications_text: str | None,
    permalink_text: str | None,
    level: int = 2,
    title: str = "Target",
) -> str:
    age = now.astimezone(UTC) - reply.at
    mature = age >= min_age
    lines = [
        heading(level, title),
        "",
        f"- Posted: `{reply.at.strftime('%Y-%m-%dT%H:%MZ')}` by `{reply.agent}`",
        f"- URL: {reply.url}",
        f"- Needle: `{needle}`",
        f"- Age at check: {age.total_seconds() / 60:.1f} minutes",
    ]
    if not mature:
        due = reply.at + min_age
        lines.extend(
            [
                "",
                heading(level, "Decision"),
                "",
                (
                    "Observe window is not mature yet. Keep the channel quiet and "
                    f"recheck after `{due.strftime('%Y-%m-%dT%H:%MZ')}`."
                ),
            ]
        )
        return "\n".join(lines) + "\n"

    if notifications_text is None and permalink_text is None:
        lines.extend(
            [
                "",
                heading(level, "Decision"),
                "",
                "Browser collection was skipped. Target selection is recorded, but no render or notification conclusion was made.",
            ]
        )
        return "\n".join(lines) + "\n"

    notifications_text = notifications_text or ""
    permalink_text = permalink_text or ""
    needle_present = needle.lower() in permalink_text.lower()
    account_present = "dutchaiagents" in permalink_text.lower()
    no_notifications = "no notifications" in notifications_text.lower()
    lines.extend(
        [
            "",
            heading(level, "Notifications"),
            "",
            (
                "No notifications visible."
                if no_notifications
                else summarize_text(notifications_text, limit=700)
            ),
            "",
            heading(level, "Permalink Render Check"),
            "",
            "| Check | Result |",
            "| --- | --- |",
            f"| Reply needle | {'present' if needle_present else 'not found'} |",
            f"| Account marker | {'present' if account_present else 'not found'} |",
            "",
            heading(level, "Excerpt"),
            "",
            summarize_text(permalink_text, limit=900),
            "",
            heading(level, "Decision"),
            "",
        ]
    )
    if needle_present and account_present and no_notifications:
        lines.append(
            "Reply appears rendered, with no visible notification signal. Keep Farcaster in watch-only mode until a reply or notification appears."
        )
    elif needle_present and account_present:
        lines.append(
            "Reply appears rendered. Review notifications manually before deciding whether the signal merits a response."
        )
    else:
        lines.append(
            "Permalink did not provide a clean rendered-reply confirmation. Do not post again; retry observation or let the channel owner inspect in-browser."
        )
    return "\n".join(lines) + "\n"


def render_report(
    reply: FarcasterReply,
    *,
    now: datetime,
    min_age: timedelta,
    needle: str,
    notifications_text: str | None,
    permalink_text: str | None,
) -> str:
    lines = [
        f"# Farcaster Reply Observe - {now.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Read-only follow-up after the heartbeat router selected `farcaster_reply_observe`.",
        "No casts, replies, deletes, or profile edits were performed.",
        "",
        render_target_lines(
            reply,
            now=now,
            min_age=min_age,
            needle=needle,
            notifications_text=notifications_text,
            permalink_text=permalink_text,
        ).rstrip(),
    ]
    return "\n".join(lines) + "\n"


def render_sweep_report(
    observations: list[tuple[FarcasterReply, str, str | None, str | None]],
    *,
    now: datetime,
    min_age: timedelta,
    since: timedelta,
    watch_urls: tuple[str, ...] = (),
    stale_verify_after: timedelta | None = None,
) -> str:
    mature_count = sum(1 for reply, _, _, _ in observations if now - reply.at >= min_age)
    scope = (
        "recent successful Farcaster replies that either lack a later `verify ->` row, "
        "or are warm-watch URLs whose latest verification is stale."
        if watch_urls
        else "recent successful Farcaster replies that do not have a later `verify ->` row in `ops/farcaster_reply_log.md`."
    )
    lines = [
        f"# Farcaster Reply Observe Sweep - {now.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Read-only sweep across {scope}",
        "No casts, replies, deletes, or profile edits were performed.",
        "",
        "## Summary",
        "",
        f"- Lookback: {since.total_seconds() / 3600:.1f} hours",
        f"- Targets: {len(observations)}",
        f"- Mature targets checked: {mature_count}",
        f"- Deferred targets: {len(observations) - mature_count}",
    ]
    if watch_urls:
        lines.append(f"- Warm-watch URLs: {len(watch_urls)}")
        if stale_verify_after is not None:
            lines.append(
                f"- Stale verify threshold: {stale_verify_after.total_seconds() / 3600:.1f} hours"
            )
    if not observations:
        lines.extend(
            [
                "",
                "No unobserved successful replies found in the lookback window.",
            ]
        )
        return "\n".join(lines) + "\n"

    for index, (reply, needle, notifications_text, permalink_text) in enumerate(observations, start=1):
        lines.extend(
            [
                "",
                render_target_lines(
                    reply,
                    now=now,
                    min_age=min_age,
                    needle=needle,
                    notifications_text=notifications_text,
                    permalink_text=permalink_text,
                    level=3,
                    title=f"Target {index}",
                ).rstrip(),
            ]
        )
    return "\n".join(lines) + "\n"


def normalize_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return parse_timestamp(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reply-log", type=Path, default=DEFAULT_REPLY_LOG)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--agent", default=default_agent_name())
    parser.add_argument("--url", help="Override the latest logged reply URL.")
    parser.add_argument("--needle", help="Text expected in the rendered reply.")
    parser.add_argument(
        "--all-recent",
        action="store_true",
        help="Observe every recent successful reply without a later verify row.",
    )
    parser.add_argument(
        "--watch-url",
        action="append",
        default=[],
        help=(
            "With --all-recent, also include this warm thread when its latest "
            "matching verify row is older than --stale-verify-hours. Can be repeated."
        ),
    )
    parser.add_argument("--since-hours", type=float, default=24.0)
    parser.add_argument(
        "--stale-verify-hours",
        type=float,
        default=6.0,
        help="High-watermark threshold for --watch-url in --all-recent mode.",
    )
    parser.add_argument("--now", help="UTC timestamp override for tests.")
    parser.add_argument("--min-age-minutes", type=float, default=30.0)
    parser.add_argument("--wait-seconds", type=float, default=4.0)
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument(
        "--skip-browser",
        action="store_true",
        help="Write only the cooldown/report skeleton without opening Farcaster.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = normalize_now(args.now)
    min_age = timedelta(minutes=args.min_age_minutes)

    if args.all_recent:
        since = timedelta(hours=args.since_hours)
        replies = unobserved_recent_successful_replies(
            args.reply_log,
            now=now,
            since=since,
            stale_verified_urls=tuple(args.watch_url),
            stale_after=timedelta(hours=args.stale_verify_hours) if args.watch_url else None,
        )
        observations: list[tuple[FarcasterReply, str, str | None, str | None]] = []
        for reply in replies:
            needle = args.needle or default_needle(reply.preview)
            notifications_text: str | None = None
            permalink_text: str | None = None
            if now - reply.at >= min_age and not args.skip_browser:
                notifications_text, permalink_text = collect_browser_text(
                    reply.url,
                    profile_dir=args.profile_dir,
                    wait_seconds=args.wait_seconds,
                    timeout_ms=args.timeout_ms,
                )
            observations.append((reply, needle, notifications_text, permalink_text))

        report = render_sweep_report(
            observations,
            now=now,
            min_age=min_age,
            since=since,
            watch_urls=tuple(args.watch_url),
            stale_verify_after=(
                timedelta(hours=args.stale_verify_hours) if args.watch_url else None
            ),
        )
        args.state_dir.mkdir(parents=True, exist_ok=True)
        path = sweep_state_snapshot_path(args.state_dir, args.agent, now)
        path.write_text(report, encoding="utf-8")
        print(f"wrote {path}")
        return 0

    reply = (
        latest_successful_reply_for_url(args.reply_log, args.url)
        if args.url
        else latest_successful_reply(args.reply_log)
    )
    if reply is None:
        detail = f" for {args.url}" if args.url else ""
        print(f"no successful Farcaster reply{detail} found in {args.reply_log}", file=sys.stderr)
        return 1

    if args.url:
        reply = FarcasterReply(reply.at, reply.agent, args.url, reply.preview, reply.status, reply.reason)
    needle = args.needle or default_needle(reply.preview)

    notifications_text: str | None = None
    permalink_text: str | None = None
    if now - reply.at >= min_age and not args.skip_browser:
        notifications_text, permalink_text = collect_browser_text(
            reply.url,
            profile_dir=args.profile_dir,
            wait_seconds=args.wait_seconds,
            timeout_ms=args.timeout_ms,
        )

    report = render_report(
        reply,
        now=now,
        min_age=min_age,
        needle=needle,
        notifications_text=notifications_text,
        permalink_text=permalink_text,
    )
    args.state_dir.mkdir(parents=True, exist_ok=True)
    path = state_snapshot_path(args.state_dir, args.agent, now)
    path.write_text(report, encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
