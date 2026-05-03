import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools import lobsters_newest_contact_scout as scout


class LobstersNewestContactScoutTests(unittest.TestCase):
    def story(self) -> scout.LobstersStory:
        return scout.LobstersStory(
            short_id="abc123",
            title="Agent CLI for code reviews | launch",
            url="https://github.com/alice/agent-cli",
            score=7,
            comments=2,
            tags=("ai", "github"),
            description="Open source agent automation.",
            submitter="alice",
            created_at="2026-05-02T17:11:49.000-05:00",
            short_id_url="https://lobste.rs/s/abc123",
            comments_url="https://lobste.rs/s/abc123/agent_cli_for_code_reviews",
        )

    def test_extract_emails_filters_placeholders_and_noreply(self) -> None:
        emails = scout.extract_emails(
            "Email Alice@Example.dev, noreply@github.com, "
            "123+alice@users.noreply.github.com, ihate@spam.com, and test@example.com."
        )

        self.assertEqual(emails, ("alice@example.dev",))

    def test_parse_github_repo_url_rejects_reserved_paths(self) -> None:
        self.assertEqual(
            scout.parse_github_repo_url("https://github.com/alice/agent-cli"),
            ("alice", "agent-cli"),
        )
        self.assertIsNone(scout.parse_github_repo_url("https://github.com/topics/ai"))
        self.assertIsNone(
            scout.parse_github_repo_url("https://github.com/dutchaiagency/ai-agent-duo")
        )

    def test_extract_github_repo_urls_from_launch_page(self) -> None:
        urls = scout.extract_github_repo_urls(
            '<a href="https://github.com/dutchaiagency/ai-agent-duo">ua</a>'
            '<a href="https://github.com/alice/agent-cli">repo</a>'
        )

        self.assertEqual(urls, ("https://github.com/alice/agent-cli",))

    def test_first_repo_url_prefers_story_named_repo_over_first_site_link(self) -> None:
        story = scout.LobstersStory(
            short_id="pickme",
            title="Agent CLI for code reviews",
            url="https://alice.dev/agent-cli",
            score=7,
            comments=2,
            tags=("ai", "github"),
            description="Launch notes for agent-cli.",
            submitter="alice",
            created_at="2026-05-02T17:11:49.000-05:00",
            short_id_url="https://lobste.rs/s/pickme",
            comments_url="https://lobste.rs/s/pickme/agent_cli",
        )
        launch_page = (
            '<a href="https://github.com/alice/blog">Blog source</a>'
            '<a href="https://github.com/alice/agent-cli">Agent CLI</a>'
        )

        self.assertEqual(
            scout.first_repo_url(story, "", launch_page),
            "https://github.com/alice/agent-cli",
        )

    def test_scan_story_candidate_uses_public_commit_email(self) -> None:
        def json_fetcher(url: str):
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
                    "email": "",
                    "html_url": "https://github.com/alice",
                }
            if url.endswith("/repos/alice/agent-cli/commits?per_page=5"):
                return [
                    {
                        "commit": {
                            "author": {"email": "alice@example.dev"},
                            "committer": {"email": "123+alice@users.noreply.github.com"},
                        }
                    }
                ]
            raise AssertionError(url)

        lead = scout.scan_story(
            self.story(),
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
            fetch_user_profiles=False,
        )

        self.assertEqual(lead.decision, "candidate_needs_deep_read")
        self.assertEqual(lead.emails, ("alice@example.dev",))
        self.assertIn("github repo", lead.reasons)
        self.assertIn("explicit public email", lead.reasons)

    def test_scan_story_keeps_large_org_repo_watch_only(self) -> None:
        def json_fetcher(url: str):
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
            if url.endswith("/repos/bigorg/platform/commits?per_page=5"):
                return []
            raise AssertionError(url)

        lead = scout.scan_story(
            scout.LobstersStory(
                short_id="org123",
                title="Large platform release notes",
                url="https://github.com/bigorg/platform",
                score=10,
                comments=3,
                tags=("release",),
                description="AI platform release.",
                submitter="alice",
                created_at="2026-05-02T17:11:49.000-05:00",
                short_id_url="https://lobste.rs/s/org123",
                comments_url="https://lobste.rs/s/org123/large_platform_release",
            ),
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
            fetch_user_profiles=False,
        )

        self.assertEqual(lead.decision, "watch_large_org_repo")
        self.assertIn("large org repo; needs specific issue before outreach", lead.reasons)

    def test_scan_story_keeps_massive_user_repo_watch_only(self) -> None:
        def json_fetcher(url: str):
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
            if url.endswith("/repos/alice/kernel/commits?per_page=5"):
                return []
            raise AssertionError(url)

        lead = scout.scan_story(
            scout.LobstersStory(
                short_id="big123",
                title="Kernel release",
                url="https://github.com/alice/kernel",
                score=10,
                comments=3,
                tags=("release",),
                description="Kernel release.",
                submitter="alice",
                created_at="2026-05-02T17:11:49.000-05:00",
                short_id_url="https://lobste.rs/s/big123",
                comments_url="https://lobste.rs/s/big123/kernel_release",
            ),
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
            fetch_user_profiles=False,
        )

        self.assertEqual(lead.decision, "watch_large_repo")
        self.assertIn("large repo; needs specific issue before outreach", lead.reasons)

    def test_scan_story_marks_contact_log_email_as_already_contacted(self) -> None:
        lead = scout.scan_story(
            scout.LobstersStory(
                short_id="def456",
                title="Personal blog post",
                url="https://alice.dev/post",
                score=1,
                comments=0,
                tags=("programming",),
                description="",
                submitter="alice",
                created_at="2026-05-02T17:11:49.000-05:00",
                short_id_url="https://lobste.rs/s/def456",
                comments_url="https://lobste.rs/s/def456/personal_blog_post",
            ),
            contacted_emails={"hello@alice.dev"},
            json_fetcher=lambda url: {},
            text_fetcher=lambda url: "Email hello@alice.dev" if url.endswith("/u/alice") else "",
            fetch_launch_pages=False,
        )

        self.assertEqual(lead.decision, "watch_already_contacted")

    def test_scan_story_marks_active_touch_repo_as_already_contacted(self) -> None:
        def json_fetcher(url: str):
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
                    "email": "alice@example.dev",
                    "html_url": "https://github.com/alice",
                }
            if url.endswith("/repos/alice/agent-cli/commits?per_page=5"):
                return []
            raise AssertionError(url)

        lead = scout.scan_story(
            self.story(),
            touched_repos={"alice/agent-cli"},
            json_fetcher=json_fetcher,
            text_fetcher=lambda url: "",
            fetch_launch_pages=False,
            fetch_user_profiles=False,
        )

        self.assertEqual(lead.decision, "watch_already_contacted")
        self.assertIn("repo already in active touch log", lead.reasons)

    def test_load_touched_repos_extracts_pr_watch_refs(self) -> None:
        path = Path("tmp-test-lobsters-touch-log.md")
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

    def test_load_touched_repos_extracts_bare_pipeline_refs(self) -> None:
        path = Path("tmp-test-lobsters-touch-log.md")
        path.write_text(
            "| Lead | Status |\n"
            "| --- | --- |\n"
            "| SkipLabs/skip Lobste.rs lead -- `skiplabs@skiplabs.io` | watching |\n"
            "| `state/github-leads-2026-05-03-codex-0958.md` | report |\n"
            "| `tools/farcaster_reply_gate.py` | local tool |\n",
            encoding="utf-8",
        )
        try:
            self.assertEqual(scout.load_touched_repos([path]), {"skiplabs/skip"})
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
            generated_at=datetime(2026, 5, 2, 22, 55, tzinfo=UTC),
        )

        self.assertIn("# Lobste.rs Newest Contact Scout - 2026-05-02 22:55 UTC", output)
        self.assertIn("code reviews \\| launch", output)
        self.assertIn("zero send-ready candidates", output)

    def test_state_snapshot_path_uses_agent_and_minute(self) -> None:
        path = scout.state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 22, 55, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/lobsters-newest-contact-scout-2026-05-02-codex-agent-2255.md",
        )


if __name__ == "__main__":
    unittest.main()
