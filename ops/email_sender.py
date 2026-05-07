#!/usr/bin/env python3
"""
Email sender for dutchaiagents@proton.me using protonmail-api-client.

Reuses the session pickle from email_reader.py.

Usage:
    python ops/email_sender.py --to user@example.com --subject "..." --body-file path.txt
    python ops/email_sender.py --to ... --subject ... --body-file ... --execute
    python ops/email_sender.py --to ... --subject ... --body-file ... --execute --lock custom-topic

Default mode is dry-run (prints what would be sent, no API call).
Pass --execute to actually send.

Safety:
- One target per invocation (no --to-file / no list).
- Hard fails if SUBJECT or BODY look like an unfilled template
  (contain "[name]", "[repo]", etc.).
- Hard fails before any Proton call if the recipient appears in
  ops/email_suppression_list.md.
- Live sends always lock the recipient before touching Proton.
  Optional --lock adds a second topic lock; it never bypasses recipient or
  exact-body duplicate protection.
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

try:
    from .outbound_text_guard import validate_outbound_text
    from .email_reader import get_client as get_reader_client
except ImportError:  # pragma: no cover - direct script execution
    from outbound_text_guard import validate_outbound_text
    from email_reader import get_client as get_reader_client

ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / ".secrets"
SESSION_FILE = SECRETS_DIR / "proton_session.pickle"
LOG_FILE = ROOT / "ops" / "outbound_cold_dm_2026-05-02.md"
SUPPRESSION_FILE = ROOT / "ops" / "email_suppression_list.md"
LOCKS_DIR = ROOT / "state" / "locks"
LOCK_TTL_SECONDS = 120
RECIPIENT_LOCK_TTL_SECONDS = 600
BODY_DEDUPE_LOCK_TTL_SECONDS = 24 * 60 * 60
EMAIL_RE = re.compile(r"^[^@\s|]+@[^@\s|]+\.[^@\s|]+$")

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
    return get_reader_client()


def get_fresh_client():
    from protonmail import ProtonMail
    username, password = get_credentials()
    proton = ProtonMail()
    proton.login(username, password)
    proton.save_session(str(SESSION_FILE))
    return proton


def check_placeholders(text: str, label: str) -> list[str]:
    hits = []
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(f"{label}: {pat}")
    return hits


def check_outbound_text(subject: str, body: str) -> list[str]:
    errors = []
    for label, text in (("email subject", subject), ("email body", body)):
        error = validate_outbound_text(text, label=label)
        if error:
            errors.append(error)
    return errors


def load_suppressed_emails(path: Path | None = None) -> set[str]:
    path = path or SUPPRESSION_FILE
    if not path.exists():
        raise SystemExit(f"REFUSE: suppression list missing: {path}")
    suppressed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`").lower() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[1] == "email":
            continue
        if EMAIL_RE.match(cells[1]):
            suppressed.add(cells[1])
    return suppressed


def suppressed_recipient(to_addr: str, path: Path | None = None) -> str | None:
    normalized = to_addr.strip().lower()
    return normalized if normalized in load_suppressed_emails(path) else None


def send_lock_path(topic: str) -> Path:
    normalized = topic.strip().lower()
    if not normalized:
        raise SystemExit("REFUSE: --lock topic is empty")
    slug = re.sub(r"[^a-z0-9@._+-]+", "_", normalized).strip("._-")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return LOCKS_DIR / f"{(slug or 'topic')[:80]}-{digest}.lock"


def exact_body_dedupe_topic(to_addr: str, subject: str, body: str) -> str:
    normalized_to = to_addr.strip().lower()
    body_digest = hashlib.sha256(
        f"{subject.strip()}\0{body.strip()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"dedupe:{normalized_to}:{body_digest}"


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


def acquire_live_send_locks(
    *,
    to_addr: str,
    subject: str,
    body: str,
    extra_topic: str = "",
) -> list[Path]:
    normalized_to = to_addr.strip().lower()
    topics: list[tuple[str, int]] = [
        (f"recipient:{normalized_to}", RECIPIENT_LOCK_TTL_SECONDS),
        (
            exact_body_dedupe_topic(normalized_to, subject, body),
            BODY_DEDUPE_LOCK_TTL_SECONDS,
        ),
    ]
    if extra_topic:
        topics.append((f"topic:{extra_topic}", LOCK_TTL_SECONDS))

    acquired: list[Path] = []
    for topic, ttl_seconds in topics:
        acquired.append(acquire_send_lock(topic, ttl_seconds=ttl_seconds))
    return acquired


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


def send_message_with_signature_guard(proton, *, to_addr: str, subject: str, body: str):
    msg = proton.create_message(
        recipients=[to_addr],
        subject=subject,
        body=body,
    )
    try:
        proton.send_message(msg, is_html=False)
        return msg
    except Exception as exc:
        if "Invalid or missing message signature" not in str(exc):
            raise
        print(
            "[AMBIGUOUS] Proton returned invalid/missing message signature. "
            "Not retrying automatically because this failure can land duplicate sends."
        )
        try:
            SESSION_FILE.unlink()
        except FileNotFoundError:
            pass
        raise SystemExit(
            "REFUSE: Proton signature failure leaves send status ambiguous. "
            "Session cache was cleared; inspect Sent mail before any manual retry. "
            "The recipient and exact-body locks remain active."
        )


def main():
    parser = argparse.ArgumentParser(description="Send cold outbound email via ProtonMail")
    parser.add_argument("--to", required=True, help="Recipient email address (one)")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body-file", required=True, help="Path to plain-text body")
    parser.add_argument("--source", default="manual", help="Source/UTM tag for log row")
    parser.add_argument("--personalization", default="", help="One-line note for log")
    parser.add_argument("--execute", action="store_true", help="Actually send (default = dry-run)")
    parser.add_argument("--lock", default="", help="Optional extra live-send dedupe topic")
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

    guard_errors = check_outbound_text(args.subject, body)
    if guard_errors:
        print("REFUSE: outbound text guard failed:", file=sys.stderr)
        for error in guard_errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(2)

    # Self-send guard
    if args.to.strip().lower() == "dutchaiagents@proton.me" and not args.allow_self:
        raise SystemExit("Refusing to send to self without --allow-self")

    suppressed = suppressed_recipient(args.to)
    if suppressed:
        try:
            append_log_row(
                to_addr=args.to,
                subject=args.subject,
                source=args.source,
                personalization=args.personalization or args.subject,
                status="refused_suppressed_opt_out",
            )
        except Exception as exc:
            raise SystemExit(
                f"REFUSE: {suppressed} is listed in {SUPPRESSION_FILE}; "
                f"failed to log decline: {exc}"
            ) from exc
        raise SystemExit(
            f"REFUSE: {suppressed} is listed in {SUPPRESSION_FILE}; "
            "do not email suppressed recipients"
        )

    print(f"TO: {args.to}")
    print(f"SUBJECT: {args.subject}")
    print(f"BODY ({len(body)} chars):")
    print("---")
    print(body)
    print("---")

    if not args.execute:
        print("[DRY-RUN] not sending. Pass --execute to send.")
        return

    lock_paths = acquire_live_send_locks(
        to_addr=args.to,
        subject=args.subject,
        body=body,
        extra_topic=args.lock,
    )
    for lock_path in lock_paths:
        print(f"[LOCKED] {lock_path}")

    proton = get_client()
    msg = send_message_with_signature_guard(
        proton,
        to_addr=args.to,
        subject=args.subject,
        body=body,
    )
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
