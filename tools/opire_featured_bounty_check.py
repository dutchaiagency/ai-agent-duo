#!/usr/bin/env python3
"""Verify Opire featured bounty cards against live GitHub state."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


DEFAULT_HOME_URL = "https://opire.dev/home"
DEFAULT_USER_AGENT = "survival-agents-opire-featured-check/1.0"
DEFAULT_MIN_AMOUNT = 100
DEFAULT_MAX_COMMENTS = 50
GITHUB_ISSUE_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
    r"(?:[?#].*)?$"
)
AGENT_RE = re.compile(r"[^a-z0-9_-]+")
WORK_INTENT_RE = re.compile(
    r"("
    r"/attempt\b|/try\b|/claim\b|"
    r"pull/\d+|pr\s*#\d+|"
    r"opened (?:a )?(?:pr|pull request)|"
    r"(?:pr|pull request) (?:opened|submitted)|"
    r"i(?:'m| am) (?:going to )?work(?:ing)? on|"
    r"i(?:'ll| will) (?:take|submit|open|work)|"
    r"interested in working|"
    r"i can fix"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OpireCard:
    opire_id: str
    title: str
    github_url: str
    repo: str
    number: int
    amount_cents: int
    unit: str
    languages: tuple[str, ...]
    claimer_users: tuple[str, ...]
    trying_users: tuple[str, ...]
    opire_url: str = ""

    @property
    def amount_dollars(self) -> float:
        return self.amount_cents / 100

    @property
    def label(self) -> str:
        if self.repo and self.number:
            return f"{self.repo} #{self.number}"
        return self.title or self.opire_id or "unlinked Opire card"


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    url: str
    updated_at: str = ""
    is_draft: bool = False


@dataclass(frozen=True)
class GithubIssue:
    repo: str
    number: int
    state: str
    title: str = ""
    url: str = ""
    assignees: tuple[str, ...] = ()
    comments_count: int = 0
    work_intent_comments: int = 0
    latest_work_intent_at: str = ""
    open_prs: tuple[PullRequest, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class CheckedCard:
    card: OpireCard
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
        "opire-featured-bounty-check-"
        f"{generated_at.strftime('%Y-%m-%d')}-"
        f"{safe_agent(agent)}-"
        f"{generated_at.strftime('%H%M')}.md"
    )


def parse_github_issue_url(url: str) -> tuple[str, int] | None:
    match = GITHUB_ISSUE_RE.match(url)
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo')}", int(match.group("number"))


def fetch_home(url: str, *, user_agent: str = DEFAULT_USER_AGENT) -> str:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_featured_payload(html: str) -> Any:
    marker = "featuredIssues"
    marker_index = html.find(marker)
    if marker_index < 0:
        raise ValueError("Opire home page did not contain featuredIssues data")

    prefix = 'self.__next_f.push([1,"'
    start = html.rfind(prefix, 0, marker_index)
    if start < 0:
        raise ValueError("Could not find React Flight chunk for featuredIssues")

    script_end = html.find("</script>", marker_index)
    if script_end < 0:
        raise ValueError("Could not find script end for featuredIssues chunk")

    end = html.rfind('"])', marker_index, script_end)
    if end < 0:
        raise ValueError("Could not find React Flight string terminator")

    encoded = html[start + len(prefix) : end]
    decoded = json.loads(f'"{encoded}"')
    if ":" not in decoded:
        raise ValueError("React Flight chunk did not contain a payload prefix")

    return json.loads(decoded.split(":", 1)[1])


def find_featured_issues(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        featured = value.get("featuredIssues")
        if isinstance(featured, list):
            return [item for item in featured if isinstance(item, dict)]
        for child in value.values():
            found = find_featured_issues(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_featured_issues(child)
            if found:
                return found
    return []


def usernames(items: Any) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    values = []
    for item in items:
        if isinstance(item, dict) and item.get("username"):
            values.append(str(item["username"]))
    return tuple(values)


def normalize_card(payload: dict[str, Any]) -> OpireCard:
    github_url = str(payload.get("url") or "")
    parsed = parse_github_issue_url(github_url)
    repo, number = parsed if parsed is not None else ("", 0)
    price = payload.get("pendingPrice") if isinstance(payload.get("pendingPrice"), dict) else {}
    languages = payload.get("programmingLanguages")
    if not isinstance(languages, list):
        languages = []
    opire_id = str(payload.get("id") or "")
    opire_url = f"https://app.opire.dev/issues/{opire_id}" if opire_id else ""
    return OpireCard(
        opire_id=opire_id,
        title=compact(str(payload.get("title") or "")),
        github_url=github_url,
        repo=repo,
        number=number,
        amount_cents=int(price.get("value") or 0),
        unit=str(price.get("unit") or ""),
        languages=tuple(str(item) for item in languages if item),
        claimer_users=usernames(payload.get("claimerUsers")),
        trying_users=usernames(payload.get("tryingUsers")),
        opire_url=opire_url,
    )


def parse_featured_cards(html: str) -> list[OpireCard]:
    payload = extract_featured_payload(html)
    return [normalize_card(item) for item in find_featured_issues(payload)]


def gh_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout or "{}")


def comment_author(comment: dict[str, Any]) -> str:
    author = comment.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "")
    return ""


def comment_created_at(comment: dict[str, Any]) -> str:
    return str(comment.get("createdAt") or "")


def has_work_intent_comment(value: str) -> bool:
    return bool(WORK_INTENT_RE.search(value))


def fetch_open_prs(repo: str, number: int, *, limit: int = 10) -> tuple[PullRequest, ...]:
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "open",
        "--search",
        str(number),
        "--json",
        "number,title,url,updatedAt,isDraft",
        "--limit",
        str(limit),
    ]
    try:
        payload = gh_json(cmd)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return ()
    if not isinstance(payload, list):
        return ()
    prs = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        prs.append(
            PullRequest(
                number=int(item.get("number") or 0),
                title=compact(str(item.get("title") or "")),
                url=str(item.get("url") or ""),
                updated_at=str(item.get("updatedAt") or ""),
                is_draft=bool(item.get("isDraft")),
            )
        )
    return tuple(pr for pr in prs if pr.number)


def fetch_github_issue(card: OpireCard) -> GithubIssue:
    if not card.repo or not card.number:
        return GithubIssue(
            repo=card.repo,
            number=card.number,
            state="unknown",
            title=card.title,
            url=card.github_url,
            error="Opire card has no canonical GitHub issue URL",
        )

    cmd = [
        "gh",
        "issue",
        "view",
        str(card.number),
        "--repo",
        card.repo,
        "--json",
        "state,title,url,assignees,comments",
    ]
    try:
        payload = gh_json(cmd)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as exc:
        return GithubIssue(
            repo=card.repo,
            number=card.number,
            state="error",
            title=card.title,
            url=card.github_url,
            error=str(exc),
        )

    comments = payload.get("comments")
    if not isinstance(comments, list):
        comments = []
    intent_comments = [
        comment
        for comment in comments
        if isinstance(comment, dict)
        and has_work_intent_comment(str(comment.get("body") or ""))
    ]
    latest_intent = ""
    if intent_comments:
        latest_intent = max(comment_created_at(comment) for comment in intent_comments)
    assignees_payload = payload.get("assignees")
    if not isinstance(assignees_payload, list):
        assignees_payload = []
    assignees = tuple(
        str(item.get("login") or "")
        for item in assignees_payload
        if isinstance(item, dict) and item.get("login")
    )
    return GithubIssue(
        repo=card.repo,
        number=card.number,
        state=str(payload.get("state") or ""),
        title=str(payload.get("title") or card.title),
        url=str(payload.get("url") or card.github_url),
        assignees=assignees,
        comments_count=len(comments),
        work_intent_comments=len(intent_comments),
        latest_work_intent_at=latest_intent,
        open_prs=fetch_open_prs(card.repo, card.number),
    )


def classify_card(
    card: OpireCard,
    issue: GithubIssue,
    *,
    min_amount: int = DEFAULT_MIN_AMOUNT,
    max_comments: int = DEFAULT_MAX_COMMENTS,
) -> CheckedCard:
    if issue.error:
        return CheckedCard(card, issue, "verify_manually", issue.error)

    if issue.state.upper() != "OPEN":
        return CheckedCard(
            card,
            issue,
            "skip",
            f"GitHub issue is {issue.state.lower() or 'not open'}",
        )

    blockers: list[str] = []
    if card.amount_dollars < min_amount:
        blockers.append(f"below ${min_amount} floor")
    if issue.assignees:
        blockers.append("assigned to " + ", ".join(issue.assignees))
    if card.claimer_users:
        blockers.append("Opire claimer(s): " + ", ".join(card.claimer_users[:4]))
    if card.trying_users:
        blockers.append("Opire trying user(s): " + ", ".join(card.trying_users[:4]))
    if issue.open_prs:
        prs = ", ".join(f"#{pr.number}" for pr in issue.open_prs[:4])
        blockers.append(f"open related PR(s): {prs}")
    if issue.work_intent_comments:
        latest = (
            f"; latest {issue.latest_work_intent_at}"
            if issue.latest_work_intent_at
            else ""
        )
        blockers.append(f"{issue.work_intent_comments} work-intent comment(s){latest}")
    if issue.comments_count > max_comments:
        blockers.append(f"crowded thread: {issue.comments_count} comments")

    if blockers:
        return CheckedCard(card, issue, "watch", "; ".join(blockers[:5]))
    return CheckedCard(card, issue, "candidate", "open, unassigned, uncrowded featured card")


def check_cards(
    cards: list[OpireCard],
    *,
    min_amount: int = DEFAULT_MIN_AMOUNT,
    max_comments: int = DEFAULT_MAX_COMMENTS,
) -> list[CheckedCard]:
    checked = [
        classify_card(
            card,
            fetch_github_issue(card),
            min_amount=min_amount,
            max_comments=max_comments,
        )
        for card in cards
    ]
    return sorted(
        checked,
        key=lambda item: (
            0 if item.decision == "candidate" else 1,
            0 if item.decision == "watch" else 1,
            -item.card.amount_dollars,
            item.card.repo,
            item.card.number,
        ),
    )


def markdown_link(label: str, url: str) -> str:
    escaped = label.replace("|", "\\|")
    if not url:
        return escaped
    return f"[{escaped}]({url})"


def render_markdown(
    results: list[CheckedCard],
    *,
    source_url: str = DEFAULT_HOME_URL,
    min_amount: int = DEFAULT_MIN_AMOUNT,
    max_comments: int = DEFAULT_MAX_COMMENTS,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    candidates = [result for result in results if result.decision == "candidate"]
    lines = [
        "# Opire Featured Bounty Verification",
        "",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Source: {source_url}",
        f"Trigger: open GitHub issue, amount >= ${min_amount}, unassigned, no Opire claim/try, no open related PR, <= {max_comments} comments.",
        "",
        "## Summary",
        "",
        f"- Featured cards parsed: {len(results)}",
        f"- Immediate candidates: {len(candidates)}",
    ]
    if candidates:
        labels = ", ".join(result.card.label for result in candidates)
        lines.append(f"- Candidate trigger: {labels}")
    else:
        lines.append(
            "- Result: zero immediate candidates from Opire; all parsed cards are stale, closed, claimed, crowded, assigned, below floor, or have active PR/work signals."
        )

    lines.extend(
        [
            "",
            "| Decision | Amount | Lead | GitHub state | Opire activity | Note | Source |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    if not results:
        lines.append("| none | - | - | - | - | No featured cards parsed. | - |")
        return "\n".join(lines) + "\n"

    for result in results:
        card = result.card
        issue = result.issue
        amount = f"${card.amount_dollars:,.0f}" if card.amount_dollars else "-"
        lead_title = issue.title or card.title or card.label
        lead = markdown_link(f"{card.label}: {lead_title}", issue.url or card.github_url)
        activity_bits = []
        if card.claimer_users:
            activity_bits.append(f"claimers={len(card.claimer_users)}")
        if card.trying_users:
            activity_bits.append(f"trying={len(card.trying_users)}")
        activity = ", ".join(activity_bits) or "-"
        source = markdown_link("Opire", card.opire_url) if card.opire_url else "-"
        note = result.note.replace("|", "/")
        lines.append(
            f"| {result.decision} | {amount} | {lead} | "
            f"{issue.state or '-'} | {activity} | {note} | {source} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home-url", default=DEFAULT_HOME_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--min-amount", type=int, default=DEFAULT_MIN_AMOUNT)
    parser.add_argument("--max-comments", type=int, default=DEFAULT_MAX_COMMENTS)
    parser.add_argument("--limit", type=int, help="Validate only the first N cards.")
    parser.add_argument("--write", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Write to state/opire-featured-bounty-check-YYYY-MM-DD-agent-HHMM.md.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--now", help="Override current UTC time, for tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write and args.state_dir:
        raise SystemExit("--write and --state-dir are mutually exclusive")

    generated_at = normalize_now(args.now)
    html = fetch_home(args.home_url, user_agent=args.user_agent)
    cards = parse_featured_cards(html)
    if args.limit is not None:
        cards = cards[: args.limit]
    results = check_cards(
        cards,
        min_amount=args.min_amount,
        max_comments=args.max_comments,
    )
    output = render_markdown(
        results,
        source_url=args.home_url,
        min_amount=args.min_amount,
        max_comments=args.max_comments,
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
