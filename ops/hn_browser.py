#!/usr/bin/env python3
"""
Hacker News browser flow via Playwright (persistent profile).

Subcommands:
    signup --username U                # create new account; prints generated password
    post --item ID --file PATH         # post top-level reply to item ID with body from file
    profile                            # check whether we're logged in and as whom

The persistent profile lives at state/browser/profiles/hackernews/. After a
successful signup HN auto-logs you in; the cookie is reused on subsequent
runs.

Credentials are NOT stored automatically; on signup the script prints
username + password and reminds the operator to put them in
`ops/secret_vault.py`. (Avoids a circular dep on the vault module here.)
"""
from __future__ import annotations

import argparse
import re
import secrets
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "hackernews"
SHOTS_DIR = ROOT / "state" / "browser" / "shots" / "hackernews"
LOG_PATH = ROOT / "ops" / "hn_action_log.md"

LOGIN_URL = "https://news.ycombinator.com/login"
ITEM_URL_TMPL = "https://news.ycombinator.com/item?id={id}"
USER_URL_TMPL = "https://news.ycombinator.com/user?id={username}"
MIN_LINK_KARMA = 5
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
KARMA_RE = re.compile(
    r"karma:\s*</td>\s*<td[^>]*>\s*(?P<karma>\d+)\s*</td>",
    re.IGNORECASE,
)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def get_context(playwright, headless: bool = True):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    )


def shoot(page, label: str) -> str:
    path = SHOTS_DIR / f"{stamp()}_{label}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception as e:
        return f"(screenshot failed: {e})"
    return str(path.relative_to(ROOT))


def append_log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text(
            "# HN action log\n\n"
            "Append-only log of HN browser actions (signup, post, verify).\n\n",
            encoding="utf-8",
        )
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def gen_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "-_."
    return "".join(secrets.choice(alphabet) for _ in range(length))


def body_has_url(body: str) -> bool:
    return bool(URL_RE.search(body))


def extract_karma_from_user_html(html: str) -> int | None:
    match = KARMA_RE.search(html)
    if not match:
        return None
    return int(match.group("karma"))


def low_karma_link_block_reason(body: str, karma: int | None, min_link_karma: int) -> str | None:
    if not body_has_url(body):
        return None
    if karma is None:
        return "body contains a URL and HN karma could not be verified"
    if karma < min_link_karma:
        return f"body contains a URL but HN karma is {karma}; minimum is {min_link_karma}"
    return None


def whoami(page) -> str | None:
    """Return logged-in username if visible, else None."""
    try:
        page.goto("https://news.ycombinator.com/", wait_until="domcontentloaded", timeout=30000)
        # Top-right "user" link contains the username when logged in
        user_link = page.locator("span.pagetop a#me, a#me").first
        if user_link.count() > 0:
            return user_link.text_content().strip() or None
    except Exception:
        return None
    return None


def fetch_karma(page, username: str) -> int | None:
    page.goto(USER_URL_TMPL.format(username=username), wait_until="domcontentloaded", timeout=30000)
    return extract_karma_from_user_html(page.content())


def signup(username: str, password: str | None = None, headless: bool = True) -> int:
    if password is None:
        password = gen_password()
    print(f"[{stamp()}] signup attempt username={username} (password generated, will print on success)", flush=True)
    with sync_playwright() as pw:
        ctx = get_context(pw, headless=headless)
        page = ctx.new_page()
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1)
            # The signup form is the SECOND form on /login. Selector via "create account" submit.
            create_form = page.locator("form").filter(
                has=page.locator("input[type='submit'][value='create account']")
            ).first
            if create_form.count() == 0:
                print("ERROR: could not find create-account form", flush=True)
                shot = shoot(page, "signup_no_form")
                append_log(f"{iso_now()} | signup | username={username} | FAIL no form | shot={shot}")
                return 2
            create_form.locator("input[name='acct']").fill(username)
            create_form.locator("input[name='pw']").fill(password)
            shot_pre = shoot(page, "signup_filled")
            create_form.locator("input[type='submit']").click()
            time.sleep(2)
            # Success: redirected to homepage with `me` link in nav. Failure: error text on /x?...
            current = page.url
            shot_post = shoot(page, "signup_after")
            body_text = page.content()[:1000]
            me = whoami(page)
            if me and me.lower() == username.lower():
                print(f"SUCCESS: logged in as {me}", flush=True)
                print(f"USERNAME: {username}", flush=True)
                print(f"PASSWORD: {password}", flush=True)
                print("Save to vault: python ops/secret_vault.py put platform:hackernews password --value <pw>", flush=True)
                append_log(
                    f"{iso_now()} | signup | username={username} | SUCCESS me={me} | "
                    f"shot_pre={shot_pre} shot_post={shot_post}"
                )
                return 0
            print(f"FAIL: post-signup whoami={me!r} url={current}", flush=True)
            print("First 500 chars of body:", flush=True)
            print(body_text[:500], flush=True)
            append_log(
                f"{iso_now()} | signup | username={username} | FAIL me={me!r} url={current} | "
                f"shot_pre={shot_pre} shot_post={shot_post}"
            )
            return 3
        finally:
            ctx.close()


def login(username: str, password: str, headless: bool = True) -> int:
    print(f"[{stamp()}] login attempt username={username}", flush=True)
    with sync_playwright() as pw:
        ctx = get_context(pw, headless=headless)
        page = ctx.new_page()
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1)
            login_form = page.locator("form").filter(
                has=page.locator("input[type='submit'][value='login']")
            ).first
            if login_form.count() == 0:
                print("ERROR: no login form", flush=True)
                return 2
            login_form.locator("input[name='acct']").fill(username)
            login_form.locator("input[name='pw']").fill(password)
            login_form.locator("input[type='submit']").click()
            time.sleep(2)
            me = whoami(page)
            if me and me.lower() == username.lower():
                print(f"SUCCESS: logged in as {me}", flush=True)
                append_log(f"{iso_now()} | login | username={username} | SUCCESS")
                return 0
            print(f"FAIL: whoami={me!r}", flush=True)
            append_log(f"{iso_now()} | login | username={username} | FAIL me={me!r}")
            return 3
        finally:
            ctx.close()


