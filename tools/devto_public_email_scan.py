#!/usr/bin/env python3
"""Scout dev.to authors whose public profile/site exposes a contact email.

The scanner is read-only. It never sends mail and never guesses addresses.
It only accepts emails that appear in public dev.to API fields, article bodies,
profile pages, or the linked personal site/contact pages.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from tools.agent_identity import default_agent_name
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from agent_identity import default_agent_name


DEFAULT_API_URL = "https://dev.to/api/articles"
DEFAULT_USER_AGENT = "survival-agents/1.0 (+https://github.com/dutchaiagency/ai-agent-duo)"
DEFAULT_TAGS = ("ai", "webdev", "typescript", "productivity")
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"(?![A-Za-z0-9._%+-])"
)
TAG_RE = re.compile(r"<[^>]+>")
AGENT_RE = re.compile(r"[^a-z0-9_-]+")
BLOCKED_LOCAL_PARTS = {
    "abuse",
    "donotreply",
    "example",
    "noreply",
    "no-reply",
    "postmaster",
    "privacy",
    "root",
    "security",
    "test",
}
BLOCKED_DOMAINS = {
    "dev.to",
    "example.com",
    "example.org",
    "example.net",
    "email.com",
    "yourdomain.com",
}
SKIP_HOSTS = {
    "dev.to",
    "github.com",
    "linkedin.com",
    "www.linkedin.com",
    "www.dev.to",
    "x.com",
    "twitter.com",
    "www.x.com",
    "www.twitter.com",
}
FIT_TERMS = (
    "agent",
    "ai",
    "api",
    "automation",
    "backend",
    "founder",
    "github",
    "mcp",
    "monorepo",
    "node",
    "open source",
    "react",
    "saas",
    "startup",
    "typescript",
    "websocket",
)


@dataclass(frozen=True)
class ArticleSeed:
    tag: str
    article_id: int
    title: str
    url: str
    canonical_url: str
    description: str
    tags: tuple[str, ...]
    published_at: str
    username: str
    name: str
    website_url: str
    github_username: str


@dataclass(frozen=True)
class ScanLead:
    seed: ArticleSeed
    emails: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    decision: str
    reasons: tuple[str, ...]
    profile_summary: str = ""


Fetcher = Callable[[str], str]
JsonFetcher = Callable[[str], Any]


def request_text(url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20) -> str:
    request = Request(url, headers={"Accept": "*/*", "User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return response.read(300_000).decode("utf-8", errors="replace")


def request_json(url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def strip_html(value: str) -> str:
    return html.unescape(TAG_RE.sub(" ", value or " "))


def normalize_email(value: str) -> str:
    return value.strip().strip(".,;:!?)>]}\"'").lower()


def is_usable_email(email: str) -> bool:
    local, _, domain = normalize_email(email).partition("@")
    if not local or not domain:
        return False
    if local in BLOCKED_LOCAL_PARTS:
        return False
    if domain in BLOCKED_DOMAINS:
        return False
    if domain.endswith(".invalid") or domain.endswith(".test"):
        return False
    return True


def extract_emails(text: str) -> tuple[str, ...]:
    emails: list[str] = []
    for match in EMAIL_RE.finditer(html.unescape(text or "")):
        email = normalize_email(match.group(1))
        if not is_usable_email(email) or email in emails:
            continue
        emails.append(email)
    return tuple(emails)


def as_article_seed(tag: str, payload: dict[str, Any]) -> ArticleSeed | None:
    user = payload.get("user") or {}
    username = str(user.get("username") or "")
    if not username:
        return None
    tags = payload.get("tag_list") or []
    return ArticleSeed(
        tag=tag,
        article_id=int(payload.get("id") or 0),
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or ""),
        canonical_url=str(payload.get("canonical_url") or ""),
        description=str(payload.get("description") or ""),
        tags=tuple(str(item) for item in tags if item),
        published_at=str(payload.get("published_at") or payload.get("published_timestamp") or ""),
        username=username,
        name=str(user.get("name") or username),
        website_url=str(user.get("website_url") or ""),
        github_username=str(user.get("github_username") or ""),
    )


def build_articles_url(api_url: str, tag: str, per_tag: int) -> str:
    separator = "&" if "?" in api_url else "?"
    return f"{api_url}{separator}tag={tag}&per_page={per_tag}"


def fetch_article_seeds(
    tags: tuple[str, ...],
    *,
    per_tag: int,
    api_url: str = DEFAULT_API_URL,
    json_fetcher: JsonFetcher = request_json,
) -> list[ArticleSeed]:
    by_user: dict[str, ArticleSeed] = {}
    for tag in tags:
        payload = json_fetcher(build_articles_url(api_url, tag, per_tag))
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            seed = as_article_seed(tag, item)
            if seed and seed.username not in by_user:
                by_user[seed.username] = seed
    return list(by_user.values())


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalized_host(value: str) -> str:
    host = urlparse(value).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def candidate_urls(seed: ArticleSeed) -> tuple[str, ...]:
    urls: list[str] = []
    for value in (seed.canonical_url, seed.website_url):
        if not is_http_url(value):
            continue
        host = normalized_host(value)
        if host in SKIP_HOSTS:
            continue
        if value not in urls:
            urls.append(value)
    if is_http_url(seed.website_url) and normalized_host(seed.website_url) not in SKIP_HOSTS:
        root = f"{urlparse(seed.website_url).scheme}://{urlparse(seed.website_url).netloc}/"
        for suffix in ("about/", "contact/", "about", "contact"):
            url = urljoin(root, suffix)
            if url not in urls:
                urls.append(url)
    return tuple(urls)


def source_fit_reasons(seed: ArticleSeed, profile_summary: str, detail_body: str) -> tuple[str, ...]:
    blob = " ".join(
        [
            seed.title,
            seed.description,
            " ".join(seed.tags),
            profile_summary,
            detail_body[:4000],
        ]
    ).lower()
    reasons = [term for term in FIT_TERMS if term in blob]
    return tuple(reasons[:8])


def fetch_optional_json(url: str, json_fetcher: JsonFetcher) -> dict[str, Any]:
    try:
        payload = json_fetcher(url)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_optional_text(url: str, fetcher: Fetcher) -> str:
    try:
        return fetcher(url)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return ""


def scan_seed(
    seed: ArticleSeed,
    *,
    fetcher: Fetcher = request_text,
    json_fetcher: JsonFetcher = request_json,
) -> ScanLead:
    profile = fetch_optional_json(
        f"https://dev.to/api/users/by_username?url={seed.username}",
        json_fetcher,
    )
    article = fetch_optional_json(f"https://dev.to/api/articles/{seed.article_id}", json_fetcher)
    profile_summary = str(profile.get("summary") or "")
    detail_body = str(article.get("body_markdown") or "")

    emails: list[str] = []
    evidence_urls: list[str] = []
    for text, url in (
        (json.dumps(profile), f"https://dev.to/{seed.username}"),
        (detail_body, seed.url),
    ):
        for email in extract_emails(text):
            if email not in emails:
                emails.append(email)
                evidence_urls.append(url)

    for url in candidate_urls(seed):
        text = fetch_optional_text(url, fetcher)
        if not text:
            continue
        page_text = f"{text}\n{strip_html(text)}"
        for email in extract_emails(page_text):
            if email not in emails:
                emails.append(email)
                evidence_urls.append(url)

    reasons = list(source_fit_reasons(seed, profile_summary, detail_body))
    if emails:
        decision = "candidate_needs_deep_read"
        reasons.insert(0, "explicit public email")
    else:
        decision = "reject_no_public_email"
        reasons.insert(0, "no explicit public email")

    return ScanLead(
        seed=seed,
        emails=tuple(emails),
        evidence_urls=tuple(dict.fromkeys(evidence_urls)),
        decision=decision,
        reasons=tuple(dict.fromkeys(reasons)),
        profile_summary=profile_summary,
    )


def scan(
    tags: tuple[str, ...],
    *,
    per_tag: int,
    max_profiles: int,
    sleep_seconds: float = 0.0,
    api_url: str = DEFAULT_API_URL,
    fetcher: Fetcher = request_text,
    json_fetcher: JsonFetcher = request_json,
) -> list[ScanLead]:
    seeds = fetch_article_seeds(tags, per_tag=per_tag, api_url=api_url, json_fetcher=json_fetcher)
    leads: list[ScanLead] = []
    for seed in seeds[:max_profiles]:
        leads.append(scan_seed(seed, fetcher=fetcher, json_fetcher=json_fetcher))
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return leads


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(
    leads: list[ScanLead],
    *,
    tags: tuple[str, ...],
    per_tag: int,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    candidates = [lead for lead in leads if lead.emails]
    rejects = [lead for lead in leads if not lead.emails]
    lines = [
        f"# Dev.to Public Email Supply Scan - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Read-only scan. Do not email from this file alone; deep-read the public work first and personalize one-by-one.",
        "",
        f"Tags: `{', '.join(tags)}`. Per tag: `{per_tag}`.",
        "",
        "## Summary",
        "",
        f"- Profiles scanned: {len(leads)}",
        f"- Public-email candidates: {len(candidates)}",
        f"- No-email rejects: {len(rejects)}",
        "",
        "## Candidates",
        "",
        "| Person | Email | Article | Evidence | Reasons |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not candidates:
        lines.append("| - | - | - | - | - |")
    for lead in candidates:
        seed = lead.seed
        emails = ", ".join(f"`{email}`" for email in lead.emails)
        evidence = ", ".join(f"[evidence {idx + 1}]({url})" for idx, url in enumerate(lead.evidence_urls))
        reasons = ", ".join(lead.reasons)
        lines.append(
            f"| {escape_cell(seed.name)} (`{seed.username}`) | {emails} | "
            f"[{escape_cell(seed.title)}]({seed.url}) | {evidence or '-'} | "
            f"{escape_cell(reasons)} |"
        )

    lines.extend(
        [
            "",
            "## Rejects",
            "",
            "| Person | Article | Reason |",
            "| --- | --- | --- |",
        ]
    )
    if not rejects:
        lines.append("| - | - | - |")
    for lead in rejects[:40]:
        seed = lead.seed
        reasons = ", ".join(lead.reasons)
        lines.append(
            f"| {escape_cell(seed.name)} (`{seed.username}`) | "
            f"[{escape_cell(seed.title)}]({seed.url}) | {escape_cell(reasons)} |"
        )
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
        "devto-public-email-scan-"
        f"{generated_at.strftime('%Y-%m-%d')}-"
        f"{safe_agent(agent)}-"
        f"{generated_at.strftime('%H%M')}.md"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", action="append", dest="tags", help="dev.to tag to scan. Repeatable.")
    parser.add_argument("--per-tag", type=int, default=10)
    parser.add_argument("--max-profiles", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds between profile/site scans.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--agent", default=default_agent_name())
    parser.add_argument("--now")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write and args.state_dir:
        raise SystemExit("--write and --state-dir are mutually exclusive")
    tags = tuple(args.tags or DEFAULT_TAGS)
    generated_at = normalize_now(args.now)
    leads = scan(
        tags,
        per_tag=args.per_tag,
        max_profiles=args.max_profiles,
        sleep_seconds=args.sleep,
        api_url=args.api_url,
    )
    output = render_markdown(
        leads,
        tags=tags,
        per_tag=args.per_tag,
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
