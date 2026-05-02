import unittest
from dataclasses import replace
from datetime import UTC, datetime

from tools import devto_public_email_scan as scan


class DevtoPublicEmailScanTests(unittest.TestCase):
    def seed(self) -> scan.ArticleSeed:
        return scan.ArticleSeed(
            tag="ai",
            article_id=1,
            title="Building AI agents | cheaply",
            url="https://dev.to/alice/building-ai-agents",
            canonical_url="https://alice.dev/posts/agents",
            description="TypeScript automation notes",
            tags=("ai", "typescript"),
            published_at="2026-05-02T12:00:00Z",
            username="alice",
            name="Alice",
            website_url="https://alice.dev/",
            github_username="alice",
        )

    def test_extract_emails_dedupes_and_filters_placeholders(self) -> None:
        emails = scan.extract_emails(
            "Mail Alice@Example.dev, alice@example.dev. Ignore noreply@dev.to "
            "and test@example.com."
        )

        self.assertEqual(emails, ("alice@example.dev",))

    def test_candidate_urls_include_profile_canonical_site_and_contact_pages(self) -> None:
        urls = scan.candidate_urls(self.seed())

        self.assertIn("https://alice.dev/posts/agents", urls)
        self.assertIn("https://alice.dev/", urls)
        self.assertIn("https://alice.dev/about/", urls)
        self.assertIn("https://alice.dev/contact/", urls)

    def test_candidate_urls_skip_social_only_website(self) -> None:
        seed = replace(self.seed(), website_url="https://x.com/alice", canonical_url="")

        self.assertEqual(scan.candidate_urls(seed), ())

    def test_scan_seed_accepts_only_public_email_evidence(self) -> None:
        seed = self.seed()

        def json_fetcher(url: str):
            if url.endswith("by_username?url=alice"):
                return {"summary": "Founder building agent automation."}
            if url.endswith("/api/articles/1"):
                return {"body_markdown": "No private context needed."}
            raise AssertionError(url)

        def fetcher(url: str) -> str:
            if url == "https://alice.dev/contact/":
                return "<a href='mailto:hello@alice.dev'>Email</a>"
            return ""

        lead = scan.scan_seed(seed, fetcher=fetcher, json_fetcher=json_fetcher)

        self.assertEqual(lead.emails, ("hello@alice.dev",))
        self.assertEqual(lead.decision, "candidate_needs_deep_read")
        self.assertIn("explicit public email", lead.reasons)

    def test_render_markdown_escapes_table_pipes(self) -> None:
        seed = self.seed()
        output = scan.render_markdown(
            [
                scan.ScanLead(
                    seed=seed,
                    emails=("hello@alice.dev",),
                    evidence_urls=("https://alice.dev/contact/",),
                    decision="candidate_needs_deep_read",
                    reasons=("explicit public email", "agent"),
                )
            ],
            tags=("ai",),
            per_tag=5,
            generated_at=datetime(2026, 5, 2, 16, 45, tzinfo=UTC),
        )

        self.assertIn("# Dev.to Public Email Supply Scan - 2026-05-02 16:45 UTC", output)
        self.assertIn("Building AI agents \\| cheaply", output)
        self.assertIn("`hello@alice.dev`", output)

    def test_state_snapshot_path_uses_agent_and_minute(self) -> None:
        path = scan.state_snapshot_path(
            scan.Path("state"),
            "codex",
            datetime(2026, 5, 2, 16, 45, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/devto-public-email-scan-2026-05-02-codex-1645.md",
        )


if __name__ == "__main__":
    unittest.main()