def profile(headless: bool = True) -> int:
    with sync_playwright() as pw:
        ctx = get_context(pw, headless=headless)
        page = ctx.new_page()
        try:
            me = whoami(page)
            print(f"whoami: {me!r}")
            if me:
                print(f"karma: {fetch_karma(page, me)!r}")
            return 0 if me else 1
        finally:
            ctx.close()


def post_comment(
    item_id: str,
    body: str,
    headless: bool = True,
    dry_run: bool = False,
    allow_low_karma_link: bool = False,
    min_link_karma: int = MIN_LINK_KARMA,
) -> int:
    print(f"[{stamp()}] post_comment item={item_id} dry_run={dry_run} body_len={len(body)}", flush=True)
    if not body.strip():
        print("ERROR: empty body", flush=True)
        return 2
    with sync_playwright() as pw:
        ctx = get_context(pw, headless=headless)
        page = ctx.new_page()
        try:
            url = ITEM_URL_TMPL.format(id=item_id)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1)
            me = whoami(page)
            if not me:
                print("ERROR: not logged in; run signup or login first", flush=True)
                append_log(f"{iso_now()} | post | item={item_id} | FAIL not-logged-in")
                return 3
            if body_has_url(body) and not allow_low_karma_link:
                karma = fetch_karma(page, me)
                reason = low_karma_link_block_reason(body, karma, min_link_karma)
                if reason:
                    print(f"SAFETY BLOCK: {reason}", flush=True)
                    print("Use --allow-low-karma-link only for an explicit, reviewed exception.", flush=True)
                    append_log(
                        f"{iso_now()} | post | item={item_id} | BLOCKED low-karma-link | "
                        f"user={me} karma={karma!r} min={min_link_karma}"
                    )
                    return 6
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1)
            # Top-level reply form is the first <textarea name="text"> on the item page,
            # within a form posting to /comment.
            textarea = page.locator("form[action='comment'] textarea[name='text']").first
            if textarea.count() == 0:
                print("ERROR: no top-level reply textarea found", flush=True)
                shot = shoot(page, "post_no_textarea")
                append_log(f"{iso_now()} | post | item={item_id} | FAIL no-textarea | shot={shot}")
                return 4
            textarea.fill(body)
            shot_pre = shoot(page, f"post_filled_{item_id}")
            if dry_run:
                print("DRY RUN: would submit. Skipping click.", flush=True)
                append_log(f"{iso_now()} | post | item={item_id} | DRY-RUN | shot_pre={shot_pre}")
                return 0
            submit = page.locator("form[action='comment'] input[type='submit']").first
            submit.click()
            time.sleep(2)
            shot_post = shoot(page, f"post_after_{item_id}")
            # After submit HN redirects to /threads?id=USER which lists user comments.
            # Or back to item with comment visible. Check current URL + presence of body needle.
            current_url = page.url
            page_html = page.content()
            needle = body[:60].split("\n")[0]
            success = needle and needle in page_html
            if success:
                print(f"SUCCESS: comment landed; current={current_url}", flush=True)
                append_log(
                    f"{iso_now()} | post | item={item_id} | SUCCESS | url={current_url} | "
                    f"shot_pre={shot_pre} shot_post={shot_post} | needle='{needle[:40]}'"
                )
                return 0
            print(f"UNCERTAIN: needle not found at {current_url}. Check screenshots.", flush=True)
            append_log(
                f"{iso_now()} | post | item={item_id} | UNCERTAIN | url={current_url} | "
                f"shot_pre={shot_pre} shot_post={shot_post}"
            )
            return 5
        finally:
            ctx.close()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("signup")
    sp.add_argument("--username", required=True)
    sp.add_argument("--password", default=None, help="optional; otherwise random 24-char")
    sp.add_argument("--headed", action="store_true")

    lp = sub.add_parser("login")
    lp.add_argument("--username", required=True)
    lp.add_argument("--password", required=True)
    lp.add_argument("--headed", action="store_true")

    pp = sub.add_parser("profile")
    pp.add_argument("--headed", action="store_true")

    pc = sub.add_parser("post")
    pc.add_argument("--item", required=True)
    pc.add_argument("--file", required=True, help="path to plain-text body file")
    pc.add_argument("--dry-run", action="store_true")
    pc.add_argument("--headed", action="store_true")
    pc.add_argument(
        "--allow-low-karma-link",
        action="store_true",
        help="explicitly override the safety block for URL-bearing comments from low-karma accounts",
    )
    pc.add_argument(
        "--min-link-karma",
        type=int,
        default=MIN_LINK_KARMA,
        help=f"minimum HN karma required before posting a comment containing a URL (default: {MIN_LINK_KARMA})",
    )

    args = p.parse_args()
    headless = not getattr(args, "headed", False)

    if args.cmd == "signup":
        return signup(args.username, args.password, headless=headless)
    if args.cmd == "login":
        return login(args.username, args.password, headless=headless)
    if args.cmd == "profile":
        return profile(headless=headless)
    if args.cmd == "post":
        body = Path(args.file).read_text(encoding="utf-8")
        return post_comment(
            args.item,
            body,
            headless=headless,
            dry_run=args.dry_run,
            allow_low_karma_link=args.allow_low_karma_link,
            min_link_karma=args.min_link_karma,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
