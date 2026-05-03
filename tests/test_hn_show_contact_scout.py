import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools import hn_show_contact_scout as scout


class HNShowContactScoutTests(unittest.TestCase):
    def story(self) -> scout.HNStory:
        return scout.HNStory(
            item_id=123,
            title="Show HN: Agent CLI for code reviews | launch",
            url="https://github.com/alice/agent-cli",
            by="alice",
            score=42,
            comments=7,
            text="Open source agent automation.",
        )

    def test_extract_emails_filters_placeholders(self) -> None:
        emails = scout.extract_emails(
            "Email Alice@Example.dev or noreply@github.com; ignore test@example.com and ihate@spam.com."
        )

        self.assertEqual(emails, ("alice@example.dev",))

    def test_parse_github_repo_url_rejects_reserved_paths(self) -> None:
        self.assertEqual(
            scout.parse_github_repo_url("https://github.com/alice/agent-cli"),
            ("alice", "agent-cli"),
        )
        self.assertIsNone(scout.parse_github_repo_url("https://github.com/topics/ai"))

    def test_extract_github_repo_urls_from_launch_page(self) -> None:
        urls = scout.extract_github_repo_urls(
            '<a href="https://github.com/alice/agent-cli">repo</a>'
        )

        self.assertEqual(urls, ("https://github.com/alice/agent-cli",))

    def test_scan_story_candidate_uses_public_github_email(self) -> None:
        def json_fetcher(url: str):
            if url.endswith("/user/alice.json"):
                return {"about": "No email here."}
            if url.endswith("/repos/alice/agent-cli"):
                return {
                    "full_name": "alice/agent-cli",
                    "html_url": "https://github.com/alice/agent-cli",
                    "description": "AI code review CLI",
                    "stargazers_count": 12,
                    "pushed_at": "2026-05-02T12:00:00Z",
                    "owner": {"login": "alice", "type": "User"},
                }
            if url.endswith("/users/alice"):
                return {
                    "login": "alice",
                    "type": "User",
                    "email": "hello@alice.dev",
                    "html_url": "https://github.com/alice",
                }
            raise AssertionError(url)

        lead = scout.scan_story(
            self.story(),
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
        )

        self.assertEqual(lead.decision, "candidate_needs_deep_read")
        self.assertEqual(lead.emails, ("hello@alice.dev",))
        self.assertIn("github repo", lead.reasons)
        self.assertIn("explicit public email", lead.reasons)

    def test_scan_story_keeps_large_org_repo_watch_only(self) -> None:
        def json_fetcher(url: str):
            if url.endswith("/user/alice.json"):
                return {"about": "No email here."}
            if url.endswith("/repos/bigorg/platform"):
                return {
                    "full_name": "bigorg/platform",
                    "html_url": "https://github.com/bigorg/platform",
                    "description": "Large AI platform",
                    "stargazers_count": 50_000,
                    "pushed_at": "2026-05-02T12:00:00Z",
                    "owner": {"login": "bigorg", "type": "Organization"},
                }
            if url.endswith("/users/bigorg"):
                return {
                    "login": "bigorg",
                    "type": "Organization",
                    "email": "contact@bigorg.dev",
                    "html_url": "https://github.com/bigorg",
                }
            raise AssertionError(url)

        lead = scout.scan_story(
            scout.HNStory(
                item_id=456,
                title="Show HN: Large AI platform",
                url="https://github.com/bigorg/platform",
                by="alice",
                score=100,
                comments=20,
                text="Large AI platform.",
            ),
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
        )

        self.assertEqual(lead.decision, "watch_large_org_repo")
        self.assertIn("large org repo; needs specific issue before outreach", lead.reasons)

    def test_scan_story_keeps_massive_user_repo_watch_only(self) -> None:
        def json_fetcher(url: str):
            if url.endswith("/user/alice.json"):
                return {"about": "No email here."}
            if url.endswith("/repos/alice/kernel"):
                return {
                    "full_name": "alice/kernel",
                    "html_url": "https://github.com/alice/kernel",
                    "description": "Large kernel",
                    "stargazers_count": 100_000,
                    "pushed_at": "2026-05-02T12:00:00Z",
                    "owner": {"login": "alice", "type": "User"},
                }
            if url.endswith("/users/alice"):
                return {
                    "login": "alice",
                    "type": "User",
                    "email": "alice@example.dev",
                    "html_url": "https://github.com/alice",
                }
            raise AssertionError(url)

        lead = scout.scan_story(
            scout.HNStory(
                item_id=789,
                title="Show HN: Kernel release",
                url="https://github.com/alice/kernel",
                by="alice",
                score=100,
                comments=20,
                text="Kernel release.",
            ),
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
        )

        self.assertEqual(lead.decision, "watch_large_repo")
        self.assertIn("large repo; needs specific issue before outreach", lead.reasons)

    def test_scan_story_marks_contact_log_email_as_already_contacted(self) -> None:
        story = self.story()

        def json_fetcher(url: str):
            if url.endswith("/user/alice.json"):
                return {"about": "Email hello@alice.dev"}
            if url.endswith("/repos/alice/agent-cli"):
                return {
                    "full_name": "alice/agent-cli",
                    "html_url": "https://github.com/alice/agent-cli",
                    "description": "AI code review CLI",
                    "owner": {"login": "alice", "type": "User"},
                }
            if url.endswith("/users/alice"):
                return {"login": "alice", "type": "User", "email": ""}
            raise AssertionError(url)

        lead = scout.scan_story(
            story,
            contacted_emails={"hello@alice.dev"},
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
        )

        self.assertEqual(lead.decision, "watch_already_contacted")

    def test_scan_story_marks_active_touch_repo_as_already_contacted(self) -> None:
        def json_fetcher(url: str):
            if url.endswith("/user/alice.json"):
                return {"about": "Email hello@alice.dev"}
            if url.endswith("/repos/alice/agent-cli"):
                return {
                    "full_name": "alice/agent-cli",
                    "html_url": "https://github.com/alice/agent-cli",
                    "description": "AI code review CLI",
                    "owner": {"login": "alice", "type": "User"},
                }
            if url.endswith("/users/alice"):
                return {"login": "alice", "type": "User", "email": ""}
            raise AssertionError(url)

        lead = scout.scan_story(
            self.story(),
            touched_repos={"alice/agent-cli"},
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
        )

        self.assertEqual(lead.decision, "watch_already_contacted")
        self.assertIn("repo already in active touch log", lead.reasons)

    def test_load_touched_repos_extracts_pr_watch_refs(self) -> None:
        path = Path("tmp-test-hn-touch-log.md")
        path.write_text(
            "| PR | Status |\n"
            "| --- | --- |\n"
            "| [Alice/Agent-CLI #227](https://github.com/Alice/Agent-CLI/pull/227) | open |\n"
            "| bob/tool PR #3 | watch |\n",
            encoding="utf-8",
        )
        try:
            self.assertEqual(
                scout.load_touched_repos([path]),
                {"alice/agent-cli", "bob/tool"},
            )
        finally:
            path.unlink(missing_ok=True)

    def test_render_markdown_escapes_story_title(self) -> None:
        lead = scout.ContactLead(
            story=self.story(),
            repo=None,
            emails=(),
            evidence_urls=(),
            decision="reject_no_public_email",
            reasons=("no explicit public email",),
        )

        output = scout.render_markdown(
            [lead],
            limit=5,
            generated_at=datetime(2026, 5, 2, 21, 45, tzinfo=UTC),
        )

        self.assertIn("# HN Show Contact Scout - 2026-05-02 21:45 UTC", output)
        self.assertIn("code reviews \\| launch", output)
        self.assertIn("zero send-ready candidates", output)

    def test_state_snapshot_path_uses_agent_and_minute(self) -> None:
        path = scout.state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 21, 45, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/hn-show-contact-scout-2026-05-02-codex-agent-2145.md",
        )


if __name__ == "__main__":
    unittest.main()
