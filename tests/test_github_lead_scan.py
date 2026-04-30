import unittest
from datetime import UTC, datetime

from tools.github_lead_scan import (
    Lead,
    active_target_keys,
    enrich_scored_with_comments,
    filter_scored,
    render_markdown,
    score_lead,
)


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

    def test_token_points_bounty_is_skipped_even_with_high_score(self) -> None:
        lead = Lead(
            query="fresh-bounty-typescript",
            repo="example/token-bounties",
            number=43,
            title="Tier 1 checkout bounty",
            url="https://github.com/example/token-bounties/issues/43",
            body=(
                "Reward: 500K FNDRY points.\n"
                "Acceptance criteria: checkout UI works.\n"
                "Relevant files: src/checkout.tsx."
            ),
            labels=("bounty", "bug", "help wanted"),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
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

    def test_market_validation_issue_is_not_coding_lead(self) -> None:
        lead = Lead(
            query="explicit-pay",
            repo="example/real-world-problems",
            number=1301,
            title="Student loan tracker - Willingness-to-pay",
            url="https://github.com/example/real-world-problems/issues/1301",
            body=(
                "Primary uncertainty: Willingness-to-pay.\n"
                "Method: Structured pricing interviews with 8-12 people.\n"
                "Target participant / customer: PSLF-track borrowers."
            ),
            labels=("type/experiment",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertIn("market validation not coding task", scored.blockers)

    def test_bug_bounty_program_setup_is_not_small_fix_lead(self) -> None:
        lead = Lead(
            query="fresh-bounty-typescript",
            repo="example/security-program",
            number=88,
            title="H4: Public bug-bounty program",
            url="https://github.com/example/security-program/issues/88",
            body=(
                "Launch a public bug-bounty program on Immunefi with a "
                "responsible disclosure policy and triage process."
            ),
            labels=("bounty",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertIn("program setup not small coding task", scored.blockers)

    def test_existing_external_review_comment_blocks_duplicate_outreach(self) -> None:
        lead = Lead(
            query="paid-bug-typescript",
            repo="example/openclaw",
            number=64129,
            title="Paid heartbeat usage bug",
            url="https://github.com/example/openclaw/issues/64129",
            body=(
                "Acceptance criteria: paid heartbeat traffic does not start "
                "after provider setup. Relevant files: src/setup.ts."
            ),
            labels=("bug",),
            comments_count=1,
            created_at="2026-04-29T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
            comments=("Codex review: keeping this open for maintainer follow-up.",),
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertIn("already has detailed external review", scored.blockers)

    def test_bot_authored_issue_is_skipped(self) -> None:
        lead = Lead(
            query="paid-bug-typescript",
            repo="example/automated-bugs",
            number=352,
            title="billing subscription bug",
            url="https://github.com/example/automated-bugs/issues/352",
            body=(
                "Relevant files: routes/billing.ts.\n"
                "Acceptance criteria: paid institutions resolve correctly."
            ),
            labels=("bug",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
            author_login="app/github-actions",
            author_is_bot=True,
        )

        scored = score_lead(lead, now=NOW)

        self.assertEqual(scored.decision, "skip")
        self.assertIn("bot-authored issue", scored.blockers)

    def test_github_search_bot_type_sets_author_is_bot(self) -> None:
        lead = Lead.from_gh(
            "q",
            {
                "repository": {"nameWithOwner": "example/automated-bugs"},
                "number": 353,
                "title": "generated billing bug",
                "url": "https://github.com/example/automated-bugs/issues/353",
                "body": "Acceptance criteria. File: routes/billing.ts.",
                "labels": [],
                "commentsCount": 0,
                "createdAt": "2026-04-30T12:00:00Z",
                "updatedAt": "2026-04-30T12:00:00Z",
                "assignees": [],
                "state": "OPEN",
                "author": {
                    "login": "github-actions[bot]",
                    "type": "Bot",
                    "is_bot": False,
                },
            },
        )

        self.assertTrue(lead.author_is_bot)
        self.assertEqual(score_lead(lead, now=NOW).decision, "skip")

    def test_comment_enrichment_fetches_only_candidates_with_comments(self) -> None:
        with_comments = Lead(
            query="q",
            repo="owner/reviewed",
            number=1,
            title="Fix paid checkout",
            url="https://github.com/owner/reviewed/issues/1",
            body="Acceptance criteria. Budget 25 USDC. File: src/app.ts",
            labels=("bug",),
            comments_count=1,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )
        no_comments = Lead(
            query="q",
            repo="owner/no-comments",
            number=2,
            title="Fix paid checkout",
            url="https://github.com/owner/no-comments/issues/2",
            body="Acceptance criteria. Budget 25 USDC. File: src/app.ts",
            labels=("bug",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        import tools.github_lead_scan as scan

        original = scan.fetch_issue_comment_bodies
        calls: list[str] = []

        def fake_fetch(lead: Lead) -> tuple[str, ...]:
            calls.append(lead.repo)
            return ("<!-- clawsweeper-review item=1 -->",)

        self.addCleanup(setattr, scan, "fetch_issue_comment_bodies", original)
        scan.fetch_issue_comment_bodies = fake_fetch

        enriched = enrich_scored_with_comments(
            [score_lead(with_comments, now=NOW), score_lead(no_comments, now=NOW)],
            now=NOW,
        )

        self.assertEqual(calls, ["owner/reviewed"])
        self.assertEqual(enriched[0].decision, "skip")
        self.assertEqual(enriched[1].decision, "contact_or_patch")

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

    def test_active_pipeline_targets_are_filtered_by_default(self) -> None:
        active_lead = Lead(
            query="q",
            repo="owner/repo-one",
            number=3,
            title="Fix paid checkout",
            url="https://github.com/owner/repo-one/issues/3",
            body="Acceptance criteria. Budget 25 USDC. File: src/app.ts",
            labels=("bug",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )
        new_lead = Lead(
            query="q",
            repo="owner/repo-two",
            number=4,
            title="Fix paid checkout",
            url="https://github.com/owner/repo-two/issues/4",
            body="Acceptance criteria. Budget 25 USDC. File: src/app.ts",
            labels=("bug",),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )

        filtered = filter_scored(
            [score_lead(active_lead, now=NOW), score_lead(new_lead, now=NOW)],
            min_score=35,
            active_keys={("owner/repo-one", 3)},
        )

        self.assertEqual([item.lead.repo for item in filtered], ["owner/repo-two"])

    def test_skipped_leads_are_hidden_unless_requested(self) -> None:
        skipped = Lead(
            query="q",
            repo="owner/token-points",
            number=5,
            title="Tier 1 checkout bounty",
            url="https://github.com/owner/token-points/issues/5",
            body="Reward: 500K FNDRY points. Acceptance criteria. File: src/app.ts",
            labels=("bounty", "bug"),
            comments_count=0,
            created_at="2026-04-30T12:00:00Z",
            updated_at="2026-04-30T12:00:00Z",
            assignees=(),
            state="open",
        )
        scored = [score_lead(skipped, now=NOW)]

        self.assertEqual(filter_scored(scored, min_score=35), [])
        self.assertEqual(
            [item.lead.repo for item in filter_scored(
                scored,
                min_score=35,
                include_skip=True,
            )],
            ["owner/token-points"],
        )

    def test_reads_active_targets_from_pipeline(self) -> None:
        pipeline = """
## Active Non-Farcaster Target Queue

| Lead | Status | Intake tag | Next action |
| --- | --- | --- | --- |
| Owner/Repo-One #3 | Contacted 2026-04-30 | `tag` | Wait. |

## Reply Handling
"""
        path = self.tmp_path("pipeline.md", pipeline)

        self.assertEqual(active_target_keys(path), {("owner/repo-one", 3)})

    def tmp_path(self, name: str, content: str):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / name
        path.write_text(content, encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
