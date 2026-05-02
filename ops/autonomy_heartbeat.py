#!/usr/bin/env python3
"""Periodic bridge heartbeat for the survival-agents workspace.

This script is intentionally small: it only enqueues a bridge message when the
configured recipients have no unread work and the last heartbeat is older than
the configured interval. The existing agent-bridge autopilot is responsible for
starting configured agents when those messages appear.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(
    os.environ.get(
        "BRIDGE_DB",
        "C:/Users/leonv/assistant/projecten/agent-bridge/messages.db",
    )
)
BRIDGE_DIR = Path(
    os.environ.get("AGENT_BRIDGE_DIR", "C:/Users/leonv/assistant/projecten/agent-bridge")
)
START_AUTOPILOT = BRIDGE_DIR / "start_autopilot.ps1"
DEFAULT_STATE = ROOT / "state" / "autonomy-heartbeat.json"
# Per Leon 2026-05-02T07:03Z, return to duo mode: Claude + Codex only.
DEFAULT_RECIPIENTS = ("codex", "claude")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_ts(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            body TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def pending_work(conn: sqlite3.Connection, recipients: list[str]) -> tuple[list[str], list[str]]:
    if not recipients:
        return [], []

    unread_rows = conn.execute(
        f"""
        SELECT to_agent, COUNT(*) AS count
        FROM messages
        WHERE read=0 AND to_agent IN ({placeholders(recipients)})
        GROUP BY to_agent
        """,
        recipients,
    ).fetchall()
    unread = [f"{row['to_agent']}:{row['count']}" for row in unread_rows]

    running: list[str] = []
    if table_exists(conn, "autopilot_dispatches"):
        running_rows = conn.execute(
            f"""
            SELECT agent, COUNT(*) AS count
            FROM autopilot_dispatches
            WHERE status='running' AND agent IN ({placeholders(recipients)})
            GROUP BY agent
            """,
            recipients,
        ).fetchall()
        running = [f"{row['agent']}:{row['count']}" for row in running_rows]

    return unread, running


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def due(state: dict, interval_seconds: float) -> tuple[bool, str]:
    last = parse_ts(state.get("last_sent_ts"))
    if last is None:
        return True, "no previous heartbeat recorded"
    age = (utc_now() - last).total_seconds()
    if age >= interval_seconds:
        return True, f"last heartbeat was {age:.0f}s ago"
    remaining = interval_seconds - age
    return False, f"next heartbeat due in {remaining:.0f}s"


def heartbeat_body(now: str) -> str:
    return f"""[AUTONOMY HEARTBEAT]
Trigger fired at {now}.

Ga autonoom verder in C:/Users/leonv/survival-agents. Compute is bedoeld om 24/7
te benutten voor concrete overlevingsacties; voorkom alleen duplicate noise en
publieke spam.

Duo-mode is canonical sinds Leon 2026-05-02T07:03Z: active agents are claude
and codex only. Gemini/Grok blijven buiten standaard Telegram/autopilot/
heartbeat fan-out tenzij Leon dit expliciet wijzigt. Burn: 1 EUR/dag totaal.

Checklist:
1. Lees bridge_read en stem af met de andere actieve agent (geen consensus nodig: lees, accepteer, ga aan de slag; bridge-updates signal-only, details in repo-journal).
2. Controleer alleen relevante ops/state, research, accountlog en walletstatus; gebruik voor inbox-triage `python ops/email_reader.py --unread --exclude-noise --limit 10`.
3. Kies een concrete inkomstenactie met de hoogste kans op resultaat; respecteer lanes: claude=longform/Farcaster/funnel/research, codex=GitHub outbound/code/browser-flows.
4. Gebruik Leon's 2026-04-30 mandaat: bouw accounts/vault/browser/TOTP zelf en rapporteer achteraf.
5. Escaleer alleen voor telefoon-2FA, KYC/ID, onoplosbare CAPTCHA, of spend buiten ops/spend_policy.md.
6. Multi-instance live: autopilot blokkeert niet meer op concurrente dispatches; werk gerust lang aan een taak. Watchdog is uit — geen tijdslimiet meer.
7. Concurrente file-edits: lock via .lockfile / SQLite / vergelijk-en-merge.
8. Gebruik vault/browserprofiel uit ops/autonomous_ops.md; print nooit secrets.
9. Eindig met een breed post-mortem (tooling, site, copy, outreach, wallet, bridge, brand, heartbeat-prompt, ops procedures): wat ging fout / wat verbeterd / waarom. Fix kleine dingen direct, append aan ops/improvements.md.
10. Sluit af met bridge_read zodat nieuwe berichten niet blijven wachten.
"""


def emit(conn: sqlite3.Connection, recipients: list[str], sender: str) -> list[int]:
    now = iso_now()
    body = heartbeat_body(now)
    ids: list[int] = []
    for recipient in recipients:
        cur = conn.execute(
            "INSERT INTO messages (ts, from_agent, to_agent, body) VALUES (?,?,?,?)",
            (now, sender, recipient, body),
        )
        ids.append(int(cur.lastrowid))
    return ids


def ensure_autopilot() -> None:
    if not START_AUTOPILOT.exists():
        print(f"autopilot keepalive skipped: missing {START_AUTOPILOT}")
        return
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(START_AUTOPILOT),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"autopilot keepalive failed: {exc}")
        return

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if stdout:
        print(stdout)
    if stderr:
        print(stderr)
    if result.returncode != 0:
        print(f"autopilot keepalive exit code: {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit conservative autonomy heartbeats.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="agent-bridge SQLite DB path")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="heartbeat state JSON path")
    parser.add_argument("--interval-hours", type=float, default=24.0)
    parser.add_argument("--recipient", action="append", dest="recipients")
    parser.add_argument("--sender", default="autonomy-heartbeat")
    parser.add_argument("--force", action="store_true", help="send even if not due")
    parser.add_argument("--check", action="store_true", help="print status without sending")
    parser.add_argument(
        "--no-ensure-autopilot",
        action="store_true",
        help="do not run the idempotent agent-bridge autopilot start script first",
    )
    args = parser.parse_args()

    if not args.no_ensure_autopilot:
        ensure_autopilot()

    recipients = args.recipients or list(DEFAULT_RECIPIENTS)
    interval_seconds = max(args.interval_hours * 3600, 60)
    state_path = Path(args.state)
    state = load_state(state_path)

    with connect(Path(args.db)) as conn:
        unread, running = pending_work(conn, recipients)

        is_due, reason = due(state, interval_seconds)
        print(f"heartbeat status: due={is_due} reason={reason}")
        if unread:
            print(f"unread pending: {', '.join(unread)}")
        if running:
            print(f"running dispatches: {', '.join(running)}")

        if args.check:
            return 0

        if not args.force and unread:
            print("skipping: existing unread work")
            return 0

        if not args.force and not is_due:
            print("skipping: heartbeat interval not reached")
            return 0

        ids = emit(conn, recipients, args.sender)

    state.update(
        {
            "last_sent_ts": iso_now(),
            "last_message_ids": ids,
            "recipients": recipients,
            "interval_hours": args.interval_hours,
        }
    )
    save_state(state_path, state)
    print(f"sent heartbeat messages: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
