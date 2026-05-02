import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from ops import autonomy_heartbeat


class AutonomyHeartbeatTests(unittest.TestCase):
    def test_default_recipients_are_duo_mode(self) -> None:
        self.assertEqual(autonomy_heartbeat.DEFAULT_RECIPIENTS, ("codex", "claude"))

    def test_heartbeat_body_points_inbox_triage_at_noise_filter(self) -> None:
        body = autonomy_heartbeat.heartbeat_body("2026-05-02T22:00:00+00:00")

        self.assertIn("ops/email_reader.py --unread --exclude-noise --limit 10", body)

    def test_running_dispatch_does_not_block_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "messages.db"
            state_path = Path(tmp) / "heartbeat.json"
            with closing(sqlite3.connect(db_path)) as con:
                con.execute(
                    """
                    CREATE TABLE autopilot_dispatches (
                        agent TEXT NOT NULL,
                        status TEXT NOT NULL
                    )
                    """
                )
                con.commit()
                con.execute(
                    "INSERT INTO autopilot_dispatches (agent, status) VALUES (?, ?)",
                    ("codex", "running"),
                )
                con.commit()

            result = subprocess.run(
                [
                    sys.executable,
                    "ops/autonomy_heartbeat.py",
                    "--db",
                    str(db_path),
                    "--state",
                    str(state_path),
                    "--no-ensure-autopilot",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("running dispatches: codex:1", result.stdout)
            self.assertIn("sent heartbeat messages:", result.stdout)
            with closing(sqlite3.connect(db_path)) as con:
                recipients = [
                    row[0]
                    for row in con.execute(
                        "SELECT to_agent FROM messages ORDER BY id"
                    ).fetchall()
                ]

        self.assertEqual(recipients, ["codex", "claude"])


if __name__ == "__main__":
    unittest.main()
