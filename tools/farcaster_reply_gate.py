#!/usr/bin/env python3
"""Pre-send 4-condition gate for Farcaster outbound replies.

Operationalises the reply-gate from MEMORY.md (durable rule 2026-05-03,
derived from the 1/6 inbound-conversion audit on 2026-05-02..03).

A reply only passes when ALL four conditions hit:
  (a) recipient is the founder/builder of something concrete
  (b) their cast names a CONCRETE PROBLEM (not opinion/observation/celebration)
  (c) cast is <6h old
  (d) our reply names their problem in their words AND bridges with one
      concrete lived-data point from our experience

The tool refuses to pass if any field is missing. It runs mechanical checks
where possible (age, word-overlap, problem-vocabulary, data-point evidence)
so the gate cannot be skipped silently across wakes.

Usage:
    python tools/farcaster_reply_gate.py \\
        --target-url https://farcaster.xyz/<user>/<hash> \\
        --target-cast-iso 2026-05-03T00:30:00Z \\
        --target-author-builds "Wetware: capability-based p2p runtime" \\
        --cast-text "ipfs gateway is too slow for sub-100ms reads" \\
        --reply-from-file state/drafts/reply.txt \\
        --bridge-data-point "we hit 320ms p95 on the same gateway in commit a45cd99"

Exit code 0 = pass. Non-zero = fail (reason printed to stderr).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_AGE_HOURS = 6
MIN_OVERLAP_WORDS = 2
MIN_BRIDGE_CAST_OVERLAP_WORDS = 1
MIN_OVERLAP_LEN = 4

# Words that signal a concrete problem in the target's cast.
# Presence of at least one = condition (b) likely satisfied.
PROBLEM_VOCABULARY = (
    "broken", "break", "stuck", "blocker", "blocked", "block",
    "need", "needs", "needed", "looking for", "want", "wanted",
    "can't", "cant", "cannot", "couldn't", "couldnt",
    "doesn't", "doesnt", "don't work", "dont work",
    "fails", "failing", "failed", "fail",
    "hard to", "difficult", "tough",
    "problem", "issue", "bug", "missing",
    "slow", "expensive", "costs",
    "how do i", "how do we", "how do you", "how do they", "how to",
    "how can", "anyone know", "anyone tried", "anyone solve",
    "any way to", "is there a way", "is there any way",
    "why does", "why is",
    "wish", "would love", "dream of",
    "spent", "burned", "lost",
    # Added 2026-05-03 after retro-validation false-negative on the lthibault
    # 'is hard - sandboxing alone isn't enough' pattern.
    "is hard", "isn't enough", "isnt enough", "not enough",
    "still missing", "still need",
    "still needs", "no way to", "no good way", "no primitive",
)

# Words that signal pure opinion/observation/celebration (no actionable problem).
# Cast that ONLY contains these (and no problem-vocabulary) = condition (b) fail.
OPINION_VOCABULARY = (
    "love this", "amazing", "incredible", "beautiful",
    "congrats", "congratulations", "ship it", "shipped",
    "great work", "well done", "nice job", "thanks",
    "excited about", "excited for", "looking forward",
    "agree", "agreed", "this", "based",
)

STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "could", "may", "might", "must", "shall",
    "to", "of", "in", "on", "at", "by", "for", "with", "from", "about",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "i", "me", "my", "we", "our", "you", "your", "they", "them", "their",
    "it", "its", "this", "that", "these", "those",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "if", "then", "else", "than", "so", "such",
    "not", "no", "yes", "very", "just", "only", "even", "also",
    "all", "any", "some", "many", "much", "more", "most", "few", "less",
})

DATA_POINT_PATTERNS = (
    re.compile(r"\d"),                           # any digit
    re.compile(r"https?://"),                    # URL
    re.compile(r"\b[0-9a-f]{7,40}\b"),           # git hash
    re.compile(r"\b\w+\.(py|md|js|ts|html|css|sh|bat|json|yaml|yml|toml)\b"),
)

REPLY_URL_RE = re.compile(
    r"^https://(?:www\.)?(?:farcaster\.xyz|warpcast\.com)/[^/]+/0x[0-9a-f]+/?$",
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
    """Lowercase content-words >= MIN_OVERLAP_LEN, stop-words removed."""
    words = re.findall(r"[a-zA-Z][a-zA-Z'\-]*", text.lower())
    return frozenset(
        w for w in words
        if len(w) >= MIN_OVERLAP_LEN and w not in STOP_WORDS
    )


def contains_problem_vocab(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in PROBLEM_VOCABULARY)


def contains_only_opinion(text: str) -> bool:
    """True if cast contains opinion-vocab AND no problem-vocab."""
    if contains_problem_vocab(text):
        return False
    lowered = text.lower()
    return any(token in lowered for token in OPINION_VOCABULARY)


def contains_data_point(text: str) -> bool:
    return any(pattern.search(text) for pattern in DATA_POINT_PATTERNS)


def validate_url(url: str) -> str | None:
    if not url:
        return "target-url is empty"
    if not REPLY_URL_RE.match(url.strip()):
        return f"target-url is not a Farcaster permalink: {url!r}"
    return None


def problem_evidence_source(
    target_problem: str,
    target_cast_text: str,
) -> tuple[str, str]:
    cast_text = (target_cast_text or "").strip()
    if cast_text:
        return cast_text, "cast-text"
    return (target_problem or "").strip(), "target-problem"


def evaluate_gate(
    *,
    target_url: str,
    target_cast_iso: str,
    target_author_builds: str,
    target_problem: str,
    reply_text: str,
    bridge_data_point: str,
    target_cast_text: str = "",
    now: datetime | None = None,
) -> GateResult:
    failures: list[str] = []
    now = now or datetime.now(timezone.utc)

    url_err = validate_url(target_url)
    if url_err:
        failures.append(f"url: {url_err}")

    # Condition (a): recipient is founder/builder of something concrete.
    builds = (target_author_builds or "").strip()
    if not builds:
        failures.append("(a) target-author-builds is empty: name what they build")
    elif len(tokenize_content_words(builds)) < 1:
        failures.append("(a) target-author-builds has no content words")

    # Condition (c): cast age <= MAX_AGE_HOURS.
    if not target_cast_iso:
        failures.append("(c) target-cast-iso is empty")
    else:
        try:
            cast_at = parse_iso(target_cast_iso)
        except ValueError as exc:
            failures.append(f"(c) target-cast-iso unparseable: {exc}")
        else:
            age = now - cast_at
            if age < timedelta(0):
                failures.append(
                    f"(c) target-cast-iso is in the future ({cast_at.isoformat()})"
                )
            elif age > timedelta(hours=MAX_AGE_HOURS):
                hours = age.total_seconds() / 3600
                failures.append(
                    f"(c) cast is {hours:.1f}h old; gate requires <={MAX_AGE_HOURS}h"
                )

    # Condition (b): problem named, not opinion/observation/celebration.
    # Prefer verbatim cast text over operator-supplied problem summaries, so the
    # gate cannot pass by self-attesting that a cast named a problem.
    problem, problem_source = problem_evidence_source(
        target_problem,
        target_cast_text,
    )
    if not problem:
        failures.append(
            "(b) cast-text/target-problem is empty: provide verbatim cast text "
            "or name the concrete problem in their cast"
        )
    else:
        if contains_only_opinion(problem):
            failures.append(
                f"(b) {problem_source} reads as opinion/celebration "
                "(love this / amazing / congrats / agreed). "
                "If their cast is fan-thanks framing, skip — not a peer conversation."
            )
        elif not contains_problem_vocab(problem):
            failures.append(
                f"(b) {problem_source} lacks problem-vocabulary "
                "(broken/stuck/need/can't/fails/missing/slow/...). "
                "Rephrase in their pain-words or skip."
            )

    # Condition (d): reply names their problem in their words + concrete bridge.
    reply = (reply_text or "").strip()
    if not reply:
        failures.append("(d) reply-text is empty")
    elif problem:
        problem_words = tokenize_content_words(problem)
        reply_words = tokenize_content_words(reply)
        overlap = problem_words & reply_words
        if len(overlap) < MIN_OVERLAP_WORDS:
            failures.append(
                f"(d) reply names <{MIN_OVERLAP_WORDS} words from {problem_source} "
                f"(overlap={sorted(overlap)}). "
                "Restate their pain in their words."
            )

    bridge = (bridge_data_point or "").strip()
    if not bridge:
        failures.append(
            "(d) bridge-data-point is empty: cite one concrete lived-data point "
            "(number, url, commit hash, file path) that attacks their problem"
        )
    elif not contains_data_point(bridge):
        failures.append(
            "(d) bridge-data-point has no concrete artifact "
            "(no digit/url/hash/file). "
            "'we also struggled' is fan-thanks; '320ms p95 on commit a45cd99' is bridge."
        )
    elif (target_cast_text or "").strip():
        cast_words = tokenize_content_words(target_cast_text)
        bridge_words = tokenize_content_words(bridge)
        overlap = cast_words & bridge_words
        if len(overlap) < MIN_BRIDGE_CAST_OVERLAP_WORDS:
            failures.append(
                f"(d) bridge-data-point names <{MIN_BRIDGE_CAST_OVERLAP_WORDS} "
                f"word from cast-text (overlap={sorted(overlap)}). "
                "Tie the lived-data point to the cast's own words."
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
        description="4-condition pre-send gate for Farcaster outbound replies",
    )
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--target-cast-iso", required=True,
                        help="ISO timestamp of the target cast (UTC)")
    parser.add_argument("--target-author-builds", required=True,
                        help="One-line description: what they are founder/builder of")
    parser.add_argument(
        "--target-problem",
        default="",
        help=(
            "Compatibility fallback: one sentence naming the concrete problem. "
            "Prefer --cast-text."
        ),
    )
    parser.add_argument(
        "--cast-text",
        default="",
        help=(
            "Verbatim target cast snippet. When provided, condition (b) and "
            "reply/bridge grounding use this instead of --target-problem."
        ),
    )
    parser.add_argument("--reply-text",
                        help="Inline reply text")
    parser.add_argument("--reply-from-file",
                        help="Path to UTF-8 file with the reply text")
    parser.add_argument("--bridge-data-point", required=True,
                        help="One concrete lived-data point that attacks their problem")
    parser.add_argument("--now-iso",
                        help="Override 'now' for deterministic testing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    reply_text = read_text(args.reply_text, args.reply_from_file, "reply")

    now = parse_iso(args.now_iso) if args.now_iso else None

    if not args.cast_text:
        print(
            "WARN: --cast-text not provided; falling back to --target-problem "
            "for condition (b)/(d) grounding.",
            file=sys.stderr,
        )

    result = evaluate_gate(
        target_url=args.target_url,
        target_cast_iso=args.target_cast_iso,
        target_author_builds=args.target_author_builds,
        target_problem=args.target_problem,
        reply_text=reply_text,
        bridge_data_point=args.bridge_data_point,
        target_cast_text=args.cast_text,
        now=now,
    )

    if result.passed:
        print("PASS: 4-condition gate cleared.")
        return 0

    print("FAIL: reply-gate blocked. Fix or skip:", file=sys.stderr)
    for failure in result.failures:
        print(f"  - {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
