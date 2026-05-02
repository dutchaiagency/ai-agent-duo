import unittest
from datetime import UTC, datetime

from tools.email_lead_watch import (
    EmailLead,
    classify_lead,
    default_output_path,
    parse_email_leads,
    render_markdown,
)


PIPELINE = """
## Active Email Lead Watch

| Lead | Sent (UTC) | 72h cutoff (UTC) | Owner | Personalization anchor | Next action |
| --- | --- | --- | --- | --- | --- |
| owner/repo #1 -- `a@example.com` | 2026-05-02T16:38Z | 2026-05-05T16:38Z | codex | file.py:1 | Watch inbox. |
| Other lead -- `b@example.com` | 2026-05-02T21:47Z | 2026-05-05T21:47Z | claude | form.py | Ask scope. |

Codeslegion is inbound and excluded.

## Reply Handling
"""


class EmailLeadWatchTests(unittest.TestCase):
    def test_parse_email_leads_from_active_watch_section(self) -> None:
        leads = parse_email_leads(PIPELINE)

        self.assertEqual(len(leads), 2)
        self.assertEqual(leads[0].lead, "owner/repo #1 -- a@example.com")
        self.assertEqual(leads[0].owner, "codex")
        self.assertEqual(leads[1].cutoff_at, "2026-05-05T21:47Z")

    def test_classify_watching_before_cutoff(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="lead",
                sent_at="2026-05-02T16:38Z",
                cutoff_at="2026-05-05T16:38Z",
                owner="codex",
                anchor="x",
                next_action="Watch inbox.",
            ),
            now=datetime(2026, 5, 2, 22, 30, tzinfo=UTC),
        )

        self.assertEqual(status.state, "watching")
        self.assertAlmostEqual(status.hours_to_cutoff or 0, 66.13, places=1)
        self.assertIn("No follow-up", status.note)

    def test_classify_follow_up_due_after_cutoff(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="lead",
                sent_at="2026-05-02T16:38Z",
                cutoff_at="2026-05-05T16:38Z",
                owner="codex",
                anchor="x",
                next_action="Watch inbox.",
            ),
            now=datetime(2026, 5, 5, 17, 0, tzinfo=UTC),
        )

        self.assertEqual(status.state, "follow_up_due")
        self.assertIn("window is open", status.note)

    def test_classify_cadence_mismatch(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="lead",
                sent_at="2026-05-02T16:38Z",
                cutoff_at="2026-05-06T16:38Z",
                owner="codex",
                anchor="x",
                next_action="Watch inbox.",
            ),
            now=datetime(2026, 5, 2, 22, 30, tzinfo=UTC),
        )

        self.assertEqual(status.state, "cadence_mismatch")
        self.assertIn("2026-05-05T16:38Z", status.note)

    def test_render_markdown_escapes_table_pipes(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="lead | with pipe",
                sent_at="2026-05-02T16:38Z",
                cutoff_at="2026-05-05T16:38Z",
                owner="codex",
                anchor="x",
                next_action="Ask A | B.",
            ),
            now=datetime(2026, 5, 2, 22, 30, tzinfo=UTC),
        )
        markdown = render_markdown(
            [status], generated_at=datetime(2026, 5, 2, 22, 31, tzinfo=UTC)
        )

        self.assertIn("# Email Lead Watch - 2026-05-02 22:31 UTC", markdown)
        self.assertIn("lead \\| with pipe", markdown)
        self.assertIn("Ask A \\| B.", markdown)

    def test_default_output_path_uses_generated_minute(self) -> None:
        path = default_output_path(
            self.tmp_path("state"),
            "codex",
            datetime(2026, 5, 2, 22, 31, tzinfo=UTC),
        )

        self.assertTrue(str(path).endswith("email-lead-watch-2026-05-02-codex-2231.md"))

    def tmp_path(self, name: str):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name) / name


if __name__ == "__main__":
    unittest.main()
