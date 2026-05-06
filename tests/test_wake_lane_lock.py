import datetime as dt
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tools import wake_lane_lock as locks


class WakeLaneLockTests(unittest.TestCase):
    def open_db(self, path: Path):
        return locks.connect(path)

    def test_intent_hash_normalization_contract(self) -> None:
        self.assertEqual(
            locks.normalize_intent("  Build\tcalendar_nudge   tool "),
            "build calendar nudge tool",
        )
        self.assertEqual(
            locks.intent_hash("build calendar nudge tool"),
            locks.intent_hash("Build calendar_nudge tool"),
        )
        self.assertEqual(locks.intent_hash("Build calendar_nudge tool"), "e80b8eca97dccb29")
        self.assertNotEqual(
            locks.intent_hash("calendar_nudge.py"),
            locks.intent_hash("calendar nudge py"),
        )

    def test_target_surface_validation_contract(self) -> None:
        self.assertEqual(
            locks.normalize_surface(" TOOL_BUILD:tools\\calendar_nudge.py "),
            "tool_build:tools/calendar_nudge.py",
        )
        self.assertEqual(locks.normalize_surface("farcaster_reply"), "farcaster_reply")
        with self.assertRaisesRegex(ValueError, "target surface must match"):
            locks.normalize_surface("farcaster-reply")
        with self.assertRaisesRegex(ValueError, "target surface must match"):
            locks.normalize_surface("fc_reply")
        with self.assertRaisesRegex(ValueError, "target surface must match"):
            locks.normalize_surface("fc reply")

    def test_default_ttl_is_15_minutes_with_seconds_override(self) -> None:
        self.assertEqual(locks.DEFAULT_TTL_SECONDS, 900)
        args = locks.build_parser().parse_args(
            [
                "acquire",
                "--intent",
                "long browser job",
                "--target",
                "browser_flow:coderlegion",
                "--ttl",
                "1800",
            ]
        )
        self.assertEqual(args.ttl, 1800)

    def test_acquire_blocks_fresh_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wake_locks.db"
            now = dt.datetime(2026, 5, 6, 9, 30, tzinfo=dt.UTC)
            key = locks.intent_hash("calendar nudge")
            with closing(self.open_db(db)) as conn:
                first = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="tool_build:tools/calendar_nudge.py",
                    intent="calendar nudge",
                    owner="codex",
                    ttl=dt.timedelta(minutes=30),
                    now=now,
                    pid=111,
                )
                second = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="TOOL_BUILD:TOOLS\\CALENDAR_NUDGE.PY",
                    intent="calendar nudge",
                    owner="claude",
                    ttl=dt.timedelta(minutes=30),
                    now=now + dt.timedelta(minutes=5),
                    pid=222,
                )

            self.assertTrue(first.acquired)
            self.assertFalse(second.acquired)
            self.assertEqual(second.record.owner, "codex")
            self.assertEqual(second.record.token, first.record.token)

    def test_expired_lock_is_stolen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wake_locks.db"
            now = dt.datetime(2026, 5, 6, 9, 30, tzinfo=dt.UTC)
            key = locks.intent_hash("calendar nudge")
            with closing(self.open_db(db)) as conn:
                first = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="tool_build:tools/calendar_nudge.py",
                    intent="calendar nudge",
                    owner="codex",
                    ttl=dt.timedelta(minutes=10),
                    now=now,
                    pid=111,
                )
                second = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="tool_build:tools/calendar_nudge.py",
                    intent="calendar nudge",
                    owner="claude",
                    ttl=dt.timedelta(minutes=10),
                    now=now + dt.timedelta(minutes=11),
                    pid=222,
                )

            self.assertTrue(second.acquired)
            self.assertEqual(second.previous, first.record)
            self.assertNotEqual(second.record.token, first.record.token)
            self.assertEqual(second.record.owner, "claude")

    def test_different_surfaces_do_not_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wake_locks.db"
            now = dt.datetime(2026, 5, 6, 9, 30, tzinfo=dt.UTC)
            key = locks.intent_hash("reply follow-up")
            with closing(self.open_db(db)) as conn:
                first = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="github_issue_comment:wetware/ww#437",
                    intent="reply follow-up",
                    owner="codex",
                    ttl=dt.timedelta(minutes=30),
                    now=now,
                )
                second = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="email_send_recipient_louis",
                    intent="reply follow-up",
                    owner="claude",
                    ttl=dt.timedelta(minutes=30),
                    now=now,
                )

            self.assertTrue(first.acquired)
            self.assertTrue(second.acquired)

    def test_release_requires_matching_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wake_locks.db"
            key = locks.intent_hash("calendar nudge")
            with closing(self.open_db(db)) as conn:
                result = locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="tool_build:tools/calendar_nudge.py",
                    intent="calendar nudge",
                    owner="codex",
                    ttl=dt.timedelta(minutes=30),
                )
                self.assertFalse(
                    locks.release_lock(
                        conn,
                        key=key,
                        target_surface="tool_build:tools/calendar_nudge.py",
                        token="wrong",
                    )
                )
                self.assertTrue(
                    locks.release_lock(
                        conn,
                        key=key,
                        target_surface="tool_build:tools/calendar_nudge.py",
                        token=result.record.token,
                    )
                )
                self.assertIsNone(
                    locks.row_for(
                        conn,
                        key=key,
                        target_surface="tool_build:tools/calendar_nudge.py",
                    )
                )

    def test_force_release_writes_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wake_locks.db"
            audit = Path(tmp) / "wake_locks_audit.log"
            key = locks.intent_hash("stuck lane")
            with closing(self.open_db(db)) as conn:
                locks.acquire_lock(
                    conn,
                    key=key,
                    target_surface="github_issue_comment:wetware/ww#437",
                    intent="stuck lane",
                    owner="codex",
                    ttl=dt.timedelta(minutes=30),
                    pid=111,
                )
                released = locks.release_lock(
                    conn,
                    key=key,
                    target_surface="github_issue_comment:wetware/ww#437",
                    force=True,
                    owner="claude",
                    audit_log=audit,
                    reason="stuck token rescue",
                )
                self.assertTrue(released)
                self.assertIsNone(
                    locks.row_for(
                        conn,
                        key=key,
                        target_surface="github_issue_comment:wetware/ww#437",
                    )
                )

            [line] = audit.read_text(encoding="utf-8").splitlines()
            event = json.loads(line)
            self.assertEqual(event["event"], "force_release")
            self.assertEqual(event["intent_hash"], key)
            self.assertEqual(event["target_surface"], "github_issue_comment:wetware/ww#437")
            self.assertEqual(event["owner"], "claude")
            self.assertEqual(event["previous_owner"], "codex")
            self.assertTrue(event["released"])

    def test_prune_removes_only_expired_locks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wake_locks.db"
            now = dt.datetime(2026, 5, 6, 9, 30, tzinfo=dt.UTC)
            with closing(self.open_db(db)) as conn:
                locks.acquire_lock(
                    conn,
                    key=locks.intent_hash("old"),
                    target_surface="browser_flow:old",
                    intent="old",
                    owner="codex",
                    ttl=dt.timedelta(minutes=1),
                    now=now,
                )
                locks.acquire_lock(
                    conn,
                    key=locks.intent_hash("fresh"),
                    target_surface="browser_flow:fresh",
                    intent="fresh",
                    owner="codex",
                    ttl=dt.timedelta(minutes=30),
                    now=now,
                )

                pruned = locks.prune_expired(conn, now=now + dt.timedelta(minutes=2))
                remaining = locks.list_locks(conn)

            self.assertEqual(pruned, 1)
            self.assertEqual([record.target_surface for record in remaining], ["browser_flow:fresh"])

    def test_cli_returns_busy_exit_code_for_fresh_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "wake_locks.db")
            first = locks.main(
                [
                    "--db",
                    db,
                    "acquire",
                    "--intent",
                    "calendar nudge",
                    "--target",
                    "tool_build:tools/calendar_nudge.py",
                    "--owner",
                    "codex",
                ]
            )
            second = locks.main(
                [
                    "--db",
                    db,
                    "acquire",
                    "--intent",
                    "calendar nudge",
                    "--target",
                    "tool_build:tools/calendar_nudge.py",
                    "--owner",
                    "claude",
                ]
            )

            self.assertEqual(first, 0)
            self.assertEqual(second, 2)

    def test_cli_accepts_json_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "wake_locks.db")
            result = locks.main(
                [
                    "--db",
                    db,
                    "acquire",
                    "--intent",
                    "calendar nudge",
                    "--target",
                    "tool_build:tools/calendar_nudge.py",
                    "--json",
                ]
            )

            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
