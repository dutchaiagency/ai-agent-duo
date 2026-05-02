#!/usr/bin/env python3
"""Score public GitHub issues for direct outbound and bounty follow-up.

The scanner is intentionally read-only. It never comments, claims, forks, or
messages anyone. The output is a short decision list for the next agent to
review before doing a manual code read and, only then, targeted outreach.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from tools.github_reply_check import parse_targets
    from tools.intake_link import (
        build_intake_url,
        source_for_github_lead,
        utm_content_for_github_lead,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from github_reply_check import parse_targets
    from intake_link import (
        build_intake_url,
        source_for_github_lead,
        utm_content_for_github_lead,
    )


FIELDS = (
    "repository,title,url,number,labels,commentsCount,createdAt,updatedAt,"
    "body,assignees,state,author,authorAssociation"
)

DEFAULT_QUERIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "paid-bug-typescript",
        (
            "paid",
            "bug",
            "--state",
            "open",
            "--created",
            ">2026-04-01",
            "--language",
            "TypeScript",
            "--comments",
            "<10",
        ),
    ),
    (
        "explicit-pay",
        (
            "willing to pay",
            "--state",
            "open",
            "--created",
            ">2026-01-01",
        ),
    ),
    (
        "fresh-help-wanted",
        (
            "help wanted",
            "bug",
            "--state",
            "open",
            "--created",
            ">2026-04-29",
            "--comments",
            "<5",
        ),
    ),
    (
        "fresh-bounty-typescript",
        (
            "bounty",
            "--state",
            "open",
            "--created",
            ">2026-04-01",
            "--language",
            "TypeScript",
            "--comments",
            "<10",
        ),
    ),
)

PAY_TERMS = (
    "pay even",
    "willing to pay",
    "budget",
    "bounty",
    "reward",
)
BUSINESS_TERMS = (
    "checkout",
    "billing",
    "subscription",
    "invoice",
    "payment",
    "order",
    "inventory",
    "revenue",
    "customer",
)
SCOPE_TERMS = (
    "acceptance criteria",
    "expected behavior",
    "steps to reproduce",
    "done criteria",
    "requirements",
    "scope",
)
CODE_TERMS = (
    "relevant files",
    "files affected",
    "file:",
    ".ts",
    ".tsx",
    ".py",
    ".js",
    ".jsx",
    "backend/",
    "src/",
)
GOOD_LABEL_TERMS = (
    "bug",
    "help wanted",
    "bounty",
    "critical",
    "priority: high",
    "priority: critical",
    "good first issue",
)
HARD_BLOCKER_TERMS = (
    "unsolicited \"i can implement this\" replies will be treated as spam",
    "unsolicited replies will be treated as spam",
    "reserved for",
    "requires 4+ merged",
    "assigned to",
    "application was accepted",
    "your application was accepted",
    "due on april",
)
LOW_VALUE_TERMS = (
    "$fndry",
    "fndry",
    "meeet",
    "$meeet",
    "points",
    "point reward",
    "points reward",
    "wave program",
    "eligible for a share",
    "reward pool",
    "token payout",
    "paid in token",
    "paid in tokens",
    "reward token",
)
CASH_FLOOR_RE = re.compile(
    r"(?:\$[0-9]|\b[0-9][0-9,._ ]*\s*(?:usd|usdc|eur|euro)\b|\b(?:usd|usdc|eur|euro)\s*[0-9])",
    re.IGNORECASE,
)
MARKET_VALIDATION_TERMS = (
    "willingness-to-pay",
    "validate willingness-to-pay",
    "structured pricing interviews",
    "target participant / customer",
    "recruiting path",
    "community channel conversion",
    "buyer identity",
    "type/experiment",
)
PROGRAM_SETUP_TERMS = (
    "public bug-bounty program",
    "bug bounty program",
    "bug-bounty program",
    "immunefi",
    "responsible disclosure",
    "disclosure policy",
)
SOFTWARE_CIRCUMVENTION_TERMS = (
    "crack",
    "cracked",
    "keygen",
    "license bypass",
    "bypass license",
    "activation bypass",
    "unlock tool",
    "unlocking tool",
    "trying to unlock",
    "offline setup",
    "relink the download file",
    "downloadtool",
)
OFF_PLATFORM_ONLY_TERMS = (
    "add me on discord",
    "dm me on discord",
    "message me on discord",
    "contact me on discord",
)
UI_PERFORMANCE_TERMS = (
    "scroll",
    "laggy",
    "lagging",
    "stutter",
    "stuttery",
    "jank",
    "smooth",
)
UNCERTAIN_REPRO_TERMS = (
    "rare",
    "intermittent",
    "occasionally",
    "not consistently reproducible",
    "slightly",
    "little bit",
)
EXISTING_REVIEW_COMMENT_TERMS = (
    "codex review:",
    "clawsweeper review",
    "clawsweeper-review",
    "<!-- clawsweeper-review",
    "review details</summary>",
    "public-code-only look",
    "public-code pass",
)
EXTERNAL_FIX_INTENT_COMMENT_TERMS = (
    "i'd like to fix",
    "i would like to fix",
    "i'd like to work on",
    "i would like to work on",
    "i'll submit a pr",
    "i will submit a pr",
    "submit a pr with the fix",
    "i can fix this",
    "i'm working on this",
    "i am working on this",
    "working on this",
    "interested in working on",
    "i'm interested in working",
    "i am interested in working",
    "interested in this bounty",
    "/attempt",
    "/claim",
    "pr opened",
    "pr url",
    "opened a pr",
    "opened pull request",
    "pull request opened",
    "/pull/",
    "implementation evidence",
    "please wait",
)
AMBIGUOUS_BOUNTY_TERMS = (
    "bounty-hunt",
    "bounty hunt",
    "bounty hunter",
)
BOUNTY_PAYOUT_CONTEXT_TERMS = (
    "$",
    " usd",
    " usdc",
    "payout",
    "paid",
    "reward",
    "compensation",
    "algora",
    "opire",
)
PAY_TERMS_EXCEPT_BOUNTY = tuple(term for term in PAY_TERMS if term != "bounty")
REFERENCED_ISSUE_RE = re.compile(r"#(?P<number>\d+)\b")
MAX_RELATED_ISSUES_TO_ENRICH = 3


@dataclass(frozen=True)
class Lead:
    query: str
    repo: str
    number: int
    title: str
    url: str
    body: str
    labels: tuple[str, ...]
    comments_count: int
    created_at: str
    updated_at: str
    assignees: tuple[str, ...]
    state: str
    author_login: str = ""
    author_is_bot: bool = False
    author_association: str = ""
    comments: tuple[str, ...] = ()

    @classmethod
    def from_gh(cls, query: str, raw: dict[str, Any]) -> "Lead":
        repo = raw.get("repository") or {}
        labels = tuple(label.get("name", "") for label in raw.get("labels", []))
        assignees = tuple(user.get("login", "") for user in raw.get("assignees", []))
        author = raw.get("author") or {}
        author_login = str(author.get("login") or "")
        author_type = str(author.get("type") or "")
        author_is_bot = (
            bool(author.get("is_bot") or author.get("isBot") or False)
            or author_type.lower() == "bot"
            or author_login.lower().endswith("[bot]")
        )
        return cls(
            query=query,
            repo=repo.get("nameWithOwner", ""),
            number=int(raw.get("number") or 0),
            title=raw.get("title") or "",
            url=raw.get("url") or "",
            body=raw.get("body") or "",
            labels=labels,
            comments_count=int(raw.get("commentsCount") or 0),
            created_at=raw.get("createdAt") or "",
            updated_at=raw.get("updatedAt") or "",
            assignees=assignees,
            state=raw.get("state") or "",
            author_login=author_login,
            author_is_bot=author_is_bot,
            author_association=str(raw.get("authorAssociation") or ""),
        )


@dataclass(frozen=True)
class ScoredLead:
    lead: Lead
    score: int
    decision: str
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in terms)


def has_payment_signal(text: str, label_text: str) -> bool:
    if has_any(label_text, ("bounty",)):
        return True
    if has_any(text, PAY_TERMS_EXCEPT_BOUNTY):
        return True
    return (
        "bounty" in text.lower()
        and not has_any(text, AMBIGUOUS_BOUNTY_TERMS)
        and has_any(text, BOUNTY_PAYOUT_CONTEXT_TERMS)
    )


def has_cash_floor(text: str) -> bool:
    return bool(CASH_FLOOR_RE.search(text))


def is_external_reporter_without_payment(lead: Lead, has_explicit_pay: bool) -> bool:
    if has_explicit_pay or not lead.author_association:
        return False
    return lead.author_association.upper() in {
        "NONE",
        "FIRST_TIMER",
        "FIRST_TIME_CONTRIBUTOR",
        "MANNEQUIN",
    }


def days_since(value: str, now: datetime) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (now - parsed.astimezone(UTC)).days)


def decision_for(score: int, blockers: tuple[str, ...], has_explicit_pay: bool) -> str:
    if any("anti-solicitation" in blocker for blocker in blockers):
        return "skip"
    if any("assigned" in blocker for blocker in blockers):
        return "skip"
    if any("token/points payout risk" in blocker for blocker in blockers):
        return "skip"
    if any("market validation not coding task" in blocker for blocker in blockers):
        return "skip"
    if any("program setup not small coding task" in blocker for blocker in blockers):
        return "skip"
    if any("off-platform request without public scope" in blocker for blocker in blockers):
        return "skip"
    if any("already has detailed external review" in blocker for blocker in blockers):
        return "skip"
    if any("already has external fix intent" in blocker for blocker in blockers):
        return "skip"
    if any("bot-authored issue" in blocker for blocker in blockers):
        return "skip"
    if score >= 70 and has_explicit_pay:
        return "contact_or_patch"
    if score >= 50:
        return "deep_read"
    if score >= 35:
        return "watch"
    return "skip"


def score_lead(lead: Lead, *, now: datetime | None = None) -> ScoredLead:
    now = now or datetime.now(UTC)
    text = f"{lead.title}\n{lead.body}"
    comment_text = "\n".join(lead.comments)
    label_text = " ".join(lead.labels)
    score = 0
    reasons: list[str] = []
    blockers: list[str] = []

    has_explicit_pay = has_payment_signal(text, label_text)
    if has_explicit_pay:
        score += 25
        reasons.append("explicit payment/bounty signal")
    if has_any(text, BUSINESS_TERMS):
        score += 10
        reasons.append("commercial surface")
    if has_any(text, SCOPE_TERMS):
        score += 20
        reasons.append("clear scope or acceptance criteria")
    if has_any(text, CODE_TERMS):
        score += 15
        reasons.append("specific code surface")
    if has_any(label_text, GOOD_LABEL_TERMS):
        score += 15
        reasons.append("useful labels")

    if lead.comments_count <= 2:
        score += 10
        reasons.append("low comment competition")
    elif lead.comments_count <= 5:
        score += 5
        reasons.append("moderate comment competition")
    elif lead.comments_count > 8:
        score -= 20
        blockers.append("crowded thread")

    created_days = days_since(lead.created_at, now)
    updated_days = days_since(lead.updated_at, now)
    if created_days is not None and created_days <= 3:
        score += 10
        reasons.append("fresh issue")
    elif updated_days is not None and updated_days <= 3:
        score += 5
        reasons.append("recent activity")
    elif (
        not has_explicit_pay
        and updated_days is not None
        and updated_days > 7
    ):
        score -= 20
        blockers.append("stale without payment signal")

    if lead.assignees:
        score -= 30
        blockers.append("already assigned")
    if lead.author_is_bot:
        score -= 45
        blockers.append("bot-authored issue")
    if is_external_reporter_without_payment(lead, has_explicit_pay):
        score -= 20
        blockers.append("non-maintainer reporter without payment signal")

    lowered = text.lower()
    if any(term in lowered for term in HARD_BLOCKER_TERMS[:2]):
        score -= 80
        blockers.append("explicit anti-solicitation")
    if any(term in lowered for term in HARD_BLOCKER_TERMS[2:]):
        score -= 40
        blockers.append("assigned/gated bounty")
    if has_any(text, AMBIGUOUS_BOUNTY_TERMS) and not has_explicit_pay:
        score -= 20
        blockers.append("ambiguous bounty wording")
    if has_any(text, LOW_VALUE_TERMS):
        score -= 20
        blockers.append("token/points payout risk")
        if not has_cash_floor(text):
            score -= 25
            blockers.append("token/points reward without cash floor")
    if has_any(f"{text}\n{label_text}", MARKET_VALIDATION_TERMS):
        score -= 45
        blockers.append("market validation not coding task")
    if has_any(f"{text}\n{label_text}", PROGRAM_SETUP_TERMS):
        score -= 45
        blockers.append("program setup not small coding task")
    if has_any(f"{text}\n{label_text}", SOFTWARE_CIRCUMVENTION_TERMS):
        score -= 80
        blockers.append("software unlock/circumvention risk")
    if has_any(text, OFF_PLATFORM_ONLY_TERMS):
        score -= 50
        blockers.append("off-platform request without public scope")
    if (
        not has_explicit_pay
        and not has_any(text, BUSINESS_TERMS)
        and not has_any(text, CODE_TERMS)
        and has_any(text, UI_PERFORMANCE_TERMS)
        and has_any(text, UNCERTAIN_REPRO_TERMS)
    ):
        score -= 25
        blockers.append("vague intermittent ui performance report")
    if has_any(comment_text, EXISTING_REVIEW_COMMENT_TERMS):
        score -= 45
        blockers.append("already has detailed external review")
    if has_any(comment_text, EXTERNAL_FIX_INTENT_COMMENT_TERMS):
        score -= 45
        blockers.append("already has external fix intent")

    final_score = max(0, min(100, score))
    blocker_tuple = tuple(dict.fromkeys(blockers))
    return ScoredLead(
        lead=lead,
        score=final_score,
        decision=decision_for(final_score, blocker_tuple, has_explicit_pay),
        reasons=tuple(dict.fromkeys(reasons)),
        blockers=blocker_tuple,
    )


def run_query(name: str, args: tuple[str, ...], limit: int) -> list[Lead]:
    cmd = [
        "gh",
        "search",
        "issues",
        *args,
        "--limit",
        str(limit),
        "--json",
        FIELDS,
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    rows = json.loads(proc.stdout or "[]")
    return [Lead.from_gh(name, row) for row in rows]


def collect_leads(limit_per_query: int) -> list[Lead]:
    by_url: dict[str, Lead] = {}
    for name, args in DEFAULT_QUERIES:
        for lead in run_query(name, args, limit_per_query):
            by_url.setdefault(lead.url, lead)
    return list(by_url.values())


def fetch_issue_comment_bodies_for(repo: str, number: int) -> tuple[str, ...]:
    cmd = [
        "gh",
        "issue",
        "view",
        str(number),
        "--repo",
        repo,
        "--json",
        "comments",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload = json.loads(proc.stdout or "{}")
    except subprocess.CalledProcessError:
        rest_cmd = ["gh", "api", f"repos/{repo}/issues/{number}/comments"]
        proc = subprocess.run(rest_cmd, check=True, capture_output=True, text=True)
        rows = json.loads(proc.stdout or "[]")
        return tuple(str(comment.get("body") or "") for comment in rows)
    return tuple(
        str(comment.get("body") or "")
        for comment in payload.get("comments", [])
    )


def fetch_issue_comment_bodies(lead: Lead) -> tuple[str, ...]:
    return fetch_issue_comment_bodies_for(lead.repo, lead.number)


def referenced_issue_numbers(lead: Lead) -> tuple[int, ...]:
    numbers: list[int] = []
    for match in REFERENCED_ISSUE_RE.finditer(f"{lead.title}\n{lead.body}"):
        number = int(match.group("number"))
        if number == lead.number or number in numbers:
            continue
        numbers.append(number)
        if len(numbers) >= MAX_RELATED_ISSUES_TO_ENRICH:
            break
    return tuple(numbers)


def fetch_related_issue_comment_bodies(lead: Lead) -> tuple[str, ...]:
    comments: list[str] = []
    for number in referenced_issue_numbers(lead):
        try:
            comments.extend(fetch_issue_comment_bodies_for(lead.repo, number))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
    return tuple(comments)


def enrich_scored_with_comments(
    scored: list[ScoredLead], *, now: datetime | None = None
) -> list[ScoredLead]:
    enriched: list[ScoredLead] = []
    for item in scored:
        lead = item.lead
        comments = list(lead.comments)
        if lead.comments_count > 0 and not lead.comments:
            try:
                comments.extend(fetch_issue_comment_bodies(lead))
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
        related_comments = fetch_related_issue_comment_bodies(lead)
        comments.extend(related_comments)
        if not comments or tuple(comments) == lead.comments:
            enriched.append(item)
            continue
        enriched.append(score_lead(replace(lead, comments=tuple(comments)), now=now))
    return enriched


def lead_key(repo: str, number: int) -> tuple[str, int]:
    return (repo.lower(), number)


def active_target_keys(pipeline: Path) -> set[tuple[str, int]]:
    try:
        markdown = pipeline.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {lead_key(target.repo, target.number) for target in parse_targets(markdown)}


def filter_scored(
    scored: list[ScoredLead],
    *,
    min_score: int,
    active_keys: set[tuple[str, int]] | None = None,
    include_active: bool = False,
    include_skip: bool = False,
) -> list[ScoredLead]:
    active_keys = active_keys or set()
    filtered: list[ScoredLead] = []
    for item in scored:
        lead = item.lead
        if (
            not include_active
            and lead_key(lead.repo, lead.number) in active_keys
        ):
            continue
        if item.decision == "skip" and not include_skip:
            continue
        if item.score >= min_score or item.decision != "skip":
            filtered.append(item)
    return filtered


def render_markdown(scored: list[ScoredLead], *, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        f"# GitHub Lead Scan - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Read-only scan. Do not post from this file alone; deep-read the repo first.",
        "",
    ]
    if not scored:
        lines.extend(
            [
                "No candidates passed the current filters.",
                "",
            ]
        )
    lines.extend(
        [
            "| Score | Decision | Lead | Source | Intake | Reasons | Blockers |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in scored:
        lead = item.lead
        reasons = ", ".join(item.reasons) if item.reasons else "-"
        blockers = ", ".join(item.blockers) if item.blockers else "-"
        title = ascii_safe(lead.title).replace("|", "\\|")
        source = source_for_github_lead(
            lead.repo,
            lead.number,
            day=generated_at.date(),
        )
        intake_url = build_intake_url(
            source,
            utm_medium="github",
            utm_campaign=f"outbound-{generated_at.date().isoformat()}",
            utm_content=utm_content_for_github_lead(lead.repo, lead.number),
        )
        lines.append(
            f"| {item.score} | {item.decision} | "
            f"[{lead.repo} #{lead.number}: {title}]({lead.url}) | "
            f"`{source}` | [brief]({intake_url}) | "
            f"{reasons} | {blockers} |"
        )
    return "\n".join(lines) + "\n"


def ascii_safe(value: str) -> str:
    return value.encode("ascii", "backslashreplace").decode("ascii")


def default_output_path(state_dir: Path, agent: str, generated_at: datetime) -> Path:
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d")
    hhmm = generated_at.astimezone(UTC).strftime("%H%M")
    return state_dir / f"github-leads-{stamp}-{agent}-{hhmm}.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score GitHub issues for outbound leads.")
    parser.add_argument("--limit-per-query", type=int, default=20)
    parser.add_argument("--min-score", type=int, default=35)
    parser.add_argument(
        "--pipeline",
        type=Path,
        default=Path("ops/outbound_pipeline.md"),
        help="Pipeline file whose active target queue is excluded by default.",
    )
    parser.add_argument(
        "--include-active",
        action="store_true",
        help="Include leads already present in the active target queue.",
    )
    parser.add_argument(
        "--include-skip",
        action="store_true",
        help="Include leads classified as skip.",
    )
    parser.add_argument(
        "--no-comment-enrichment",
        action="store_true",
        help="Do not fetch candidate issue comments to suppress duplicate-review leads.",
    )
    parser.add_argument("--write", type=Path, help="Write markdown report to this path.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Write to state/github-leads-YYYY-MM-DD-agent-HHMM.md.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--json", action="store_true", help="Print scored leads as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(UTC)
    try:
        leads = collect_leads(args.limit_per_query)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"github-lead-scan: {exc}", file=sys.stderr)
        return 2

    scored = [score_lead(lead) for lead in leads]
    scored.sort(key=lambda item: (-item.score, item.lead.updated_at, item.lead.url))
    filtered = filter_scored(
        scored,
        min_score=args.min_score,
        active_keys=active_target_keys(args.pipeline),
        include_active=args.include_active,
        include_skip=args.include_skip,
    )
    if not args.no_comment_enrichment:
        filtered = enrich_scored_with_comments(filtered)
        filtered.sort(key=lambda item: (-item.score, item.lead.updated_at, item.lead.url))
        filtered = filter_scored(
            filtered,
            min_score=args.min_score,
            active_keys=active_target_keys(args.pipeline),
            include_active=args.include_active,
            include_skip=args.include_skip,
        )

    if args.json:
        payload = [
            {
                "score": item.score,
                "decision": item.decision,
                "repo": item.lead.repo,
                "number": item.lead.number,
                "title": item.lead.title,
                "url": item.lead.url,
                "reasons": list(item.reasons),
                "blockers": list(item.blockers),
                "query": item.lead.query,
            }
            for item in filtered
        ]
        output = json.dumps(payload, indent=2)
    else:
        output = render_markdown(filtered, generated_at=generated_at)

    output_path = args.write
    if output_path is None and args.state_dir is not None:
        output_path = default_output_path(args.state_dir, args.agent, generated_at)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
