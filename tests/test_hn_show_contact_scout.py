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
            "Email Alice@Example.dev or noreply@github.com; ignore test@example.com."
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
