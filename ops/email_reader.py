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
import shutil
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


class EmailLoginBlocked(RuntimeError):
    """Raised when Proton requires a human action before API login can continue."""


def session_candidates() -> tuple[Path, ...]:
    """Return current and backup Proton session files, newest backups first."""
    candidates: list[Path] = []
    if SESSION_FILE.exists():
        candidates.append(SESSION_FILE)
    backups = sorted(
        SECRETS_DIR.glob("proton_session.pickle.bak-*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for backup in backups:
        if backup not in candidates:
            candidates.append(backup)
    return tuple(candidates)


def load_saved_session(proton) -> Path | None:
    """Try every saved Proton session; canonicalize a working backup."""
    for session_path in session_candidates():
        try:
            proton.load_session(str(session_path))
        except Exception:
            continue
        if session_path != SESSION_FILE:
            try:
                shutil.copy2(session_path, SESSION_FILE)
            except Exception:
                pass
        return session_path
    return None


def is_captcha_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "captcha" in text


def is_session_expired_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "invalid refresh token" in text or "can't update tokens" in text


def raise_blocked_for_client_error(exc: Exception) -> None:
    if is_session_expired_error(exc):
        try:
            SESSION_FILE.unlink()
        except FileNotFoundError:
            pass
        raise EmailLoginBlocked(
            "Saved Proton session is expired or revoked. Refresh "
            ".secrets/proton_session.pickle in a browser-backed login, then "
            "rerun ops/email_reader.py."
        ) from exc
    if is_captcha_error(exc):
        raise EmailLoginBlocked(
            "Proton login requires CAPTCHA or another human verification. "
            "Refresh .secrets/proton_session.pickle in a browser-backed login, "
            "then rerun ops/email_reader.py."
        ) from exc
    raise exc


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

        if load_saved_session(proton):
            return proton

        try:
            proton.login(username, password)
        except Exception as exc:
            raise_blocked_for_client_error(exc)
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


def body_snippet(body, query, radius=80):
    """Return a compact snippet around query in body text."""
    compact = re.sub(r"\s+", " ", body or "").strip()
    if not compact:
        return ""
    idx = compact.lower().find(query.lower())
    if idx < 0:
        return compact[: radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(compact), idx + len(query) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"


def search_messages(
    proton,
    query,
    limit=10,
    unread_only=False,
    exclude_noise=False,
    include_body=False,
):
    messages = quiet_client_call(proton.get_messages)
    query_lower = query.lower()
    results = []
    for msg in messages[:100]:
        if unread_only and msg.unread == 0:
            continue
        sender_str = str(msg.sender)
        if exclude_noise and is_noise_sender(sender_str):
            continue

        matched_fields = []
        if query_lower in (msg.subject or "").lower():
            matched_fields.append("subject")
        if query_lower in sender_str.lower():
            matched_fields.append("sender")

        snippet = ""
        if include_body and not matched_fields:
            full = quiet_client_call(lambda: proton.read_message(msg))
            body = full.body or ""
            if query_lower in body.lower():
                matched_fields.append("body")
                snippet = body_snippet(body, query)

        if matched_fields:
            result = {
                "id": msg.id,
                "subject": msg.subject,
                "sender": sender_str,
                "time": str(msg.time),
            }
            if include_body:
                result["matched_fields"] = matched_fields
                if snippet:
                    result["body_snippet"] = snippet
            results.append(result)
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
    parser.add_argument("--body", action="store_true", help="Include message bodies in --search")
    parser.add_argument("--codes", action="store_true", help="Extract verification codes")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    args = parser.parse_args()

    try:
        proton = get_client()
    except EmailLoginBlocked as exc:
        print(f"EMAIL_BLOCKED: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        if args.read:
            result = read_message(proton, args.read)
            if result:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"Message {args.read} not found", file=sys.stderr)
                sys.exit(1)
        elif args.search:
            results = search_messages(
                proton,
                args.search,
                args.limit,
                unread_only=args.unread,
                exclude_noise=args.exclude_noise,
                include_body=args.body,
            )
            print(json.dumps(results, indent=2, ensure_ascii=False))
        elif args.codes:
            results = extract_codes(proton, args.limit)
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            results = list_messages(proton, args.unread, args.limit, args.exclude_noise)
            print(json.dumps(results, indent=2, ensure_ascii=False))
    except Exception as exc:
        try:
            raise_blocked_for_client_error(exc)
        except EmailLoginBlocked as blocked:
            print(f"EMAIL_BLOCKED: {blocked}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
