#!/usr/bin/env python3
"""Scan upcoming-calls schedule and nudge Leon on Telegram before each call.

Reads `ops/upcoming_calls.md` (committed schedule) and emits T-30 and T-5
nudges for any `pending` / `confirmed` call with `start_utc` in the near future.
Idempotent via `state/.calendar_nudge_state.json` (gitignored): each
(call_key, offset) combination fires at most once.

Default mode is dry-run (prints what nudges would fire). `--send` actually
relays to Leon's Telegram via `ops/telegram_daia.py send`.

Created 2026-05-06 after the 2026-05-05T14:00Z Wetware call was missed because
no nudge was wired between Proton RSVP and Leon's Telegram. See
`ops/improvements.md` for the post-mortem.

Recommended runtime hookups:

  # Every 5 min via Windows Task Scheduler / cron
  python tools/calendar_nudge.py --send

  # Or piggy-backed on the existing telegram_bridge.py poll loop
  # (insert one call per cycle inside the bridge daemon).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEDULE = REPO_ROOT / "ops" / "upcoming_calls.md"
DEFAULT_STATE = REPO_ROOT / "state" / ".calendar_nudge_state.json"
TELEGRAM_DAIA = REPO_ROOT / "ops" / "telegram_daia.py"

# Two nudge offsets. (offset_minutes_before_start, window_minutes, label)
# A nudge fires when `minutes_to_start` is inside
# [offset - window/2, offset + window/2].
NUDGE_OFFSETS = [
    (30, 10, "T-30"),  # fires when call is 25-35 min out
    (5, 7, "T-5"),     # fires when call is 1.5-8.5 min out
]
ACTIVE_STATUSES = {"pending", "confirmed"}
ROW_COLUMNS = ("start_utc", "duration_min", "counterparty", "url", "status")


@dataclass(frozen=True)
class Call:
    start_utc: datetime
    duration_min: int
    counterparty: str
    url: str
    status: str
    raw: str  # original markdown row, for debugging

    @property
    def key(self) -> str:
        return f"{self.start_utc.isoformat()}|{self.counterparty}"


def parse_schedule(path: Path) -> list[Call]:
    """Read the schedule markdown and return parsed calls.

    Tolerant: skips header rows, separator rows, and malformed rows. Logs
    malformed rows to stderr but does not raise.
    """
    if not path.exists():
        raise FileNotFoundError(f"schedule file not found: {path}")

    calls: list[Call] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(ROW_COLUMNS):
            continue
        # Skip header row.
        if cells[0] == "start_utc":
            in_table = True
            continue
        # Skip separator row (|---|---|...).
        if all(set(c) <= set("-:") and c for c in cells):
            continue
        if not in_table:
            continue
        try:
            start = datetime.strptime(cells[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            duration = int(cells[1])
        except (ValueError, IndexError):
            print(f"warn: skipping malformed row: {line}", file=sys.stderr)
            continue
        calls.append(
            Call(
                start_utc=start,
                duration_min=duration,
                counterparty=cells[2],
                url=cells[3],
                status=cells[4].lower(),
                raw=line,
            )
        )
    return calls


def load_nudge_state(path: Path) -> dict:
    if not path.exists():
        return {"sent": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(f"warn: nudge-state unreadable, starting fresh: {path}", file=sys.stderr)
        return {"sent": []}


def save_nudge_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def already_sent(state: dict, call: Call, label: str) -> bool:
    needle = f"{call.key}|{label}"
    return needle in state.get("sent", [])


def mark_sent(state: dict, call: Call, label: str, now: datetime) -> None:
    state.setdefault("sent", []).append(f"{call.key}|{label}")
    state.setdefault("history", []).append(
        {
            "call_key": call.key,
            "label": label,
            "fired_at": now.isoformat(),
            "counterparty": call.counterparty,
            "url": call.url,
        }
    )


def due_nudges(call: Call, now: datetime) -> list[str]:
    """Return labels of nudge offsets currently within window for this call."""
    if call.status not in ACTIVE_STATUSES:
        return []
    minutes_to_start = (call.start_utc - now).total_seconds() / 60.0
    due: list[str] = []
    for offset_min, window_min, label in NUDGE_OFFSETS:
        lo = offset_min - window_min / 2
        hi = offset_min + window_min / 2
        if lo <= minutes_to_start <= hi:
            due.append(label)
    return due


def build_nudge_text(call: Call, label: str, now: datetime) -> str:
    minutes_to_start = (call.start_utc - now).total_seconds() / 60.0
    return (
        f"⏰ {label} reminder: call with {call.counterparty}\n"
        f"Starts {call.start_utc.strftime('%Y-%m-%d %H:%M')} UTC "
        f"(in ~{minutes_to_start:.0f} min)\n"
        f"Duration: {call.duration_min} min\n"
        f"Link: {call.url}\n"
        f"Status: {call.status}"
    )


def send_via_telegram(text: str) -> tuple[bool, str]:
    """Relay text via ops/telegram_daia.py. Returns (ok, output)."""
    if not TELEGRAM_DAIA.exists():
        return False, f"telegram_daia.py not found at {TELEGRAM_DAIA}"
    try:
        result = subprocess.run(
            [sys.executable, str(TELEGRAM_DAIA), "send", text],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "telegram send timed out after 30s"
    except OSError as exc:
        return False, f"telegram send failed: {exc}"
    if result.returncode != 0:
        return False, f"telegram exit {result.returncode}: {result.stderr.strip()}"
    return True, result.stdout.strip()


def run(
    schedule_path: Path,
    state_path: Path,
    now: datetime,
    send: bool,
) -> int:
    calls = parse_schedule(schedule_path)
    state = load_nudge_state(state_path)
    fired = 0
    skipped_already = 0
    skipped_inactive = 0
    skipped_out_of_window = 0
    for call in calls:
        if call.status not in ACTIVE_STATUSES:
            skipped_inactive += 1
            continue
        labels = due_nudges(call, now)
        if not labels:
            skipped_out_of_window += 1
            continue
        for label in labels:
            if already_sent(state, call, label):
                skipped_already += 1
                continue
            text = build_nudge_text(call, label, now)
            print(f"--- {label} for {call.counterparty} ---")
            print(text)
            if send:
                ok, output = send_via_telegram(text)
                if not ok:
                    print(f"!! send failed: {output}", file=sys.stderr)
                    continue  # do not mark sent if relay failed
                print(f"sent: {output}")
            mark_sent(state, call, label, now)
            fired += 1
    if send:
        save_nudge_state(state_path, state)
    print(
        f"\nsummary: fired={fired} already_sent={skipped_already} "
        f"inactive={skipped_inactive} out_of_window={skipped_out_of_window} "
        f"now={now.isoformat()} send={send}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--schedule",
        type=Path,
        default=DEFAULT_SCHEDULE,
        help=f"path to schedule markdown (default: {DEFAULT_SCHEDULE})",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help=f"path to nudge-state json (default: {DEFAULT_STATE})",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="override current time as ISO-8601 (UTC). Default: real now.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="actually send Telegram nudges (default is dry-run print).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.now:
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(UTC)
    else:
        now = datetime.now(tz=UTC)
    return run(args.schedule, args.state, now, args.send)


if __name__ == "__main__":
    raise SystemExit(main())
