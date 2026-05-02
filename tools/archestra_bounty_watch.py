#!/usr/bin/env python3
"""Watch Archestra bounties for newly unreserved high-value slots.

The checker is intentionally read-only. It uses one GitHub issue-search API
request, classifies the open bounty board, and only treats unreserved,
unassigned issues above the configured cash floor as immediate triggers.
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
DEFAULT_REPO = "archestra-ai/archestra"
DEFAULT_BOUNTY_LABEL = "\U0001F48E Bounty"
DEFAULT_MIN_AMOUNT = 200
DEFAULT_USER_AGENT = "survival-agents-archestra-watch/1.0"
RESERVED_LABEL = "reserved for se interview"
AMOUNT_LABEL_RE = re.compile(r"^\$(?P<amount>[0-9][0-9,]*(?:\.\d+)?)$")
AGENT_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True)
class GithubIssue:
    number: int
    title: str
    url: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    updated_at: str
    comments: int

    @property
    def amount_dollars(self) -> float | None:
        for label in self.labels:
            match = AMOUNT_LABEL_RE.match(label.strip())
            if not match:
                continue
            return float(match.group("amount").replace(",", ""))
        return None

    @property
    def reserved(self) -> bool:
        return any(label.strip().lower() == RESERVED_LABEL for label in self.labels)


@dataclass(frozen=True)
class CheckedIssue:
    issue: GithubIssue
    decision: str
    note: str


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
        "archestra-bounty-label-watch-"
        f"{generated_at.strftime('%Y-%m-%d')}-"
        f"{safe_agent(agent)}-"
        f"{generated_at.strftime('%H%M')}.md"
    )


def normalize_issue(payload: dict[str, Any]) -> GithubIssue:
    labels = tuple(
        str(label.get("name") or "")
        for label in payload.get("labels") or []
        if isinstance(label, dict)
    )
    assignees = tuple(
        str(user.get("login") or "")
        for user in payload.get("assignees") or []
        if isinstance(user, dict)
    )
    return GithubIssue(
        number=int(payload.get("number") or 0),
        title=compact(str(payload.get("title") or "")),
        url=str(payload.get("html_url") or payload.get("url") or ""),
        labels=labels,
        assignees=tuple(login for login in assignees if login),
        updated_at=str(payload.get("updated_at") or ""),
        comments=int(payload.get("comments") or 0),
    )


def classify_issue(issue: GithubIssue, *, min_amount: int) -> CheckedIssue:
    amount = issue.amount_dollars
    if amount is None:
        return CheckedIssue(issue, "watch", "missing cash amount label")
    if issue.reserved:
        return CheckedIssue(issue, "watch", "reserved for SE interview")
    if issue.assignees:
        return CheckedIssue(issue, "watch", "already assigned")
    if amount < min_amount:
        return CheckedIssue(
            issue,
            "watch",
            f"open and unassigned, but below ${min_amount} trigger floor",
        )
    return CheckedIssue(issue, "candidate", "fresh unreserved unassigned bounty slot")


def build_query(repo: str, bounty_label: str) -> str:
    return f'repo:{repo} state:open label:"{bounty_label}"'


def fetch_open_bounties(
    *,
    repo: str,
    bounty_label: str,
    api_url: str = DEFAULT_API_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    token: str | None = None,
) -> list[GithubIssue]:
    query = build_query(repo, bounty_label)
    url = f"{api_url}?{urlencode({'q': query, 'per_page': 100})}"
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
    return [normalize_issue(item) for item in items if isinstance(item, dict)]


def classify_issues(issues: list[GithubIssue], *, min_amount: int) -> list[CheckedIssue]:
    results = [classify_issue(issue, min_amount=min_amount) for issue in issues]
    return sorted(
        results,
        key=lambda result: (
            0 if result.decision == "candidate" else 1,
            -(result.issue.amount_dollars or 0),
            result.issue.number,
        ),
    )


def markdown_link(label: str, url: str) -> str:
    escaped = label.replace("|", "\\|")
    if not url:
        return escaped
    return f"[{escaped}]({url})"


def render_markdown(
    results: list[CheckedIssue],
    *,
    repo: str = DEFAULT_REPO,
    bounty_label: str = DEFAULT_BOUNTY_LABEL,
    min_amount: int = DEFAULT_MIN_AMOUNT,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    candidates = [result for result in results if result.decision == "candidate"]
    reserved_or_assigned = [
        result
        for result in results
        if result.issue.reserved or bool(result.issue.assignees)
    ]
    lines = [
        "# Archestra Bounty Label Watch",
        "",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Query: `{build_query(repo, bounty_label)}`",
        f"Trigger: unreserved, unassigned, amount >= ${min_amount}.",
        "",
        "## Summary",
        "",
        f"- Open bounty issues: {len(results)}",
        f"- Reserved or assigned: {len(reserved_or_assigned)}",
        f"- Trigger candidates: {len(candidates)}",
    ]
    if candidates:
        candidate_bits = ", ".join(f"#{result.issue.number}" for result in candidates)
        lines.append(f"- Fresh-slot trigger: {candidate_bits}")
    else:
        lines.append(
            f"- Result: zero immediate candidates. 0 fresh unreserved ${min_amount}+ candidates; keep watch."
        )

    lines.extend(
        [
            "",
            "| Decision | Amount | Issue | Reserved | Assignees | Comments | Updated | Note |",
            "| --- | ---: | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    if not results:
        lines.append("| watch | - | - | - | - | 0 | - | No open bounty issues parsed. |")
        return "\n".join(lines) + "\n"

    for result in results:
        issue = result.issue
        amount = issue.amount_dollars
        amount_text = f"${amount:g}" if amount is not None else "-"
        issue_label = markdown_link(f"#{issue.number} {issue.title}", issue.url)
        assignees = ", ".join(issue.assignees) if issue.assignees else "-"
        lines.append(
            f"| {result.decision} | {amount_text} | {issue_label} | "
            f"{'yes' if issue.reserved else 'no'} | {assignees} | "
            f"{issue.comments} | {issue.updated_at or '-'} | "
            f"{result.note.replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--bounty-label", default=DEFAULT_BOUNTY_LABEL)
    parser.add_argument("--min-amount", type=int, default=DEFAULT_MIN_AMOUNT)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--token", help="Optional GitHub token; defaults to GITHUB_TOKEN/GH_TOKEN.")
    parser.add_argument("--write", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Write to state/archestra-bounty-label-watch-YYYY-MM-DD-agent-HHMM.md.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--now", help="Override current UTC time, for tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write and args.state_dir:
        raise SystemExit("--write and --state-dir are mutually exclusive")

    generated_at = normalize_now(args.now)
    issues = fetch_open_bounties(
        repo=args.repo,
        bounty_label=args.bounty_label,
        api_url=args.api_url,
        user_agent=args.user_agent,
        token=args.token,
    )
    results = classify_issues(issues, min_amount=args.min_amount)
    output = render_markdown(
        results,
        repo=args.repo,
        bounty_label=args.bounty_label,
        min_amount=args.min_amount,
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
