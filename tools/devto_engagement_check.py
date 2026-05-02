#!/usr/bin/env python3
"""Fetch and render a dev.to engagement snapshot for one username."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_URL = "https://dev.to/api/articles"
DEFAULT_USER_AGENT = "survival-agents/1.0 (+https://github.com/dutchaiagency/ai-agent-duo)"
AGENT_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True)
class DevtoArticle:
    title: str
    published_at: str
    reactions: int
    comments: int
    url: str


def parse_count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_article(payload: dict[str, Any]) -> DevtoArticle:
    return DevtoArticle(
        title=str(payload.get("title") or ""),
        published_at=str(payload.get("published_at") or payload.get("created_at") or ""),
        reactions=parse_count(payload.get("public_reactions_count")),
        comments=parse_count(payload.get("comments_count")),
        url=str(payload.get("url") or ""),
    )


def build_url(api_url: str, username: str, per_page: int) -> str:
    separator = "&" if "?" in api_url else "?"
    return f"{api_url}{separator}{urlencode({'username': username, 'per_page': per_page})}"


def fetch_articles(
    username: str,
    *,
    per_page: int = 100,
    api_url: str = DEFAULT_API_URL,
    user_agent: str = DEFAULT_USER_AGENT,
) -> list[DevtoArticle]:
    request = Request(
        build_url(api_url, username, per_page),
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, list):
        raise ValueError("dev.to API response was not a list")
    return [normalize_article(item) for item in payload if isinstance(item, dict)]


def render_markdown(
    articles: list[DevtoArticle],
    *,
    username: str,
    per_page: int,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    total_reactions = sum(article.reactions for article in articles)
    total_comments = sum(article.comments for article in articles)
    lines = [
        f"# Dev.to engagement - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Endpoint: `https://dev.to/api/articles?username={username}&per_page={per_page}`",
        "",
        "Headers: normal heartbeat User-Agent, no auth.",
        "",
        "## Result",
        "",
        f"Total visible posts: {len(articles)}",
        f"Total reactions: {total_reactions}",
        f"Total comments: {total_comments}",
        "",
        "| Post | Published | Reactions | Comments | URL |",
        "|---|---:|---:|---:|---|",
    ]
    for article in articles:
        title = article.title.replace("|", "\\|")
        lines.append(
            "| "
            f"{title} | {article.published_at} | {article.reactions} | "
            f"{article.comments} | {article.url} |"
        )
    if not articles:
        lines.append("| - | - | 0 | 0 | - |")
    return "\n".join(lines) + "\n"


def normalize_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def safe_agent(value: str) -> str:
    normalized = AGENT_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "agent"


def state_snapshot_path(state_dir: Path, agent: str, generated_at: datetime) -> Path:
    return state_dir / (
        "devto-engagement-"
        f"{generated_at.strftime('%Y-%m-%d')}-"
        f"{safe_agent(agent)}-"
        f"{generated_at.strftime('%H%M')}.md"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="dutchaiagents")
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--write", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Write to a timestamped state/devto-engagement-YYYY-MM-DD-agent-HHMM.md file.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--now", help="Override current UTC time, for tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write and args.state_dir:
        raise SystemExit("--write and --state-dir are mutually exclusive")

    generated_at = normalize_now(args.now)
    articles = fetch_articles(
        args.username,
        per_page=args.per_page,
        api_url=args.api_url,
        user_agent=args.user_agent,
    )
    output = render_markdown(
        articles,
        username=args.username,
        per_page=args.per_page,
        generated_at=generated_at,
    )
    write_path = args.write
    if args.state_dir:
        write_path = state_snapshot_path(args.state_dir, args.agent, generated_at)

    if write_path:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(output, encoding="utf-8")
        print(write_path.as_posix())
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
