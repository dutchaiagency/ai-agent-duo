#!/usr/bin/env python3
"""
Farcaster posting via Playwright browser automation.
Uses persistent browser profile with saved login session.

Usage:
    python ops/farcaster_browser.py cast "Hello world!"
    python ops/farcaster_browser.py cast "Reply text" --channel farcaster
    python ops/farcaster_browser.py profile              # check profile
    python ops/farcaster_browser.py set-bio "Bio text"
"""
import argparse
from datetime import datetime, timezone
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "state" / "browser" / "profiles" / "dutchaiagency"
BASE_URL = "https://farcaster.xyz"
MAX_CAST_CHARS = 320
CADENCE_SECONDS = 30 * 60
LOCK_STALE_SECONDS = 10 * 60
LOCK_WAIT_SECONDS = 120
CAST_LOG = ROOT / "ops" / "farcaster_cast_log.md"
CAST_LOCK = ROOT / "state" / "farcaster_cast.lock"
SUSPICIOUS_ESCAPE_MARKERS = (
    "\\00",
    "\\0",
    "\\/",
)


def get_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=True,
        viewport={"width": 1440, "height": 900},
    )


def read_cast_text(text=None, from_file=None):
    if text and from_file:
        raise ValueError("Use either cast text or --from-file, not both.")
    if from_file:
        return Path(from_file).read_text(encoding="utf-8").strip()
    if text is None:
        raise ValueError("Cast text is required unless --from-file is used.")
    return text


def validate_cast_text(text):
    if not text.strip():
        return "Cast text is empty."
    for marker in SUSPICIOUS_ESCAPE_MARKERS:
        if marker in text:
            return f"Suspicious escape marker found in cast text: {marker}"
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return "Cast text contains non-ASCII characters; use plain ASCII for predictable browser input."
    return None


def prepare_cast_text(text, max_chars=MAX_CAST_CHARS):
    error = validate_cast_text(text)
    if error:
        raise ValueError(error)
    if len(text) > max_chars:
        print(f"WARNING: Text exceeds {max_chars} chars, will be truncated", file=sys.stderr)
        return text[:max_chars]
    return text


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_log_time(line):
    timestamp = line.split("|", 1)[0].strip()
    try:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def successful_cast_times(log_path=CAST_LOG):
    path = Path(log_path)
    if not path.exists():
        return []

    times = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if " | success " not in f"{line} " and " | success |" not in line:
            continue
        parsed = _parse_log_time(line)
        if parsed:
            times.append(parsed)
    return times


def last_successful_cast(log_path=CAST_LOG):
    times = successful_cast_times(log_path)
    return max(times) if times else None


def cadence_block_reason(log_path=CAST_LOG, now=None, cooldown_seconds=CADENCE_SECONDS):
    now = now or _utc_now()
    last_cast = last_successful_cast(log_path)
    if not last_cast:
        return None

    elapsed = (now - last_cast).total_seconds()
    if elapsed >= cooldown_seconds:
        return None

    wait_seconds = int(cooldown_seconds - elapsed)
    wait_minutes = max(1, (wait_seconds + 59) // 60)
    return (
        f"Farcaster cadence block: last successful cast was "
        f"{last_cast.strftime('%Y-%m-%dT%H:%MZ')}; wait ~{wait_minutes}m "
        "or use --force-cadence only after explicit team/Leon agreement."
    )


class CastLock:
    def __init__(
        self,
        path=CAST_LOCK,
        wait_seconds=LOCK_WAIT_SECONDS,
        stale_seconds=LOCK_STALE_SECONDS,
    ):
        self.path = Path(path)
        self.wait_seconds = wait_seconds
        self.stale_seconds = stale_seconds
        self.acquired = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._is_stale():
                    try:
                        self.path.unlink()
                        continue
                    except FileNotFoundError:
                        continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for Farcaster cast lock: {self.path}")
                time.sleep(0.5)
                continue

            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"pid={os.getpid()} started={_utc_now().isoformat()}\n")
            self.acquired = True
            return self

    def __exit__(self, exc_type, exc, tb):
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self.acquired = False

    def _is_stale(self):
        try:
            age = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return False
        return age > self.stale_seconds


def summarize_cast_text(text, max_chars=120):
    summary = " ".join(text.split())
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3] + "..."


