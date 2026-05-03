"""Tests for tools.github_reply_gate (GitHub pain-reply gate)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.github_reply_gate import (  # noqa: E402
    artifact_mentioned_in_reply,
    contains_code_artifact,
    contains_only_opinion,
    contains_problem_vocab,
    evaluate_gate,
    extract_code_artifacts,
    main,
    tokenize_content_words,
    validate_url,
)


NOW = datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc)
ISO_2D_AGO = (NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z")
ISO_9D_AGO = (NOW - timedelta(days=9)).isoformat().replace("+00:00", "Z")
ISO_FUTURE = (NOW + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

VALID_URL = "https://github.com/owner/repo/issues/123"


def _passing_kwargs(**overrides):
    base = dict(
        target_url=VALID_URL,
        target_thread_iso=ISO_2D_AGO,
        target_actor_builds="maintainer of a SaaS billing workflow",
        target_problem=(
            "checkout payment webhook retries fail to mark invoices paid"
        ),
        reply_text=(
            "You described checkout payment webhook retries that fail to mark "
            "invoices paid. Public-code check: src/billing/webhooks.ts only "
            "marks the invoice paid after the first gateway event and drops "
            "retry events in handleWebhook(). Minimal fix: add idempotent retry "
            "handling and verify with a webhook retry test."
        ),
        code_observation=(
            "src/billing/webhooks.ts:88 handleWebhook() drops retry events before "
            "marking invoices paid"
        ),
        next_step="Patch retry handling and add a webhook retry regression test.",
        now=NOW,
    )
    base.update(overrides)
    return base


class HelperTests(unittest.TestCase):
    def test_tokenize_strips_stop_words_and_short_words(self) -> None:
        words = tokenize_content_words("The checkout webhook fails for paid invoices")
        self.assertIn("checkout", words)
        self.assertIn("webhook", words)
        self.assertIn("fails", words)
        self.assertNotIn("the", words)
        self.assertNotIn("for", words)

    def test_problem_vocab_detection(self) -> None:
        self.assertTrue(contains_problem_vocab("webhook retries fail"))
        self.assertTrue(contains_problem_vocab("expected behavior says paid"))
        self.assertFalse(contains_problem_vocab("cool repo, excited to watch"))

    def test_only_opinion_detection(self) -> None:
        self.assertTrue(contains_only_opinion("cool repo, congrats on shipping"))
        self.assertFalse(contains_only_opinion("cool repo, but retries fail"))

    def test_validate_url_accepts_issues_pulls_and_comment_fragments(self) -> None:
        self.assertIsNone(validate_url(VALID_URL))
        self.assertIsNone(
            validate_url("https://github.com/owner/repo/pull/42")
        )
        self.assertIsNone(
            validate_url(
                "https://github.com/owner/repo/issues/123#issuecomment-987"
            )
        )
        self.assertIsNotNone(validate_url("https://github.com/owner/repo"))
        self.assertIsNotNone(validate_url("https://example.com/owner/repo/issues/1"))

    def test_code_artifact_detection(self) -> None:
        self.assertTrue(contains_code_artifact("src/billing/webhooks.ts:88"))
        self.assertTrue(contains_code_artifact("README.md explains the route"))
        self.assertFalse(contains_code_artifact("the webhook handler drops retries"))
        self.assertEqual(
            extract_code_artifacts("See `src/billing/webhooks.ts:88`."),
            frozenset({"src/billing/webhooks.ts:88"}),
        )

    def test_artifact_must_be_mentioned_in_reply(self) -> None:
        self.assertTrue(
            artifact_mentioned_in_reply(
                "src/billing/webhooks.ts:88 drops retries",
                "The likely path is src/billing/webhooks.ts.",
            )
        )
        self.assertTrue(
            artifact_mentioned_in_reply(
                "src/billing/webhooks.ts:88 drops retries",
                "The likely path is webhooks.ts.",
            )
        )
        self.assertFalse(
            artifact_mentioned_in_reply(
                "src/billing/webhooks.ts:88 drops retries",
                "The likely path is the webhook handler.",
            )
        )


class GateEvaluationTests(unittest.TestCase):
    def test_passing_case_clears_all_conditions(self) -> None:
        result = evaluate_gate(**_passing_kwargs())
        self.assertTrue(result.passed, msg=f"expected pass, got {result.failures}")
        self.assertEqual(result.failures, ())

    def test_invalid_url_fails(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_url="not-a-url"))
        self.assertFalse(result.passed)
        self.assertTrue(any("url" in failure for failure in result.failures))

    def test_missing_actor_build_surface_fails_condition_a(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_actor_builds=""))
        self.assertFalse(result.passed)
        self.assertTrue(any(failure.startswith("(a)") for failure in result.failures))

    def test_old_thread_fails_condition_c(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_thread_iso=ISO_9D_AGO))
        self.assertFalse(result.passed)
        self.assertTrue(any(failure.startswith("(c)") for failure in result.failures))
        self.assertTrue(any("9.0d old" in failure for failure in result.failures))

    def test_future_thread_fails_condition_c(self) -> None:
        result = evaluate_gate(**_passing_kwargs(target_thread_iso=ISO_FUTURE))
        self.assertFalse(result.passed)
        self.assertTrue(any("future" in failure for failure in result.failures))

    def test_opinion_only_problem_fails_condition_b(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(target_problem="cool repo, congrats on shipping")
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(failure.startswith("(b)") for failure in result.failures))

    def test_problem_without_pain_vocabulary_fails_condition_b(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(target_problem="they are discussing a billing workflow")
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(failure.startswith("(b)") for failure in result.failures))

    def test_reply_without_problem_overlap_fails_condition_d(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(
                reply_text=(
                    "Read-only check: src/billing/webhooks.ts could use a cleanup. "
                    "I can help if useful."
                )
            )
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any(
                failure.startswith("(d)") and "names <" in failure
                for failure in result.failures
            )
        )

    def test_code_observation_without_file_path_fails_condition_d(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(
                code_observation="the webhook handler drops retries too early"
            )
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("no file/code artifact" in failure for failure in result.failures)
        )

    def test_reply_must_cite_code_artifact_from_observation(self) -> None:
        result = evaluate_gate(
            **_passing_kwargs(
                reply_text=(
                    "You described checkout payment webhook retries that fail to "
                    "mark invoices paid. Public-code check: the handler drops retry "
                    "events before marking invoices paid."
                )
            )
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("does not cite the code artifact" in failure for failure in result.failures)
        )

    def test_vague_next_step_fails_condition_d(self) -> None:
        result = evaluate_gate(**_passing_kwargs(next_step="happy to help if useful"))
        self.assertFalse(result.passed)
        self.assertTrue(any("next-step" in failure for failure in result.failures))

    def test_meathead_class_public_code_reply_passes(self) -> None:
        result = evaluate_gate(
            target_url="https://github.com/AutomationAlchemyst/meathead-app/issues/8",
            target_thread_iso=ISO_2D_AGO,
            target_actor_builds="maintainer of a recipe generation app",
            target_problem="free generation quota fails to persist after reload",
            reply_text=(
                "You described free generation quota fails after reload. "
                "Read-only check: src/lib/generationQuota.ts stores the remaining "
                "free generation count in local state before the Firestore write, "
                "so a failed write can reset the quota on refresh. Minimal fix: "
                "move quota decrement into a transaction and add a reload regression test."
            ),
            code_observation=(
                "src/lib/generationQuota.ts:41 updates local quota before the "
                "Firestore write confirms persistence"
            ),
            next_step="Patch the quota transaction and add a reload regression test.",
            now=NOW,
        )
        self.assertTrue(result.passed, msg=f"expected pass, got {result.failures}")

    def test_fan_thanks_class_fails(self) -> None:
        result = evaluate_gate(
            target_url=VALID_URL,
            target_thread_iso=ISO_2D_AGO,
            target_actor_builds="maintainer of an AI evals repo",
            target_problem="amazing project, congrats on the launch",
            reply_text=(
                "We love what you are building. Your tool would help our agents "
                "with evaluation workflows."
            ),
            code_observation="we also struggled with evals",
            next_step="happy to try it",
            now=NOW,
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(failure.startswith("(b)") for failure in result.failures))
        self.assertTrue(
            any("no file/code artifact" in failure for failure in result.failures)
        )
        self.assertTrue(any("next-step" in failure for failure in result.failures))


class CLITests(unittest.TestCase):
    def test_cli_pass_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reply = Path(tmp) / "reply.txt"
            reply.write_text(_passing_kwargs()["reply_text"], encoding="utf-8")
            argv = [
                "--target-url",
                VALID_URL,
                "--target-thread-iso",
                ISO_2D_AGO,
                "--target-actor-builds",
                "maintainer of a SaaS billing workflow",
                "--target-problem",
                "checkout payment webhook retries fail to mark invoices paid",
                "--reply-from-file",
                str(reply),
                "--code-observation",
                "src/billing/webhooks.ts:88 drops retry events",
                "--next-step",
                "Patch retry handling and add a webhook retry regression test.",
                "--now-iso",
                NOW.isoformat().replace("+00:00", "Z"),
            ]
            self.assertEqual(main(argv), 0)

    def test_cli_fail_returns_nonzero(self) -> None:
        argv = [
            "--target-url",
            VALID_URL,
            "--target-thread-iso",
            ISO_9D_AGO,
            "--target-actor-builds",
            "maintainer",
            "--target-problem",
            "cool repo, congrats",
            "--reply-text",
            "great project",
            "--code-observation",
            "we also struggled",
            "--next-step",
            "happy to help",
            "--now-iso",
            NOW.isoformat().replace("+00:00", "Z"),
        ]
        self.assertNotEqual(main(argv), 0)


if __name__ == "__main__":
    unittest.main()
