import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ops import email_sender


class FakeMessage:
    id = "message-1"


class FakeProtonClient:
    def __init__(self) -> None:
        self.created = None
        self.sent = None

    def create_message(self, recipients, subject, body):
        self.created = {
            "recipients": recipients,
            "subject": subject,
            "body": body,
        }
        return FakeMessage()

    def send_message(self, msg, is_html=False):
        self.sent = {
            "message": msg,
            "is_html": is_html,
        }


class EmailSenderLockTests(unittest.TestCase):
    def test_fresh_lock_refuses_duplicate_send_topic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            locks_dir = Path(tmp) / "locks"
            with patch.object(email_sender, "LOCKS_DIR", locks_dir):
                first = email_sender.acquire_send_lock("ben@codeslegion.com")

                with self.assertRaises(SystemExit) as raised:
                    email_sender.acquire_send_lock("ben@codeslegion.com")

        self.assertTrue(first.name.startswith("ben@codeslegion.com-"))
        self.assertIn("REFUSE: active send lock", str(raised.exception))
        self.assertIn("ben@codeslegion.com", str(raised.exception))

    def test_stale_lock_can_be_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            locks_dir = Path(tmp) / "locks"
            with patch.object(email_sender, "LOCKS_DIR", locks_dir):
                path = email_sender.acquire_send_lock("ben@codeslegion.com")
                stale = time.time() - 180
                os.utime(path, (stale, stale))

                reclaimed = email_sender.acquire_send_lock("ben@codeslegion.com")

                self.assertEqual(path, reclaimed)
                self.assertTrue(reclaimed.exists())

    def test_empty_lock_topic_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            email_sender.send_lock_path("  ")

        self.assertIn("--lock topic is empty", str(raised.exception))

    def test_lock_topic_cannot_escape_lock_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            locks_dir = Path(tmp) / "locks"
            with patch.object(email_sender, "LOCKS_DIR", locks_dir):
                path = email_sender.acquire_send_lock("../../ben@example.com")

        self.assertEqual(path.parent, locks_dir)
        self.assertNotIn("..", path.name)

    def test_execute_without_explicit_lock_defaults_to_recipient_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("I read the stale PR and can scope it.", encoding="utf-8")
            locks_dir = root / "locks"
            fake_client = FakeProtonClient()
            argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Scoped stale PR review",
                "--body-file",
                str(body_path),
                "--execute",
            ]

            with (
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client", return_value=fake_client),
                patch.object(email_sender, "append_log_row") as append_log_row,
                patch.object(sys, "argv", argv),
            ):
                email_sender.main()
                self.assertTrue(any(locks_dir.glob("lead@example.dev-*.lock")))

        self.assertIsNotNone(fake_client.sent)
        self.assertEqual(fake_client.created["recipients"], ["lead@example.dev"])
        append_log_row.assert_called_once()

    def test_dry_run_without_explicit_lock_does_not_create_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("Dry-run body.", encoding="utf-8")
            locks_dir = root / "locks"
            argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Dry run",
                "--body-file",
                str(body_path),
            ]

            with (
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client") as get_client,
                patch.object(sys, "argv", argv),
            ):
                email_sender.main()

        self.assertFalse(locks_dir.exists())
        get_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
