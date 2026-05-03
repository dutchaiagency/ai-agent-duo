import unittest
from datetime import UTC, datetime
from urllib.error import URLError

from tools import algora_bounty_check as algora
from tools.algora_bounty_check import (
    AlgoraBounty,
    GithubIssue,
    algora_org_bounties_url,
    classify_bounty,
    check_sources,
    expand_sources,
    has_work_intent_comment,
    parse_algora_bounties,
    render_markdown,
)


class AlgoraBountyCheckTests(unittest.TestCase):
    def test_builds_org_bounties_url_from_slug_and_url(self) -> None:
        self.assertEqual(
            algora_org_bounties_url("twentyhq"),
            "https://algora.io/twentyhq/bounties",
        )
        self.assertEqual(
            algora_org_bounties_url("https://algora.io/twentyhq"),
            "https://algora.io/twentyhq/bounties",
        )

    def test_expands_sources_with_orgs_and_defaults_once(self) -> None:
        sources = expand_sources(
            ["https://algora.io/bounties"],
            orgs=["twentyhq"],
            include_default_orgs=True,
        )

        self.assertEqual(sources[0], "https://algora.io/bounties")
        self.assertEqual(
            sources.count("https://algora.io/twentyhq/bounties"),
            1,
        )
        self.assertIn("https://algora.io/vercel/bounties", sources)

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

    def test_parses_algora_main_page_inline_amount_links(self) -> None:
        html = """
        <h1>Bounties</h1>
        <p>Open bounties for you</p>
        <a href="https://github.com/zio/zio/issues/519">
          <span>ZI</span> <span>ZIO</span> <span>#519</span>
          <span>$4,000</span> Schema Migration System for ZIO Schema 2
        </a>
        <a href="https://github.com/zio/zio/issues/9878">
          ZI ZIO #9878 $850 ZScheduler parks workers too frequently
        </a>
        <h2>Fund GitHub issues</h2>
        <a href="https://github.com/noise/repo/issues/1">View issue</a>
        """

        bounties = parse_algora_bounties(html, source_url="https://algora.io/bounties")

        self.assertEqual(len(bounties), 2)
        self.assertEqual(bounties[0].amount, "$4,000")
        self.assertEqual(bounties[0].repo, "zio/zio")
        self.assertEqual(bounties[0].number, 519)
        self.assertEqual(
            bounties[0].title,
            "ZI ZIO #519 Schema Migration System for ZIO Schema 2",
        )
        self.assertEqual(bounties[1].amount, "$850")
        self.assertEqual(bounties[1].repo, "zio/zio")
        self.assertEqual(bounties[1].number, 9878)

    def test_derives_issue_from_individual_bounty_pr_reference(self) -> None:
        html = """
        <html>
          <head><meta property="og:title" content="IMAP"></head>
          <body>
            <div>$2,500</div>
            <p>Solution submitted for #19494. Pull Request:
            https://github.com/twentyhq/twenty/pull/19737</p>
          </body>
        </html>
        """

        bounties = parse_algora_bounties(
            html,
            source_url="https://algora.io/twentyhq/bounties/g6i2c8YSNV9nHogT",
        )

        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0].amount, "$2,500")
        self.assertEqual(bounties[0].title, "IMAP")
        self.assertEqual(bounties[0].repo, "twentyhq/twenty")
        self.assertEqual(bounties[0].number, 19494)
        self.assertEqual(
            bounties[0].github_url,
            "https://github.com/twentyhq/twenty/issues/19494",
        )

    def test_keeps_pr_link_when_individual_bounty_has_no_issue_reference(self) -> None:
        html = """
        <html>
          <head><meta property="og:title" content="IMAP"></head>
          <body>
            <div>$2,500</div>
            <p>Pull Request: https://github.com/twentyhq/twenty/pull/19737</p>
          </body>
        </html>
        """

        bounties = parse_algora_bounties(
            html,
            source_url="https://algora.io/twentyhq/bounties/g6i2c8YSNV9nHogT",
        )

        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0].repo, "")
        self.assertEqual(
            bounties[0].github_url,
            "https://github.com/twentyhq/twenty/pull/19737",
        )

    def test_parses_individual_bounty_page_github_issue(self) -> None:
        html = """
        <html>
          <head><title>Fix sync | Algora</title></head>
          <body>
            <div>$750</div>
            <a href="https://github.com/org/repo/issues/44">Issue</a>
          </body>
        </html>
        """

        bounties = parse_algora_bounties(
            html,
            source_url="https://algora.io/org/bounties/issue44",
        )

        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0].amount, "$750")
        self.assertEqual(bounties[0].title, "Fix sync")
        self.assertEqual(bounties[0].repo, "org/repo")
        self.assertEqual(bounties[0].number, 44)

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

    def test_source_fetch_error_is_not_reported_as_manual_candidate(self) -> None:
        def fake_fetch_url(url: str) -> str:
            raise URLError("offline")

        original = algora.fetch_url
        self.addCleanup(setattr, algora, "fetch_url", original)
        algora.fetch_url = fake_fetch_url

        results = check_sources(["https://algora.io/twentyhq/bounties"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].decision, "source_error")
        self.assertEqual(results[0].issue.state, "error")
        self.assertIn("source fetch failed", results[0].note)

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
