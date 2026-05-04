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

try:
    from tools.agent_identity import default_agent_name
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from agent_identity import default_agent_name


TARGET_RE = re.compile(
    r"^\|\s*(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+#(?P<number>\d+)\s*\|"
)
TARGET_SPEC_RE = re.compile(
    r"^(?:https://github\.com/)?"
    r"(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"(?:/(?:issues|pull)/|#)"
    r"(?P<number>\d+)"
    r"/?$"
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


class IssueUnavailable(RuntimeError):
    """Raised when an active target issue can no longer be read."""


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


def parse_target_spec(value: str) -> Target:
    match = TARGET_SPEC_RE.match(value.strip())
    if not match:
        raise ValueError(
            "target must look like owner/repo#123 or "
            "https://github.com/owner/repo/issues/123"
        )
    return Target(repo=match.group("repo"), number=int(match.group("number")))


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
        issue_state = str(payload.get("state") or "").upper()
        if issue_state == "CLOSED":
            return ReplyStatus(
                repo=target.repo,
                number=target.number,
                state="closed_no_reply",
                issue_title=str(payload.get("title") or ""),
                issue_url=str(payload.get("url") or ""),
                last_agent_comment_at=last_agent_at,
                note=(
                    "Issue is closed with no maintainer or user reply after "
                    "our latest comment."
                ),
            )
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


def normalize_rest_issue(
    issue: dict[str, Any], comments: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "title": issue.get("title") or "",
        "state": str(issue.get("state") or "").upper(),
        "url": issue.get("html_url") or issue.get("url") or "",
        "comments": [
            {
                "author": {"login": (comment.get("user") or {}).get("login") or ""},
                "createdAt": comment.get("created_at") or "",
                "body": comment.get("body") or "",
            }
            for comment in comments
        ],
    }


def gh_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout or "{}")


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
    try:
        return gh_json(cmd)
    except subprocess.CalledProcessError as exc:
        issue_cmd = ["gh", "api", f"repos/{target.repo}/issues/{target.number}"]
        comments_cmd = [
            "gh",
            "api",
            f"repos/{target.repo}/issues/{target.number}/comments",
        ]
        try:
            issue = gh_json(issue_cmd)
            comments = gh_json(comments_cmd)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as rest_exc:
            raise IssueUnavailable(
                "Repo or issue is no longer readable through GraphQL or REST."
            ) from rest_exc
        return normalize_rest_issue(issue, comments)


def check_targets(targets: list[Target], *, agent_login: str) -> list[ReplyStatus]:
    results: list[ReplyStatus] = []
    for target in targets:
        try:
            payload = fetch_issue(target)
        except IssueUnavailable as exc:
            results.append(
                ReplyStatus(
                    repo=target.repo,
                    number=target.number,
                    state="unavailable",
                    note=str(exc),
                )
            )
            continue
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


def target_slug(targets: list[Target]) -> str:
    if len(targets) == 1:
        target = targets[0]
        value = f"{target.repo}-{target.number}".lower()
        return re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return f"multi-{len(targets)}"


def default_output_path(
    state_dir: Path,
    agent: str,
    generated_at: datetime,
    *,
    ad_hoc_targets: list[Target] | None = None,
) -> Path:
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d")
    hhmm = generated_at.astimezone(UTC).strftime("%H%M")
    if ad_hoc_targets:
        slug = target_slug(ad_hoc_targets)
        return state_dir / f"github-ad-hoc-replies-{slug}-{stamp}-{agent}-{hhmm}.md"
    return state_dir / f"github-replies-{stamp}-{agent}-{hhmm}.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check GitHub outbound replies.")
    parser.add_argument(
        "--pipeline",
        type=Path,
        default=Path("ops/outbound_pipeline.md"),
        help="Markdown pipeline file containing the active target queue.",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help=(
            "Ad-hoc GitHub issue target to check, e.g. owner/repo#123 or "
            "https://github.com/owner/repo/issues/123. Can be repeated. "
            "When supplied, --pipeline is not read."
        ),
    )
    parser.add_argument("--agent-login", default="dutchaiagency")
    parser.add_argument("--write", type=Path, help="Write report to this path.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        help=(
            "Write to state/github-replies-YYYY-MM-DD-agent-HHMM.md, or "
            "state/github-ad-hoc-replies-<target>-YYYY-MM-DD-agent-HHMM.md "
            "when --target is supplied."
        ),
    )
    parser.add_argument("--agent", default=default_agent_name())
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        targets = [parse_target_spec(value) for value in args.target]
    except ValueError as exc:
        print(f"github-reply-check: {exc}", file=sys.stderr)
        return 2
    if not targets:
        try:
            markdown = args.pipeline.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"github-reply-check: {exc}", file=sys.stderr)
            return 2
        targets = parse_targets(markdown)
    if not targets:
        print("github-reply-check: no active targets found", file=sys.stderr)
        return 1

    generated_at = datetime.now(UTC)
    results = check_targets(targets, agent_login=args.agent_login)
    if args.json:
        output = json.dumps([asdict(result) for result in results], indent=2)
    else:
        output = render_markdown(results, generated_at=generated_at)

    output_path = args.write
    if output_path is None and args.state_dir is not None:
        output_path = default_output_path(
            args.state_dir,
            args.agent,
            generated_at,
            ad_hoc_targets=targets if args.target else None,
        )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
