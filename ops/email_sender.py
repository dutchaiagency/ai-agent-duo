#!/usr/bin/env python3
"""
Email sender for dutchaiagents@proton.me using protonmail-api-client.

Reuses the session pickle from email_reader.py.

Usage:
    python ops/email_sender.py --to user@example.com --subject "..." --body-file path.txt
    python ops/email_sender.py --to ... --subject ... --body-file ... --execute
    python ops/email_sender.py --to ... --subject ... --body-file ... --execute --lock user@example.com

Default mode is dry-run (prints what would be sent, no API call).
Pass --execute to actually send.

Safety:
- One target per invocation (no --to-file / no list).
- Hard fails if SUBJECT or BODY look like an unfilled template
  (contain "[name]", "[repo]", etc.).
- Optional --lock refuses a live send when the same topic has been
  locked in the last 2 minutes. Use recipient email as the topic.
- Logs every send (and dry-run-with-execute-intended) to
  ops/outbound_cold_dm_2026-05-02.md `Targets` table.
"""
import argparse
import datetime as dt
import hashlib
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / ".secrets"
SESSION_FILE = SECRETS_DIR / "proton_session.pickle"
LOG_FILE = ROOT / "ops" / "outbound_cold_dm_2026-05-02.md"
LOCKS_DIR = ROOT / "state" / "locks"
LOCK_TTL_SECONDS = 120

PLACEHOLDER_PATTERNS = [
    r"\[name\]",
    r"\[repo\]",
    r"\[issue/PR\]",
    r"\[issue\|PR\]",
    r"\[ONE concrete observation",
    r"\[issue\]",
    r"\[your name\]",
]


def get_credentials():
    email_file = SECRETS_DIR / "email.txt"
    lines = email_file.read_text().strip().splitlines()
    return lines[0].strip(), lines[1].strip()


def get_client():
    from protonmail import ProtonMail
    username, password = get_credentials()
    proton = ProtonMail()
    if SESSION_FILE.exists():
        try:
            proton.load_session(str(SESSION_FILE))
            return proton
        except Exception:
            pass
    proton.login(username, password)
    proton.save_session(str(SESSION_FILE))
    return proton


def check_placeholders(text: str, label: str) -> list[str]:
    hits = []
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(f"{label}: {pat}")
    return hits


def send_lock_path(topic: str) -> Path:
    normalized = topic.strip().lower()
    if not normalized:
        raise SystemExit("REFUSE: --lock topic is empty")
    slug = re.sub(r"[^a-z0-9@._+-]+", "_", normalized).strip("._-")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return LOCKS_DIR / f"{(slug or 'topic')[:80]}-{digest}.lock"


def acquire_send_lock(topic: str, ttl_seconds: int = LOCK_TTL_SECONDS) -> Path:
    path = send_lock_path(topic)
    path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue

            age = time.time() - stat.st_mtime
            if age < ttl_seconds:
                raise SystemExit(
                    "REFUSE: active send lock for "
                    f"{topic!r} ({age:.0f}s old, ttl {ttl_seconds}s): {path}"
                )

            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            ts = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            handle.write(f"topic: {topic}\ncreated_utc: {ts}\npid: {os.getpid()}\n")
        return path


def append_log_row(to_addr: str, subject: str, source: str, personalization: str, status: str):
    ts = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%MZ")
    row = (
        f"| {ts} | email | {to_addr} | {source} | "
        f"{personalization[:80].replace('|', '/')} | "
        f"{'yes' if status == 'sent' else 'no'} | {status} |\n"
    )
    text = LOG_FILE.read_text(encoding="utf-8")
    marker = "(rows appended as actions complete)\n"
    target_marker = "## Targets (GitHub-sourced read-only discovery)"
    targets_idx = text.find(target_marker)
    if targets_idx == -1:
        raise SystemExit("Targets section missing in log file")

    # Preferred path for older/newer logs that carry an explicit insertion marker.
    after_targets = text.find(marker, targets_idx)
    if after_targets != -1:
        insert_at = after_targets + len(marker)
    else:
        header_idx = text.find("| ts (UTC) |", targets_idx)
        separator_idx = text.find("| --- |", header_idx)
        if header_idx == -1 or separator_idx == -1:
            raise SystemExit("Targets table header missing")
        line_start = text.find("\n", separator_idx)
        if line_start == -1:
            raise SystemExit("Targets table separator is unterminated")
        line_start += 1
        insert_at = len(text)
        cursor = line_start
        while cursor < len(text):
            next_line = text.find("\n", cursor)
            if next_line == -1:
                next_line = len(text)
            line = text[cursor:next_line]
            if not line.startswith("|"):
                insert_at = cursor
                break
            cursor = next_line + 1
    new_text = text[:insert_at] + row + text[insert_at:]
    LOG_FILE.write_text(new_text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Send cold outbound email via ProtonMail")
    parser.add_argument("--to", required=True, help="Recipient email address (one)")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body-file", required=True, help="Path to plain-text body")
    parser.add_argument("--source", default="manual", help="Source/UTM tag for log row")
    parser.add_argument("--personalization", default="", help="One-line note for log")
    parser.add_argument("--execute", action="store_true", help="Actually send (default = dry-run)")
    parser.add_argument("--lock", default="", help="Live-send dedupe topic; use recipient email")
    parser.add_argument("--allow-self", action="store_true", help="Allow sending to dutchaiagents@proton.me (self-test)")
    args = parser.parse_args()

    body_path = Path(args.body_file)
    if not body_path.is_file():
        raise SystemExit(f"body file not found: {body_path}")
    body = body_path.read_text(encoding="utf-8")

    # Placeholder gate
    hits = check_placeholders(args.subject, "subject") + check_placeholders(body, "body")
    if hits:
        print("REFUSE: unfilled template placeholders detected:", file=sys.stderr)
        for h in hits:
            print(f"  - {h}", file=sys.stderr)
        sys.exit(2)

    # Self-send guard
    if args.to.strip().lower() == "dutchaiagents@proton.me" and not args.allow_self:
        raise SystemExit("Refusing to send to self without --allow-self")

    print(f"TO: {args.to}")
    print(f"SUBJECT: {args.subject}")
    print(f"BODY ({len(body)} chars):")
    print("---")
    print(body)
    print("---")

    if not args.execute:
        print("[DRY-RUN] not sending. Pass --execute to send.")
        return

    if args.lock:
        lock_path = acquire_send_lock(args.lock)
        print(f"[LOCKED] {lock_path}")

    proton = get_client()
    msg = proton.create_message(
        recipients=[args.to],
        subject=args.subject,
        body=body,
    )
    proton.send_message(msg, is_html=False)
    print(f"[SENT] message_id={msg.id}")

    append_log_row(
        to_addr=args.to,
        subject=args.subject,
        source=args.source,
        personalization=args.personalization or args.subject,
        status="sent",
    )
    print(f"[LOGGED] {LOG_FILE}")


if __name__ == "__main__":
    main()
