#!/usr/bin/env python3
"""Lint a task brief for scope clarity and accidental secret leakage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


REQUIRED_SIGNALS = {
    "goal": (
        "goal",
        "objective",
        "outcome",
        "problem",
        "fix",
        "build",
        "review",
    ),
    "context": (
        "context",
        "link",
        "links",
        "repository",
        "repo",
        "file",
        "files",
        "input",
        "error",
        "steps",
    ),
    "done_criteria": (
        "done criteria",
        "acceptance",
        "verify",
        "verification",
        "expected",
        "tests pass",
        "deliverable",
    ),
}

OPTIONAL_SIGNALS = {
    "deadline": ("deadline", "due", "timeline", "asap", "by "),
    "budget": ("budget", "usdc", "usd", "payment", "price", "rate"),
}

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|private[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
    re.compile(
        r"(?i)\b(?:seed phrase|mnemonic|recovery phrase)\s*[:=]\s*(?:[a-z]+[\s,]+){11,23}[a-z]+\b"
    ),
)

URL_RE = re.compile(r"https?://\S+")
BUDGET_RE = re.compile(
    r"(?ix)"
    r"(?:\b(\d+(?:\.\d+)?)\s*(?:usdc|usd|eur)\b)"
    r"|(?:\b(?:usdc|usd|eur)\s*(\d+(?:\.\d+)?)\b)"
    r"|(?:[$€]\s*(\d+(?:\.\d+)?))"
)


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str


def has_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def detect_budget_amounts(text: str) -> list[float]:
    amounts: list[float] = []
    for match in BUDGET_RE.finditer(text):
        value = match.group(1) or match.group(2) or match.group(3)
        if value:
            amounts.append(float(value))
    return amounts


def escape_github_command_value(value: str, *, property_value: bool = False) -> str:
    escaped = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        escaped = escaped.replace(":", "%3A").replace(",", "%2C")
    return escaped


def github_annotation(finding: Finding, path: str) -> str:
    command = {
        "fail": "error",
        "warn": "warning",
        "info": "notice",
    }[finding.level]
    properties = [f"title={escape_github_command_value(finding.code, property_value=True)}"]
    if path != "-":
        properties.insert(0, f"file={escape_github_command_value(path, property_value=True)}")
    message = escape_github_command_value(finding.message)
    return f"::{command} {','.join(properties)}::{message}"


def lint(text: str, min_budget_usdc: float) -> list[Finding]:
    normalized = text.lower()
    findings: list[Finding] = []

    if len(text.strip()) < 80:
        findings.append(
            Finding("fail", "brief_too_short", "Brief is too short to be actionable.")
        )

    for name, signals in REQUIRED_SIGNALS.items():
        if not has_signal(normalized, signals):
            findings.append(
                Finding("fail", f"missing_{name}", f"Missing clear {name.replace('_', ' ')}.")
            )

    for name, signals in OPTIONAL_SIGNALS.items():
        if not has_signal(normalized, signals):
            findings.append(
                Finding("warn", f"missing_{name}", f"Missing {name}; quote or scheduling may be slower.")
            )

    if not URL_RE.search(text):
        findings.append(
            Finding("warn", "missing_url", "No URL found; include a repo, issue, docs, or sample link when possible.")
        )

    budget_amounts = detect_budget_amounts(text)
    if budget_amounts and max(budget_amounts) < min_budget_usdc:
        findings.append(
            Finding(
                "warn",
                "budget_below_minimum",
                f"Highest detected budget is below {min_budget_usdc:g} USDC.",
            )
        )

    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    "fail",
                    "possible_secret",
                    "Possible secret, private key, password, API key, or seed phrase detected.",
                )
            )
            break

    if not findings:
        findings.append(Finding("info", "ok", "Brief looks actionable."))

    return findings


def read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint a task brief for agent handoff.")
    parser.add_argument("path", help="Brief path, or '-' for stdin.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--github-annotations",
        action="store_true",
        help="Print GitHub Actions annotations.",
    )
    parser.add_argument("--fail-on-warn", action="store_true", help="Return non-zero when warnings exist.")
    parser.add_argument("--min-budget-usdc", type=float, default=25.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        text = read_input(args.path)
    except OSError as exc:
        print(f"brief-lint: {exc}", file=sys.stderr)
        return 2

    findings = lint(text, args.min_budget_usdc)
    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    elif args.github_annotations:
        for finding in findings:
            print(github_annotation(finding, args.path))
    else:
        for finding in findings:
            print(f"{finding.level.upper():5} {finding.code}: {finding.message}")

    has_fail = any(finding.level == "fail" for finding in findings)
    has_warn = any(finding.level == "warn" for finding in findings)
    return 1 if has_fail or (args.fail_on_warn and has_warn) else 0


if __name__ == "__main__":
    raise SystemExit(main())
