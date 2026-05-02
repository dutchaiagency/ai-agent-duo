#!/usr/bin/env python3
"""Read a Farcaster channel feed (or home) and dump top casts as text.

Usage:
    python ops/farcaster_feed_read.py [channel]

If `channel` is omitted, defaults to `ai`. Use `home` to read the personal
home feed instead (requires logged-in profile).

Output: plain text dump of the page body (top portion only), enough to
scout 5-15 recent casts for outbound-engagement scouting. No parsing,
no posting -- read-only signal collection. Pair with farcaster_browser.py
for the actual reply step once a target is picked.

Uses domcontentloaded + sleep instead of networkidle (Farcaster SPA polls
continuously, networkidle never settles -- see commit 0094546 lesson).
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "dutchaiagency"


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "ai"
    if target == "home":
        url = "https://farcaster.xyz/~/feed"
    else:
        url = f"https://farcaster.xyz/~/channel/{target}"

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        body = page.inner_text("body")[:6000]
        print(f"# Farcaster feed read: {url}")
        print(f"# (top 6000 chars of inner_text, {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())})")
        print()
        print(body)
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
