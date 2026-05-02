import unittest
from datetime import UTC, datetime

from tools.algora_bounty_check import (
    AlgoraBounty,
    GithubIssue,
    classify_bounty,
    has_work_intent_comment,
    parse_algora_bounties,
    render_markdown,
)


class AlgoraBountyCheckTests(unittest.TestCase):
    def test_parses_only_open_section_github_issues(self) -> None:
        html = """
        <h2>Open Bounties</h2>
        <div>$250</div>
        <a href="https://github.com/org/repo/issues/12">Fix bug</a>
        <a href="https://github.com/org/repo/issues/12">repo#12</a>
        <h2>Completed Bounties</h2>
        <div>$100</div>
        <a href="https://github.com/org/repo/issues/1">Old bug</a>
        """

        bounties = parse_algora_bounties(html, source_url="https://algora.io/example")

        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0].amount, "$250")
        self.assertEqual(bounties[0].repo, "org/repo")
        self.assertEqual(bounties[0].number, 12)
        self.assertEqual(bounties[0].title, "Fix bug")

    def test_parses_unlinked_algora_bounty_for_manual_verification(self) -> None:
        html = """
        <h2>Open Bounties</h2>
        <a href="/example/bounties">View all</a>
        <div>$2500</div>
        <a href="/example/bounties/abc123">IMAP</a>
        """

        bounties = parse_algora_bounties(html, source_url="https://algora.io/example")

        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0].amount, "$2500")
        self.assertEqual(bounties[0].title, "IMAP")
        self.assertEqual(bounties[0].repo, "")
        self.assertEqual(bounties[0].github_url, "https://algora.io/example/bounties/abc123")

    def test_closed_github_issue_is_skipped(self) -> None:
        bounty = AlgoraBounty(
            source_url="https://algora.io/example",
            amount="$1000",
            title="Stale bounty",
            github_url="https://github.com/org/repo/issues/99",
            repo="org/repo",
            number=99,
        )
        issue = GithubIssue(repo="org/repo", number=99, state="CLOSED")

        checked = classify_bounty(bounty, issue)

        self.assertEqual(checked.decision, "skip")
        self.assertIn("closed", checked.note)

    def test_open_assigned_issue_is_watch_only(self) -> None:
        bounty = AlgoraBounty(
            source_url="https://algora.io/example",
            amount="$250",
            title="Assigned bounty",
            github_url="https://github.com/org/repo/issues/2",
            repo="org/repo",
            number=2,
        )
        issue = GithubIssue(
            repo="org/repo",
            number=2,
            state="OPEN",
            assignees=("maintainer",),
        )

        checked = classify_bounty(bounty, issue)

        self.assertEqual(checked.decision, "watch")
        self.assertIn("maintainer", checked.note)

    def test_open_issue_with_work_intent_is_watch_only(self) -> None:
        bounty = AlgoraBounty(
            source_url="https://algora.io/example",
            amount="$100",
            title="Crowded bounty",
            github_url="https://github.com/org/repo/issues/3",
            repo="org/repo",
            number=3,
        )
        issue = GithubIssue(
            repo="org/repo",
            number=3,
            state="OPEN",
            work_intent_comments=4,
            latest_work_intent_at="2026-04-30T17:24:32Z",
        )

        checked = classify_bounty(bounty, issue)

        self.assertEqual(checked.decision, "watch")
        self.assertIn("crowded", checked.note)
        self.assertIn("2026-04-30T17:24:32Z", checked.note)

    def test_detects_non_slash_work_intent_comments(self) -> None:
        examples = [
            "I'm working on this now.",
            "Interested in working on this bounty.",
            "Opened a pull request with the fix.",
            "Please wait while the assigned contributor finishes.",
        ]

        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(has_work_intent_comment(example))

    def test_ignores_regular_scope_comments(self) -> None:
        self.assertFalse(
            has_work_intent_comment(
                "Acceptance criteria are clear; no one has claimed the work yet."
            )
        )

    def test_render_markdown_mentions_decision_and_state(self) -> None:
        bounty = AlgoraBounty(
            source_url="https://algora.io/example",
            amount="$250",
            title="Fix bug",
            github_url="https://github.com/org/repo/issues/12",
            repo="org/repo",
            number=12,
        )
        issue = GithubIssue(
            repo="org/repo",
            number=12,
            state="OPEN",
            title="Fix bug",
            url="https://github.com/org/repo/issues/12",
        )
        checked = classify_bounty(bounty, issue)

        markdown = render_markdown(
            [checked], generated_at=datetime(2026, 4, 30, 18, 30, tzinfo=UTC)
        )

        self.assertIn("| candidate | $250 |", markdown)
        self.assertIn("OPEN", markdown)
        self.assertIn("open and unassigned", markdown)


if __name__ == "__main__":
    unittest.main()
