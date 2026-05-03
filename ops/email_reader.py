#!/usr/bin/env python3
"""
Email reader for dutchaiagents@proton.me using protonmail-api-client.
Usage:
    python ops/email_reader.py                  # list recent 10 messages
    python ops/email_reader.py --unread         # unread only
    python ops/email_reader.py --exclude-noise  # filter known automated senders
    python ops/email_reader.py --read ID        # read specific message by ID
    python ops/email_reader.py --search QUERY   # search subject/sender
    python ops/email_reader.py --codes          # extract verification codes from recent unread
"""
import argparse
import contextlib
import io
import json
import os
import re
import sys
import warnings
from pathlib import Path

SECRETS_DIR = Path(__file__).resolve().parent.parent / ".secrets"
SESSION_FILE = SECRETS_DIR / "proton_session.pickle"

# Substrings (lowercased) of senders that are system/operational notifications,
# not real inbound replies. Triage-noise filter for `--exclude-noise`. Keep
# narrow and explicit; only add a sender after observing >=2 noise hits across
# wakes.
NOISE_SENDER_SUBSTRINGS = (
    "dutchaiagents@proton.me",
    "no-reply@notify.proton.me",
    "noreply@gumroad.com",
    "yo@dev.to",
    "notifier@farcaster.xyz",
)


def is_noise_sender(sender: str) -> bool:
    """Return True if the sender string matches a known automated-notification source."""
    s = (sender or "").lower()
    return any(needle in s for needle in NOISE_SENDER_SUBSTRINGS)


def get_credentials():
    email_file = SECRETS_DIR / "email.txt"
    lines = email_file.read_text().strip().splitlines()
    return lines[0].strip(), lines[1].strip()


@contextlib.contextmanager
def suppress_client_noise():
    """Keep Proton client progress/warning chatter out of JSON CLI output."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*urllib3.*chardet.*charset_normalizer.*",
            category=Warning,
        )
        with contextlib.redirect_stderr(io.StringIO()):
            yield


def quiet_client_call(callable_):
    with suppress_client_noise():
        return callable_()


def get_client():
    with suppress_client_noise():
        from protonmail import ProtonMail

        username, password = get_credentials()
        proton = ProtonMail()

        # Try loading saved session first
        if SESSION_FILE.exists():
            try:
                proton.load_session(str(SESSION_FILE))
                return proton
            except Exception:
                pass

        proton.login(username, password)
        proton.save_session(str(SESSION_FILE))
        return proton


def list_messages(proton, unread_only=False, limit=10, exclude_noise=False):
    messages = quiet_client_call(proton.get_messages)
    results = []
    for msg in messages[:50]:
        if unread_only and msg.unread == 0:
            continue
        sender_str = str(msg.sender)
        if exclude_noise and is_noise_sender(sender_str):
            continue
        results.append({
            "id": msg.id,
            "subject": msg.subject,
            "sender": sender_str,
            "time": str(msg.time),
            "unread": bool(msg.unread),
        })
        if len(results) >= limit:
            break
    return results


def read_message(proton, msg_id):
    messages = quiet_client_call(proton.get_messages)
    for msg in messages:
        if msg.id == msg_id:
            full = quiet_client_call(lambda: proton.read_message(msg))
            return {
                "id": full.id,
                "subject": full.subject,
                "sender": str(full.sender),
                "time": str(full.time),
                "body": full.body,
            }
    return None


def search_messages(proton, query, limit=10):
    messages = quiet_client_call(proton.get_messages)
    query_lower = query.lower()
    results = []
    for msg in messages[:100]:
        if query_lower in msg.subject.lower() or query_lower in str(msg.sender).lower():
            results.append({
                "id": msg.id,
                "subject": msg.subject,
                "sender": str(msg.sender),
                "time": str(msg.time),
            })
            if len(results) >= limit:
                break
    return results


def extract_codes(proton, limit=5):
    """Extract verification/login codes from recent unread messages."""
    messages = quiet_client_call(proton.get_messages)
    codes = []
    for msg in messages[:20]:
        if not msg.unread:
            continue
        full = quiet_client_call(lambda: proton.read_message(msg))
        body = full.body or ""
        # Common patterns for verification codes
        patterns = [
            r'\b(\d{4,8})\b',  # 4-8 digit codes
            r'code[:\s]+([A-Z0-9]{4,8})',
            r'verification[:\s]+([A-Z0-9]{4,8})',
            r'OTP[:\s]+([A-Z0-9]{4,8})',
        ]
        found = set()
        for pat in patterns:
            matches = re.findall(pat, body, re.IGNORECASE)
            found.update(matches)
        if found:
            codes.append({
                "subject": full.subject,
                "sender": str(full.sender),
                "time": str(full.time),
                "codes": list(found),
            })
        if len(codes) >= limit:
            break
    return codes


def main():
    parser = argparse.ArgumentParser(description="Read ProtonMail emails")
    parser.add_argument("--unread", action="store_true", help="Show unread only")
    parser.add_argument("--exclude-noise", action="store_true", help="Filter known automated-notification senders")
    parser.add_argument("--read", type=str, help="Read message by ID")
    parser.add_argument("--search", type=str, help="Search by subject/sender")
    parser.add_argument("--codes", action="store_true", help="Extract verification codes")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    args = parser.parse_args()

    proton = get_client()

    if args.read:
        result = read_message(proton, args.read)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Message {args.read} not found", file=sys.stderr)
            sys.exit(1)
    elif args.search:
        results = search_messages(proton, args.search, args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.codes:
        results = extract_codes(proton, args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        results = list_messages(proton, args.unread, args.limit, args.exclude_noise)
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
