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


def build_intake_url(
    source: str,
    *,
    target: str = "issue",
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_content: str | None = None,
) -> str:
    source_slug = normalize_source(source)
    params = {"source": source_slug}
    if utm_medium:
        params["utm_source"] = "dutchaiagency"
        params["utm_medium"] = normalize_source(utm_medium)
    if utm_campaign:
        params["utm_campaign"] = normalize_source(utm_campaign)
    if utm_content:
        params["utm_content"] = normalize_source(utm_content)
    if target == "issue":
        return add_query_params(
            ISSUE_INTAKE_URL,
            {"template": ISSUE_TEMPLATE, **params},
        )
    if target == "site":
        return add_query_params(SITE_URL, params)
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


def utm_content_for_github_lead(repo: str, number: int) -> str:
    if not repo or number <= 0:
        raise ValueError("repo and positive issue number are required")
    return normalize_source(f"{repo}-{number}")


def github_outbound_utm_defaults(
    repo: str,
    number: int,
    *,
    day: date | str | None = None,
) -> dict[str, str]:
    if not repo or number <= 0:
        raise ValueError("repo and positive issue number are required")
    if day is None:
        day_value = datetime.now(UTC).date().isoformat()
    elif isinstance(day, date):
        day_value = day.isoformat()
    else:
        day_value = day
    return {
        "utm_medium": "github",
        "utm_campaign": f"outbound-{day_value}",
        "utm_content": utm_content_for_github_lead(repo, number),
    }


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
    parser.add_argument("--utm-medium", help="Optional UTM medium, e.g. github.")
    parser.add_argument("--utm-campaign", help="Optional UTM campaign.")
    parser.add_argument("--utm-content", help="Optional UTM content slug.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    utm_medium = args.utm_medium
    utm_campaign = args.utm_campaign
    utm_content = args.utm_content
    if args.repo or args.issue:
        if not args.repo or not args.issue:
            raise SystemExit("--repo and --issue must be used together")
        source = source_for_github_lead(args.repo, args.issue, day=args.date)
        defaults = github_outbound_utm_defaults(args.repo, args.issue, day=args.date)
        utm_medium = utm_medium or defaults["utm_medium"]
        utm_campaign = utm_campaign or defaults["utm_campaign"]
        utm_content = utm_content or defaults["utm_content"]
    elif args.source:
        source = args.source
    else:
        raise SystemExit("provide a source or --repo/--issue")
    print(
        build_intake_url(
            source,
            target=args.target,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
