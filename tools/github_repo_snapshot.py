#!/usr/bin/env python3
"""Render a compact Markdown snapshot for a public GitHub repository.

This avoids `gh --jq` so social-signal scouts keep working from PowerShell even
when optional GitHub fields, such as topics or latest releases, are null.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_FIELDS = (
    "nameWithOwner,description,stargazerCount,forkCount,licenseInfo,"
    "latestRelease,createdAt,updatedAt,primaryLanguage,repositoryTopics,"
    "homepageUrl,issues"
)
ISSUE_FIELDS = "number,title,url,state,labels,createdAt,updatedAt"


@dataclass(frozen=True)
class IssueSnapshot:
    number: int
    title: str
    url: str
    state: str
    labels: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class RepoSnapshot:
    name_with_owner: str
    description: str = ""
    stars: int = 0
    forks: int = 0
    license: str = ""
    primary_language: str = ""
    topics: tuple[str, ...] = ()
    homepage_url: str = ""
    created_at: str = ""
    updated_at: str = ""
    open_issue_count: int = 0
    latest_release_tag: str = ""
    latest_release_url: str = ""
    latest_release_published_at: str = ""
    open_issues: tuple[IssueSnapshot, ...] = field(default_factory=tuple)

    @property
    def url(self) -> str:
        return f"https://github.com/{self.name_with_owner}"


def gh_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout or "{}")


def label_names(labels: Any) -> tuple[str, ...]:
    if not isinstance(labels, list):
        return ()
    names = []
    for label in labels:
        if isinstance(label, dict):
            name = label.get("name")
            if name:
                names.append(str(name))
    return tuple(names)


def topic_names(topics: Any) -> tuple[str, ...]:
    if not isinstance(topics, list):
        return ()
    names = []
    for topic in topics:
        if isinstance(topic, dict):
            name = topic.get("name")
            if name:
                names.append(str(name))
        elif isinstance(topic, str):
            names.append(topic)
    return tuple(names)


def from_repo_payload(payload: dict[str, Any]) -> RepoSnapshot:
    release = payload.get("latestRelease") or {}
    license_info = payload.get("licenseInfo") or {}
    language = payload.get("primaryLanguage") or {}
    issues = payload.get("issues") or {}
    return RepoSnapshot(
        name_with_owner=str(payload.get("nameWithOwner") or ""),
        description=str(payload.get("description") or ""),
        stars=int(payload.get("stargazerCount") or 0),
        forks=int(payload.get("forkCount") or 0),
        license=str(
            license_info.get("spdxId")
            or license_info.get("key")
            or license_info.get("name")
            or ""
        ),
        primary_language=str(language.get("name") or ""),
        topics=topic_names(payload.get("repositoryTopics")),
        homepage_url=str(payload.get("homepageUrl") or ""),
        created_at=str(payload.get("createdAt") or ""),
        updated_at=str(payload.get("updatedAt") or ""),
        open_issue_count=int(issues.get("totalCount") or 0),
        latest_release_tag=str(release.get("tagName") or ""),
        latest_release_url=str(release.get("url") or ""),
        latest_release_published_at=str(release.get("publishedAt") or ""),
    )


def from_issue_payload(payload: dict[str, Any]) -> IssueSnapshot:
    return IssueSnapshot(
        number=int(payload.get("number") or 0),
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or ""),
        state=str(payload.get("state") or ""),
        labels=label_names(payload.get("labels")),
        created_at=str(payload.get("createdAt") or ""),
        updated_at=str(payload.get("updatedAt") or ""),
    )


def fetch_snapshot(repo: str, *, issue_limit: int) -> RepoSnapshot:
    repo_payload = gh_json(["gh", "repo", "view", repo, "--json", REPO_FIELDS])
    issues_payload = gh_json(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(issue_limit),
            "--json",
            ISSUE_FIELDS,
        ]
    )
    snapshot = from_repo_payload(repo_payload)
    return RepoSnapshot(
        **{
            **snapshot.__dict__,
            "open_issues": tuple(
                from_issue_payload(issue)
                for issue in issues_payload
                if isinstance(issue, dict)
            ),
        }
    )


def md_escape(value: str) -> str:
    return value.replace("|", "\\|")


def fmt(value: str | int) -> str:
    return str(value) if value not in ("", 0) else "-"


def render_markdown(
    snapshot: RepoSnapshot,
    *,
    generated_at: datetime,
    scout_note: str = "",
) -> str:
    generated = generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    release = "-"
    if snapshot.latest_release_tag:
        if snapshot.latest_release_url:
            release = f"[{snapshot.latest_release_tag}]({snapshot.latest_release_url})"
        else:
            release = snapshot.latest_release_tag
        if snapshot.latest_release_published_at:
            release += f" ({snapshot.latest_release_published_at})"

    topics = ", ".join(snapshot.topics) if snapshot.topics else "-"
    lines = [
        f"# GitHub Repo Snapshot - {snapshot.name_with_owner}",
        "",
        f"Generated: {generated}",
        "",
        f"Source: {snapshot.url}",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Description | {md_escape(snapshot.description or '-')} |",
        f"| Stars / forks | {snapshot.stars} / {snapshot.forks} |",
        f"| Primary language | {fmt(snapshot.primary_language)} |",
        f"| License | {fmt(snapshot.license)} |",
        f"| Latest release | {release} |",
        f"| Created / updated | {fmt(snapshot.created_at)} / {fmt(snapshot.updated_at)} |",
        f"| Open issues | {snapshot.open_issue_count} |",
        f"| Homepage | {snapshot.homepage_url or '-'} |",
        f"| Topics | {md_escape(topics)} |",
        "",
        "## Open Issues",
        "",
    ]

    if snapshot.open_issues:
        lines.extend(["| Issue | Labels | Updated |", "| --- | --- | --- |"])
        for issue in snapshot.open_issues:
            label_text = ", ".join(issue.labels) if issue.labels else "-"
            lines.append(
                f"| [#{issue.number} {md_escape(issue.title)}]({issue.url}) "
                f"| {md_escape(label_text)} | {fmt(issue.updated_at)} |"
            )
    else:
        lines.append("No open issues returned by `gh issue list`.")

    if scout_note:
        lines.extend(["", "## Scout Note", "", scout_note.strip()])

    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="GitHub repo in owner/name form")
    parser.add_argument("--issue-limit", type=int, default=5)
    parser.add_argument("--write", type=Path, help="Write Markdown to this path")
    parser.add_argument(
        "--scout-note",
        default="",
        help="Optional short Markdown note appended after metadata",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    snapshot = fetch_snapshot(args.repo, issue_limit=args.issue_limit)
    markdown = render_markdown(
        snapshot,
        generated_at=datetime.now(UTC),
        scout_note=args.scout_note,
    )
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
