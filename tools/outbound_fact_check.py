#!/usr/bin/env python3
"""Catch stale survival facts in active outbound drafts before publication."""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


DEFAULT_PATHS = (Path("research/longform-survival-experiment-hn.md"),)


@dataclass(frozen=True)
class Rule:
    code: str
    pattern: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    code: str
    message: str
    excerpt: str


STALE_FACT_RULES = (
    Rule(
        "stale_agent_count_title",
        re.compile(r"\b(?:four|4)\s+AI agents\b", re.IGNORECASE),
        "active publication copy should not present the current roster as four agents",
    ),
    Rule(
        "stale_agent_roster",
        re.compile(r"\bfour autonomous coding agents\b", re.IGNORECASE),
        "current roster is claude + codex duo-mode",
    ),
    Rule(
        "stale_daily_burn",
        re.compile(r"(?:1\.50\s*EUR/day|\u20ac\s*1\.50\s*/?\s*day|1\.50\s*EUR/dag)", re.IGNORECASE),
        "current compute baseline is 1 EUR/day for the pair",
    ),
    Rule(
        "stale_wallet_balance",
        re.compile(r"\b115\.89\d*\s*USDC\b", re.IGNORECASE),
        "current publish-time wallet copy should be rechecked against the live #runway counter",
    ),
    Rule(
        "stale_runway_days",
        re.compile(r"\b(?:~\s*)?77\s+days\b|\b77\s+dagen\b", re.IGNORECASE),
        "current runway is about 113 days before price and fee variance",
    ),
    Rule(
        "stale_cast_count",
        re.compile(r"\bSix lukewarm casts\b", re.IGNORECASE),
        "cast-count copy should be generalized or rechecked before posting",
    ),
    Rule(
        "stale_playbook_runway_offset",
        re.compile(
            r"\boffsets?\s+(?:about\s+)?(?:~\s*)?6\s+days\s+of\s+(?:group\s+)?runway\b",
            re.IGNORECASE,
        ),
        "current 9 USDC playbook copy should use about nine days at 1 EUR/day",
    ),
)


IGNORE_RE = re.compile(r"factcheck:ignore\s+([A-Za-z0-9_,\s]+)", re.IGNORECASE)
HISTORICAL_TRANSITION_RE = re.compile(
    r"\bstarted\s+as\s+(?:four|4)\b.*\bnow\s+(?:(?:we'?re|we are)\s+)?(?:two|2)\b",
    re.IGNORECASE,
)
HISTORICAL_ROSTER_RE = re.compile(
    r"\b(?:at publication|then-current|active ruleset for this phase)\b",
    re.IGNORECASE,
)


def ignored_codes(line: str) -> set[str]:
    match = IGNORE_RE.search(line)
    if not match:
        return set()
    return {
        code.strip().lower()
        for code in re.split(r"[\s,]+", match.group(1))
        if code.strip()
    }


def normalized_line(line: str) -> str:
    return html.unescape(line.replace("&rsquo;", "'")).replace("\u2019", "'")


def is_historical_context(line: str, code: str) -> bool:
    normalized = normalized_line(line)
    if code == "stale_agent_count_title":
        return HISTORICAL_TRANSITION_RE.search(normalized) is not None
    if code in {"stale_agent_roster", "stale_daily_burn"}:
        return HISTORICAL_ROSTER_RE.search(normalized) is not None
    return False


def check_paths(paths: tuple[Path, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            ignores = ignored_codes(line)
            for rule in STALE_FACT_RULES:
                if rule.pattern.search(line):
                    if "all" in ignores or rule.code.lower() in ignores:
                        continue
                    if is_historical_context(line, rule.code):
                        continue
                    findings.append(
                        Finding(
                            path=path,
                            line=line_number,
                            code=rule.code,
                            message=rule.message,
                            excerpt=line.strip(),
                        )
                    )
    return findings


def format_finding(finding: Finding) -> str:
    path = PurePosixPath(finding.path).as_posix()
    return (
        f"{path}:{finding.line}: {finding.code}: "
        f"{finding.message}: {finding.excerpt}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=list(DEFAULT_PATHS),
        help="active outbound draft files to validate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    findings = check_paths(tuple(args.paths))
    if findings:
        for finding in findings:
            print(format_finding(finding), file=sys.stderr)
        return 1
    print("outbound facts ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
