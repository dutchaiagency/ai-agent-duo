#!/usr/bin/env python3
"""Read-only Farcaster reply render/notification observer.

The heartbeat router can select `farcaster_reply_observe` shortly after a peer
posts a reply. This tool makes the follow-up repeatable: it reads the latest
successful reply from `ops/farcaster_reply_log.md`, waits for the observe window
to mature, then checks notifications plus the reply permalink without posting.
"""

from __future__ import annotations

import argparse
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


@dataclass(frozen=True)
class FarcasterReply:
    at: datetime
    agent: str
    url: str
    preview: str
    status: str
    reason: str


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


def latest_successful_reply(log_path: Path) -> FarcasterReply | None:
    if not log_path.exists():
        return None
    replies = [
        reply
        for reply in parse_reply_log(log_path.read_text(encoding="utf-8", errors="replace"))
        if reply.status == "success"
    ]
    return max(replies, key=lambda reply: reply.at) if replies else None


def default_needle(preview: str) -> str:
    clean = re.sub(r"\s*\(\d+\s+chars\)\s*$", "", preview).strip()
    clean = clean.replace("...", " ")
    words = clean.split()
    return " ".join(words[:8])


def normalize_agent(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"


def state_snapshot_path(state_dir: Path, agent: str, now: datetime) -> Path:
    stamp = now.astimezone(UTC)
    return state_dir / (
        f"farcaster-reply-observe-{stamp.strftime('%Y-%m-%d')}-"
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


def render_report(
    reply: FarcasterReply,
    *,
    now: datetime,
    min_age: timedelta,
    needle: str,
    notifications_text: str | None,
    permalink_text: str | None,
) -> str:
    age = now.astimezone(UTC) - reply.at
    mature = age >= min_age
    lines = [
        f"# Farcaster Reply Observe - {now.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Read-only follow-up after the heartbeat router selected `farcaster_reply_observe`.",
        "No casts, replies, deletes, or profile edits were performed.",
        "",
        "## Target",
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
                "## Decision",
                "",
                (
                    "Observe window is not mature yet. Keep the channel quiet and "
                    f"recheck after `{due.strftime('%Y-%m-%dT%H:%MZ')}`."
                ),
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
            "## Notifications",
            "",
            (
                "No notifications visible."
                if no_notifications
                else summarize_text(notifications_text, limit=700)
            ),
            "",
            "## Permalink Render Check",
            "",
            "| Check | Result |",
            "| --- | --- |",
            f"| Reply needle | {'present' if needle_present else 'not found'} |",
            f"| Account marker | {'present' if account_present else 'not found'} |",
            "",
            "## Excerpt",
            "",
            summarize_text(permalink_text, limit=900),
            "",
            "## Decision",
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


def normalize_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return parse_timestamp(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reply-log", type=Path, default=DEFAULT_REPLY_LOG)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--url", help="Override the latest logged reply URL.")
    parser.add_argument("--needle", help="Text expected in the rendered reply.")
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
    reply = latest_successful_reply(args.reply_log)
    if reply is None:
        print(f"no successful Farcaster reply found in {args.reply_log}", file=sys.stderr)
        return 1

    if args.url:
        reply = FarcasterReply(reply.at, reply.agent, args.url, reply.preview, reply.status, reply.reason)
    needle = args.needle or default_needle(reply.preview)
    min_age = timedelta(minutes=args.min_age_minutes)

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