def append_cast_log(agent, description, text, reason="", log_path=CAST_LOG):
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_now().strftime("%Y-%m-%dT%H:%MZ")
    safe_agent = (agent or "unknown").strip() or "unknown"
    safe_description = (description or summarize_cast_text(text)).strip()
    safe_reason = (reason or "ops/farcaster_browser.py auto-log").strip()
    line = (
        f"{timestamp} | {safe_agent} | {safe_description} "
        f"({len(text)} chars) | success | reason: {safe_reason}\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def post_cast(text, channel=None):
    with sync_playwright() as p:
        ctx = get_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        url = BASE_URL
        if channel:
            url = f"{BASE_URL}/~/channel/{channel}"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        # Open compose with 'n' key
        page.keyboard.press("n")
        time.sleep(2)

        editor = page.query_selector("[contenteditable=true]")
        if not editor:
            print("ERROR: No compose editor found. Session may be expired.", file=sys.stderr)
            ctx.close()
            return False

        editor.click()
        time.sleep(0.5)
        page.keyboard.type(text, delay=10)
        time.sleep(1)

        # Submit with Ctrl+Enter
        page.keyboard.press("Control+Enter")
        time.sleep(3)

        # Verify compose closed
        editor2 = page.query_selector("[contenteditable=true]")
        if editor2 and editor2.inner_text().strip() == text:
            print("WARNING: Cast may not have been submitted", file=sys.stderr)
            ctx.close()
            return False

        print(f"Cast posted: {text[:80]}...")
        ctx.storage_state(path=str(PROFILE_DIR / "storage-state.json"))
        ctx.close()
        return True


def check_profile():
    with sync_playwright() as p:
        ctx = get_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{BASE_URL}/dutchaiagents", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        text = page.inner_text("body")[:2000]
        print(text)
        ctx.close()


def set_bio(bio_text):
    with sync_playwright() as p:
        ctx = get_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{BASE_URL}/~/settings", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        # Navigate to profile editing
        page.goto(f"{BASE_URL}/~/edit-profile", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        text = page.inner_text("body")[:1000]
        print(f"Edit profile page: {text[:300]}")

        # Find bio textarea
        textareas = page.query_selector_all("textarea")
        for ta in textareas:
            ph = ta.get_attribute("placeholder") or ""
            if "bio" in ph.lower() or not ph:
                ta.fill(bio_text)
                time.sleep(1)
                print(f"Bio set to: {bio_text}")
                break

        # Save
        save_btn = page.get_by_text("Save", exact=True)
        if save_btn.count() > 0:
            save_btn.first.click(force=True)
            time.sleep(3)
            print("Profile saved")

        ctx.close()


def main():
    parser = argparse.ArgumentParser(description="Farcaster browser automation")
    sub = parser.add_subparsers(dest="command")

    cast_p = sub.add_parser("cast", help="Post a cast")
    cast_p.add_argument("text", nargs="?", help="Cast text (max 320 chars)")
    cast_p.add_argument("--from-file", help="Read cast text from a UTF-8 file")
    cast_p.add_argument("--channel", help="Channel to post in")
    cast_p.add_argument("--agent", default=os.environ.get("AGENT_NAME", "unknown"), help="Agent name for the cast log")
    cast_p.add_argument("--description", help="Short cast-log description")
    cast_p.add_argument("--reason", default="", help="Reason to write to the cast log")
    cast_p.add_argument(
        "--force-cadence",
        action="store_true",
        help="Bypass the 30-minute cooldown only after explicit team/Leon agreement",
    )

    sub.add_parser("profile", help="Check profile")

    bio_p = sub.add_parser("set-bio", help="Set profile bio")
    bio_p.add_argument("bio", help="Bio text")

    args = parser.parse_args()

    if args.command == "cast":
        try:
            text = prepare_cast_text(read_cast_text(args.text, args.from_file))
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(2)
        try:
            with CastLock():
                if not args.force_cadence:
                    block_reason = cadence_block_reason()
                    if block_reason:
                        print(f"ERROR: {block_reason}", file=sys.stderr)
                        sys.exit(3)
                success = post_cast(text, args.channel)
                if success:
                    append_cast_log(args.agent, args.description, text, args.reason)
                else:
                    sys.exit(1)
        except TimeoutError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(4)
    elif args.command == "profile":
        check_profile()
    elif args.command == "set-bio":
        set_bio(args.bio)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
