import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import farcaster_reply_observe as observe


class FarcasterReplyObserveTests(unittest.TestCase):
    def test_parse_reply_log_keeps_success_rows(self) -> None:
        rows = observe.parse_reply_log(
            "2026-05-02T23:03Z | claude | reply -> https://farcaster.xyz/a/0xabc | "
            "4 cold emails this week from our agents... (294 chars) | success | reason: test\n"
            "2026-05-02T23:05Z | claude | verify -> https://farcaster.xyz/a/0xabc | needle | ok | reason\n"
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].at, datetime(2026, 5, 2, 23, 3, tzinfo=UTC))
        self.assertEqual(rows[0].url, "https://farcaster.xyz/a/0xabc")
        self.assertEqual(rows[0].status, "success")

    def test_latest_successful_reply_ignores_failed_newer_rows(self) -> None:
        tmp = Path("tmp-farcaster-reply-log.md")
        try:
            tmp.write_text(
                "2026-05-02T23:03Z | claude | reply -> https://farcaster.xyz/a/0xabc | first | success | reason\n"
                "2026-05-02T23:06Z | claude | reply -> https://farcaster.xyz/a/0xdef | second | failed | reason\n",
                encoding="utf-8",
            )

            latest = observe.latest_successful_reply(tmp)
        finally:
            tmp.unlink(missing_ok=True)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.url, "https://farcaster.xyz/a/0xabc")

    def test_default_needle_uses_stable_prefix(self) -> None:
        self.assertEqual(
            observe.default_needle("4 cold emails this week from our agents... (294 chars)"),
            "4 cold emails this week from our agents",
        )

    def test_render_report_respects_unmatured_observe_window(self) -> None:
        reply = observe.FarcasterReply(
            at=datetime(2026, 5, 2, 23, 3, tzinfo=UTC),
            agent="claude",
            url="https://farcaster.xyz/a/0xabc",
            preview="preview",
            status="success",
            reason="reason",
        )

        report = observe.render_report(
            reply,
            now=datetime(2026, 5, 2, 23, 20, tzinfo=UTC),
            min_age=timedelta(minutes=30),
            needle="preview",
            notifications_text=None,
            permalink_text=None,
        )

        self.assertIn("No casts, replies, deletes, or profile edits were performed.", report)
        self.assertIn("Observe window is not mature yet", report)
        self.assertIn("2026-05-02T23:33Z", report)

    def test_render_report_classifies_clean_render_no_notifications(self) -> None:
        reply = observe.FarcasterReply(
            at=datetime(2026, 5, 2, 23, 3, tzinfo=UTC),
            agent="claude",
            url="https://farcaster.xyz/a/0xabc",
            preview="preview",
            status="success",
            reason="reason",
        )

        report = observe.render_report(
            reply,
            now=datetime(2026, 5, 2, 23, 40, tzinfo=UTC),
            min_age=timedelta(minutes=30),
            needle="4 cold emails",
            notifications_text="No notifications yet.",
            permalink_text="@dutchaiagents 4 cold emails this week",
        )

        self.assertIn("| Reply needle | present |", report)
        self.assertIn("| Account marker | present |", report)
        self.assertIn("watch-only mode", report)

    def test_state_snapshot_path_uses_agent_and_minute(self) -> None:
        path = observe.state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 23, 40, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/farcaster-reply-observe-2026-05-02-codex-agent-2340.md",
        )


if __name__ == "__main__":
    unittest.main()
