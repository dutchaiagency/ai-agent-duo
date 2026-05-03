#!/usr/bin/env python3
"""Scout Show HN launches for contactable dev-tool service leads.

Read-only by design. This script does not send email, post comments, or guess
addresses. It only accepts emails that are explicitly present in public HN
profiles, launch pages, or GitHub profile metadata.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_SHOWSTORIES_URL = "https://hacker-news.firebaseio.com/v0/showstories.json"
DEFAULT_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
DEFAULT_USER_URL = "https://hacker-news.firebaseio.com/v0/user/{id}.json"
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_USER_AGENT = (
    "survival-agents-hn-show-contact-scout/1.0 "
    "(+https://github.com/dutchaiagency/ai-agent-duo)"
)
AGENT_RE = re.compile(r"[^a-z0-9_-]+")
TAG_RE = re.compile(r"<[^>]+>")
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"(?![A-Za-z0-9._%+-])"
)
GITHUB_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"(?:[/?#\"'<>\\\s]|$)",
    re.IGNORECASE,
)
GITHUB_REPO_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"\s+(?:PR\s+)?#\d+",
    re.IGNORECASE,
)
GITHUB_BARE_REPO_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_.:-])"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"(?=$|[\s`),;:\]|<])",
    re.IGNORECASE,
)
LOCAL_PATH_OWNERS = {
    ".github",
    "assets",
    "bounties",
    "evidence",
    "longform",
    "ops",
    "products",
    "pull",
    "research",
    "issues",
    "state",
    "tests",
    "tmp",
    "tools",
    "wallet",
    "writing",
}
LOCAL_PATH_EXTENSIONS = {
    ".bat",
    ".css",
    ".html",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".txt",
    ".xml",
    ".yml",
}
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
    "example.com",
    "example.org",
    "example.net",
    "email.com",
    "github.com",
    "hackernews.com",
    "news.ycombinator.com",
    "spam.com",
    "yourdomain.com",
}
LARGE_ORG_STAR_THRESHOLD = 10_000
MASSIVE_REPO_STAR_THRESHOLD = 25_000
DEV_FIT_TERMS = (
    "agent",
    "ai",
    "api",
    "automation",
    "cli",
    "code",
    "database",
    "dev",
    "developer",
    "framework",
    "github",
    "llm",
    "mcp",
    "open source",
    "python",
    "rag",
    "runtime",
    "server",
    "shell",
    "typescript",
    "wasm",
)
GITHUB_RESERVED_OWNERS = {
    "about",
    "apps",
    "blog",
    "collections",
    "customer-stories",
    "events",
    "explore",
    "features",
    "login",
    "marketplace",
    "new",
    "notifications",
    "orgs",
    "pricing",
    "pulls",
    "search",
    "settings",
    "sponsors",
    "topics",
}
GITHUB_RESERVED_REPOS = {
    "followers",
    "following",
    "projects",
    "repositories",
    "stars",
    "tab",
}
BLOCKED_GITHUB_REPOS = {
    "dutchaiagency/ai-agent-duo",
}


@dataclass(frozen=True)
class HNStory:
    item_id: int
    title: str
    url: str
    by: str
    score: int
    comments: int
    text: str = ""

    @property
    def hn_url(self) -> str:
        return f"https://news.ycombinator.com/item?id={self.item_id}"


@dataclass(frozen=True)
class GithubRepo:
    full_name: str
    html_url: str
    description: str
    stars: int
    pushed_at: str
    owner_login: str
    owner_type: str
    owner_email: str
    owner_url: str


@dataclass(frozen=True)
class ContactLead:
    story: HNStory
    repo: GithubRepo | None
    emails: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    decision: str
    reasons: tuple[str, ...]


JsonFetcher = Callable[[str], Any]
TextFetcher = Callable[[str], str]


def request_json(url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20) -> Any:
    headers = {"Accept": "application/json", "User-Agent": user_agent}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith(DEFAULT_GITHUB_API_URL):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20) -> str:
    request = Request(url, headers={"Accept": "*/*", "User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return response.read(300_000).decode("utf-8", errors="replace")


def compact(value: str) -> str:
    return " ".join(value.split())


def strip_html(value: str) -> str:
    return compact(html.unescape(TAG_RE.sub(" ", value or "")))


def safe_agent(value: str) -> str:
    normalized = AGENT_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "agent"


def normalize_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def state_snapshot_path(state_dir: Path, agent: str, generated_at: datetime) -> Path:
    return state_dir / (
        "hn-show-contact-scout-"
        f"{generated_at.strftime('%Y-%m-%d')}-"
        f"{safe_agent(agent)}-"
        f"{generated_at.strftime('%H%M')}.md"
    )


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


def is_large_org_repo(repo: GithubRepo | None) -> bool:
    if repo is None:
        return False
    return repo.owner_type.lower() == "organization" and repo.stars >= LARGE_ORG_STAR_THRESHOLD


def is_massive_repo(repo: GithubRepo | None) -> bool:
    if repo is None:
        return False
    return repo.stars >= MASSIVE_REPO_STAR_THRESHOLD


def extract_emails(text: str) -> tuple[str, ...]:
    emails: list[str] = []
    for match in EMAIL_RE.finditer(html.unescape(text or "")):
        email = normalize_email(match.group(1))
        if not is_usable_email(email) or email in emails:
            continue
        emails.append(email)
    return tuple(emails)


def parse_github_repo_url(url: str) -> tuple[str, str] | None:
    parsed = urlparse(html.unescape(url.strip()))
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if owner.lower() in GITHUB_RESERVED_OWNERS or repo.lower() in GITHUB_RESERVED_REPOS:
        return None
    if repo.endswith(".git"):
        repo = repo[:-4]
    if normalize_repo(f"{owner}/{repo}") in BLOCKED_GITHUB_REPOS:
        return None
    return owner, repo


def normalize_repo(value: str) -> str:
    return value.strip().strip("/").lower()


def is_probable_github_repo_ref(owner: str, repo: str) -> bool:
    owner_norm = owner.strip().lower()
    repo_norm = repo.strip().lower()
    if owner_norm in LOCAL_PATH_OWNERS:
        return False
    if owner_norm in GITHUB_RESERVED_OWNERS or repo_norm in GITHUB_RESERVED_REPOS:
        return False
    if any(repo_norm.endswith(extension) for extension in LOCAL_PATH_EXTENSIONS):
        return False
    return bool(owner_norm and repo_norm)


def extract_github_repo_urls(text: str) -> tuple[str, ...]:
    urls: list[str] = []
    for match in GITHUB_URL_RE.finditer(text or ""):
        owner = match.group("owner")
        repo = match.group("repo")
        url = f"https://github.com/{owner}/{repo}"
        if parse_github_repo_url(url) and url not in urls:
            urls.append(url)
    return tuple(urls)


def normalize_repo_match_text(value: str) -> str:
    normalized = html.unescape(value or "").lower().replace("_", "-")
    return re.sub(r"[^a-z0-9./-]+", " ", normalized)


def repo_context_score(url: str, context: str) -> int:
    parsed = parse_github_repo_url(url)
    if parsed is None:
        return 0
    owner, repo = parsed
    owner_norm = owner.lower().replace("_", "-")
    repo_norm = repo.lower().replace("_", "-")
    context_norm = normalize_repo_match_text(context)

    score = 0
    if f"{owner_norm}/{repo_norm}" in context_norm:
        score += 8
    if repo_norm and repo_norm in context_norm:
        score += 5
    if owner_norm and owner_norm in context_norm:
        score += 1
    return score


def best_repo_url(urls: tuple[str, ...], context: str) -> str:
    if not urls:
        return ""
    return max(enumerate(urls), key=lambda item: (repo_context_score(item[1], context), -item[0]))[1]


def normalize_story(payload: dict[str, Any]) -> HNStory | None:
    if payload.get("type") != "story":
        return None
    title = compact(str(payload.get("title") or ""))
    if not title:
        return None
    return HNStory(
        item_id=int(payload.get("id") or 0),
        title=title,
        url=str(payload.get("url") or ""),
        by=str(payload.get("by") or ""),
        score=int(payload.get("score") or 0),
        comments=int(payload.get("descendants") or 0),
        text=strip_html(str(payload.get("text") or "")),
    )


def fetch_show_stories(
    *,
    limit: int,
    showstories_url: str = DEFAULT_SHOWSTORIES_URL,
    item_url_template: str = DEFAULT_ITEM_URL,
    json_fetcher: JsonFetcher = request_json,
) -> list[HNStory]:
    ids = json_fetcher(showstories_url)
    if not isinstance(ids, list):
        raise ValueError("HN showstories response was not a list")
    stories: list[HNStory] = []
    for item_id in ids[:limit]:
        payload = json_fetcher(item_url_template.format(id=item_id))
        if not isinstance(payload, dict):
            continue
        story = normalize_story(payload)
        if story is not None:
            stories.append(story)
    return stories


def fetch_hn_user_about(
    username: str,
    *,
    user_url_template: str = DEFAULT_USER_URL,
    json_fetcher: JsonFetcher = request_json,
) -> str:
    if not username:
        return ""
    try:
        payload = json_fetcher(user_url_template.format(id=username))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return strip_html(str(payload.get("about") or ""))


def github_api_json(path: str, *, api_url: str, json_fetcher: JsonFetcher) -> dict[str, Any]:
    try:
        payload = json_fetcher(f"{api_url.rstrip('/')}/{path.lstrip('/')}")
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_github_repo(
    owner: str,
    repo: str,
    *,
    api_url: str = DEFAULT_GITHUB_API_URL,
    json_fetcher: JsonFetcher = request_json,
) -> GithubRepo | None:
    repo_payload = github_api_json(f"repos/{owner}/{repo}", api_url=api_url, json_fetcher=json_fetcher)
    if not repo_payload:
        return None
    owner_payload = github_api_json(f"users/{owner}", api_url=api_url, json_fetcher=json_fetcher)
    owner_info = repo_payload.get("owner") if isinstance(repo_payload.get("owner"), dict) else {}
    email = normalize_email(str(owner_payload.get("email") or ""))
    if email and not is_usable_email(email):
        email = ""
    return GithubRepo(
        full_name=str(repo_payload.get("full_name") or f"{owner}/{repo}"),
        html_url=str(repo_payload.get("html_url") or f"https://github.com/{owner}/{repo}"),
        description=compact(str(repo_payload.get("description") or "")),
        stars=int(repo_payload.get("stargazers_count") or 0),
        pushed_at=str(repo_payload.get("pushed_at") or ""),
        owner_login=str(owner_payload.get("login") or owner_info.get("login") or owner),
        owner_type=str(owner_payload.get("type") or owner_info.get("type") or ""),
        owner_email=email,
        owner_url=str(owner_payload.get("html_url") or f"https://github.com/{owner}"),
    )


def fetch_optional_text(url: str, fetcher: TextFetcher) -> str:
    if not urlparse(url).scheme in {"http", "https"}:
        return ""
    try:
        return fetcher(url)
    except (HTTPError, URLError, TimeoutError, ValueError, UnicodeDecodeError):
        return ""


def first_repo_url(story: HNStory, launch_page: str) -> str:
    if parse_github_repo_url(story.url):
        return story.url
    urls = extract_github_repo_urls(" ".join([story.text, launch_page]))
    context = " ".join([story.title, story.text])
    return best_repo_url(urls, context)


def fit_reasons(story: HNStory, repo: GithubRepo | None, launch_page: str) -> tuple[str, ...]:
    blob = " ".join(
        [
            story.title,
            story.text,
            repo.description if repo else "",
            strip_html(launch_page[:8000]),
        ]
    ).lower()
    reasons = [term for term in DEV_FIT_TERMS if term in blob]
    if repo is not None:
        reasons.insert(0, "github repo")
    return tuple(dict.fromkeys(reasons))[:10]


def scan_story(
    story: HNStory,
    *,
    contacted_emails: set[str] | None = None,
    touched_repos: set[str] | None = None,
    fetch_launch_pages: bool = True,
    json_fetcher: JsonFetcher = request_json,
    text_fetcher: TextFetcher = request_text,
    github_api_url: str = DEFAULT_GITHUB_API_URL,
) -> ContactLead:
    contacted_emails = contacted_emails or set()
    touched_repos = touched_repos or set()
    evidence_urls: list[str] = []
    emails: list[str] = []

    hn_about = fetch_hn_user_about(story.by, json_fetcher=json_fetcher)
    for email in extract_emails(hn_about):
        emails.append(email)
        evidence_urls.append(f"https://news.ycombinator.com/user?id={story.by}")

    launch_page = ""
    parsed_story_url = urlparse(story.url)
    if fetch_launch_pages and parsed_story_url.scheme in {"http", "https"}:
        launch_page = fetch_optional_text(story.url, text_fetcher)
        for email in extract_emails(launch_page):
            if email not in emails:
                emails.append(email)
                evidence_urls.append(story.url)

    repo: GithubRepo | None = None
    repo_url = first_repo_url(story, launch_page)
    parsed_repo = parse_github_repo_url(repo_url) if repo_url else None
    if parsed_repo is not None:
        repo = fetch_github_repo(
            parsed_repo[0],
            parsed_repo[1],
            api_url=github_api_url,
            json_fetcher=json_fetcher,
        )
        if repo and repo.owner_email and repo.owner_email not in emails:
            emails.append(repo.owner_email)
            evidence_urls.append(repo.owner_url)

    reasons = list(fit_reasons(story, repo, launch_page))
    if not emails:
        decision = "reject_no_public_email"
        reasons.append("no explicit public email")
    elif any(email in contacted_emails for email in emails):
        decision = "watch_already_contacted"
        reasons.append("email already in contact log")
    elif repo is not None and normalize_repo(repo.full_name) in touched_repos:
        decision = "watch_already_contacted"
        reasons.append("repo already in active touch log")
    elif repo is None:
        decision = "watch_public_email_no_repo"
        reasons.append("public email but no GitHub repo found")
    elif is_large_org_repo(repo):
        decision = "watch_large_org_repo"
        reasons.append("large org repo; needs specific issue before outreach")
    elif is_massive_repo(repo):
        decision = "watch_large_repo"
        reasons.append("large repo; needs specific issue before outreach")
    elif not reasons:
        decision = "watch_low_fit"
        reasons.append("low service-fit signal")
    else:
        decision = "candidate_needs_deep_read"
        reasons.append("explicit public email")

    return ContactLead(
        story=story,
        repo=repo,
        emails=tuple(dict.fromkeys(emails)),
        evidence_urls=tuple(dict.fromkeys(evidence_urls)),
        decision=decision,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def scan_stories(
    stories: list[HNStory],
    *,
    contacted_emails: set[str] | None = None,
    touched_repos: set[str] | None = None,
    fetch_launch_pages: bool = True,
    json_fetcher: JsonFetcher = request_json,
    text_fetcher: TextFetcher = request_text,
    github_api_url: str = DEFAULT_GITHUB_API_URL,
) -> list[ContactLead]:
    return [
        scan_story(
            story,
            contacted_emails=contacted_emails,
            touched_repos=touched_repos,
            fetch_launch_pages=fetch_launch_pages,
            json_fetcher=json_fetcher,
            text_fetcher=text_fetcher,
            github_api_url=github_api_url,
        )
        for story in stories
    ]


def load_contacted_emails(paths: list[Path]) -> set[str]:
    contacted: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        contacted.update(extract_emails(path.read_text(encoding="utf-8", errors="replace")))
    return contacted


def load_touched_repos(paths: list[Path]) -> set[str]:
    touched: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in GITHUB_URL_RE.finditer(text):
            touched.add(normalize_repo(f"{match.group('owner')}/{match.group('repo')}"))
        for match in GITHUB_REPO_REF_RE.finditer(text):
            touched.add(normalize_repo(f"{match.group('owner')}/{match.group('repo')}"))
        for match in GITHUB_BARE_REPO_REF_RE.finditer(text):
            owner = match.group("owner")
            repo = match.group("repo")
            if is_probable_github_repo_ref(owner, repo):
                touched.add(normalize_repo(f"{owner}/{repo}"))
    return touched


def table_escape(value: str) -> str:
    return compact(value).replace("|", "\\|")


def markdown_link(label: str, url: str) -> str:
    escaped = table_escape(label)
    if not url:
        return escaped
    return f"[{escaped}]({url})"


def render_markdown(
    leads: list[ContactLead],
    *,
    limit: int,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    candidates = [lead for lead in leads if lead.decision == "candidate_needs_deep_read"]
    already_contacted = [lead for lead in leads if lead.decision == "watch_already_contacted"]
    lines = [
        f"# HN Show Contact Scout - {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Read-only scout. Do not send email from this file alone: first do a public-code deep read and write one concrete personalization sentence.",
        "",
        "## Summary",
        "",
        f"- Show HN stories scanned: {len(leads)} (limit {limit})",
        f"- Candidate leads needing deep read: {len(candidates)}",
        f"- Already-contacted or active-touch leads: {len(already_contacted)}",
    ]
    if candidates:
        labels = ", ".join(f"HN #{lead.story.item_id}" for lead in candidates[:10])
        lines.append(f"- Result: candidate supply present after public-email gate ({labels}).")
    else:
        lines.append("- Result: zero send-ready candidates; hold outbound until a deep-readable lead clears the gate.")

    lines.extend(
        [
            "",
            "| Decision | Story | Score / comments | Repo | Public contact | Evidence | Reasons |",
            "| --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    if not leads:
        lines.append("| reject_no_public_email | - | 0 / 0 | - | - | - | No stories parsed. |")
        return "\n".join(lines) + "\n"

    for lead in leads:
        story = markdown_link(f"#{lead.story.item_id} {lead.story.title}", lead.story.hn_url)
        score = f"{lead.story.score} / {lead.story.comments}"
        repo = markdown_link(lead.repo.full_name, lead.repo.html_url) if lead.repo else "-"
        emails = ", ".join(f"`{email}`" for email in lead.emails) or "-"
        evidence = ", ".join(markdown_link(urlparse(url).netloc or url, url) for url in lead.evidence_urls) or "-"
        reasons = ", ".join(table_escape(reason) for reason in lead.reasons) or "-"
        lines.append(
            f"| {lead.decision} | {story} | {score} | {repo} | {emails} | {evidence} | {reasons} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="Number of Show HN stories to inspect.")
    parser.add_argument("--showstories-url", default=DEFAULT_SHOWSTORIES_URL)
    parser.add_argument("--item-url-template", default=DEFAULT_ITEM_URL)
    parser.add_argument("--github-api-url", default=DEFAULT_GITHUB_API_URL)
    parser.add_argument("--skip-launch-page-fetch", action="store_true")
    parser.add_argument(
        "--contact-log",
        action="append",
        type=Path,
        default=[],
        help="Markdown/text file whose public emails should be treated as already contacted.",
    )
    parser.add_argument(
        "--touched-repo-log",
        action="append",
        type=Path,
        default=[Path("ops/outbound_pipeline.md")],
        help="Markdown/text file whose GitHub repo refs should be treated as already touched.",
    )
    parser.add_argument("--write", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Write to state/hn-show-contact-scout-YYYY-MM-DD-agent-HHMM.md.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--now", help="Override current UTC time, for tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write and args.state_dir:
        raise SystemExit("--write and --state-dir are mutually exclusive")

    generated_at = normalize_now(args.now)
    stories = fetch_show_stories(
        limit=args.limit,
        showstories_url=args.showstories_url,
        item_url_template=args.item_url_template,
    )
    leads = scan_stories(
        stories,
        contacted_emails=load_contacted_emails(args.contact_log),
        touched_repos=load_touched_repos(args.touched_repo_log),
        fetch_launch_pages=not args.skip_launch_page_fetch,
        github_api_url=args.github_api_url,
    )
    output = render_markdown(leads, limit=args.limit, generated_at=generated_at)
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
