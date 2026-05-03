#!/usr/bin/env python3
"""Pre-send 4-condition gate for GitHub outbound replies.

This is the GitHub analogue of ``tools/farcaster_reply_gate.py``. It turns the
GitHub Pain-Reply Gate in ``ops/outbound_pipeline.md`` into an opt-in CLI check
before any public GitHub comment, PR comment, or GitHub-sourced email/DM.

A reply only passes when ALL four conditions hit:
  (a) recipient has a real build/fix surface
  (b) the thread names a concrete problem, not opinion/launch/fan-thanks framing
  (c) the issue/comment is recent enough to enter the active conversation
  (d) our reply names their problem in their words and bridges with a concrete
      public-code observation that cites a file path/code artifact

Usage:
    python tools/github_reply_gate.py \
        --target-url https://github.com/owner/repo/issues/123 \
        --target-thread-iso 2026-05-03T08:30:00Z \
        --target-actor-builds "maintainer of a billing workflow" \
        --target-problem "checkout webhook retries fail to mark invoices paid" \
        --reply-from-file state/drafts/github-reply.txt \
        --code-observation "src/billing/webhooks.ts:88 drops retry events" \
        --next-step "patch idempotent retry handling and add a webhook test"

Exit code 0 = pass. Non-zero = fail (reason printed to stderr).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


MAX_AGE_DAYS = 7
MIN_OVERLAP_WORDS = 2
MIN_OVERLAP_LEN = 4

PROBLEM_VOCABULARY = (
    "acceptance criteria",
    "actual behavior",
    "block",
    "blocked",
    "blocker",
    "broken",
    "bug",
    "can't",
    "cant",
    "cannot",
    "crash",
    "crashes",
    "deadlock",
    "doesn't work",
    "doesnt work",
    "don't work",
    "dont work",
    "error",
    "exception",
    "expected behavior",
    "fail",
    "failed",
    "failing",
    "fails",
    "flaky",
    "hard to",
    "how can",
    "how do i",
    "how do we",
    "how do you",
    "how do they",
    "how to",
    "incorrect",
    "invalid",
    "issue",
    "leak",
    "missing",
    "need",
    "needs",
    "not working",
    "problem",
    "race",
    "regression",
    "repro",
    "slow",
    "stale",
    "stuck",
    "timeout",
    "unable",
    "anyone know",
    "anyone tried",
    "anyone solve",
    "any way to",
    "is there a way",
    "is there any way",
    "wrong",
)

OPINION_VOCABULARY = (
    "amazing",
    "beautiful",
    "congrats",
    "congratulations",
    "cool repo",
    "excited",
    "great work",
    "interesting",
    "love this",
    "nice project",
    "ship it",
    "thanks",
    "well done",
)

ACTION_VOCABULARY = (
    "add",
    "checklist",
    "change",
    "diagnose",
    "fix",
    "guard",
    "patch",
    "regression",
    "remove",
    "reproduce",
    "review",
    "test",
    "triage",
    "update",
    "verify",
)

STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "shall",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "about",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "they",
        "them",
        "their",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        "where",
        "when",
        "why",
        "how",
        "if",
        "then",
        "else",
        "than",
        "so",
        "such",
        "not",
        "no",
        "yes",
        "very",
        "just",
        "only",
        "even",
        "also",
        "all",
        "any",
        "some",
        "many",
        "much",
        "more",
        "most",
        "few",
        "less",
    }
)

GITHUB_URL_RE = re.compile(
    r"^https://github\.com/"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:issues|pull)/\d+"
    r"(?:#(?:issuecomment-\d+|discussion_r\d+))?/?$",
    re.IGNORECASE,
)

CODE_ARTIFACT_RE = re.compile(
    r"(?:^|[\s`'\"(])"
    r"(?P<path>"
    r"(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+"
    r"\.(?:bat|c|cc|clj|compact|cpp|cs|css|dart|ex|exs|fs|fsx|go|h|hpp|html|"
    r"java|js|json|jsx|kt|md|php|ps1|py|rb|rs|scala|scss|sh|sql|svelte|swift|"
    r"toml|ts|tsx|vue|yaml|yml)"
    r"(?:[:#L-]*\d+)?"
    r"|"
    r"[A-Za-z0-9_.-]+"
    r"\.(?:bat|c|cc|clj|compact|cpp|cs|css|dart|ex|exs|fs|fsx|go|h|hpp|html|"
    r"java|js|json|jsx|kt|md|php|ps1|py|rb|rs|scala|scss|sh|sql|svelte|swift|"
    r"toml|ts|tsx|vue|yaml|yml)"
    r"(?:[:#L-]*\d+)?"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    failures: tuple[str, ...]


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def tokenize_content_words(text: str) -> frozenset[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'\-]*", text.lower())
    return frozenset(
        word
        for word in words
        if len(word) >= MIN_OVERLAP_LEN and word not in STOP_WORDS
    )


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def contains_problem_vocab(text: str) -> bool:
    return has_any(text, PROBLEM_VOCABULARY)


def contains_only_opinion(text: str) -> bool:
    return has_any(text, OPINION_VOCABULARY) and not contains_problem_vocab(text)


def extract_code_artifacts(text: str) -> frozenset[str]:
    artifacts: set[str] = set()
    for match in CODE_ARTIFACT_RE.finditer(text):
        path = match.group("path").replace("\\", "/").strip("`'\"()")
        artifacts.add(path.lower())
    return frozenset(artifacts)


def contains_code_artifact(text: str) -> bool:
    return bool(extract_code_artifacts(text))


def artifact_mentioned_in_reply(code_observation: str, reply_text: str) -> bool:
    artifacts = extract_code_artifacts(code_observation)
    if not artifacts:
        return False
    lowered_reply = reply_text.lower().replace("\\", "/")
    for artifact in artifacts:
        basename = artifact.rsplit("/", 1)[-1].split(":", 1)[0].split("#", 1)[0]
        if artifact in lowered_reply or basename in lowered_reply:
            return True
    return False


def validate_url(url: str) -> str | None:
    if not url:
        return "target-url is empty"
    if not GITHUB_URL_RE.match(url.strip()):
        return f"target-url is not a GitHub issue/PR permalink: {url!r}"
    return None


def evaluate_gate(
    *,
    target_url: str,
    target_thread_iso: str,
    target_actor_builds: str,
    target_problem: str,
    reply_text: str,
    code_observation: str,
    next_step: str,
    now: datetime | None = None,
    max_age_days: float = MAX_AGE_DAYS,
) -> GateResult:
    failures: list[str] = []
    now = now or datetime.now(timezone.utc)

    url_err = validate_url(target_url)
    if url_err:
        failures.append(f"url: {url_err}")

    builds = (target_actor_builds or "").strip()
    if not builds:
        failures.append("(a) target-actor-builds is empty: name their build/fix surface")
    elif len(tokenize_content_words(builds)) < 1:
        failures.append("(a) target-actor-builds has no content words")

    if not target_thread_iso:
        failures.append("(c) target-thread-iso is empty")
    else:
        try:
            thread_at = parse_iso(target_thread_iso)
        except ValueError as exc:
            failures.append(f"(c) target-thread-iso unparseable: {exc}")
        else:
            age = now - thread_at
            if age < timedelta(0):
                failures.append(
                    f"(c) target-thread-iso is in the future ({thread_at.isoformat()})"
                )
            elif age > timedelta(days=max_age_days):
                days = age.total_seconds() / 86400
                failures.append(
                    f"(c) thread is {days:.1f}d old; gate requires <= {max_age_days:g}d"
                )

    problem = (target_problem or "").strip()
    if not problem:
        failures.append("(b) target-problem is empty: name the concrete problem")
    else:
        if contains_only_opinion(problem):
            failures.append(
                "(b) target-problem reads as opinion/celebration/launch chatter. "
                "Skip unless the thread names a fixable pain."
            )
        elif not contains_problem_vocab(problem):
            failures.append(
                "(b) target-problem lacks problem-vocabulary "
                "(bug/fails/error/missing/blocked/acceptance criteria/...). "
                "Restate the maintainer's pain or skip."
            )

    reply = (reply_text or "").strip()
    if not reply:
        failures.append("(d) reply-text is empty")
    elif problem:
        problem_words = tokenize_content_words(problem)
        reply_words = tokenize_content_words(reply)
        overlap = problem_words & reply_words
        if len(overlap) < MIN_OVERLAP_WORDS:
            failures.append(
                f"(d) reply names <{MIN_OVERLAP_WORDS} words from their problem "
                f"(overlap={sorted(overlap)}). Restate their pain in their words."
            )

    observation = (code_observation or "").strip()
    if not observation:
        failures.append(
            "(d) code-observation is empty: cite one public-code observation "
            "(file path, line, or code artifact) that narrows their problem"
        )
    elif not contains_code_artifact(observation):
        failures.append(
            "(d) code-observation has no file/code artifact. "
            "GitHub bridge must be code-path X in file Y, not a generic opinion."
        )
    elif reply and not artifact_mentioned_in_reply(observation, reply):
        failures.append(
            "(d) reply does not cite the code artifact from code-observation. "
            "Mention the file/path in the outbound text."
        )

    action = (next_step or "").strip()
    if not action:
        failures.append(
            "(d) next-step is empty: name the review, patch, or verification that "
            "would solve their pain"
        )
    elif contains_only_opinion(action) or not has_any(action, ACTION_VOCABULARY):
        failures.append(
            "(d) next-step lacks a concrete action "
            "(fix/patch/test/review/verify/checklist/...)."
        )

    return GateResult(passed=not failures, failures=tuple(failures))


def read_text(value: str | None, from_file: str | None, label: str) -> str:
    if value is not None and from_file is not None:
        raise SystemExit(f"{label}: pass either inline value or --from-file, not both")
    if from_file:
        return Path(from_file).read_text(encoding="utf-8").strip()
    return (value or "").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="4-condition pre-send gate for GitHub outbound replies",
    )
    parser.add_argument("--target-url", required=True)
    parser.add_argument(
        "--target-thread-iso",
        required=True,
        help="ISO timestamp of the issue/comment/update being answered (UTC)",
    )
    parser.add_argument(
        "--target-actor-builds",
        required=True,
        help="One-line role/build/fix surface for the recipient",
    )
    parser.add_argument(
        "--target-problem",
        required=True,
        help="One sentence: the concrete problem in the thread, in their words",
    )
    parser.add_argument("--reply-text", help="Inline outbound reply text")
    parser.add_argument(
        "--reply-from-file",
        help="Path to UTF-8 file with the outbound reply text",
    )
    parser.add_argument(
        "--code-observation",
        required=True,
        help="One public-code observation with file/path/line evidence",
    )
    parser.add_argument(
        "--next-step",
        required=True,
        help="The concrete review/patch/test/verification step offered",
    )
    parser.add_argument("--now-iso", help="Override 'now' for deterministic testing")
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=MAX_AGE_DAYS,
        help="Maximum allowed thread age in days (default: 7)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    reply_text = read_text(args.reply_text, args.reply_from_file, "reply")
    now = parse_iso(args.now_iso) if args.now_iso else None

    result = evaluate_gate(
        target_url=args.target_url,
        target_thread_iso=args.target_thread_iso,
        target_actor_builds=args.target_actor_builds,
        target_problem=args.target_problem,
        reply_text=reply_text,
        code_observation=args.code_observation,
        next_step=args.next_step,
        now=now,
        max_age_days=args.max_age_days,
    )

    if result.passed:
        print("PASS: GitHub 4-condition gate cleared.")
        return 0

    print("FAIL: GitHub reply-gate blocked. Fix or skip:", file=sys.stderr)
    for failure in result.failures:
        print(f"  - {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
