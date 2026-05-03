#!/usr/bin/env python3
"""Validate Algora bounty listings against live GitHub issue state.

Algora pages can show stale "open" bounties after the linked GitHub issue has
already been closed. This tool keeps the bounty lane read-only and filters those
false positives before any agent claims or implements work.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


GITHUB_ISSUE_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)(?:[?#].*)?$")
GITHUB_PR_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:[?#].*)?$")
GITHUB_REFERENCE_URL_RE = re.compile(
    r"https://github\.com/[^\s\"'<>]+/[^\s\"'<>]+/(?:issues|pull)/\d+(?:[?#][^\s\"'<>]*)?"
)
ISSUE_REFERENCE_TEXT_RE = re.compile(
    r"(?:issue|for|fix(?:es)?|close[sd]?)\s+#(?P<number>\d{2,})",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(r"\$[\d][\d,]*(?:\.\d+)?")
OPEN_BOUNTIES_SECTION_RE = re.compile(r"^open bounties\b", re.IGNORECASE)
WORK_INTENT_RE = re.compile(
    r"("
    r"/attempt\b|/claim\b|pull/\d+|pr\s*#\d+|"
    r"pr submitted|submitted pr|"
    r"opened (?:a )?(?:pr|pull request)|(?:pr|pull request) opened|"
    r"i(?:'d| would) like to (?:fix|work on)|"
    r"i(?:'ll| will) submit a pr|"
    r"submit a pr with the fix|"
    r"i can fix this|"
    r"i(?:'m| am) working on this|"
    r"working on this|"
    r"interested in working|"
    r"interested in this bounty|"
    r"please wait"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AlgoraBounty:
    source_url: str
    amount: str
    title: str
    github_url: str
    repo: str
    number: int

    @property
    def label(self) -> str:
        if not self.repo or not self.number:
            return "unlinked bounty"
        return f"{self.repo} #{self.number}"


@dataclass(frozen=True)
class GithubIssue:
    repo: str
    number: int
    state: str
    title: str = ""
    url: str = ""
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()
    work_intent_comments: int = 0
    latest_work_intent_at: str = ""
    error: str = ""


@dataclass(frozen=True)
class CheckedBounty:
    bounty: AlgoraBounty
    issue: GithubIssue
    decision: str
    note: str


def compact_text(value: str) -> str:
    return " ".join(value.split())


def has_work_intent_comment(value: str) -> bool:
    return bool(WORK_INTENT_RE.search(value))


def parse_github_issue_url(url: str) -> tuple[str, int] | None:
    match = GITHUB_ISSUE_RE.match(url)
    if not match:
        return None
    owner, repo, number = match.groups()
    return f"{owner}/{repo}", int(number)


def parse_github_pr_url(url: str) -> tuple[str, int] | None:
    match = GITHUB_PR_RE.match(url)
    if not match:
        return None
    owner, repo, number = match.groups()
    return f"{owner}/{repo}", int(number)


def is_algora_bounty_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "algora.io" and "/bounties/" in parsed.path


class AlgoraBountyParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.in_open_section = False
        self.current_amount = ""
        self.current_href = ""
        self.current_anchor_text_parts: list[str] = []
        self.bounties: list[AlgoraBounty] = []
        self._seen: set[tuple[str, int]] = set()
        self._seen_unlinked: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = {name: value for name, value in attrs}
        href = attr_map.get("href")
        self.current_href = urljoin(self.source_url, href) if href else ""
        self.current_anchor_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            anchor_text = compact_text(" ".join(self.current_anchor_text_parts))
            self._record_anchor_bounty(anchor_text)
            self.current_href = ""
            self.current_anchor_text_parts = []

    def handle_data(self, data: str) -> None:
        text = compact_text(data)
        if not text:
            return

        if self.current_href:
            self.current_anchor_text_parts.append(text)
            return

        if text.startswith(("Completed Bounties", "Fund GitHub issues")):
            self.in_open_section = False
            return
        if OPEN_BOUNTIES_SECTION_RE.match(text):
            self.in_open_section = True
            return

        if not self.in_open_section:
            return

        amount_match = AMOUNT_RE.fullmatch(text)
        if amount_match:
            self.current_amount = amount_match.group(0)
            return

    def _record_anchor_bounty(self, text: str) -> None:
        if not text or not self.current_href or not self.in_open_section:
            return
        inline_amount_match = AMOUNT_RE.search(text)
        amount = self.current_amount or (inline_amount_match.group(0) if inline_amount_match else "")
        title = (
            compact_text(AMOUNT_RE.sub("", text, count=1))
            if inline_amount_match
            else text
        )

        parsed = parse_github_issue_url(self.current_href)
        if parsed is None and not (
            amount and is_algora_bounty_url(self.current_href)
        ):
            return
        if parsed is None:
            if self.current_href in self._seen_unlinked:
                return
            self._seen_unlinked.add(self.current_href)
            self.bounties.append(
                AlgoraBounty(
                    source_url=self.source_url,
                    amount=amount,
                    title=title,
                    github_url=self.current_href,
                    repo="",
                    number=0,
                )
            )
            return

        repo, number = parsed
        key = (repo, number)
        if key in self._seen:
            return
        self._seen.add(key)
        self.bounties.append(
                AlgoraBounty(
                    source_url=self.source_url,
                    amount=amount,
                    title=title,
                    github_url=self.current_href,
                    repo=repo,
                    number=number,
            )
        )


class IndividualAlgoraBountyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.meta_title = ""
        self.amount = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value for name, value in attrs}
        if tag == "title":
            self.in_title = True
            return
        if tag != "meta":
            return
        prop = attr_map.get("property") or attr_map.get("name") or ""
        if prop in {"og:title", "twitter:title"} and attr_map.get("content"):
            self.meta_title = compact_text(str(attr_map["content"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        text = compact_text(data)
        if not text:
            return
        self.text_parts.append(text)
        if self.in_title:
            self.title_parts.append(text)
        if not self.amount and AMOUNT_RE.fullmatch(text):
            self.amount = text

    @property
    def title(self) -> str:
        if self.meta_title:
            return self.meta_title
        title = compact_text(" ".join(self.title_parts))
        return title.removesuffix("| Algora").strip()

    @property
    def text(self) -> str:
        return compact_text(" ".join(self.text_parts))


def parse_individual_algora_bounty(html: str, *, source_url: str) -> AlgoraBounty | None:
    if not is_algora_bounty_url(source_url):
        return None

    parser = IndividualAlgoraBountyParser()
    parser.feed(html)
    if not parser.title and not parser.amount:
        return None

    github_urls = [
        match.group(0).rstrip(".,)")
        for match in GITHUB_REFERENCE_URL_RE.finditer(html)
    ]
    for github_url in github_urls:
        parsed = parse_github_issue_url(github_url)
        if parsed is None:
            continue
        repo, number = parsed
        return AlgoraBounty(
            source_url=source_url,
            amount=parser.amount,
            title=parser.title,
            github_url=github_url,
            repo=repo,
            number=number,
        )

    pr_repos = []
    for github_url in github_urls:
        parsed_pr = parse_github_pr_url(github_url)
        if parsed_pr is not None:
            pr_repos.append((parsed_pr[0], github_url))
    issue_numbers = {
        int(match.group("number"))
        for match in ISSUE_REFERENCE_TEXT_RE.finditer(parser.text)
    }
    unique_pr_repos = {repo for repo, _github_url in pr_repos}
    if len(unique_pr_repos) == 1 and len(issue_numbers) == 1:
        repo = next(iter(unique_pr_repos))
        number = next(iter(issue_numbers))
        return AlgoraBounty(
            source_url=source_url,
            amount=parser.amount,
            title=parser.title,
            github_url=f"https://github.com/{repo}/issues/{number}",
            repo=repo,
            number=number,
        )

    return AlgoraBounty(
        source_url=source_url,
        amount=parser.amount,
        title=parser.title,
        github_url=github_urls[0] if github_urls else source_url,
        repo="",
        number=0,
    )


def parse_algora_bounties(html: str, *, source_url: str) -> list[AlgoraBounty]:
    parser = AlgoraBountyParser(source_url)
    parser.feed(html)
    if not parser.bounties:
        bounty = parse_individual_algora_bounty(html, source_url=source_url)
        if bounty is not None:
            return [bounty]
    return parser.bounties


def fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": "survival-agents-algora-check/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_github_issue(bounty: AlgoraBounty) -> GithubIssue:
    cmd = [
        "gh",
        "issue",
        "view",
        str(bounty.number),
        "--repo",
        bounty.repo,
        "--json",
        "state,title,url,labels,assignees,comments",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload: dict[str, Any] = json.loads(proc.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as exc:
        return GithubIssue(
            repo=bounty.repo,
            number=bounty.number,
            state="error",
            error=str(exc),
        )

    labels = tuple(str(label.get("name") or "") for label in payload.get("labels") or [])
    assignees = tuple(
        str(user.get("login") or "") for user in payload.get("assignees") or []
    )
    intent_comments = [
        comment
        for comment in payload.get("comments") or []
        if has_work_intent_comment(str(comment.get("body") or ""))
    ]
    latest_intent_at = ""
    if intent_comments:
        latest_intent_at = max(str(comment.get("createdAt") or "") for comment in intent_comments)
    return GithubIssue(
        repo=bounty.repo,
        number=bounty.number,
        state=str(payload.get("state") or ""),
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or bounty.github_url),
        labels=labels,
        assignees=assignees,
        work_intent_comments=len(intent_comments),
        latest_work_intent_at=latest_intent_at,
    )


def classify_bounty(bounty: AlgoraBounty, issue: GithubIssue) -> CheckedBounty:
    if issue.state.lower() == "error":
        return CheckedBounty(bounty, issue, "verify_manually", issue.error)
    if issue.state.upper() != "OPEN":
        return CheckedBounty(
            bounty,
            issue,
            "skip",
            f"GitHub issue is {issue.state.lower() or 'not open'}",
        )
    if issue.assignees:
        return CheckedBounty(
            bounty,
            issue,
            "watch",
            "already assigned to " + ", ".join(issue.assignees),
        )
    if issue.work_intent_comments >= 3:
        latest = (
            f"; latest {issue.latest_work_intent_at}"
            if issue.latest_work_intent_at
            else ""
        )
        return CheckedBounty(
            bounty,
            issue,
            "watch",
            f"crowded: {issue.work_intent_comments} attempt/claim/PR comments{latest}",
        )
    if issue.work_intent_comments:
        latest = (
            f"; latest {issue.latest_work_intent_at}"
            if issue.latest_work_intent_at
            else ""
        )
        return CheckedBounty(
            bounty,
            issue,
            "watch",
            (
                f"active work signal: {issue.work_intent_comments} "
                f"attempt/claim/PR comment{latest}"
            ),
        )
    return CheckedBounty(bounty, issue, "candidate", "open and unassigned on GitHub")


def check_sources(source_urls: list[str], *, limit: int | None = None) -> list[CheckedBounty]:
    bounties: list[AlgoraBounty] = []
    for source_url in source_urls:
        try:
            html = fetch_url(source_url)
        except URLError as exc:
            failed = AlgoraBounty(
                source_url=source_url,
                amount="",
                title="source fetch failed",
                github_url="",
                repo="",
                number=0,
            )
            issue = GithubIssue(repo="", number=0, state="error", error=str(exc))
            bounties.append(failed)
            continue
        bounties.extend(parse_algora_bounties(html, source_url=source_url))

    if limit is not None:
        bounties = bounties[:limit]

    checked: list[CheckedBounty] = []
    for bounty in bounties:
        if not bounty.repo:
            issue = GithubIssue(
                repo="",
                number=0,
                state="unknown",
                title=bounty.title,
                url=bounty.github_url,
            )
            checked.append(
                CheckedBounty(
                    bounty,
                    issue,
                    "verify_manually",
                    "Algora listing has no linked GitHub issue; validate scope manually",
                )
            )
            continue
        else:
            issue = fetch_github_issue(bounty)
        checked.append(classify_bounty(bounty, issue))
    return checked


def markdown_link(label: str, url: str) -> str:
    if not url:
        return label
    return f"[{label}]({url})"


def render_markdown(
    results: list[CheckedBounty], *, generated_at: datetime | None = None
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        "# Algora Bounty Verification",
        "",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Decision | Amount | Issue | GitHub State | Note | Source |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    if not results:
        lines.append("| none | - | - | - | No Algora open bounties parsed. | - |")
        return "\n".join(lines) + "\n"

    for result in results:
        bounty = result.bounty
        issue = result.issue
        title = issue.title or bounty.title or bounty.label
        issue_label = f"{bounty.label}: {title}" if bounty.label.strip() else title
        source = markdown_link("Algora", bounty.source_url)
        issue_link = markdown_link(issue_label, issue.url or bounty.github_url)
        note = result.note.replace("|", "/")
        lines.append(
            f"| {result.decision} | {bounty.amount or '-'} | {issue_link} | "
            f"{issue.state or '-'} | {note} | {source} |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse Algora bounty pages and validate linked GitHub issue state."
    )
    parser.add_argument("sources", nargs="+", help="Algora organization or bounty page URLs.")
    parser.add_argument("--limit", type=int, help="Validate only the first N parsed bounties.")
    parser.add_argument("--write", type=Path, help="Write markdown report to this path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = check_sources(args.sources, limit=args.limit)
    markdown = render_markdown(results)
    if args.write:
        args.write.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
