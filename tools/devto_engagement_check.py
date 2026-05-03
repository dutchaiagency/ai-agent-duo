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
from typing import Any, Sequence
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlparse
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


def normalize_slug(value: str) -> str:
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        cleaned = parsed.path
    cleaned = cleaned.strip("/")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    if not cleaned:
        raise ValueError("dev.to article slug must not be empty")
    return cleaned


def build_article_url(api_url: str, username: str, slug: str) -> str:
    return (
        f"{api_url.rstrip('/')}/"
        f"{quote(username, safe='')}/"
        f"{quote(normalize_slug(slug), safe='')}"
    )


def read_json_api(url: str, *, user_agent: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def article_key(article: DevtoArticle) -> tuple[str, ...]:
    if article.url:
        return ("url", article.url)
    return ("title-published", article.title, article.published_at)


def published_sort_key(article: DevtoArticle) -> datetime:
    try:
        parsed = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def merge_articles(
    username_articles: Sequence[DevtoArticle],
    fallback_articles: Sequence[DevtoArticle],
) -> list[DevtoArticle]:
    merged: list[DevtoArticle] = []
    seen: set[tuple[str, ...]] = set()
    for article in [*username_articles, *fallback_articles]:
        key = article_key(article)
        if key in seen:
            continue
        seen.add(key)
        merged.append(article)
    if fallback_articles:
        merged.sort(key=published_sort_key, reverse=True)
    return merged


def fetch_article_by_slug(
    username: str,
    slug: str,
    *,
    api_url: str = DEFAULT_API_URL,
    user_agent: str = DEFAULT_USER_AGENT,
) -> DevtoArticle:
    payload = read_json_api(
        build_article_url(api_url, username, slug),
        user_agent=user_agent,
    )
    if not isinstance(payload, dict):
        raise ValueError("dev.to article response was not an object")
    return normalize_article(payload)


def fetch_articles(
    username: str,
    *,
    per_page: int = 100,
    api_url: str = DEFAULT_API_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    slugs: Sequence[str] | None = None,
    missing_slugs: list[str] | None = None,
) -> list[DevtoArticle]:
    payload = read_json_api(
        build_url(api_url, username, per_page),
        user_agent=user_agent,
    )

    if not isinstance(payload, list):
        raise ValueError("dev.to API response was not a list")
    username_articles = [normalize_article(item) for item in payload if isinstance(item, dict)]
    fallback_articles: list[DevtoArticle] = []
    for slug in slugs or []:
        normalized_slug = normalize_slug(slug)
        try:
            fallback_articles.append(
                fetch_article_by_slug(
                    username,
                    normalized_slug,
                    api_url=api_url,
                    user_agent=user_agent,
                )
            )
        except HTTPError as exc:
            if exc.code != 404:
                raise
            if missing_slugs is not None:
                missing_slugs.append(normalized_slug)
            print(
                f"warning: dev.to article slug not found: {username}/{normalized_slug}",
                file=sys.stderr,
            )
    return merge_articles(username_articles, fallback_articles)


def render_markdown(
    articles: list[DevtoArticle],
    *,
    username: str,
    per_page: int,
    slugs: Sequence[str] | None = None,
    missing_slugs: Sequence[str] | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    total_reactions = sum(article.reactions for article in articles)
    total_comments = sum(article.comments for article in articles)
    lines = [
        f"# Dev.to engagement - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Endpoint: `https://dev.to/api/articles?username={username}&per_page={per_page}`",
    ]
    if slugs:
        rendered_slugs = ", ".join(f"`{normalize_slug(slug)}`" for slug in slugs)
        lines.append(
            f"Fresh-publish fallback: `/api/articles/{username}/<slug>` for {rendered_slugs}"
        )
    if missing_slugs:
        rendered_missing = ", ".join(f"`{slug}`" for slug in missing_slugs)
        lines.append(f"Missing fallback slugs skipped: {rendered_missing} (404)")
    lines.extend(
        [
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
    )
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
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        help=(
            "Also fetch /api/articles/{username}/{slug}; useful when the "
            "username article list lags behind a fresh publish. May be repeated."
        ),
    )
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
    missing_slugs: list[str] = []
    articles = fetch_articles(
        args.username,
        per_page=args.per_page,
        api_url=args.api_url,
        user_agent=args.user_agent,
        slugs=args.slug,
        missing_slugs=missing_slugs,
    )
    output = render_markdown(
        articles,
        username=args.username,
        per_page=args.per_page,
        slugs=args.slug,
        missing_slugs=missing_slugs,
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
