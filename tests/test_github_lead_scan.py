import unittest
from datetime import UTC, datetime

from tools.github_lead_scan import Lead, render_markdown, score_lead


NOW = datetime(2026, 4, 30, 17, 30, tzinfo=UTC)


class GitHubLeadScanTests(unittest.TestCase):
    def test_scores_concrete_paid_bug_high(self) -> None:
        lead = Lead(
            query="paid-bug-typescript",
            repo="example/app",
            number=7,
            title="Fix paid checkout bug",
            url="https://github.com/example/app/issues/7",
            body=(
                "Acceptance criteria: paid orders sync correctly.\n"
                "Relevant files: src/server.ts and src/payments.ts.\n"
                "Budget: 60 USDC."
            ),
            labels=("bug", "help wanted"),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertGreaterEqual(scored.score, 70)
        self.assertEqual(scored.decision, "contact_or_patch")

    def test_skips_explicit_anti_solicitation_thread(self) -> None:
        lead = Lead(
            query="fresh-bounty-typescript",
            repo="example/tracker",
            number=1,
            title="Opire bounty tracker",
            url="https://github.com/example/tracker/issues/1",
            body='Unsolicited "I can implement this" replies will be treated as spam.',
            labels=(),
            comments_count=1,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertIn("explicit anti-solicitation", scored.blockers)

    def test_assigned_token_bounty_is_blocked(self) -> None:
        lead = Lead(
            query="fresh-bounty-typescript",
            repo="example/token-bounties",
            number=42,
            title="Tier 2 bounty",
            url="https://github.com/example/token-bounties/issues/42",
            body="Reward: 500K FNDRY. Requires 4+ merged T1 bounties to access.",
            labels=("bounty",),
            comments_count=2,
            created_at="2026-04-29T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertIn("assigned/gated bounty", scored.blockers)
        self.assertIn("token/points payout risk", scored.blockers)

    def test_bounty_hunt_wording_is_not_payment_signal(self) -> None:
        lead = Lead(
            query="fresh-bounty-typescript",
            repo="example/sim",
            number=1008,
            title="Bounty-hunt convergence framework",
            url="https://github.com/example/sim/issues/1008",
            body=(
                "Goal: implement deterministic hostile actors pursuing a target.\n"
                "Acceptance criteria: targeted tests cover entrant convergence."
            ),
            labels=("simulation", "system"),
            comments_count=1,
            created_at="2026-04-29T12:00:00Z",
            updated_at="2026-04-29T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertNotIn("explicit payment/bounty signal", scored.reasons)
        self.assertIn("ambiguous bounty wording", scored.blockers)

    def test_bounty_product_wording_needs_payout_context(self) -> None:
        lead = Lead(
            query="fresh-bounty-typescript",
            repo="example/bounty-ui",
            number=853,
            title="Add tooltip for truncated bounty status text",
            url="https://github.com/example/bounty-ui/issues/853",
            body="The Bounties page status column is truncated in a table.",
            labels=("enhancement",),
            comments_count=1,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertNotIn("explicit payment/bounty signal", scored.reasons)
        self.assertLess(scored.score, 50)

    def test_markdown_escapes_table_pipes(self) -> None:
        lead = Lead(
            query="q",
            repo="example/app",
            number=1,
            title="Fix A | B",
            url="https://github.com/example/app/issues/1",
            body="Acceptance criteria. Budget 25 USDC. File: src/app.ts",
            labels=("bug",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        markdown = render_markdown([score_lead(lead, now=NOW)], generated_at=NOW)

        self.assertIn("Fix A \\| B", markdown)

    def test_markdown_includes_source_tagged_intake_link(self) -> None:
        lead = Lead(
            query="q",
            repo="example/app",
            number=1,
            title="Fix paid checkout",
            url="https://github.com/example/app/issues/1",
            body="Acceptance criteria. Budget 25 USDC. File: src/app.ts",
            labels=("bug",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        markdown = render_markdown([score_lead(lead, now=NOW)], generated_at=NOW)

        self.assertIn("`github-outbound-example-app-1-2026-04-30`", markdown)
        self.assertIn(
            "source=github-outbound-example-app-1-2026-04-30",
            markdown,
        )


if __name__ == "__main__":
    unittest.main()
