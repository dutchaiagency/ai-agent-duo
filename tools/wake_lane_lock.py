#!/usr/bin/env python3
"""Wake-level lane lock primitive for parallel autopilot dispatches.

The lock is intentionally repo-local and advisory. It gives a wake a cheap way
to claim a logical intent before choosing a concrete file, browser flow, or
outbound surface. Fresh locks block duplicate work; expired locks are stolen so
crashed wakes do not permanently block the lane.

Intent normalization is deliberately small and stable: lowercase, treat
underscores as word separators, collapse whitespace runs to one space, and
strip leading/trailing whitespace. Other punctuation is preserved, so
``calendar_nudge.py`` and ``calendar nudge py`` stay distinct. The resulting
intent hash is ``sha256(normalized_intent)[:16]`` unless ``--intent-hash`` is
provided as an explicit override.

Target surfaces are canonical lowercase snake-case names with an optional
``:detail`` suffix, for example ``farcaster_reply``,
``github_issue_comment:owner/repo#123``, or
``tool_build:tools/calendar_nudge.py``. Invalid surfaces fail at acquire time
so aliases like ``farcaster-reply``, ``fc_reply``, and ``fc reply`` do not
silently miss each other in the ``(intent_hash, target_surface)`` key.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .agent_identity import default_agent_name
except ImportError:  # pragma: no cover - direct script execution
    from agent_identity import default_agent_name


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "wake_locks.db"
DEFAULT_TTL_SECONDS = 900
DEFAULT_AUDIT_LOG = ROOT / "state" / "wake_locks_audit.log"
INTENT_HASH_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{3,127}$")
SURFACE_RE = re.compile(r"^[a-z][a-z0-9_]*(?::[a-z0-9][a-z0-9_./#@+-]*)?$")
CANONICAL_SURFACE_BASES = frozenset(
    {
        "browser_flow",
        "devto_comment",
        "devto_post",
        "farcaster_cast",
        "farcaster_reply",
        "funnel_doc",
        "github_issue_comment",
        "github_lead_scan",
        "github_pr_comment",
        "lead_scan",
        "longform_edit",
        "outbound_pipeline",
        "research_doc",
        "tool_build",
    }
)
CANONICAL_SURFACE_BASE_PREFIXES = ("email_send_recipient_",)
SURFACE_EXAMPLES = (
    "farcaster_reply",
    "email_send_recipient_leon",
    "github_issue_comment:owner/repo#123",
    "tool_build:tools/calendar_nudge.py",
)
SURFACE_HINT = (
    "target surface must match "
    f"{SURFACE_RE.pattern!r} and use a documented surface family; "
    f"examples: {', '.join(SURFACE_EXAMPLES)}"
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def parse_ts(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def stamp(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_intent(value: str) -> str:
    """Normalize work intent before hashing.

    Rules: lowercase, convert underscores to spaces, collapse whitespace runs
    to one space, strip leading/trailing whitespace, and preserve other
    punctuation.
    """

    return re.sub(r"\s+", " ", value.replace("_", " ").strip().lower())


def normalize_surface(value: str) -> str:
    normalized = value.strip().lower().replace("\\", "/")
    if not normalized:
        raise ValueError("target surface must not be empty")
    if not SURFACE_RE.match(normalized):
        raise ValueError(SURFACE_HINT)
    base = normalized.split(":", 1)[0]
    if base not in CANONICAL_SURFACE_BASES and not base.startswith(
        CANONICAL_SURFACE_BASE_PREFIXES
    ):
        raise ValueError(SURFACE_HINT)
    return normalized


def intent_hash(intent: str) -> str:
    normalized = normalize_intent(intent)
    if not normalized:
        raise ValueError("intent must not be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def validate_hash(value: str) -> str:
    normalized = value.strip().lower()
    if not INTENT_HASH_RE.match(normalized):
        raise ValueError(
            "intent hash must be 4-128 chars: lowercase letters, digits, _, ., :, or -"
        )
    return normalized


def resolve_intent_hash(intent: str | None, supplied_hash: str | None) -> tuple[str, str]:
    if supplied_hash:
        digest = validate_hash(supplied_hash)
        return digest, normalize_intent(intent or supplied_hash)
    if not intent:
        raise ValueError("provide --intent or --intent-hash")
    return intent_hash(intent), normalize_intent(intent)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wake_lane_locks (
            intent_hash TEXT NOT NULL,
            target_surface TEXT NOT NULL,
            token TEXT NOT NULL,
            owner TEXT NOT NULL,
            pid INTEGER NOT NULL,
            intent TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (intent_hash, target_surface)
        )
        """
    )
    return conn


