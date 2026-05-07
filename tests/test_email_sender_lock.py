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


class FakeSignatureFailureClient:
    def __init__(self) -> None:
        self.created_count = 0
        self.sent_count = 0

    def create_message(self, recipients, subject, body):
        self.created_count += 1
        return FakeMessage()

    def send_message(self, msg, is_html=False):
        self.sent_count += 1
        raise Exception("Invalid or missing message signature")


def write_suppression_file(root: Path, rows: str = "") -> Path:
    path = root / "email_suppression_list.md"
    path.write_text(
        "| date | email | reason |\n"
        "| --- | --- | --- |\n"
        f"{rows}",
        encoding="utf-8",
    )
    return path


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

    def test_get_client_uses_validated_reader_client(self) -> None:
        fake_client = FakeProtonClient()

        with patch.object(email_sender, "get_reader_client", return_value=fake_client):
            client = email_sender.get_client()

        self.assertIs(client, fake_client)

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

    def test_transient_lock_is_released_by_log_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "outbound.md"
            log_file.write_text(
                "\n".join(
                    [
                        "## Targets (GitHub-sourced read-only discovery)",
                        "",
                        "| ts (UTC) | channel | target | source | personalization | sent | status |",
                        "| --- | --- | --- | --- | --- | --- | --- |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            locks_dir = root / "locks"

            with (
                patch.object(email_sender, "LOG_FILE", log_file),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
            ):
                email_sender.append_log_row(
                    "lead@example.dev",
                    "Follow-up",
                    "unit-test",
                    "parallel-safe append",
                    "sent",
                )

            self.assertIn("| lead@example.dev | unit-test |", log_file.read_text())
            self.assertFalse(any(locks_dir.glob("log_outbound_cold_dm_2026-05-02-*.lock")))

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
            suppression_path = write_suppression_file(root)
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
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client", return_value=fake_client),
                patch.object(email_sender, "append_log_row") as append_log_row,
                patch.object(sys, "argv", argv),
            ):
                email_sender.main()
                self.assertTrue(any(locks_dir.glob("recipient_lead@example.dev-*.lock")))
                self.assertTrue(any(locks_dir.glob("dedupe_lead@example.dev_*.lock")))

        self.assertIsNotNone(fake_client.sent)
        self.assertEqual(fake_client.created["recipients"], ["lead@example.dev"])
        append_log_row.assert_called_once()

    def test_explicit_lock_cannot_bypass_recipient_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("One clean response to a warm lead.", encoding="utf-8")
            locks_dir = root / "locks"
            suppression_path = write_suppression_file(root)
            argv = [
                "email_sender.py",
                "--to",
                "Lead@Example.dev",
                "--subject",
                "Warm reply",
                "--body-file",
                str(body_path),
                "--execute",
                "--lock",
                "custom-thread-lock",
            ]

            with (
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client", return_value=FakeProtonClient()),
                patch.object(email_sender, "append_log_row"),
                patch.object(sys, "argv", argv),
            ):
                email_sender.main()
                self.assertTrue(any(locks_dir.glob("recipient_lead@example.dev-*.lock")))
                self.assertTrue(any(locks_dir.glob("topic_custom-thread-lock-*.lock")))

            retry_argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Warm reply",
                "--body-file",
                str(body_path),
                "--execute",
                "--lock",
                "different-thread-lock",
            ]

            with (
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client") as get_client,
                patch.object(email_sender, "append_log_row"),
                patch.object(sys, "argv", retry_argv),
            ):
                with self.assertRaises(SystemExit) as raised:
                    email_sender.main()

        self.assertIn("recipient:lead@example.dev", str(raised.exception))
        get_client.assert_not_called()

    def test_exact_body_duplicate_blocks_after_recipient_lock_expires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            locks_dir = root / "locks"
            with patch.object(email_sender, "LOCKS_DIR", locks_dir):
                paths = email_sender.acquire_live_send_locks(
                    to_addr="lead@example.dev",
                    subject="Warm reply",
                    body="Same body.",
                    extra_topic="first-topic",
                )
                stale = time.time() - (email_sender.RECIPIENT_LOCK_TTL_SECONDS + 30)
                for path in paths:
                    if path.name.startswith("recipient_"):
                        os.utime(path, (stale, stale))

                with self.assertRaises(SystemExit) as raised:
                    email_sender.acquire_live_send_locks(
                        to_addr="lead@example.dev",
                        subject="Warm reply",
                        body="Same body.",
                        extra_topic="second-topic",
                    )

        self.assertIn("dedupe:lead@example.dev", str(raised.exception))

    def test_explicit_lock_also_keeps_recipient_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("Contributor setup reply.", encoding="utf-8")
            locks_dir = root / "locks"
            suppression_path = write_suppression_file(root)
            fake_client = FakeProtonClient()
            argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Contributor setup",
                "--body-file",
                str(body_path),
                "--execute",
                "--lock",
                "contributor-setup",
            ]

            with (
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client", return_value=fake_client),
                patch.object(email_sender, "append_log_row"),
                patch.object(sys, "argv", argv),
            ):
                email_sender.main()
                self.assertTrue(any(locks_dir.glob("recipient_lead@example.dev-*.lock")))
                self.assertTrue(any(locks_dir.glob("topic_contributor-setup-*.lock")))

    def test_execute_refuses_different_explicit_lock_when_recipient_is_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("Contributor setup reply.", encoding="utf-8")
            locks_dir = root / "locks"
            suppression_path = write_suppression_file(root)
            with patch.object(email_sender, "LOCKS_DIR", locks_dir):
                email_sender.acquire_send_lock(
                    "recipient:lead@example.dev",
                    ttl_seconds=email_sender.RECIPIENT_LOCK_TTL_SECONDS,
                )

            argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Contributor setup",
                "--body-file",
                str(body_path),
                "--execute",
                "--lock",
                "different-topic",
            ]

            with (
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client") as get_client,
                patch.object(sys, "argv", argv),
            ):
                with self.assertRaises(SystemExit) as raised:
                    email_sender.main()

        self.assertIn("REFUSE: active send lock", str(raised.exception))
        self.assertIn("lead@example.dev", str(raised.exception))
        get_client.assert_not_called()

    def test_signature_failure_does_not_auto_resend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("Contributor setup reply.", encoding="utf-8")
            locks_dir = root / "locks"
            session_file = root / "proton_session.pickle"
            session_file.write_text("stale", encoding="utf-8")
            suppression_path = write_suppression_file(root)
            fake_client = FakeSignatureFailureClient()
            argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Contributor setup",
                "--body-file",
                str(body_path),
                "--execute",
            ]

            with (
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "SESSION_FILE", session_file),
                patch.object(email_sender, "get_client", return_value=fake_client),
                patch.object(email_sender, "get_fresh_client") as get_fresh_client,
                patch.object(email_sender, "append_log_row") as append_log_row,
                patch.object(sys, "argv", argv),
            ):
                with self.assertRaises(SystemExit) as raised:
                    email_sender.main()

        self.assertIn("send status ambiguous", str(raised.exception))
        self.assertEqual(fake_client.created_count, 1)
        self.assertEqual(fake_client.sent_count, 1)
        self.assertFalse(session_file.exists())
        get_fresh_client.assert_not_called()
        append_log_row.assert_not_called()

    def test_dry_run_without_explicit_lock_does_not_create_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("Dry-run body.", encoding="utf-8")
            locks_dir = root / "locks"
            suppression_path = write_suppression_file(root)
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
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client") as get_client,
                patch.object(sys, "argv", argv),
            ):
                email_sender.main()

        self.assertFalse(locks_dir.exists())
        get_client.assert_not_called()

    def test_outbound_text_guard_blocks_tool_call_artifact_before_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("draft " + "</" + "parameter>", encoding="utf-8")
            locks_dir = root / "locks"
            argv = [
                "email_sender.py",
                "--to",
                "lead@example.dev",
                "--subject",
                "Guarded draft",
                "--body-file",
                str(body_path),
            ]

            with (
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client") as get_client,
                patch.object(sys, "argv", argv),
            ):
                with self.assertRaises(SystemExit) as raised:
                    email_sender.main()

        self.assertEqual(raised.exception.code, 2)
        self.assertFalse(locks_dir.exists())
        get_client.assert_not_called()

    def test_suppression_list_parser_reads_exact_email_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "email_suppression_list.md"
            path.write_text(
                "\n".join(
                    [
                        "| date | email | reason |",
                        "| --- | --- | --- |",
                        "| 2026-05-03 | EndiSukaj@gmail.com | STOP |",
                        "| 2026-05-03 | not-an-email | ignored |",
                    ]
                ),
                encoding="utf-8",
            )

            suppressed = email_sender.load_suppressed_emails(path)

        self.assertEqual(suppressed, {"endisukaj@gmail.com"})

    def test_missing_suppression_list_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing_suppression_list.md"

            with self.assertRaises(SystemExit) as raised:
                email_sender.load_suppressed_emails(path)

        self.assertIn("suppression list missing", str(raised.exception))

    def test_suppressed_recipient_refuses_before_lock_and_proton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_path = root / "body.txt"
            body_path.write_text("We can scope the review if useful.", encoding="utf-8")
            suppression_path = root / "email_suppression_list.md"
            suppression_path.write_text(
                "| date | email | reason |\n"
                "| --- | --- | --- |\n"
                "| 2026-05-03 | endisukaj@gmail.com | STOP |\n",
                encoding="utf-8",
            )
            locks_dir = root / "locks"
            argv = [
                "email_sender.py",
                "--to",
                "EndiSukaj@gmail.com",
                "--subject",
                "Scoped review",
                "--body-file",
                str(body_path),
                "--execute",
            ]

            with (
                patch.object(email_sender, "SUPPRESSION_FILE", suppression_path),
                patch.object(email_sender, "LOCKS_DIR", locks_dir),
                patch.object(email_sender, "get_client") as get_client,
                patch.object(email_sender, "append_log_row") as append_log_row,
                patch.object(sys, "argv", argv),
            ):
                with self.assertRaises(SystemExit) as raised:
                    email_sender.main()

        self.assertIn("suppressed recipients", str(raised.exception))
        self.assertFalse(locks_dir.exists())
        get_client.assert_not_called()
        append_log_row.assert_called_once()
        self.assertEqual(
            append_log_row.call_args.kwargs["status"],
            "refused_suppressed_opt_out",
        )


if __name__ == "__main__":
    unittest.main()
