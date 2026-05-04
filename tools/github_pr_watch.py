#!/usr/bin/env python3
"""Check active GitHub PRs for maintainer comments or reviews.

This is separate from github_reply_check.py because proof-work often moves from
issue comments into PRs, where reviews are as important as plain comments.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from tools.agent_identity import default_agent_name
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from agent_identity import default_agent_name


WATCH_HEADING = "## Active GitHub PR Watch"
TARGET_CELL_RE = re.compile(
    r"^(?:https://github\.com/)?"
    r"(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"(?:(?:/pull/)|(?:\s*#))"
    r"(?P<number>\d+)"
    r"/?$"
)
MARKDOWN_LINK_RE = re.compile(r"^\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)$")
PR_FIELDS = (
    "number,state,title,url,author,createdAt,updatedAt,comments,reviews,"
    "latestReviews,reviewDecision,mergeStateStatus,statusCheckRollup,body,"
    "mergedAt,mergedBy,headRefName,headRefOid"
)
ISSUE_FIELDS = (
    "number,state,stateReason,closedAt,title,url,closedByPullRequestsReferences"
)
CHECK_FAILURE_CONCLUSIONS = {
    "ACTION_REQUIRED",
    "CANCELLED",
    "FAILURE",
    "FAILED",
    "STARTUP_FAILURE",
    "TIMED_OUT",
}
CHECK_SUCCESS_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
CHECK_PENDING_STATUSES = {
    "EXPECTED",
    "IN_PROGRESS",
    "PENDING",
    "QUEUED",
    "REQUESTED",
    "WAITING",
}
WORKFLOW_ACTION_REQUIRED_VALUES = {"ACTION_REQUIRED"}
IGNORABLE_DEPLOY_AUTH_PHRASES = (
    "is attempting to deploy a commit",
    "first needs to",
    "authorize it",
)
IGNORABLE_CODERABBIT_PROGRESS_PHRASES = (
    "auto-generated comment",
    "review in progress",
    "currently processing new changes",
)
IGNORABLE_CODERABBIT_SUMMARY_PHRASES = (
    "auto-generated comment: summarize",
    "no actionable comments were generated",
)
IGNORABLE_CUBIC_NO_ISSUES_PHRASES = (
    "no issues found",
)


@dataclass(frozen=True)
class PullTarget:
    repo: str
    number: int

    @property
    def label(self) -> str:
        return f"{self.repo} #{self.number}"


@dataclass(frozen=True)
class PullStatus:
    repo: str
    number: int
    state: str
    pr_state: str = ""
    title: str = ""
    url: str = ""
    last_agent_activity_at: str = ""
    latest_signal_author: str = ""
    latest_signal_at: str = ""
    latest_signal_excerpt: str = ""
    review_decision: str = ""
    merge_state_status: str = ""
    check_summary: str = ""
    note: str = ""

    @property
    def label(self) -> str:
        return f"{self.repo} #{self.number}"


def parse_target_spec(value: str) -> PullTarget:
    value = value.strip()
    match = TARGET_CELL_RE.match(value)
    if not match:
        raise ValueError(
            "PR target must look like owner/repo#123, owner/repo #123, "
            "or https://github.com/owner/repo/pull/123"
        )
    return PullTarget(repo=match.group("repo"), number=int(match.group("number")))


def parse_target_cell(value: str) -> PullTarget:
    value = value.strip()
    link = MARKDOWN_LINK_RE.match(value)
    if link:
        url = link.group("url")
        if "github.com/" in url:
            return parse_target_spec(url)
        return parse_target_spec(link.group("label"))
    return parse_target_spec(value)


def parse_watch_targets(markdown: str) -> list[PullTarget]:
    targets: list[PullTarget] = []
    in_watch = False
    for line in markdown.splitlines():
        if line.startswith(WATCH_HEADING):
            in_watch = True
            continue
        if in_watch and line.startswith("## "):
            break
        if not in_watch or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in {"pr", "---"}:
            continue
        try:
            targets.append(parse_target_cell(cells[0]))
        except ValueError:
            continue
    return targets


def parse_github_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def excerpt(value: str, limit: int = 120) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def actor_login(item: dict[str, Any], *, field: str = "author") -> str:
    actor = item.get(field) or {}
    return str(actor.get("login") or "")


def item_time(item: dict[str, Any]) -> str:
    return str(item.get("createdAt") or item.get("submittedAt") or "")


def item_body(item: dict[str, Any]) -> str:
    return str(item.get("body") or item.get("state") or "")


def check_name(item: dict[str, Any]) -> str:
    return str(
        item.get("name")
        or item.get("workflowName")
        or item.get("context")
        or item.get("__typename")
        or "check"
    )


def check_conclusion(item: dict[str, Any]) -> str:
    return str(item.get("conclusion") or "").upper()


def check_status(item: dict[str, Any]) -> str:
    return str(item.get("status") or item.get("state") or "").upper()


def check_target_url(item: dict[str, Any]) -> str:
    return str(item.get("targetUrl") or item.get("target_url") or "")


def is_ignorable_deploy_auth_check(item: dict[str, Any]) -> bool:
    name = check_name(item).lower()
    target_url = check_target_url(item).lower()
    return name == "vercel" and "/git/authorize" in target_url


def check_completed_at(item: dict[str, Any]) -> str:
    return str(
        item.get("completedAt")
        or item.get("completed_at")
        or item.get("startedAt")
        or item.get("started_at")
        or ""
    )


def check_rollup_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("statusCheckRollup") or []
    return [
        item
        for item in items
        if isinstance(item, dict) and not is_ignorable_deploy_auth_check(item)
    ]


def run_conclusion(item: dict[str, Any]) -> str:
    return str(item.get("conclusion") or "").upper()


def run_status(item: dict[str, Any]) -> str:
    return str(item.get("status") or "").upper()


def run_time(item: dict[str, Any]) -> str:
    return str(
        item.get("updatedAt")
        or item.get("createdAt")
        or item.get("startedAt")
        or ""
    )


def run_label(item: dict[str, Any]) -> str:
    return str(item.get("workflowName") or item.get("name") or "workflow")


def is_action_required_run(item: dict[str, Any]) -> bool:
    return (
        run_conclusion(item) in WORKFLOW_ACTION_REQUIRED_VALUES
        or run_status(item) in WORKFLOW_ACTION_REQUIRED_VALUES
    )


def failing_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in check_rollup_items(payload)
        if check_conclusion(item) in CHECK_FAILURE_CONCLUSIONS
        or (
            not check_conclusion(item)
            and check_status(item) in CHECK_FAILURE_CONCLUSIONS
        )
    ]


def check_rollup_summary(payload: dict[str, Any]) -> str:
    items = check_rollup_items(payload)
    if not items:
        return "none reported"

    failed = failing_checks(payload)
    pending = [
        item
        for item in items
        if not check_conclusion(item) and check_status(item) in CHECK_PENDING_STATUSES
    ]
    passed = [
        item
        for item in items
        if check_conclusion(item) in CHECK_SUCCESS_CONCLUSIONS
        or (
            not check_conclusion(item)
            and check_status(item) in CHECK_SUCCESS_CONCLUSIONS
        )
    ]
    other = len(items) - len(failed) - len(pending) - len(passed)
    parts = [
        f"{len(failed)} failed",
        f"{len(pending)} pending",
        f"{len(passed)} passed/skipped",
    ]
    if other:
        parts.append(f"{other} other")
    return ", ".join(parts)


def check_failure_excerpt(payload: dict[str, Any]) -> tuple[str, str]:
    failed = failing_checks(payload)
    if not failed:
        return "", ""

    latest = max(
        failed,
        key=lambda item: check_completed_at(item) or "0000-00-00T00:00:00Z",
    )
    first = failed[0]
    label = check_name(first)
    conclusion = check_conclusion(first) or check_status(first) or "FAILED"
    if len(failed) == 1:
        body = f"check: {label} ({conclusion})"
    else:
        body = f"checks: {len(failed)} failing; first {label} ({conclusion})"
    return check_completed_at(latest), body


def timeline_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for comment in payload.get("comments") or []:
        created_at = item_time(comment)
        if not created_at:
            continue
        items.append(
            {
                "author": actor_login(comment),
                "created_at": created_at,
                "body": item_body(comment),
                "kind": "comment",
            }
        )
    for review in list(payload.get("reviews") or []) + list(
        payload.get("latestReviews") or []
    ):
        submitted_at = item_time(review)
        if not submitted_at:
            continue
        items.append(
            {
                "author": actor_login(review),
                "created_at": submitted_at,
                "body": item_body(review),
                "kind": "review",
            }
        )
    deduped: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for item in items:
        deduped[
            (item["author"], item["created_at"], item["kind"], item["body"])
        ] = item
    return list(deduped.values())


def is_ignorable_timeline_item(item: dict[str, str]) -> bool:
    author = item["author"].lower()
    body = item["body"].lower()
    if author == "vercel" and all(phrase in body for phrase in IGNORABLE_DEPLOY_AUTH_PHRASES):
        return True
    if author == "coderabbitai" and all(
        phrase in body for phrase in IGNORABLE_CODERABBIT_PROGRESS_PHRASES
    ):
        return True
    if author == "coderabbitai" and all(
        phrase in body for phrase in IGNORABLE_CODERABBIT_SUMMARY_PHRASES
    ):
        return True
    if author == "coderabbitai" and item["kind"] == "review" and body == "approved":
        return True
    if author in {"cubic-dev-ai", "cubic"} and item["kind"] == "review" and all(
        phrase in body for phrase in IGNORABLE_CUBIC_NO_ISSUES_PHRASES
    ):
        return True
    return False


def is_ship_timeline_item(item: dict[str, str]) -> bool:
    body = item["body"].lower()
    return bool(
        re.search(r"\bshipped\s+in\s+v?\d", body)
        or re.search(r"\breleased\s+in\s+v?\d", body)
        or ("now live" in body and ("fix" in body or "change" in body or "patch" in body))
    )


def classify_pr(
    target: PullTarget, payload: dict[str, Any], *, agent_login: str
) -> PullStatus:
    pr_author = actor_login(payload)
    created_at = str(payload.get("createdAt") or "")
    items = timeline_items(payload)
    agent_times = [
        item["created_at"]
        for item in items
        if item["author"].lower() == agent_login.lower()
    ]
    if pr_author.lower() == agent_login.lower() and created_at:
        agent_times.append(created_at)
    if not agent_times:
        return PullStatus(
            repo=target.repo,
            number=target.number,
            state="no_agent_activity",
            pr_state=str(payload.get("state") or ""),
            title=str(payload.get("title") or ""),
            url=str(payload.get("url") or ""),
            review_decision=str(payload.get("reviewDecision") or ""),
            merge_state_status=str(payload.get("mergeStateStatus") or ""),
            check_summary=check_rollup_summary(payload),
            note=f"No {agent_login} PR activity found.",
        )

    last_agent_at = max(agent_times, key=parse_github_time)
    last_agent_dt = parse_github_time(last_agent_at)
    signals = [
        item
        for item in items
        if item["author"].lower() != agent_login.lower()
        and parse_github_time(item["created_at"]) > last_agent_dt
        and not is_ignorable_timeline_item(item)
    ]
    pr_state = str(payload.get("state") or "").upper()
    base = {
        "repo": target.repo,
        "number": target.number,
        "pr_state": str(payload.get("state") or ""),
        "title": str(payload.get("title") or ""),
        "url": str(payload.get("url") or ""),
        "last_agent_activity_at": last_agent_at,
        "review_decision": str(payload.get("reviewDecision") or ""),
        "merge_state_status": str(payload.get("mergeStateStatus") or ""),
        "check_summary": check_rollup_summary(payload),
    }
    if signals:
        latest = max(signals, key=lambda item: parse_github_time(item["created_at"]))
        shipped = pr_state == "MERGED" or (
            pr_state == "CLOSED" and is_ship_timeline_item(latest)
        )
        return PullStatus(
            **base,
            state="shipped" if shipped else "signal",
            latest_signal_author=latest["author"],
            latest_signal_at=latest["created_at"],
            latest_signal_excerpt=excerpt(
                f"{latest['kind']}: {latest['body']}".strip()
            ),
            note=(
                "PR is merged; latest non-agent signal shown."
                if pr_state == "MERGED"
                else "Closed PR has maintainer ship/release signal after latest agent activity."
                if shipped
                else ""
            ),
        )

    if pr_state == "MERGED":
        merged_at = str(payload.get("mergedAt") or payload.get("updatedAt") or "")
        return PullStatus(
            **base,
            state="shipped",
            latest_signal_author=actor_login(payload, field="mergedBy") or "github-pr",
            latest_signal_at=merged_at,
            latest_signal_excerpt="merged",
            note="PR is merged with no non-agent comment or review after latest agent activity.",
        )

    if pr_state in {"CLOSED", "MERGED"}:
        return PullStatus(
            **base,
            state="closed_no_signal",
            note="PR is closed with no non-agent comment or review after latest agent activity.",
        )

    check_signal_at, check_signal_body = check_failure_excerpt(payload)
    if check_signal_body:
        return PullStatus(
            **base,
            state="check_signal",
            latest_signal_author="github-checks",
            latest_signal_at=check_signal_at,
            latest_signal_excerpt=excerpt(check_signal_body),
            note="Current PR checks need action; no non-agent comment or review after latest agent activity.",
        )

    return PullStatus(
        **base,
        state="waiting",
        note="No non-agent comment, review, or failing check after latest agent activity.",
    )


def gh_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout or "{}")


def fetch_pr(target: PullTarget) -> dict[str, Any]:
    return gh_json(
        [
            "gh",
            "pr",
            "view",
            str(target.number),
            "--repo",
            target.repo,
            "--json",
            PR_FIELDS,
        ]
    )


def fetch_recent_pr_workflow_runs(
    target: PullTarget, payload: dict[str, Any], *, limit: int = 10
) -> list[dict[str, Any]]:
    head_ref = str(payload.get("headRefName") or "")
    if not head_ref:
        return []

    rows = gh_json(
        [
            "gh",
            "run",
            "list",
            "--repo",
            target.repo,
            "--branch",
            head_ref,
            "--event",
            "pull_request",
            "--limit",
            str(limit),
            "--json",
            (
                "databaseId,displayTitle,event,status,conclusion,createdAt,"
                "updatedAt,headBranch,headSha,url,workflowName"
            ),
        ]
    )
    if not isinstance(rows, list):
        return []

    head_sha = str(payload.get("headRefOid") or "")
    runs = [row for row in rows if isinstance(row, dict)]
    if head_sha:
        runs = [row for row in runs if str(row.get("headSha") or "") == head_sha]
    return runs


def apply_workflow_action_required_signal(
    target: PullTarget,
    status: PullStatus,
    payload: dict[str, Any],
) -> PullStatus:
    if (
        status.state != "waiting"
        or str(payload.get("state") or "").upper() != "OPEN"
        or check_rollup_items(payload)
    ):
        return status

    try:
        runs = fetch_recent_pr_workflow_runs(target, payload)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return status

    action_required = [run for run in runs if is_action_required_run(run)]
    if not action_required:
        return status

    latest = max(action_required, key=lambda item: run_time(item) or "")
    label = run_label(latest)
    return replace(
        status,
        state="workflow_action_required",
        latest_signal_author="github-actions",
        latest_signal_at=run_time(latest),
        latest_signal_excerpt=excerpt(f"{label}: action required before checks run"),
        check_summary="workflow approval required",
        note=(
            "Latest pull_request workflow run requires maintainer approval before "
            "checks can execute; wait unless a reviewer requests changes."
        ),
    )


def fetch_error_note(exc: subprocess.CalledProcessError | json.JSONDecodeError) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        parts = [
            str(exc),
            str(exc.stderr or "").strip(),
            str(exc.stdout or "").strip(),
        ]
        return " ".join(part for part in parts if part).strip()
    return str(exc)


def unavailable_error(note: str) -> bool:
    lowered = note.lower()
    return (
        "could not resolve to a repository" in lowered
        or "not found (http 404)" in lowered
        or '"status":"404"' in lowered
        or "repository not found" in lowered
    )


def check_targets(targets: list[PullTarget], *, agent_login: str) -> list[PullStatus]:
    results: list[PullStatus] = []
    for target in targets:
        try:
            payload = fetch_pr(target)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            note = fetch_error_note(exc)
            if unavailable_error(note):
                results.append(
                    PullStatus(
                        repo=target.repo,
                        number=target.number,
                        state="unavailable",
                        note=(
                            "PR or repository is no longer readable via GitHub; "
                            "treat as watch-only until a fresh canonical URL appears."
                        ),
                    )
                )
                continue
            results.append(
                PullStatus(
                    repo=target.repo,
                    number=target.number,
                    state="error",
                    note=note,
                )
            )
            continue
        status = classify_pr(target, payload, agent_login=agent_login)
        status = apply_workflow_action_required_signal(target, status, payload)
        if status.state == "closed_no_signal":
            status = apply_release_ship_signal(
                target,
                status,
                agent_login=agent_login,
            )
        if status.state == "closed_no_signal":
            status = apply_linked_issue_closure_signal(target, status, payload)
        results.append(status)
    return results


def linked_issue_numbers(target: PullTarget, payload: dict[str, Any]) -> list[int]:
    text = "\n".join(
        str(payload.get(field) or "") for field in ("title", "body")
    )
    numbers: list[int] = []
    seen: set[int] = set()
    for match in re.finditer(r"#\s*(\d+)\b", text):
        number = int(match.group(1))
        if number == target.number or number in seen:
            continue
        seen.add(number)
        numbers.append(number)
    return numbers


def fetch_issue(repo: str, number: int) -> dict[str, Any]:
    return gh_json(
        [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            ISSUE_FIELDS,
        ]
    )


def closing_pr_label(ref: dict[str, Any]) -> str:
    number = ref.get("number")
    repo = ref.get("repository") or {}
    owner = repo.get("owner") or {}
    repo_name = str(repo.get("name") or "")
    owner_login = str(owner.get("login") or "")
    if owner_login and repo_name and number:
        return f"{owner_login}/{repo_name} #{number}"
    if number:
        return f"PR #{number}"
    return str(ref.get("url") or "another PR")


def issue_closed_by_other_pr(
    target: PullTarget, issue: dict[str, Any]
) -> dict[str, Any] | None:
    refs = issue.get("closedByPullRequestsReferences") or []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        number = ref.get("number")
        repo = ref.get("repository") or {}
        owner = repo.get("owner") or {}
        repo_name = str(repo.get("name") or "")
        owner_login = str(owner.get("login") or "")
        same_repo = f"{owner_login}/{repo_name}".lower() == target.repo.lower()
        if same_repo and number == target.number:
            continue
        return ref
    return None


def apply_linked_issue_closure_signal(
    target: PullTarget,
    status: PullStatus,
    payload: dict[str, Any],
) -> PullStatus:
    if not status.last_agent_activity_at:
        return status

    last_agent_dt = parse_github_time(status.last_agent_activity_at)
    fetch_errors: list[str] = []
    for issue_number in linked_issue_numbers(target, payload):
        try:
            issue = fetch_issue(target.repo, issue_number)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            fetch_errors.append(f"#{issue_number}: {fetch_error_note(exc)}")
            continue

        if str(issue.get("state") or "").upper() != "CLOSED":
            continue
        closed_at = str(issue.get("closedAt") or "")
        if not closed_at or safe_github_datetime(closed_at) < last_agent_dt:
            continue
        ref = issue_closed_by_other_pr(target, issue)
        if not ref:
            continue

        issue_reason = str(issue.get("stateReason") or "").lower()
        reason = f" as {issue_reason}" if issue_reason else ""
        label = closing_pr_label(ref)
        return replace(
            status,
            state="superseded",
            latest_signal_author="github-issue",
            latest_signal_at=closed_at,
            latest_signal_excerpt=excerpt(
                f"issue #{issue_number} closed{reason} by {label}"
            ),
            note=(
                f"Linked issue #{issue_number} was closed by {label} after this "
                "PR; treat the PR as superseded unless a maintainer asks for "
                "follow-up."
            ),
        )

    if fetch_errors:
        return replace(
            status,
            note=(
                f"{status.note} Linked-issue closure check failed for "
                f"{'; '.join(fetch_errors)}"
            ),
        )
    return status


def fetch_recent_releases(repo: str, limit: int = 10) -> list[dict[str, Any]]:
    payload = gh_json(["gh", "api", f"repos/{repo}/releases?per_page={limit}"])
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def safe_github_datetime(value: str) -> datetime:
    try:
        return parse_github_time(value)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def release_text(release: dict[str, Any]) -> str:
    return " ".join(
        str(release.get(field) or "")
        for field in ("tag_name", "tagName", "name", "body")
    )


def release_time(release: dict[str, Any]) -> str:
    return str(
        release.get("published_at")
        or release.get("publishedAt")
        or release.get("created_at")
        or release.get("createdAt")
        or ""
    )


def release_tag(release: dict[str, Any]) -> str:
    return str(release.get("tag_name") or release.get("tagName") or "release")


def release_url(release: dict[str, Any]) -> str:
    return str(release.get("html_url") or release.get("url") or "")


def release_mentions_pr_by_agent(
    release: dict[str, Any],
    target: PullTarget,
    *,
    agent_login: str,
) -> bool:
    text = release_text(release)
    pr_re = re.compile(rf"#\s*{target.number}\b", re.IGNORECASE)
    agent_re = re.compile(rf"@{re.escape(agent_login)}\b", re.IGNORECASE)
    for match in pr_re.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 120)
        if agent_re.search(text[start:end]):
            return True
    return False


def release_ship_signal(
    target: PullTarget,
    status: PullStatus,
    releases: list[dict[str, Any]],
    *,
    agent_login: str,
) -> dict[str, Any] | None:
    if not status.last_agent_activity_at:
        return None

    last_agent_dt = parse_github_time(status.last_agent_activity_at)
    candidates = []
    for release in releases:
        published_at = release_time(release)
        if not published_at:
            continue
        if safe_github_datetime(published_at) < last_agent_dt:
            continue
        if release_mentions_pr_by_agent(release, target, agent_login=agent_login):
            candidates.append(release)

    if not candidates:
        return None
    return max(candidates, key=lambda item: safe_github_datetime(release_time(item)))


def apply_release_ship_signal(
    target: PullTarget,
    status: PullStatus,
    *,
    agent_login: str,
) -> PullStatus:
    try:
        releases = fetch_recent_releases(target.repo)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return replace(
            status,
            note=(
                f"{status.note} Release-note ship check failed: "
                f"{fetch_error_note(exc)}"
            ),
        )

    release = release_ship_signal(
        target,
        status,
        releases,
        agent_login=agent_login,
    )
    if not release:
        return status

    tag = release_tag(release)
    published_at = release_time(release)
    url = release_url(release)
    url_suffix = f" {url}" if url else ""
    return replace(
        status,
        state="shipped",
        latest_signal_author="github-release",
        latest_signal_at=published_at,
        latest_signal_excerpt=excerpt(f"{tag}: {release_text(release)}"),
        note=(
            "Closed PR appears shipped via release notes referencing "
            f"#{target.number} by @{agent_login}.{url_suffix}"
        ),
    )


def md_escape(value: str) -> str:
    return value.replace("|", "\\|")


def render_markdown(
    results: list[PullStatus],
    *,
    generated_at: datetime | None = None,
    note: str = "",
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        f"# GitHub PR Watch - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| State | PR | PR state | Last agent activity | Latest signal | Review / merge / checks | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        pr = result.label
        if result.url:
            pr = f"[{pr}]({result.url})"
        signal = "-"
        if result.latest_signal_author:
            signal = (
                f"{result.latest_signal_author} at {result.latest_signal_at}: "
                f"{result.latest_signal_excerpt}"
            )
        review = " / ".join(
            part
            for part in (
                result.review_decision or "-",
                result.merge_state_status or "-",
                f"checks: {result.check_summary or '-'}",
            )
            if part
        )
        lines.append(
            f"| {result.state} | {pr} | {result.pr_state or '-'} | "
            f"{result.last_agent_activity_at or '-'} | {md_escape(signal)} | "
            f"{md_escape(review)} | {md_escape(result.note or '-')} |"
        )
    if note:
        lines.extend(["", "## Note", "", note.strip()])
    return "\n".join(lines) + "\n"


def target_slug(targets: list[PullTarget]) -> str:
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
    ad_hoc_targets: list[PullTarget] | None = None,
) -> Path:
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d")
    hhmm = generated_at.astimezone(UTC).strftime("%H%M")
    if ad_hoc_targets:
        slug = target_slug(ad_hoc_targets)
        return state_dir / f"github-pr-watch-{slug}-{stamp}-{agent}-{hhmm}.md"
    return state_dir / f"github-pr-watch-{stamp}-{agent}-{hhmm}.md"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipeline",
        type=Path,
        default=Path("ops/outbound_pipeline.md"),
        help="Markdown pipeline file containing the active PR watch table.",
    )
    parser.add_argument(
        "--pr",
        action="append",
        default=[],
        help=(
            "Ad-hoc PR target, e.g. owner/repo#123 or "
            "https://github.com/owner/repo/pull/123. Can be repeated. "
            "When supplied, --pipeline is not read."
        ),
    )
    parser.add_argument("--agent-login", default="dutchaiagency")
    parser.add_argument("--write", type=Path, help="Write report to this path.")
    parser.add_argument("--state-dir", type=Path, help="Write timestamped report.")
    parser.add_argument("--agent", default=default_agent_name())
    parser.add_argument("--note", default="", help="Optional Markdown note.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        targets = [parse_target_spec(value) for value in args.pr]
    except ValueError as exc:
        print(f"github-pr-watch: {exc}", file=sys.stderr)
        return 2
    if not targets:
        try:
            markdown = args.pipeline.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"github-pr-watch: {exc}", file=sys.stderr)
            return 2
        targets = parse_watch_targets(markdown)
    if not targets:
        print("github-pr-watch: no active PR watch targets found", file=sys.stderr)
        return 1

    generated_at = datetime.now(UTC)
    results = check_targets(targets, agent_login=args.agent_login)
    if args.json:
        output = json.dumps([asdict(result) for result in results], indent=2)
    else:
        output = render_markdown(results, generated_at=generated_at, note=args.note)

    output_path = args.write
    if output_path is None and args.state_dir is not None:
        output_path = default_output_path(
            args.state_dir,
            args.agent,
            generated_at,
            ad_hoc_targets=targets if args.pr else None,
        )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"wrote {output_path}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
