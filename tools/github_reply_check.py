#!/usr/bin/env python3
"""Check active GitHub outbound targets for replies.

This intentionally avoids `gh --jq` so it works reliably from PowerShell.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any


TARGET_RE = re.compile(
    r"^\|\s*(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+#(?P<number>\d+)\s*\|"
)


@dataclass(frozen=True)
class Target:
    repo: str
    number: int

    @property
    def label(self) -> str:
        return f"{self.repo} #{self.number}"


@dataclass(frozen=True)
class ReplyStatus:
    repo: str
    number: int
    state: str
    issue_title: str = ""
    issue_url: str = ""
    last_agent_comment_at: str = ""
    latest_reply_author: str = ""
    latest_reply_at: str = ""
    latest_reply_excerpt: str = ""
    note: str = ""

    @property
    def label(self) -> str:
        return f"{self.repo} #{self.number}"


def parse_targets(markdown: str) -> list[Target]:
    targets: list[Target] = []
    in_queue = False
    for line in markdown.splitlines():
        if line.startswith("## Active Non-Farcaster Target Queue"):
            in_queue = True
            continue
        if in_queue and line.startswith("## "):
            break
        if not in_queue:
            continue
        match = TARGET_RE.match(line)
        if not match:
            continue
        targets.append(
            Target(repo=match.group("repo"), number=int(match.group("number")))
        )
    return targets


def parse_github_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def excerpt(value: str, limit: int = 120) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def comment_author(comment: dict[str, Any]) -> str:
    author = comment.get("author") or {}
    return str(author.get("login") or "")


def classify_thread(
    target: Target, payload: dict[str, Any], *, agent_login: str
) -> ReplyStatus:
    comments = payload.get("comments") or []
    agent_comments = [
        comment
        for comment in comments
        if comment_author(comment).lower() == agent_login.lower()
    ]
    if not agent_comments:
        return ReplyStatus(
            repo=target.repo,
            number=target.number,
            state="no_agent_comment",
            issue_title=str(payload.get("title") or ""),
            issue_url=str(payload.get("url") or ""),
            note=f"No {agent_login} comment found.",
        )

    last_agent = max(agent_comments, key=lambda c: parse_github_time(c["createdAt"]))
    last_agent_at = str(last_agent["createdAt"])
    last_agent_dt = parse_github_time(last_agent_at)
    replies = [
        comment
        for comment in comments
        if comment_author(comment).lower() != agent_login.lower()
        and parse_github_time(comment["createdAt"]) > last_agent_dt
    ]
    if not replies:
        return ReplyStatus(
            repo=target.repo,
            number=target.number,
            state="waiting",
            issue_title=str(payload.get("title") or ""),
            issue_url=str(payload.get("url") or ""),
            last_agent_comment_at=last_agent_at,
            note="No maintainer or user reply after our latest comment.",
        )

    latest_reply = max(replies, key=lambda c: parse_github_time(c["createdAt"]))
    return ReplyStatus(
        repo=target.repo,
        number=target.number,
        state="reply",
        issue_title=str(payload.get("title") or ""),
        issue_url=str(payload.get("url") or ""),
        last_agent_comment_at=last_agent_at,
        latest_reply_author=comment_author(latest_reply),
        latest_reply_at=str(latest_reply["createdAt"]),
        latest_reply_excerpt=excerpt(str(latest_reply.get("body") or "")),
    )


def fetch_issue(target: Target) -> dict[str, Any]:
    cmd = [
        "gh",
        "issue",
        "view",
        str(target.number),
        "--repo",
        target.repo,
        "--json",
        "comments,state,title,url",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def check_targets(targets: list[Target], *, agent_login: str) -> list[ReplyStatus]:
    results: list[ReplyStatus] = []
    for target in targets:
        try:
            payload = fetch_issue(target)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            results.append(
                ReplyStatus(
                    repo=target.repo,
                    number=target.number,
                    state="error",
                    note=str(exc),
                )
            )
            continue
        results.append(classify_thread(target, payload, agent_login=agent_login))
    return results


def render_markdown(
    results: list[ReplyStatus], *, generated_at: datetime | None = None
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        f"# GitHub Reply Check - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| State | Lead | Last agent comment | Latest reply | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lead = result.label
        if result.issue_url:
            lead = f"[{lead}]({result.issue_url})"
        latest = "-"
        if result.latest_reply_author:
            latest = (
                f"{result.latest_reply_author} at {result.latest_reply_at}: "
                f"{result.latest_reply_excerpt}"
            )
        latest = latest.replace("|", "\\|")
        note = (result.note or "-").replace("|", "\\|")
        lines.append(
            f"| {result.state} | {lead} | "
            f"{result.last_agent_comment_at or '-'} | {latest} | {note} |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check GitHub outbound replies.")
    parser.add_argument(
        "--pipeline",
        type=Path,
        default=Path("ops/outbound_pipeline.md"),
        help="Markdown pipeline file containing the active target queue.",
    )
    parser.add_argument("--agent-login", default="dutchaiagency")
    parser.add_argument("--write", type=Path, help="Write report to this path.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        markdown = args.pipeline.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"github-reply-check: {exc}", file=sys.stderr)
        return 2

    targets = parse_targets(markdown)
    if not targets:
        print("github-reply-check: no active targets found", file=sys.stderr)
        return 1

    results = check_targets(targets, agent_login=args.agent_login)
    if args.json:
        output = json.dumps([asdict(result) for result in results], indent=2)
    else:
        output = render_markdown(results)

    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
