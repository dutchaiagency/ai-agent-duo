import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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

    def test_latest_successful_reply_for_url_uses_matching_metadata(self) -> None:
        tmp = Path("tmp-farcaster-reply-log.md")
        try:
            tmp.write_text(
                "2026-05-02T22:00Z | claude | reply -> https://farcaster.xyz/a/0xold | older target | success | reason\n"
                "2026-05-02T23:00Z | claude | reply -> https://farcaster.xyz/a/0xnew | newest target | success | reason\n",
                encoding="utf-8",
            )

            reply = observe.latest_successful_reply_for_url(
                tmp,
                "https://farcaster.xyz/a/0xold",
            )
        finally:
            tmp.unlink(missing_ok=True)

        self.assertIsNotNone(reply)
        self.assertEqual(reply.at, datetime(2026, 5, 2, 22, 0, tzinfo=UTC))
        self.assertEqual(reply.preview, "older target")

    def test_unobserved_recent_successful_replies_skips_verified_and_dedupes(self) -> None:
        tmp = Path("tmp-farcaster-reply-log.md")
        try:
            tmp.write_text(
                "2026-05-02T20:00Z | claude | reply -> https://farcaster.xyz/a/0xverified | first | success | reason\n"
                "2026-05-02T20:40Z | codex | verify -> https://farcaster.xyz/a/0xverified | needle present | state\n"
                "2026-05-02T22:00Z | claude | reply -> https://farcaster.xyz/a/0xdup | short | success | reason\n"
                "2026-05-02T22:00Z | claude | reply -> https://farcaster.xyz/a/0xdup | longer preview | success | reason\n",
                encoding="utf-8",
            )

            replies = observe.unobserved_recent_successful_replies(
                tmp,
                now=datetime(2026, 5, 2, 23, 0, tzinfo=UTC),
                since=timedelta(hours=24),
            )
        finally:
            tmp.unlink(missing_ok=True)

        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].url, "https://farcaster.xyz/a/0xdup")
        self.assertEqual(replies[0].preview, "longer preview")

    def test_unobserved_recent_successful_replies_keeps_later_same_url_reply(self) -> None:
        tmp = Path("tmp-farcaster-reply-log.md")
        try:
            tmp.write_text(
                "2026-05-02T20:00Z | claude | reply -> https://farcaster.xyz/a/0xsame | old needle text here | success | reason\n"
                "2026-05-02T20:40Z | codex | verify -> https://farcaster.xyz/a/0xsame | needle 'old needle text here' present | state\n"
                "2026-05-02T22:00Z | claude | reply -> https://farcaster.xyz/a/0xsame | new needle text here | success | reason\n",
                encoding="utf-8",
            )

            replies = observe.unobserved_recent_successful_replies(
                tmp,
                now=datetime(2026, 5, 2, 23, 0, tzinfo=UTC),
                since=timedelta(hours=24),
            )
        finally:
            tmp.unlink(missing_ok=True)

        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].preview, "new needle text here")

    def test_reply_has_later_verification_matches_quoted_partial_needles(self) -> None:
        reply = observe.FarcasterReply(
            at=datetime(2026, 5, 2, 23, 58, tzinfo=UTC),
            agent="claude",
            url="https://farcaster.xyz/lthibault/0x180793f2",
            preview=(
                "Yes -- happy to chat. dutchaiagents@proton.me works for scheduling. "
                "We'll bring the actual collision log: 6 races in 48h."
            ),
            status="success",
            reason="inbound",
        )
        verifications = (
            observe.FarcasterVerification(
                at=datetime(2026, 5, 3, 0, 23, tzinfo=UTC),
                agent="codex",
                url="https://farcaster.xyz/lthibault/0x180793f2",
                note="needle 'Running 2 autonomous agents in a shared checkout' present | chat request visible",
            ),
            observe.FarcasterVerification(
                at=datetime(2026, 5, 3, 0, 30, tzinfo=UTC),
                agent="claude",
                url="https://farcaster.xyz/lthibault/0x180793f2",
                note=(
                    "needles 'collision log' / '6 races' / 'Yes -- happy' / "
                    "'happy to chat' / 'scheduling' all count==1"
                ),
            ),
        )

        self.assertTrue(
            observe.reply_has_later_verification(
                reply,
                verifications,
                require_needle=True,
            )
        )

    def test_reply_has_later_verification_rejects_unrelated_quoted_needle(self) -> None:
        reply = observe.FarcasterReply(
            at=datetime(2026, 5, 2, 23, 58, tzinfo=UTC),
            agent="claude",
            url="https://farcaster.xyz/lthibault/0x180793f2",
            preview="Yes -- happy to chat. dutchaiagents@proton.me works for scheduling.",
            status="success",
            reason="inbound",
        )
        verifications = (
            observe.FarcasterVerification(
                at=datetime(2026, 5, 3, 0, 23, tzinfo=UTC),
                agent="codex",
                url="https://farcaster.xyz/lthibault/0x180793f2",
                note="needle 'Running 2 autonomous agents in a shared checkout' present | chat request visible",
            ),
        )

        self.assertFalse(
            observe.reply_has_later_verification(
                reply,
                verifications,
                require_needle=True,
            )
        )

    def test_default_needle_uses_stable_prefix(self) -> None:
        self.assertEqual(
            observe.default_needle("4 cold emails this week from our agents... (294 chars)"),
            "4 cold emails this week from our agents",
        )

    def test_default_agent_name_prefers_runtime_agent_env(self) -> None:
        with patch.dict("os.environ", {"AGENT_NAME": "claude", "BRIDGE_AGENT_NAME": "codex"}, clear=True):
            self.assertEqual(observe.default_agent_name(), "claude")

        with patch.dict("os.environ", {"BRIDGE_AGENT_NAME": "claude"}, clear=True):
            self.assertEqual(observe.default_agent_name(), "claude")

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(observe.default_agent_name(), "codex")

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

    def test_sweep_state_snapshot_path_marks_batch_output(self) -> None:
        path = observe.sweep_state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 23, 40, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/farcaster-reply-observe-sweep-2026-05-02-codex-agent-2340.md",
        )


if __name__ == "__main__":
    unittest.main()
