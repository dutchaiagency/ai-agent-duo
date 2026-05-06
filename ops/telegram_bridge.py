#!/usr/bin/env python3
"""Two-way bridge between Telegram bot and agent-bridge.

- Polls Telegram every 5s for new messages from Leon's chat -> forwards to
  agent-bridge as leon->claude + leon->codex (TEAM-CHAT format).
- Polls agent-bridge every 5s for new messages to_agent='leon' -> forwards
  to Telegram via sendMessage.

State file: ops/.telegram_bridge_state.json
"""
from __future__ import annotations

import datetime
import io
import json
import re
import signal
import sqlite3
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secret_vault import SecretVault  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import calendar_nudge  # noqa: E402

STATE_FILE = ROOT / "ops" / ".telegram_bridge_state.json"
BRIDGE_DB = "C:/Users/leonv/assistant/projecten/agent-bridge/messages.db"
POLL_INTERVAL = 5
CALENDAR_NUDGE_INTERVAL = 60
API_BASE = "https://api.telegram.org/bot{token}"
# Per Leon 2026-05-02: gemini removed too. Duo only: claude + codex.
RECIPIENTS = ("claude", "codex")

TEAM_PROMPT = """[TEAM-CHAT vanuit Leon - via Telegram bot]

Leon stelt deze vraag aan {recipients} tegelijk via Telegram. Reageer
via bridge_send naar elkaar voor korte afstemming waar nodig, en stuur het uiteindelijke
antwoord naar recipient "leon" - dat verschijnt automatisch terug in
Leon's Telegram chat via deze bridge.

Leon's bericht:
{sep}
{text}
{sep}"""

SEP = "-" * 31


def recipient_list_text() -> str:
    if len(RECIPIENTS) <= 1:
        return ", ".join(RECIPIENTS)
    return ", ".join(RECIPIENTS[:-1]) + " EN " + RECIPIENTS[-1]


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"telegram_offset": 0, "last_bridge_id": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def init_last_bridge_id(state: dict) -> None:
    if state["last_bridge_id"] == 0:
        con = sqlite3.connect(BRIDGE_DB)
        max_id = con.execute("SELECT MAX(id) FROM messages").fetchone()[0] or 0
        con.close()
        state["last_bridge_id"] = max_id
        save_state(state)


def telegram_to_bridge(state: dict, api: str, chat_id: int) -> int:
    params: dict = {"timeout": 0}
    if state["telegram_offset"]:
        params["offset"] = state["telegram_offset"] + 1
    try:
        resp = requests.get(f"{api}/getUpdates", params=params, timeout=15)
        data = resp.json()
    except Exception as exc:
        print(f"[bridge] tg getUpdates error: {exc}", flush=True)
        return 0
    if not data.get("ok"):
        print(f"[bridge] tg getUpdates not ok: {data}", flush=True)
        return 0
    forwarded = 0
    for upd in data.get("result", []):
        state["telegram_offset"] = upd["update_id"]
        message = upd.get("message") or upd.get("edited_message") or {}
        if message.get("chat", {}).get("id") != chat_id:
            continue
        text = (message.get("text") or "").strip()
        if not text:
            continue
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        body = TEAM_PROMPT.format(text=text, sep=SEP, recipients=recipient_list_text())
        con = sqlite3.connect(BRIDGE_DB)
        cur = con.cursor()
        for recipient in RECIPIENTS:
            cur.execute(
                "INSERT INTO messages (ts, from_agent, to_agent, body, read) VALUES (?, 'leon', ?, ?, 0)",
                (ts, recipient, body),
            )
        con.commit()
        con.close()
        forwarded += 1
        print(f"[bridge] tg->bridge: {text[:80]!r}", flush=True)
    save_state(state)
    return forwarded


def bridge_to_telegram(state: dict, api: str, chat_id: int) -> int:
    con = sqlite3.connect(BRIDGE_DB)
    rows = con.execute(
        "SELECT id, ts, from_agent, body FROM messages WHERE to_agent='leon' AND id > ? ORDER BY id",
        (state["last_bridge_id"],),
    ).fetchall()
    con.close()
    sent = 0
    for mid, ts, sender, body in rows:
        # don't echo Telegram-bridge's own outputs (prevent loops if anything ever inserts as "leon")
        if sender == "leon":
            state["last_bridge_id"] = mid
            continue
        prefix = f"[{sender}] " if sender not in ("autopilot",) else f"[{sender}]\n"
        text = prefix + body
        if len(text) > 3900:
            text = text[:3900] + "...\n[truncated]"
        try:
            r = requests.post(
                f"{api}/sendMessage",
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                timeout=15,
            )
            if r.ok and r.json().get("ok"):
                sent += 1
                print(f"[bridge] bridge#{mid} ({sender}) -> tg", flush=True)
            else:
                print(f"[bridge] tg sendMessage failed for #{mid}: {r.status_code} {r.text[:200]}", flush=True)
                # advance anyway to avoid infinite retry loop on a malformed body
        except Exception as exc:
            print(f"[bridge] tg sendMessage error #{mid}: {exc}", flush=True)
        state["last_bridge_id"] = mid
    if rows:
        save_state(state)
    return sent


def calendar_nudge_needs_log(stdout: str, stderr: str) -> bool:
    if stderr.strip():
        return True
    match = re.search(r"\bsummary:\s*fired=(\d+)\b", stdout)
    return bool(match and int(match.group(1)) > 0)


def log_calendar_nudge_output(stdout: str, stderr: str) -> None:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    if not combined:
        return
    print("[bridge] calendar_nudge output:", flush=True)
    for line in combined.splitlines():
        print(f"[bridge] {line}", flush=True)


def calendar_to_telegram(now: datetime.datetime | None = None) -> int:
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = calendar_nudge.run(
                calendar_nudge.DEFAULT_SCHEDULE,
                calendar_nudge.DEFAULT_STATE,
                now,
                send=True,
            )
    except Exception as exc:
        print(f"[bridge] calendar_nudge error: {exc}", flush=True)
        return 0

    out = stdout.getvalue()
    err = stderr.getvalue()
    if calendar_nudge_needs_log(out, err):
        log_calendar_nudge_output(out, err)
    return rc


def main() -> int:
    v = SecretVault()
    token = v.get("telegram:daia", "bot_token").strip()
    chat_id = int(v.get("telegram:daia", "chat_id").strip())
    api = API_BASE.format(token=token)

    state = load_state()
    init_last_bridge_id(state)

    print(
        f"[bridge] starting; tg_offset={state['telegram_offset']}, "
        f"last_bridge_id={state['last_bridge_id']}, chat_id={chat_id}",
        flush=True,
    )

    running = {"v": True}

    def stop(_sig, _frame):
        running["v"] = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    last_calendar_nudge_at = 0.0
    while running["v"]:
        try:
            telegram_to_bridge(state, api, chat_id)
            bridge_to_telegram(state, api, chat_id)
            if time.monotonic() - last_calendar_nudge_at >= CALENDAR_NUDGE_INTERVAL:
                calendar_to_telegram()
                last_calendar_nudge_at = time.monotonic()
        except Exception as exc:
            print(f"[bridge] loop error: {exc}", flush=True)
        time.sleep(POLL_INTERVAL)

    print("[bridge] stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