@dataclass(frozen=True)
class LockRecord:
    intent_hash: str
    target_surface: str
    token: str
    owner: str
    pid: int
    intent: str
    created_at: str
    expires_at: str
    metadata: str = "{}"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "LockRecord":
        return cls(
            intent_hash=str(row["intent_hash"]),
            target_surface=str(row["target_surface"]),
            token=str(row["token"]),
            owner=str(row["owner"]),
            pid=int(row["pid"]),
            intent=str(row["intent"]),
            created_at=str(row["created_at"]),
            expires_at=str(row["expires_at"]),
            metadata=str(row["metadata"]),
        )

    @property
    def active(self) -> bool:
        return parse_ts(self.expires_at) > utc_now()


@dataclass(frozen=True)
class AcquireResult:
    acquired: bool
    record: LockRecord
    previous: LockRecord | None = None


def row_for(
    conn: sqlite3.Connection,
    *,
    key: str,
    target_surface: str,
) -> LockRecord | None:
    normalized_target = normalize_surface(target_surface)
    row = conn.execute(
        """
        SELECT intent_hash, target_surface, token, owner, pid, intent,
               created_at, expires_at, metadata
        FROM wake_lane_locks
        WHERE intent_hash=? AND target_surface=?
        """,
        (key, normalized_target),
    ).fetchone()
    return LockRecord.from_row(row) if row else None


