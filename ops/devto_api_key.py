#!/usr/bin/env python3
"""Extract or generate a dev.to API key via persistent browser session.

Uses the same persistent profile as Farcaster/Gumroad. The session must already
be logged in via the codex-shipped Proton magic-code flow (verified 2026-05-01).

Usage:
    python ops/devto_api_key.py extract                # try to read existing key
    python ops/devto_api_key.py generate --name "agent" # generate a new key
    python ops/devto_api_key.py probe                  # screenshot only

Stores the key in vault as platform:devto.api_key.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "dutchaiagency"
SHOTS_DIR = ROOT / "state" / "browser" / "shots" / "devto"
SETTINGS_URL = "https://dev.to/settings/extensions"
API_KEY_RE = re.compile(r"\b[a-zA-Z0-9]{40,80}\b")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ctx(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=True,
        viewport={"width": 1440, "height": 1200},
    )


def _shot(page, label: str) -> Path:
    p = SHOTS_DIR / f"{_ts()}_{label}.png"
    page.screenshot(path=str(p), full_page=True)
    return p


def _store_key(key: str) -> None:
    import subprocess

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "ops" / "secret_vault.py"),
            "put",
            "platform:devto",
            "api_key",
            key,
        ],
        check=True,
    )


def cmd_probe(args: argparse.Namespace) -> int:
    with sync_playwright() as p:
        ctx = _ctx(p)
        try:
            page = ctx.new_page()
            page.goto(SETTINGS_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            shot = _shot(page, "probe_settings")
            print(f"url={page.url}")
            print(f"title={page.title()}")
            print(f"screenshot={shot}")
            text = page.inner_text("body")[:4000]
            print("--- body excerpt ---")
            print(text)
            return 0
        finally:
            ctx.close()


def _try_extract(page) -> str | None:
    # Pattern 1: existing keys table
    selectors = [
        'input[name="api_secret[secret]"]',
        'input[type="text"][readonly]',
        'code',
        'pre',
    ]
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
        except Exception:
            els = []
        for el in els:
            try:
                val = el.get_attribute("value") or el.inner_text()
            except Exception:
                continue
            if val:
                m = API_KEY_RE.search(val.strip())
                if m:
                    return m.group(0)
    return None


def cmd_extract(args: argparse.Namespace) -> int:
    with sync_playwright() as p:
        ctx = _ctx(p)
        try:
            page = ctx.new_page()
            page.goto(SETTINGS_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            _shot(page, "extract_initial")
            key = _try_extract(page)
            if key:
                print(f"FOUND key length={len(key)} prefix={key[:6]}...")
                if not args.dry_run:
                    _store_key(key)
                    print("stored at platform:devto.api_key")
                return 0
            print("NO existing key found in DOM; use 'generate' subcommand")
            return 2
        finally:
            ctx.close()


def cmd_generate(args: argparse.Namespace) -> int:
    desc = args.name
    with sync_playwright() as p:
        ctx = _ctx(p)
        try:
            page = ctx.new_page()
            page.goto(SETTINGS_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            _shot(page, "gen_initial")
            # Try existing first
            existing = _try_extract(page)
            if existing:
                print(f"existing key found, reusing length={len(existing)}")
                if not args.dry_run:
                    _store_key(existing)
                return 0
            # Find description input
            input_selectors = [
                'input[name="api_secret[description]"]',
                'input#api_secret_description',
                'input[placeholder*="description" i]',
                'input[placeholder*="name" i]',
            ]
            filled = False
            for sel in input_selectors:
                el = page.query_selector(sel)
                if el:
                    el.fill(desc)
                    filled = True
                    print(f"filled description via {sel}")
                    break
            if not filled:
                _shot(page, "gen_no_input")
                print("could not find description input", file=sys.stderr)
                return 3
            # Find submit button
            btn_selectors = [
                'button:has-text("Generate API Key")',
                'button:has-text("Generate")',
                'input[type="submit"][value*="Generate" i]',
                'form button[type="submit"]',
            ]
            clicked = False
            for sel in btn_selectors:
                el = page.query_selector(sel)
                if el:
                    el.click()
                    clicked = True
                    print(f"clicked via {sel}")
                    break
            if not clicked:
                _shot(page, "gen_no_button")
                print("could not find generate button", file=sys.stderr)
                return 4
            # Wait for response
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
            _shot(page, "gen_after_submit")
            key = _try_extract(page)
            if key:
                print(f"GENERATED key length={len(key)} prefix={key[:6]}...")
                if not args.dry_run:
                    _store_key(key)
                    print("stored at platform:devto.api_key")
                return 0
            print("submit completed but no key extracted; inspect screenshot")
            return 5
        finally:
            ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_probe = sub.add_parser("probe", help="screenshot settings page only")
    p_probe.set_defaults(func=cmd_probe)
    p_extract = sub.add_parser("extract", help="extract existing API key")
    p_extract.add_argument("--dry-run", action="store_true")
    p_extract.set_defaults(func=cmd_extract)
    p_gen = sub.add_parser("generate", help="generate a new API key")
    p_gen.add_argument("--name", default="agent-bridge", help="key description")
    p_gen.add_argument("--dry-run", action="store_true")
    p_gen.set_defaults(func=cmd_generate)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
