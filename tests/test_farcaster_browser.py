import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ops.farcaster_browser import (
    append_cast_log,
    append_reply_log,
    cadence_block_reason,
    count_substring,
    extract_verify_needle,
    last_successful_cast,
    prepare_cast_text,
    read_cast_text,
    reply_gate_block_reason,
    reply_cadence_block_reason,
    validate_cast_text,
    validate_reply_url,
    verify_landed,
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

    def test_rejects_xml_tool_call_closing_tag_artifacts(self) -> None:
        # Documented in MEMORY.md (2026-05-02 16:25Z): tool-call closing tags
        # leak into cast bodies via Write tool input and render verbatim on
        # Farcaster (320-char limit cuts them mid-tag). Build markers via
        # concat so this test file itself never contains the literal tag.
        for tag_name in ("content", "invoke", "parameter"):
            artifact = "honest take..." + "</" + tag_name + ">"
            error = validate_cast_text(artifact)
            self.assertIsNotNone(error, f"missed {tag_name} closing tag")
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
    VALID_URL = "https://farcaster.xyz/lthibault/0xbb649951"

    def test_validate_reply_url_accepts_permalink(self) -> None:
        self.assertIsNone(validate_reply_url(self.VALID_URL))

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

    def test_reply_gate_blocks_missing_metadata_by_default(self) -> None:
        reason = reply_gate_block_reason(
            target_url=self.VALID_URL,
            reply_text="the ipfs gateway slow read pain hit us too",
        )

        self.assertIn("reply gate missing", reason)
        self.assertIn("--cast-text", reason)

    def test_reply_gate_allows_warm_followup_bypass_with_reason(self) -> None:
        reason = reply_gate_block_reason(
            target_url=self.VALID_URL,
            reply_text="thanks, happy to send the exact patch scope",
            skip_reply_gate=True,
            reason="warm inbound follow-up after maintainer asked for scope",
        )

        self.assertIsNone(reason)

    def test_reply_gate_bypass_requires_reason(self) -> None:
        reason = reply_gate_block_reason(
            target_url=self.VALID_URL,
            reply_text="thanks, happy to send the exact patch scope",
            skip_reply_gate=True,
        )

        self.assertIn("bypass requires --reason", reason)

    def test_reply_gate_passes_with_cast_text_grounding(self) -> None:
        now = datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc)
        reason = reply_gate_block_reason(
            target_url=self.VALID_URL,
            target_cast_iso="2026-05-03T08:00:00Z",
            target_author_builds="Wetware: capability-based p2p runtime",
            target_problem="",
            target_cast_text="ipfs gateway is too slow for sub-100ms reads",
            reply_text=(
                "the ipfs gateway slow read pain hit us too: 320ms p95 over "
                "the same endpoint. workaround in commit a45cd99."
            ),
            bridge_data_point="gateway 320ms p95 measured in commit a45cd99",
            now=now,
        )

        self.assertIsNone(reason)

    def test_reply_gate_blocks_fan_thanks_cast_text(self) -> None:
        now = datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc)
        reason = reply_gate_block_reason(
            target_url=self.VALID_URL,
            target_cast_iso="2026-05-03T08:00:00Z",
            target_author_builds="Vera: founder CRM tool",
            target_cast_text="congrats on the launch, amazing work",
            reply_text="love what you are building, happy to compare notes",
            bridge_data_point="320ms p95 measured in commit a45cd99",
            now=now,
        )

        self.assertIn("reply gate failed", reason)
        self.assertIn("cast-text reads as opinion", reason)


class FarcasterReplyVerifyTests(unittest.TestCase):
    """Tests for the post_reply needle-delta verification helpers.

    Documented in MEMORY.md (refinement #7, 2026-05-03 00:30Z): the
    Farcaster composer clears on Ctrl+Enter even when server-side
    spam-dedupe silently rejects the submit, producing false-success
    rows in ops/farcaster_reply_log.md. The verify_landed helper plus
    a before/after needle count in post_reply close that gap.
    """

    def test_extract_needle_picks_longest_alpha_run(self) -> None:
        text = (
            "the ipfs gateway slow read pain hit us too: 320ms p95 over the "
            "same endpoint. workaround in commit a45cd99."
        )
        needle = extract_verify_needle(text)
        # Should be a substantive alphabetic phrase, not a digit-heavy or
        # punctuation-heavy substring.
        self.assertTrue(needle.replace(" ", "").isalpha(), needle)
        self.assertGreaterEqual(len(needle), 20)

    def test_extract_needle_falls_back_for_short_punctuation_text(self) -> None:
        # All-digit + URL reply has no qualifying alpha run, but is long
        # enough to take a literal first-N fallback.
        needle = extract_verify_needle("https://x.io/path 12345 67890 abc")
        self.assertEqual(len(needle), 20)

    def test_extract_needle_returns_empty_for_unverifiable_text(self) -> None:
        self.assertEqual(extract_verify_needle(""), "")
        self.assertEqual(extract_verify_needle("hi!"), "")

    def test_count_substring_counts_overlapping_occurrences(self) -> None:
        self.assertEqual(count_substring("abcabcabc", "abc"), 3)
        self.assertEqual(count_substring("aaaa", "aa"), 3)
        self.assertEqual(count_substring("nope", "missing"), 0)
        self.assertEqual(count_substring("", "needle"), 0)
        self.assertEqual(count_substring("haystack", ""), 0)

    def test_verify_landed_true_on_positive_delta(self) -> None:
        landed, reason = verify_landed(0, 1, "ipfs gateway slow read")
        self.assertTrue(landed)
        self.assertEqual(reason, "")

    def test_verify_landed_false_on_no_delta(self) -> None:
        # Server-side rejection: needle was already in the parent cast
        # (count=1) and stayed at 1 after submit -> no new reply landed.
        landed, reason = verify_landed(1, 1, "ipfs gateway slow read")
        self.assertFalse(landed)
        self.assertIn("server-side verify failed", reason)
        self.assertIn("1->1", reason)

    def test_verify_landed_false_when_count_drops(self) -> None:
        # Defensive: count should never drop, but if Farcaster re-renders
        # and trims something, treat as not-landed rather than
        # falsely-success.
        landed, _ = verify_landed(2, 1, "needle phrase here")
        self.assertFalse(landed)

    def test_verify_landed_optimistic_when_no_needle(self) -> None:
        # URL-only or digit-only replies have no extractable needle.
        # Falls back to optimistic success (composer-clear is the only
        # signal). Documented in extract_verify_needle docstring.
        landed, reason = verify_landed(0, 0, "")
        self.assertTrue(landed)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
