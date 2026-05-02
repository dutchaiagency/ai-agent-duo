#!/usr/bin/env python3
"""Decode and sanity-check X/Twitter snowflake status IDs."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, date, datetime, time


TWITTER_EPOCH_MS = 1288834974657
MODERN_STATUS_ID_DIGITS = 19
STATUS_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/([^/\s]+)/status/(\d+)"
)
REPEATED_DIGIT_RE = re.compile(r"(\d)\1{5,}")


def extract_status_id(value: str) -> int:
    value = value.strip()
    match = STATUS_URL_RE.search(value)
    raw_id = match.group(2) if match else value
    if not raw_id.isdigit():
        raise ValueError(f"not a numeric X status ID: {value}")
    return int(raw_id)


def decode_snowflake_utc(status_id: int) -> datetime:
    if status_id <= 0:
        raise ValueError("status ID must be positive")
    timestamp_ms = (status_id >> 22) + TWITTER_EPOCH_MS
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    end = datetime.combine(day, time.max, tzinfo=UTC)
    return start, end


def in_window(created_at: datetime, *, after: date | None, before: date | None) -> bool:
    if after is not None and created_at < datetime.combine(after, time.min, tzinfo=UTC):
        return False
    if before is not None and created_at > datetime.combine(before, time.max, tzinfo=UTC):
        return False
    return True


def has_modern_status_id_length(status_id: int) -> bool:
    return len(str(status_id)) == MODERN_STATUS_ID_DIGITS


def has_synthetic_digit_pattern(status_id: int) -> bool:
    """Flag hand-written looking decimal patterns in claimed status IDs."""
    digits = str(status_id)
    if REPEATED_DIGIT_RE.search(digits):
        return True

    for index in range(len(digits) - 6):
        window = digits[index : index + 7]
        steps = [
            (int(window[position + 1]) - int(window[position])) % 10
            for position in range(len(window) - 1)
        ]
        if all(step == 1 for step in steps) or all(step == 9 for step in steps):
            return True
    return False


def looks_like_real_snowflake(
    status_id: int,
    *,
    after: date | None = None,
    before: date | None = None,
) -> tuple[bool, str]:
    created_at = decode_snowflake_utc(status_id)
    if not has_modern_status_id_length(status_id):
        return False, "wrong_length"
    if after is not None and created_at.date() < after:
        return False, "before_window"
    if before is not None and created_at.date() > before:
        return False, "after_window"
    if has_synthetic_digit_pattern(status_id):
        return False, "synthetic_digit_pattern"
    return True, "ok"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode X/Twitter status IDs and optionally check a UTC date window."
    )
    parser.add_argument("values", nargs="+", help="Status IDs or x.com/twitter.com URLs.")
    parser.add_argument("--after", type=parse_day, help="Reject IDs before YYYY-MM-DD UTC.")
    parser.add_argument("--before", type=parse_day, help="Reject IDs after YYYY-MM-DD UTC.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok = True
    for value in args.values:
        try:
            status_id = extract_status_id(value)
            created_at = decode_snowflake_utc(status_id)
            window_ok = in_window(created_at, after=args.after, before=args.before)
        except ValueError as exc:
            ok = False
            print(f"{value}\tinvalid\t{exc}")
            continue
        synthetic = has_synthetic_digit_pattern(status_id)
        status_parts = []
        if not has_modern_status_id_length(status_id):
            status_parts.append("wrong_length")
        if not window_ok:
            status_parts.append("outside_window")
        if synthetic:
            status_parts.append("synthetic_digit_pattern")
        status = ",".join(status_parts) if status_parts else "ok"
        if not window_ok or synthetic:
            ok = False
        print(f"{status_id}\t{created_at.isoformat()}\t{status}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