def acquire_lock(
    conn: sqlite3.Connection,
    *,
    key: str,
    target_surface: str,
    intent: str,
    owner: str,
    ttl: dt.timedelta,
    pid: int | None = None,
    now: dt.datetime | None = None,
    metadata: str = "{}",
) -> AcquireResult:
    now = (now or utc_now()).astimezone(dt.UTC)
    if ttl.total_seconds() <= 0:
        raise ValueError("ttl must be positive")
    expires_at = now + ttl
    pid = os.getpid() if pid is None else pid
    token = uuid.uuid4().hex
    normalized_target = normalize_surface(target_surface)

    conn.execute("BEGIN IMMEDIATE")
    try:
        previous = row_for(conn, key=key, target_surface=normalized_target)
        if previous and parse_ts(previous.expires_at) > now:
            conn.execute("COMMIT")
            return AcquireResult(False, previous)

        conn.execute(
            """
            INSERT INTO wake_lane_locks (
                intent_hash, target_surface, token, owner, pid, intent,
                created_at, expires_at, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(intent_hash, target_surface) DO UPDATE SET
                token=excluded.token,
                owner=excluded.owner,
                pid=excluded.pid,
                intent=excluded.intent,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at,
                metadata=excluded.metadata
            """,
            (
                key,
                normalized_target,
                token,
                owner.strip() or "unknown",
                pid,
                intent,
                stamp(now),
                stamp(expires_at),
                metadata,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    record = row_for(conn, key=key, target_surface=normalized_target)
    if record is None:  # pragma: no cover - defensive guard
        raise RuntimeError("lock insert failed")
    return AcquireResult(True, record, previous)


def release_lock(
    conn: sqlite3.Connection,
    *,
    key: str,
    target_surface: str,
    token: str | None = None,
    force: bool = False,
    owner: str = "",
    audit_log: Path | None = None,
    reason: str = "",
) -> bool:
    normalized_target = normalize_surface(target_surface)
    if force:
        previous = row_for(conn, key=key, target_surface=normalized_target)
        cur = conn.execute(
            "DELETE FROM wake_lane_locks WHERE intent_hash=? AND target_surface=?",
            (key, normalized_target),
        )
        released = cur.rowcount > 0
        if audit_log is not None:
            append_audit(
                audit_log,
                {
                    "event": "force_release",
                    "ts": stamp(utc_now()),
                    "intent_hash": key,
                    "target_surface": normalized_target,
                    "owner": owner.strip() or default_agent_name(),
                    "released": released,
                    "reason": reason.strip(),
                    "previous_owner": previous.owner if previous else None,
                    "previous_pid": previous.pid if previous else None,
                    "previous_expires_at": previous.expires_at if previous else None,
                },
            )
        return released
    if not token:
        raise ValueError("release requires --token unless --force is used")
    cur = conn.execute(
        """
        DELETE FROM wake_lane_locks
        WHERE intent_hash=? AND target_surface=? AND token=?
        """,
        (key, normalized_target, token.strip()),
    )
    return cur.rowcount > 0


def append_audit(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def prune_expired(
    conn: sqlite3.Connection,
    *,
    now: dt.datetime | None = None,
) -> int:
    now = (now or utc_now()).astimezone(dt.UTC)
    cur = conn.execute(
        "DELETE FROM wake_lane_locks WHERE expires_at <= ?",
        (stamp(now),),
    )
    return int(cur.rowcount)


def list_locks(conn: sqlite3.Connection) -> list[LockRecord]:
    rows = conn.execute(
        """
        SELECT intent_hash, target_surface, token, owner, pid, intent,
               created_at, expires_at, metadata
        FROM wake_lane_locks
        ORDER BY expires_at DESC, target_surface ASC
        """
    ).fetchall()
    return [LockRecord.from_row(row) for row in rows]


def record_to_dict(record: LockRecord, *, now: dt.datetime | None = None) -> dict:
    now = (now or utc_now()).astimezone(dt.UTC)
    expires_at = parse_ts(record.expires_at)
    data = asdict(record)
    data["active"] = expires_at > now
    data["seconds_remaining"] = max(0, int((expires_at - now).total_seconds()))
    try:
        data["metadata"] = json.loads(record.metadata)
    except json.JSONDecodeError:
        pass
    return data


def print_payload(payload: dict | list[dict], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, list):
        for item in payload:
            status = "active" if item["active"] else "expired"
            print(
                f"{status} {item['intent_hash']} {item['target_surface']} "
                f"owner={item['owner']} pid={item['pid']} expires={item['expires_at']}"
            )
        if not payload:
            print("no locks")
        return
    status = payload.get("status", "ok")
    record = payload.get("record") or payload
    if isinstance(record, dict) and "intent_hash" in record:
        print(
            f"{status} {record['intent_hash']} {record['target_surface']} "
            f"token={record['token']} owner={record['owner']} "
            f"expires={record['expires_at']}"
        )
    else:
        print(f"{status}: {payload}")


def add_intent_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--intent", help="Human-readable logical work intent")
    parser.add_argument("--intent-hash", help="Stable precomputed intent key")
    parser.add_argument(
        "--target",
        required=True,
        help=f"Canonical target surface. {SURFACE_HINT}",
    )


def add_subcommand_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Advisory wake-level lane locks.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG)
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    acquire = sub.add_parser("acquire", help="Acquire or steal an expired lane lock")
    add_subcommand_json_arg(acquire)
    add_intent_args(acquire)
    acquire.add_argument("--owner", default=default_agent_name())
    acquire.add_argument(
        "--ttl",
        type=float,
        default=None,
        help="Lock TTL in seconds; default is 900 (15 minutes)",
    )
    acquire.add_argument(
        "--ttl-minutes",
        type=float,
        default=None,
        help=argparse.SUPPRESS,
    )
    acquire.add_argument(
        "--metadata",
        default="{}",
        help="Optional JSON metadata string stored with the lock",
    )

    status = sub.add_parser("status", help="Show one lock")
    add_subcommand_json_arg(status)
    add_intent_args(status)

    release = sub.add_parser("release", help="Release one lock")
    add_subcommand_json_arg(release)
    add_intent_args(release)
    release.add_argument("--owner", default=default_agent_name())
    release.add_argument("--token", help="Token returned by acquire")
    release.add_argument("--force", action="store_true", help="Delete without token match")
    release.add_argument("--reason", default="", help="Reason recorded for --force audit")

    list_parser = sub.add_parser("list", help="List all locks")
    add_subcommand_json_arg(list_parser)
    prune_parser = sub.add_parser("prune", help="Delete expired locks")
    add_subcommand_json_arg(prune_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with closing(connect(args.db)) as conn:
            if args.command == "list":
                payload = [record_to_dict(record) for record in list_locks(conn)]
                print_payload(payload, as_json=args.json)
                return 0
            if args.command == "prune":
                count = prune_expired(conn)
                print_payload({"status": "pruned", "count": count}, as_json=args.json)
                return 0

            key, normalized_intent = resolve_intent_hash(args.intent, args.intent_hash)
            target = normalize_surface(args.target)

            if args.command == "acquire":
                if args.ttl_minutes is not None and args.ttl is not None:
                    raise ValueError("use --ttl seconds or legacy --ttl-minutes, not both")
                ttl_seconds = DEFAULT_TTL_SECONDS if args.ttl is None else args.ttl
                if args.ttl_minutes is not None:
                    ttl_seconds = args.ttl_minutes * 60
                if ttl_seconds <= 0:
                    raise ValueError("--ttl must be positive seconds")
                json.loads(args.metadata)
                result = acquire_lock(
                    conn,
                    key=key,
                    target_surface=target,
                    intent=normalized_intent,
                    owner=args.owner,
                    ttl=dt.timedelta(seconds=ttl_seconds),
                    metadata=args.metadata,
                )
                payload = {
                    "status": "acquired" if result.acquired else "busy",
                    "record": record_to_dict(result.record),
                }
                if result.previous:
                    payload["previous"] = record_to_dict(result.previous)
                print_payload(payload, as_json=args.json)
                return 0 if result.acquired else 2

            if args.command == "status":
                record = row_for(conn, key=key, target_surface=target)
                if record is None:
                    print_payload({"status": "missing"}, as_json=args.json)
                    return 1
                print_payload({"status": "found", "record": record_to_dict(record)}, as_json=args.json)
                return 0

            if args.command == "release":
                released = release_lock(
                    conn,
                    key=key,
                    target_surface=target,
                    token=args.token,
                    force=args.force,
                    owner=args.owner,
                    audit_log=args.audit_log if args.force else None,
                    reason=args.reason,
                )
                print_payload(
                    {"status": "released" if released else "not-released"},
                    as_json=args.json,
                )
                return 0 if released else 1
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
