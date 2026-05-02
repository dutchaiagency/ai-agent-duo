#!/usr/bin/env python3
"""Scan GitHub bounty issues by priority label before topic fit.

This is intentionally read-only. It turns a bounty-board habit into a cheap
preflight: fetch open issues with a bounty label, group them by priority
labels, and write a state snapshot that agents can use before choosing a
topic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_URL = "https://api.github.com/search/issues"
DEFAULT_BOUNTY_LABEL = "bounty"
DEFAULT_PRIORITY_LABELS = ("high-priority", "medium-priority", "low-priority")
DEFAULT_USER_AGENT = "survival-agents-github-bounty-priority-scan/1.0"
AGENT_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True)
class GithubIssue:
    number: int
    title: str
    url: str
    labels: tuple[str, ...]
    updated_at: str
    comments: int


@dataclass(frozen=True)
class PrioritizedIssue:
    issue: GithubIssue
    priority: str
    priority_rank: int


def compact(value: str) -> str:
    return " ".join(value.split())


def safe_agent(value: str) -> str:
    normalized = AGENT_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "agent"


def normalize_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def state_snapshot_path(state_dir: Path, agent: str, generated_at: datetime) -> Path:
    return state_dir / (
        "github-bounty-priority-scan-"
        f"{generated_at.strftime('%Y-%m-%d')}-"
        f"{safe_agent(agent)}-"
        f"{generated_at.strftime('%H%M')}.md"
    )


def build_query(repo: str, bounty_label: str = DEFAULT_BOUNTY_LABEL) -> str:
    return f'repo:{repo} type:issue state:open label:"{bounty_label}"'


def normalize_issue(payload: dict[str, Any]) -> GithubIssue:
    labels = tuple(
        str(label.get("name") or "")
        for label in payload.get("labels") or []
        if isinstance(label, dict)
    )
    return GithubIssue(
        number=int(payload.get("number") or 0),
        title=compact(str(payload.get("title") or "")),
        url=str(payload.get("html_url") or payload.get("url") or ""),
        labels=labels,
        updated_at=str(payload.get("updated_at") or ""),
        comments=int(payload.get("comments") or 0),
    )


def priority_for_labels(
    labels: tuple[str, ...],
    priority_labels: tuple[str, ...] = DEFAULT_PRIORITY_LABELS,
) -> tuple[str, int]:
    lower_labels = {label.strip().lower(): label.strip() for label in labels}
    for rank, wanted in enumerate(priority_labels):
        match = lower_labels.get(wanted.strip().lower())
        if match:
            return match, rank
    return "unprioritized", len(priority_labels)


def prioritize_issues(
    issues: list[GithubIssue],
    priority_labels: tuple[str, ...] = DEFAULT_PRIORITY_LABELS,
) -> list[PrioritizedIssue]:
    prioritized: list[PrioritizedIssue] = []
    for issue in issues:
        priority, rank = priority_for_labels(issue.labels, priority_labels)
        prioritized.append(PrioritizedIssue(issue=issue, priority=priority, priority_rank=rank))
    return sorted(prioritized, key=lambda item: (item.priority_rank, item.issue.number))


def fetch_open_bounty_issues(
    *,
    repo: str,
    bounty_label: str = DEFAULT_BOUNTY_LABEL,
    api_url: str = DEFAULT_API_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    token: str | None = None,
    limit: int = 100,
) -> list[GithubIssue]:
    per_page = max(1, min(limit, 100))
    url = f"{api_url}?{urlencode({'q': build_query(repo, bounty_label), 'per_page': per_page})}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": user_agent,
    }
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("GitHub search response did not contain an items list")
    return [normalize_issue(item) for item in items[:limit] if isinstance(item, dict)]


def markdown_link(label: str, url: str) -> str:
    escaped = label.replace("|", "\\|")
    if not url:
        return escaped
    return f"[{escaped}]({url})"


def priority_counts(
    results: list[PrioritizedIssue],
    priority_labels: tuple[str, ...] = DEFAULT_PRIORITY_LABELS,
) -> dict[str, int]:
    counts = {label: 0 for label in priority_labels}
    counts["unprioritized"] = 0
    by_lower = {label.lower(): label for label in counts}
    for result in results:
        key = by_lower.get(result.priority.lower(), "unprioritized")
        counts[key] += 1
    return counts


def render_markdown(
    results: list[PrioritizedIssue],
    *,
    repo: str,
    bounty_label: str = DEFAULT_BOUNTY_LABEL,
    priority_labels: tuple[str, ...] = DEFAULT_PRIORITY_LABELS,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    counts = priority_counts(results, priority_labels)
    lowest_priority_rank = max(0, len(priority_labels) - 1)
    higher_than_low = [
        result for result in results if result.priority_rank < lowest_priority_rank
    ]
    priority_order = " > ".join((*priority_labels, "unprioritized"))

    lines = [
        "# GitHub Bounty Priority Scan",
        "",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Query: `{build_query(repo, bounty_label)}`",
        f"Priority order: `{priority_order}`",
        "",
        "## Summary",
        "",
        f"- Open bounty issues: {len(results)}",
    ]
    lines.extend(f"- {label}: {count}" for label, count in counts.items())
    lines.append(f"- Higher-than-low candidates: {len(higher_than_low)}")
    if higher_than_low:
        labels = ", ".join(f"#{result.issue.number}" for result in higher_than_low[:20])
        lines.append(
            f"- Result: priority candidates present; triage priority before topic fit ({labels})."
        )
    else:
        lines.append(
            "- Result: zero higher-than-low candidates; low/unprioritized bounty work is watch/hold unless no better cash lane exists."
        )

    lines.extend(
        [
            "",
            "| Priority | Issue | Comments | Updated | Labels |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    if not results:
        lines.append("| unprioritized | - | 0 | - | No open bounty issues parsed. |")
        return "\n".join(lines) + "\n"

    for result in results:
        issue = result.issue
        issue_link = markdown_link(f"#{issue.number} {issue.title}", issue.url)
        labels = ", ".join(label for label in issue.labels if label) or "-"
        lines.append(
            f"| {result.priority} | {issue_link} | {issue.comments} | "
            f"{issue.updated_at or '-'} | {labels.replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repo as owner/name.")
    parser.add_argument("--bounty-label", default=DEFAULT_BOUNTY_LABEL)
    parser.add_argument(
        "--priority-labels",
        nargs="+",
        default=list(DEFAULT_PRIORITY_LABELS),
        help="Priority labels from highest to lowest.",
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--token", help="Optional GitHub token; defaults to GITHUB_TOKEN/GH_TOKEN.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--write", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Write to state/github-bounty-priority-scan-YYYY-MM-DD-agent-HHMM.md.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--now", help="Override current UTC time, for tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write and args.state_dir:
        raise SystemExit("--write and --state-dir are mutually exclusive")

    generated_at = normalize_now(args.now)
    priority_labels = tuple(args.priority_labels)
    issues = fetch_open_bounty_issues(
        repo=args.repo,
        bounty_label=args.bounty_label,
        api_url=args.api_url,
        user_agent=args.user_agent,
        token=args.token,
        limit=args.limit,
    )
    results = prioritize_issues(issues, priority_labels)
    output = render_markdown(
        results,
        repo=args.repo,
        bounty_label=args.bounty_label,
        priority_labels=priority_labels,
        generated_at=generated_at,
    )
    write_path = args.write
    if args.state_dir:
        write_path = state_snapshot_path(args.state_dir, args.agent, generated_at)

    if write_path:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(output, encoding="utf-8")
        print(write_path.as_posix())
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
