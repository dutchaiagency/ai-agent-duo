#!/usr/bin/env python3
"""Build source-tagged intake links for outbound messages."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ISSUE_INTAKE_URL = "https://github.com/dutchaiagency/ai-agent-duo/issues/new"
SITE_URL = "https://dutchaiagency.github.io/ai-agent-duo/"
ISSUE_TEMPLATE = "task-request.yml"
MAX_SOURCE_LEN = 96


def normalize_source(value: str) -> str:
    """Return a compact ASCII source slug safe for URL query fields."""

    ascii_value = value.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug[:MAX_SOURCE_LEN].rstrip("-")
    if not slug:
        raise ValueError("source must contain at least one ASCII letter or digit")
    return slug


def add_query_params(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def build_intake_url(source: str, *, target: str = "issue") -> str:
    source_slug = normalize_source(source)
    if target == "issue":
        return add_query_params(
            ISSUE_INTAKE_URL,
            {"template": ISSUE_TEMPLATE, "source": source_slug},
        )
    if target == "site":
        return add_query_params(SITE_URL, {"source": source_slug})
    raise ValueError(f"unknown target: {target}")


def source_for_github_lead(
    repo: str,
    number: int,
    *,
    day: date | str | None = None,
) -> str:
    if not repo or number <= 0:
        raise ValueError("repo and positive issue number are required")
    if day is None:
        day_value = datetime.now(UTC).date().isoformat()
    elif isinstance(day, date):
        day_value = day.isoformat()
    else:
        day_value = day
    return normalize_source(f"github-outbound-{repo}-{number}-{day_value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate source-tagged Dutch AI Agents intake links."
    )
    parser.add_argument("source", nargs="?", help="Raw source label or slug.")
    parser.add_argument(
        "--target",
        choices=("issue", "site"),
        default="issue",
        help="Destination to tag. Default: issue intake form.",
    )
    parser.add_argument("--repo", help="GitHub repo, e.g. owner/name.")
    parser.add_argument("--issue", type=int, help="GitHub issue number.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).date().isoformat(),
        help="Source date for --repo/--issue mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repo or args.issue:
        if not args.repo or not args.issue:
            raise SystemExit("--repo and --issue must be used together")
        source = source_for_github_lead(args.repo, args.issue, day=args.date)
    elif args.source:
        source = args.source
    else:
        raise SystemExit("provide a source or --repo/--issue")
    print(build_intake_url(source, target=args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
