#!/usr/bin/env python3
"""
Gumroad login attempt via Playwright (persistent profile).

Account: dutchaiagents@proton.me, password from vault
(gumroad:dutchaiagency.password). Account created by Leon manually
2026-05-01 (passed signup CAPTCHA there).

Goals:
  - Navigate to https://gumroad.com/login, fill creds, submit.
  - Detect post-submit blocker (CAPTCHA, 2FA, email confirmation, etc.).
  - On success: dump current URL + screenshot of creator dashboard.

Usage:
    python ops/gumroad_login.py login                 # headless attempt
    python ops/gumroad_login.py login --visible       # show browser
    python ops/gumroad_login.py login --visible --manual-pause 180
    python ops/gumroad_login.py status                # check session via /dashboard
    python ops/gumroad_login.py publish               # dry-run product payload
    python ops/gumroad_login.py publish --live        # open Gumroad; no submit
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "gumroad"
SHOTS_DIR = ROOT / "state" / "browser" / "shots" / "gumroad"
LOGIN_URL = "https://gumroad.com/login"
DASHBOARD_URL = "https://gumroad.com/dashboard"
NEW_PRODUCT_URL = "https://gumroad.com/products/new"
DEFAULT_LISTING = ROOT / "products" / "agent-playbook" / "listing.md"
DEFAULT_ASSET = ROOT / "products" / "agent-playbook" / "playbook.pdf"
PUBLIC_CUTOFF = "<!-- ============================================================"
MAX_GUMROAD_TITLE_CHARS = 80
MAX_ASSET_BYTES = 2 * 1024 * 1024


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def require_sync_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "playwright is required for browser actions; install it before "
            "running login/status/live publish"
        ) from exc
    return sync_playwright


def vault_get(name: str, field: str) -> str:
    out = subprocess.run(
        [sys.executable, "ops/secret_vault.py", "get", name, field],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip().lstrip("\ufeff")


def load_email() -> str:
    try:
        email = vault_get("gumroad:dutchaiagency", "email")
        if email:
            return email
    except subprocess.CalledProcessError:
        pass

    fallback = ROOT / ".secrets" / "email.txt"
    if not fallback.exists():
        raise SystemExit("missing gumroad:dutchaiagency.email in vault")
    txt = fallback.read_text(encoding="utf-8-sig").splitlines()
    if not txt:
        raise SystemExit("missing gumroad:dutchaiagency.email in vault")
    return txt[0].strip().lstrip("\ufeff")


def load_password() -> str:
    return vault_get("gumroad:dutchaiagency", "password")


def get_context(playwright, headless: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    )


def shoot(page, label: str) -> str:
    path = SHOTS_DIR / f"{stamp()}_{label}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path.relative_to(ROOT))
    except Exception as e:
        return f"(screenshot failed: {e})"


def login_flow(headless: bool, manual_pause: int) -> dict:
    email = load_email()
    pw = load_password()
    log: list[str] = []

    def lg(msg: str):
        line = f"[{stamp()}] {msg}"
        print(line, flush=True)
        log.append(line)

    lg(f"login attempt email={email} headless={headless}")

    sync_playwright = require_sync_playwright()
    with sync_playwright() as p:
        ctx = get_context(p, headless=headless)
        page = ctx.new_page()
        try:
            lg(f"goto {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)
            lg(f"loaded url={page.url} title={page.title()!r}")
            lg(f"shot {shoot(page, 'login_01_loaded')}")

            html = page.content().lower()
            for needle in ("just a moment", "checking your browser",
                           "cf-browser-verification", "press and hold"):
                if needle in html:
                    lg(f"BOT-WALL detected: {needle!r}")
                    lg(f"shot {shoot(page, 'login_01b_blocker')}")
                    return {"stage": "bot_wall", "blocker": needle,
                            "url": page.url, "log": log}

            # If already logged in, /login often redirects to dashboard.
            if "dashboard" in page.url or "products" in page.url:
                lg("already-logged-in: redirected away from /login")
                lg(f"shot {shoot(page, 'login_already')}")
                return {"stage": "already_logged_in", "url": page.url, "log": log}

            # Email field
            email_filled = False
            for sel in ('input[type="email"]', 'input[name="user[email]"]',
                        'input[name="email"]', 'input[placeholder*="email" i]'):
                try:
                    el = page.locator(sel).first
                    if el.count() and el.is_visible(timeout=2000):
                        el.fill(email)
                        lg(f"email filled via {sel}")
                        email_filled = True
                        break
                except Exception as e:
                    lg(f"email selector {sel}: {e}")
            if not email_filled:
                lg(f"shot {shoot(page, 'login_02_no_email')}")
                return {"stage": "no_email_field", "url": page.url, "log": log}

            # Password field
            pw_filled = False
            for sel in ('input[type="password"]', 'input[name="user[password]"]',
                        'input[name="password"]'):
                try:
                    el = page.locator(sel).first
                    if el.count() and el.is_visible(timeout=2000):
                        el.fill(pw)
                        lg(f"password filled via {sel}")
                        pw_filled = True
                        break
                except Exception as e:
                    lg(f"pw selector {sel}: {e}")
            if not pw_filled:
                lg(f"shot {shoot(page, 'login_03_no_pw')}")
                return {"stage": "no_password_field", "url": page.url, "log": log}

            lg(f"shot {shoot(page, 'login_04_filled')}")

            submitted = False
            for sel in ('button[type="submit"]', 'button:has-text("Login")',
                        'button:has-text("Log in")', 'input[type="submit"]'):
                try:
                    el = page.locator(sel).first
                    if el.count() and el.is_visible(timeout=2000):
                        el.click()
                        lg(f"submit clicked via {sel}")
                        submitted = True
                        break
                except Exception as e:
                    lg(f"submit selector {sel}: {e}")
            if not submitted:
                lg(f"shot {shoot(page, 'login_05_no_submit')}")
                return {"stage": "no_submit_button", "url": page.url, "log": log}

            time.sleep(5)
            lg(f"after-submit url={page.url} title={page.title()!r}")
            lg(f"shot {shoot(page, 'login_06_after_submit')}")

            if manual_pause > 0:
                lg(f"manual_pause: holding {manual_pause}s")
                ticks = manual_pause // 10
                for i in range(ticks):
                    time.sleep(10)
                    lg(f"  pause {i+1}/{ticks} url={page.url}")
                lg(f"shot {shoot(page, 'login_07_post_pause')}")

            after_html = page.content().lower()
            blockers = {
                "captcha": ("captcha", "are you a robot", "press and hold",
                            "verify you are human", "select all images"),
                "two_factor": ("two-factor", "2fa", "authenticator code",
                               "enter the code"),
                "email_confirmation": ("check your email", "confirmation email",
                                       "verify your email"),
                "wrong_password": ("invalid email", "incorrect password",
                                   "wrong password"),
                "rate_limited": ("too many", "rate limit"),
            }
            hits = []
            for tag, needles in blockers.items():
                for n in needles:
                    if n in after_html:
                        hits.append((tag, n))
                        break

            success = ("dashboard" in page.url
                       or "products" in page.url
                       or "/discover" in page.url
                       or page.url.rstrip("/") == "https://gumroad.com")

            return {
                "stage": "submitted",
                "url": page.url,
                "title": page.title(),
                "logged_in": success and not hits,
                "blockers": hits,
                "log": log,
            }
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def status_check(headless: bool) -> dict:
    log: list[str] = []

    def lg(msg: str):
        line = f"[{stamp()}] {msg}"
        print(line, flush=True)
        log.append(line)

    sync_playwright = require_sync_playwright()
    with sync_playwright() as p:
        ctx = get_context(p, headless=headless)
        page = ctx.new_page()
        try:
            lg(f"goto {DASHBOARD_URL}")
            page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)
            lg(f"url={page.url} title={page.title()!r}")
            lg(f"shot {shoot(page, 'status_dashboard')}")
            on_login = "/login" in page.url or "log in" in page.title().lower()
            return {
                "stage": "status",
                "url": page.url,
                "title": page.title(),
                "logged_in": not on_login,
                "log": log,
            }
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def public_listing_markdown(path: Path = DEFAULT_LISTING) -> str:
    markdown = path.read_text(encoding="utf-8")
    public = markdown.split(PUBLIC_CUTOFF, 1)[0]
    return public.strip()


def section_key(heading: str) -> str:
    heading = heading.lower()
    heading = re.sub(r"\s*\([^)]*\)", "", heading)
    heading = heading.replace("/", " ")
    heading = re.sub(r"[^a-z0-9]+", "_", heading)
    return heading.strip("_")


def extract_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            current = section_key(line[3:].strip())
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def parse_price_cents(price_text: str) -> int:
    match = re.search(r"\$([0-9]+(?:\.[0-9]{1,2})?)\s*USD", price_text, re.I)
    if not match:
        raise ValueError("price section must contain a USD price like '$9 USD'")
    return int(round(float(match.group(1)) * 100))


def parse_tags(tags_text: str) -> list[str]:
    tags = re.findall(r"`([^`]+)`", tags_text)
    return [tag.strip() for tag in tags if tag.strip()]


def build_product_payload(
    listing_path: Path = DEFAULT_LISTING,
    asset_path: Path = DEFAULT_ASSET,
) -> dict:
    public_markdown = public_listing_markdown(listing_path)
    sections = extract_sections(public_markdown)

    title = sections.get("listing_title", "").strip()
    subtitle = sections.get("subtitle_one_liner", "").strip()
    description = sections.get("long_description", "").strip()
    price_text = sections.get("price", "").strip()
    tags_text = sections.get("tags", "").strip()

    errors: list[str] = []
    if not title:
        errors.append("missing listing title")
    if len(title) > MAX_GUMROAD_TITLE_CHARS:
        errors.append(
            f"title is {len(title)} chars; Gumroad title limit is "
            f"{MAX_GUMROAD_TITLE_CHARS}"
        )
    if not subtitle:
        errors.append("missing subtitle")
    if not description:
        errors.append("missing long description")
    if "INTERNAL ONLY" in description or "Distribution checklist" in description:
        errors.append("long description includes internal-only content")

    if not asset_path.exists():
        errors.append(f"missing PDF asset: {asset_path}")
        asset_bytes = 0
    else:
        asset_bytes = asset_path.stat().st_size
        if asset_bytes <= 0:
            errors.append("PDF asset is empty")
        if asset_bytes > MAX_ASSET_BYTES:
            errors.append(
                f"PDF asset is {asset_bytes} bytes; target max is "
                f"{MAX_ASSET_BYTES}"
            )

    try:
        price_cents = parse_price_cents(price_text)
    except ValueError as exc:
        errors.append(str(exc))
        price_cents = 0

    tags = parse_tags(tags_text)
    if not tags:
        errors.append("missing tags")

    return {
        "title": title,
        "title_chars": len(title),
        "subtitle": subtitle,
        "description_markdown": description,
        "price_cents": price_cents,
        "price_usd": price_cents / 100,
        "format": sections.get("format", "").strip(),
        "refund_policy": sections.get("refund_policy", "").strip(),
        "tags": tags,
        "asset_path": str(asset_path.relative_to(ROOT)),
        "asset_bytes": asset_bytes,
        "listing_path": str(listing_path.relative_to(ROOT)),
        "errors": errors,
    }


def payload_summary(payload: dict) -> str:
    status = "ready" if not payload["errors"] else "blocked"
    lines = [
        f"stage: dry_run_{status}",
        f"title: {payload['title']} ({payload['title_chars']} chars)",
        f"price: ${payload['price_usd']:.2f} USD",
        f"asset: {payload['asset_path']} ({payload['asset_bytes']} bytes)",
        f"tags: {', '.join(payload['tags'])}",
        "",
        "subtitle:",
        payload["subtitle"],
        "",
        "description:",
        payload["description_markdown"],
    ]
    if payload["errors"]:
        lines.extend(["", "errors:", *[f"- {error}" for error in payload["errors"]]])
    return "\n".join(lines)


def publish_flow(
    *,
    listing_path: Path,
    asset_path: Path,
    headless: bool,
    live: bool,
) -> dict:
    payload = build_product_payload(listing_path, asset_path)
    if payload["errors"]:
        return {"stage": "dry_run_blocked", "payload": payload}
    if not live:
        return {"stage": "dry_run_ready", "payload": payload}

    log: list[str] = []

    def lg(msg: str):
        line = f"[{stamp()}] {msg}"
        print(line, flush=True)
        log.append(line)

    sync_playwright = require_sync_playwright()
    with sync_playwright() as p:
        ctx = get_context(p, headless=headless)
        page = ctx.new_page()
        try:
            lg("live publish preflight: opening Gumroad product page; no submit")
            page.goto(NEW_PRODUCT_URL, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)
            lg(f"url={page.url} title={page.title()!r}")
            lg(f"shot {shoot(page, 'publish_new_product_probe')}")
            on_login = "/login" in page.url or "log in" in page.title().lower()
            return {
                "stage": (
                    "not_logged_in" if on_login else "live_probe_ready_manual_fill"
                ),
                "url": page.url,
                "title": page.title(),
                "payload": payload,
                "log": log,
            }
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_login = sub.add_parser("login")
    p_login.add_argument("--visible", action="store_true")
    p_login.add_argument("--manual-pause", type=int, default=0)
    p_status = sub.add_parser("status")
    p_status.add_argument("--visible", action="store_true")
    p_publish = sub.add_parser("publish")
    p_publish.add_argument("--listing", type=Path, default=DEFAULT_LISTING)
    p_publish.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    p_publish.add_argument(
        "--live",
        action="store_true",
        help="Open Gumroad product page with the prepared payload; does not submit",
    )
    p_publish.add_argument("--visible", action="store_true")
    p_publish.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "login":
        result = login_flow(headless=not args.visible,
                            manual_pause=args.manual_pause)
    elif args.cmd == "status":
        result = status_check(headless=not args.visible)
    else:
        result = publish_flow(
            listing_path=args.listing,
            asset_path=args.asset,
            headless=not args.visible,
            live=args.live,
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(payload_summary(result["payload"]))
            print(f"\nresult: {result['stage']}")
        raise SystemExit(1 if result["payload"]["errors"] else 0)

    print("\n=== RESULT ===")
    for k, v in result.items():
        if k == "log":
            continue
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
