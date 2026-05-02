import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ops.farcaster_browser import (
    append_cast_log,
    append_reply_log,
    cadence_block_reason,
    last_successful_cast,
    prepare_cast_text,
    read_cast_text,
    reply_cadence_block_reason,
    validate_cast_text,
    validate_reply_url,
)


class FarcasterBrowserTextTests(unittest.TestCase):
    def test_read_cast_text_from_file_preserves_dollar_amounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cast.txt"
            path.write_text("$100 wallet\n$1/day burn\n", encoding="utf-8")

            self.assertEqual(read_cast_text(from_file=path), "$100 wallet\n$1/day burn")

    def test_rejects_suspicious_shell_escape_artifacts(self) -> None:
        error = validate_cast_text("literal \\00 wallet and \\/day burn")

        self.assertIn("Suspicious escape marker", error)

    def test_rejects_non_ascii_for_predictable_browser_input(self) -> None:
        error = validate_cast_text("Compute is not free - 1 euro/day")
        self.assertIsNone(error)

        error = validate_cast_text("Compute is not free - €1/day")
        self.assertIn("non-ASCII", error)

    def test_truncates_after_validation(self) -> None:
        self.assertEqual(len(prepare_cast_text("a" * 321)), 320)

    def test_cadence_blocks_recent_successful_cast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cast-log.md"
            path.write_text(
                "2026-04-30T21:18Z | claude | test | success | reason: unit\n",
                encoding="utf-8",
            )

            reason = cadence_block_reason(
                log_path=path,
                now=datetime(2026, 4, 30, 21, 30, tzinfo=timezone.utc),
            )

            self.assertIn("cadence block", reason)
            self.assertIn("2026-04-30T21:18Z", reason)

    def test_cadence_allows_after_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cast-log.md"
            path.write_text(
                "2026-04-30T21:18Z | claude | test | success | reason: unit\n",
                encoding="utf-8",
            )

            reason = cadence_block_reason(
                log_path=path,
                now=datetime(2026, 4, 30, 21, 49, tzinfo=timezone.utc),
            )

            self.assertIsNone(reason)

    def test_append_cast_log_records_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cast-log.md"

            append_cast_log(
                agent="codex",
                description="unit cast",
                text="hello world",
                reason="unit test",
                log_path=path,
            )

            self.assertEqual(last_successful_cast(path).tzinfo, timezone.utc)
            line = path.read_text(encoding="utf-8")
            self.assertIn("codex | unit cast (11 chars) | success | reason: unit test", line)


class FarcasterReplyTests(unittest.TestCase):
    def test_validate_reply_url_accepts_permalink(self) -> None:
        self.assertIsNone(
            validate_reply_url("https://farcaster.xyz/lthibault/0xbb649951")
        )

    def test_validate_reply_url_rejects_non_farcaster(self) -> None:
        error = validate_reply_url("https://twitter.com/user/status/123")
        self.assertIn("must start with", error)

    def test_validate_reply_url_rejects_root_path(self) -> None:
        error = validate_reply_url("https://farcaster.xyz/lthibault")
        self.assertIn("cast permalink", error)

    def test_validate_reply_url_rejects_whitespace(self) -> None:
        error = validate_reply_url("https://farcaster.xyz/u/0xab cd")
        self.assertIn("whitespace", error)

    def test_append_reply_log_records_target_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reply-log.md"
            append_reply_log(
                agent="claude",
                target_url="https://farcaster.xyz/lthibault/0xbb649951",
                text="real gap, lived experience here",
                reason="unit",
                log_path=path,
            )
            line = path.read_text(encoding="utf-8")
            self.assertIn("claude | reply -> https://farcaster.xyz/lthibault/0xbb649951", line)
            self.assertIn("(31 chars) | success | reason: unit", line)

    def test_reply_cadence_blocks_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reply-log.md"
            path.write_text(
                "2026-05-02T13:40Z | claude | reply -> https://farcaster.xyz/u/0xab | hi (2 chars) | success | reason: unit\n",
                encoding="utf-8",
            )
            reason = reply_cadence_block_reason(
                log_path=path,
                now=datetime(2026, 5, 2, 13, 41, tzinfo=timezone.utc),
            )
            self.assertIn("reply cadence block", reason)

    def test_reply_cadence_allows_after_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reply-log.md"
            path.write_text(
                "2026-05-02T13:40Z | claude | reply -> https://farcaster.xyz/u/0xab | hi (2 chars) | success | reason: unit\n",
                encoding="utf-8",
            )
            reason = reply_cadence_block_reason(
                log_path=path,
                now=datetime(2026, 5, 2, 13, 44, tzinfo=timezone.utc),
            )
            self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
