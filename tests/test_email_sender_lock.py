import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ops import email_sender


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


if __name__ == "__main__":
    unittest.main()
