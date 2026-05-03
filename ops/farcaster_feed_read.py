#!/usr/bin/env python3
"""Read a Farcaster channel feed (or home) and dump top casts as text.

Usage:
    python ops/farcaster_feed_read.py [channel]

If `channel` is omitted, defaults to `ai`. Use `home` to read the personal
home feed instead (requires logged-in profile).

Output: targetable cast hashes/permalinks plus a plain text dump of the page
body (top portion only), enough to scout 5-15 recent casts for outbound
engagement. No posting -- read-only signal collection. Pair the cast hash with
ops/farcaster.py if an API token exists, or use the permalink for manual
browser reply validation.

Uses domcontentloaded + sleep instead of networkidle (Farcaster SPA polls
continuously, networkidle never settles -- see commit 0094546 lesson).
"""
import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "dutchaiagency"
BASE_URL = "https://farcaster.xyz"
DEFAULT_TARGET = "ai"
DEFAULT_WAIT_SECONDS = 3.0
DEFAULT_MAX_CHARS = 6000
DEFAULT_CAST_LIMIT = 15


def target_url(target: str) -> str:
    raw_target = (target or DEFAULT_TARGET).strip() or DEFAULT_TARGET
    parsed = urlparse(raw_target)

    if parsed.scheme in {"http", "https"}:
        host = parsed.netloc.lower()
        if host not in {"farcaster.xyz", "www.farcaster.xyz"}:
            raise ValueError(f"target URL must be on farcaster.xyz, got {parsed.netloc!r}")
        target = parsed.path.strip("/")
    else:
        target = raw_target.strip().strip("/")

    normalized = target.lower()
    if normalized in {"home", "feed", "~/feed"}:
        return f"{BASE_URL}/~/feed"

    channel_prefix = "~/channel/"
    if normalized.startswith(channel_prefix):
        target = target[len(channel_prefix) :].strip("/")

    if not target:
        target = DEFAULT_TARGET

    return f"{BASE_URL}/~/channel/{target}"


def summarize_text(text: str, max_chars: int = 280) -> str:
    summary = " ".join(text.split())
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3] + "..."


def absolute_farcaster_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("/"):
        return f"{BASE_URL}{href}"
    if href.startswith(BASE_URL):
        return href
    return None


def permalink_from_hrefs(cast_hash: str | None, hrefs: list[str | None]) -> str | None:
    """Return the cast permalink whose short hash matches the DOM cast hash."""
    short_hash = cast_hash[:10].lower() if cast_hash else ""
    fallback = None

    for href in hrefs:
        if not href:
            continue
        match = re.fullmatch(r"/[A-Za-z0-9._-]+/(0x[0-9a-fA-F]{8,})", href)
        if not match:
            continue
        absolute = absolute_farcaster_url(href)
        if short_hash and match.group(1).lower() == short_hash:
            return absolute
        fallback = fallback or absolute

    return fallback


def cast_hash_from_id(cast_id: str | None) -> str | None:
    if cast_id and cast_id.startswith("cast:"):
        return cast_id.split(":", 1)[1]
    return None


def extract_cast_targets(page, limit: int = DEFAULT_CAST_LIMIT) -> list[dict[str, str | None]]:
    targets = []
    casts = page.locator("div[id^='cast:']")
    count = min(casts.count(), limit)

    for idx in range(count):
        cast = casts.nth(idx)
        cast_hash = cast_hash_from_id(cast.get_attribute("id"))
        links = cast.locator("a")
        hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
        targets.append(
            {
                "hash": cast_hash,
                "permalink": permalink_from_hrefs(cast_hash, hrefs),
                "summary": summarize_text(cast.inner_text(timeout=2000)),
            }
        )

    return targets


def print_cast_targets(targets: list[dict[str, str | None]]) -> None:
    print("# Cast targets")
    if not targets:
        print("# (none found)")
        return

    for idx, target in enumerate(targets, start=1):
        print(f"# {idx}. hash={target.get('hash') or '<missing>'}")
        print(f"#    permalink={target.get('permalink') or '<missing>'}")
        print(f"#    summary={target.get('summary') or ''}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Farcaster feed/channel casts without posting.")
    parser.add_argument("target", nargs="?", default=DEFAULT_TARGET, help="Channel name, or 'home' for the home feed.")
    parser.add_argument("--wait", type=float, default=DEFAULT_WAIT_SECONDS, help="Seconds to wait after domcontentloaded.")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, help="Maximum body text characters to print.")
    parser.add_argument("--cast-limit", type=int, default=DEFAULT_CAST_LIMIT, help="Maximum cast target rows to print.")
    parser.add_argument("--no-body", action="store_true", help="Print only target hashes/permalinks, not body text.")
    args = parser.parse_args()

    try:
        url = target_url(args.target)
    except ValueError as exc:
        parser.error(str(exc))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(max(0.0, args.wait))
        targets = extract_cast_targets(page, args.cast_limit)
        body = page.inner_text("body")[: args.max_chars]
        print(f"# Farcaster feed read: {url}")
        if page.url.rstrip("/") != url.rstrip("/"):
            print(f"# Final browser URL: {page.url}")
        print(f"# (top {args.max_chars} chars of inner_text, {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())})")
        print()
        print_cast_targets(targets)
        if not args.no_body:
            print()
            print(body)
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
