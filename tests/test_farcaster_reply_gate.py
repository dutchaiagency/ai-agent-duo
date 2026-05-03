"""Tests for tools.farcaster_reply_gate (4-condition Farcaster reply gate)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.farcaster_reply_gate import (  # noqa: E402
    contains_data_point,
    contains_only_opinion,
    contains_problem_vocab,
    evaluate_gate,
    main,
    tokenize_content_words,
    validate_url,
)


# A reasonable reference "now": 2026-05-03T10:00Z.
NOW = datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc)
ISO_2H_AGO = (NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
ISO_8H_AGO = (NOW - timedelta(hours=8)).isoformat().replace("+00:00", "Z")
ISO_FUTURE = (NOW + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

VALID_URL = "https://farcaster.xyz/lthibault.eth/0x044b22b9"


def _passing_kwargs(**overrides):
    base = dict(
        target_url=VALID_URL,
        target_cast_iso=ISO_2H_AGO,
        target_author_builds="Wetware: capability-based p2p runtime",
        target_problem="ipfs gateway is too slow for sub-100ms reads",
        reply_text=(
            "the ipfs gateway slow read pain hit us too: 320ms p95 over the same "
            "endpoint. workaround in commit a45cd99."
        ),
        bridge_data_point="320ms p95 measured in commit a45cd99",
        now=NOW,
    )
    base.update(overrides)
    return base


class HelperTests(unittest.TestCase):
    def test_tokenize_strips_stop_words_and_short_words(self) -> None:
        words = tokenize_content_words("The gateway is slow for reads")
        # "the", "is", "for" stripped (stop-words); "slow" kept.
        self.assertIn("gateway", words)
        self.assertIn("slow", words)
        self.assertIn("reads", words)
        self.assertNotIn("the", words)
        self.assertNotIn("for", words)

    def test_problem_vocab_detection(self) -> None:
        self.assertTrue(contains_problem_vocab("our gateway is too slow"))
        self.assertTrue(contains_problem_vocab("we can't ship without this"))
        self.assertFalse(contains_problem_vocab("love this approach, agreed"))

    def test_only_opinion_detection(self) -> None:
        self.assertTrue(contains_only_opinion("congrats on the launch, amazing work"))
        self.assertFalse(
            contains_only_opinion(
                "amazing tool but the docs are missing the auth flow"
            )
        )
        # Pure problem statement isn't "only opinion" either.
        self.assertFalse(contains_only_opinion("our build is broken on windows"))

    def test_data_point_detection(self) -> None:
        self.assertTrue(contains_data_point("320ms p95"))
        self.assertTrue(contains_data_point("see https://example.com/x"))
        self.assertTrue(contains_data_point("commit a45cd99 fixed it"))
        self.assertTrue(contains_data_point("look at ops/improvements.md"))
        self.assertFalse(contains_data_point("we also struggled with this"))

    def test_validate_url_accepts_farcaster_and_warpcast(self) -> None:
        self.assertIsNone(validate_url(VALID_URL))
        self.assertIsNone(
            validate_url("https://warpcast.com/dwr.eth/0xabcdef12")
        )
        self.assertIsNotNone(validate_url("https://twitter.com/x/status/1"))
        self.assertIsNotNone(validate_url(""))


class GateEvaluationTests(unittest.TestCase):
    def test_passing_case_clears_all_conditions(self) -> None:
        result = evaluate_gate(**_passing_kwargs())
        self.assertTrue(result.passed, msg=f"expected pass, got {result.failures}")
        self.assertEqual(result.failures, ())

    def test_invalid_url_fails(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_url="not-a-url"))
        self.assertFalse(result.passed)
        self.assertTrue(any("url" in f for f in result.failures))

    def test_missing_author_builds_fails_condition_a(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_author_builds=""))
        self.assertFalse(result.passed)
        self.assertTrue(any(f.startswith("(a)") for f in result.failures))

    def test_old_cast_fails_condition_c(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_cast_iso=ISO_8H_AGO))
        self.assertFalse(result.passed)
        self.assertTrue(any(f.startswith("(c)") for f in result.failures))
        self.assertTrue(any("8.0h old" in f for f in result.failures))

    def test_future_cast_fails_condition_c(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_cast_iso=ISO_FUTURE))
        self.assertFalse(result.passed)
        self.assertTrue(any("future" in f for f in result.failures))

    def test_opinion_only_problem_fails_condition_b(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(target_problem="love this, congrats on shipping")
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(f.startswith("(b)") for f in result.failures))

    def test_problem_without_pain_vocabulary_fails_condition_b(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(target_problem="they posted about distributed systems")
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(f.startswith("(b)") for f in result.failures))

    def test_reply_without_word_overlap_fails_condition_d(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(
                reply_text="great post, our project is also exploring edge cases",
            )
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any(f.startswith("(d)") and "names" in f for f in result.failures)
        )

    def test_bridge_without_concrete_artifact_fails_condition_d(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(
                bridge_data_point="we also struggled with this exact thing",
            )
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("(d)" in f and "concrete artifact" in f for f in result.failures)
        )

    def test_empty_reply_text_fails(self) -> None:
        result = evaluate_gate(**_passing_kwargs(reply_text=""))
        self.assertFalse(result.passed)
        self.assertTrue(any("reply-text is empty" in f for f in result.failures))

    def test_empty_bridge_fails(self) -> None:
        result = evaluate_gate(**_passing_kwargs(bridge_data_point=""))
        self.assertFalse(result.passed)
        self.assertTrue(
            any("bridge-data-point is empty" in f for f in result.failures)
        )

    def test_lthibault_class_pass_replays_audit(self) -> None:
        """Regression-style: lthibault was the 1/6 that hit all 4 conditions."""
        result = evaluate_gate(
            target_url="https://farcaster.xyz/lthibault.eth/0x044b22b9",
            target_cast_iso=ISO_2H_AGO,
            target_author_builds="Wetware: capability-based p2p runtime for autonomous agents",
            target_problem="agents need a primitive to coordinate without a central scheduler",
            reply_text=(
                "the coordinate-without-scheduler primitive is exactly the gap we hit. "
                "our two agents collide on warm-inbound: one acquires a 120s file lock in "
                "ops/email_sender.py but cross-agent claim is still manual."
            ),
            bridge_data_point="120s file lock in ops/email_sender.py, commit ec57e9f",
            now=NOW,
        )
        self.assertTrue(result.passed, msg=f"expected pass, got {result.failures}")

    def test_fan_thanks_class_fails(self) -> None:
        """5/6 of the audit losses: 'your tool would help us' framing."""
        result = evaluate_gate(
            target_url=VALID_URL,
            target_cast_iso=ISO_2H_AGO,
            target_author_builds="Vera: an AI evals platform",
            target_problem="amazing platform, congrats on the launch",
            reply_text=(
                "we love what you're building, would help us a lot with our agent "
                "evaluations. excited to try it out."
            ),
            bridge_data_point="we also struggled with eval harnesses",
            now=NOW,
        )
        self.assertFalse(result.passed)
        # Should fail on (b) opinion-only AND (d) no-concrete bridge.
        self.assertTrue(any(f.startswith("(b)") for f in result.failures))
        self.assertTrue(
            any("(d)" in f and "concrete artifact" in f for f in result.failures)
        )


class CLITests(unittest.TestCase):
    def test_cli_pass_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reply = Path(tmp) / "reply.txt"
            reply.write_text(
                "the ipfs gateway slow read pain hit us too: 320ms p95 over the "
                "same endpoint. workaround in commit a45cd99.",
                encoding="utf-8",
            )
            argv = [
                "--target-url", VALID_URL,
                "--target-cast-iso", ISO_2H_AGO,
                "--target-author-builds", "Wetware: capability-based p2p runtime",
                "--target-problem", "ipfs gateway is too slow for sub-100ms reads",
                "--reply-from-file", str(reply),
                "--bridge-data-point", "320ms p95 measured in commit a45cd99",
                "--now-iso", NOW.isoformat().replace("+00:00", "Z"),
            ]
            self.assertEqual(main(argv), 0)

    def test_cli_fail_returns_nonzero(self) -> None:
        argv = [
            "--target-url", VALID_URL,
            "--target-cast-iso", ISO_8H_AGO,
            "--target-author-builds", "Wetware",
            "--target-problem", "love this, amazing work",
            "--reply-text", "great",
            "--bridge-data-point", "we also struggled",
            "--now-iso", NOW.isoformat().replace("+00:00", "Z"),
        ]
        self.assertNotEqual(main(argv), 0)


if __name__ == "__main__":
    unittest.main()
