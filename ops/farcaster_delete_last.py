#!/usr/bin/env python3
"""Dry-run-first Farcaster cast deletion via the logged-in browser profile.

The default mode only finds the target cast, opens its overflow menu, and writes
a screenshot. Use --execute only after the dry-run identifies exactly one cast
and exactly one "Delete cast" menu item.

Usage:
    python ops/farcaster_delete_last.py --target-text "\\00 wallet"
    python ops/farcaster_delete_last.py --target-text "\\00 wallet" --execute
"""
import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "dutchaiagency"
BASE_URL = "https://farcaster.xyz"
DEFAULT_HANDLE = "dutchaiagents"
DEFAULT_TARGET_TEXT = "\\00 wallet"
SCREENSHOT_DRY_RUN = ROOT / "state" / "farcaster-delete-dry-run.png"
SCREENSHOT_FAILED = ROOT / "state" / "farcaster-delete-failed.png"


def validate_target_text(target_text: str) -> str:
    target_text = target_text.strip()
    if len(target_text) < 6:
        raise ValueError("--target-text must be at least 6 characters.")
    return target_text


def profile_url(handle: str) -> str:
    handle = handle.strip().lstrip("@")
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,32}", handle):
        raise ValueError(f"Invalid Farcaster handle: {handle!r}")
    return f"{BASE_URL}/{handle}"


def summarize_text(text: str, max_len: int = 240) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3]}..."


def get_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=True,
        viewport={"width": 1440, "height": 900},
    )


def find_target_cast(page: Page, target_text: str) -> Locator:
    casts = page.locator("div[id^='cast:']").filter(has_text=target_text)
    count = casts.count()
    if count != 1:
        raise RuntimeError(f"Expected exactly one matching cast, found {count}.")
    return casts.first


def open_cast_menu(cast: Locator) -> None:
    menu_buttons = cast.locator("button[aria-haspopup='menu']")
    count = menu_buttons.count()
    if count != 1:
        raise RuntimeError(f"Expected exactly one overflow menu button in target cast, found {count}.")
    menu_buttons.first.click()
    time.sleep(1)


def find_delete_menu_item(page: Page) -> Locator:
    delete_items = page.get_by_role("menuitem", name=re.compile(r"^Delete cast$"))
    count = delete_items.count()
    if count != 1:
        raise RuntimeError(f"Expected exactly one 'Delete cast' menu item, found {count}.")
    return delete_items.first


def find_confirm_delete_button(page: Page) -> Locator:
    dialogs = page.get_by_role("dialog")
    if dialogs.count() < 1:
        raise RuntimeError("Delete confirmation dialog did not appear.")
    dialog = dialogs.last
    buttons = dialog.get_by_role("button", name=re.compile(r"^Delete$"))
    count = buttons.count()
    if count != 1:
        raise RuntimeError(f"Expected exactly one confirm Delete button, found {count}.")
    return buttons.first


def click_confirm_if_needed(page: Page, target_text: str) -> str:
    if page.locator("div[id^='cast:']").filter(has_text=target_text).count() == 0:
        return "not_required"

    confirm_button = find_confirm_delete_button(page)
    confirm_button.click()
    time.sleep(3)
    return "clicked"


def delete_cast(handle: str, target_text: str, execute: bool) -> int:
    with sync_playwright() as p:
        ctx = get_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(profile_url(handle), wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        try:
            cast = find_target_cast(page, target_text)
            cast_id = cast.get_attribute("id") or "<missing-id>"
            summary = summarize_text(cast.inner_text(timeout=2000))
            print(f"target_cast_id={cast_id}")
            print(f"target_summary={summary}")

            open_cast_menu(cast)
            delete_item = find_delete_menu_item(page)
            print("delete_menu_item=found")
            page.screenshot(path=str(SCREENSHOT_DRY_RUN), full_page=False)

            if not execute:
                print(f"dry_run=true screenshot={SCREENSHOT_DRY_RUN}")
                return 0

            delete_item.click()
            time.sleep(1)
            confirm_result = click_confirm_if_needed(page, target_text)
            print(f"delete_confirm={confirm_result}")

            page.goto(profile_url(handle), wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            remaining = page.locator("div[id^='cast:']").filter(has_text=target_text).count()
            if remaining != 0:
                raise RuntimeError(f"Delete was attempted but target still appears {remaining} time(s).")

            print("delete_executed=true")
            return 0
        except Exception:
            page.screenshot(path=str(SCREENSHOT_FAILED), full_page=False)
            print(f"failure_screenshot={SCREENSHOT_FAILED}", file=sys.stderr)
            raise
        finally:
            ctx.storage_state(path=str(PROFILE_DIR / "storage-state.json"))
            ctx.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete a specific Farcaster cast after dry-run validation.")
    parser.add_argument("--handle", default=DEFAULT_HANDLE, help="Farcaster handle, without @.")
    parser.add_argument("--target-text", default=DEFAULT_TARGET_TEXT, help="Unique text snippet in the cast to delete.")
    parser.add_argument("--execute", action="store_true", help="Actually delete the matched cast.")
    args = parser.parse_args()

    try:
        target_text = validate_target_text(args.target_text)
        return delete_cast(args.handle, target_text, args.execute)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
