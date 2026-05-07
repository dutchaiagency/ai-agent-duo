import unittest
from datetime import UTC, datetime

from tools.email_lead_watch import (
    EmailLead,
    classify_lead,
    default_output_path,
    parse_email_leads,
    parse_suppressed_emails,
    render_markdown,
)


PIPELINE = """
## Active Email Lead Watch

| Lead | Sent (UTC) | Cutoff (UTC) | Owner | Personalization anchor | Next action | Policy |
| --- | --- | --- | --- | --- | --- | --- |
| owner/repo #1 -- `a@example.com` | 2026-05-02T16:38Z | 2026-05-05T16:38Z | codex | file.py:1 | Watch inbox. | 72h-bump |
| Other lead -- `b@example.com` | 2026-05-02T21:47Z | 2026-05-09T21:47Z | claude | form.py | Ask scope. | 7d-if-reply-only |

Codeslegion is inbound and excluded.

## Reply Handling
"""


class EmailLeadWatchTests(unittest.TestCase):
    def test_parse_email_leads_from_active_watch_section(self) -> None:
        leads = parse_email_leads(PIPELINE)

        self.assertEqual(len(leads), 2)
        self.assertEqual(leads[0].lead, "owner/repo #1 -- a@example.com")
        self.assertEqual(leads[0].owner, "codex")
        self.assertEqual(leads[0].policy, "72h-bump")
        self.assertEqual(leads[1].cutoff_at, "2026-05-09T21:47Z")
        self.assertEqual(leads[1].policy, "7d-if-reply-only")

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

    def test_classify_follow_up_sent_watches_without_second_bump(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="lead",
                sent_at="2026-05-02T16:38Z",
                cutoff_at="2026-05-05T16:38Z",
                owner="codex",
                anchor="x",
                next_action=(
                    "Follow-up sent 2026-05-07T18:55Z; monitor inbox only; "
                    "no further bumps."
                ),
                policy="72h-bump-sent",
            ),
            now=datetime(2026, 5, 7, 19, 0, tzinfo=UTC),
        )

        self.assertEqual(status.state, "watching_after_follow_up")
        self.assertIn("already sent", status.note)

    def test_reply_only_policy_watches_until_cutoff_then_closes(self) -> None:
        lead = EmailLead(
            lead="lead",
            sent_at="2026-05-03T07:05Z",
            cutoff_at="2026-05-10T07:05Z",
            owner="claude",
            anchor="x",
            next_action="Watch inbox.",
            policy="7d-if-reply-only",
        )

        watching = classify_lead(
            lead,
            now=datetime(2026, 5, 7, 18, 20, tzinfo=UTC),
        )
        closed = classify_lead(
            lead,
            now=datetime(2026, 5, 10, 8, 0, tzinfo=UTC),
        )

        self.assertEqual(watching.state, "watching")
        self.assertIn("reply-only", watching.note)
        self.assertEqual(closed.state, "closed")
        self.assertIn("forbids a follow-up bump", closed.note)

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

    def test_classify_suppressed_email(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="Endi1/fabrica -- endisukaj@gmail.com",
                sent_at="2026-05-02T22:46Z",
                cutoff_at="2026-05-05T22:46Z",
                owner="codex",
                anchor="x",
                next_action="Watch inbox.",
            ),
            now=datetime(2026, 5, 5, 17, 0, tzinfo=UTC),
            suppressed_emails={"endisukaj@gmail.com"},
        )

        self.assertEqual(status.state, "suppressed")
        self.assertIn("no contact", status.note)

    def test_classify_closed_no_action_needed_policy(self) -> None:
        status = classify_lead(
            EmailLead(
                lead="git-pkgs/proxy -- andrewnez@gmail.com",
                sent_at="2026-05-03T00:52Z",
                cutoff_at="2026-05-06T00:52Z",
                owner="codex",
                anchor="#74/#75/#76 closed by maintainer",
                next_action="Closed no action needed; do not send bump.",
                policy="drift-closed-no-bump",
            ),
            now=datetime(2026, 5, 7, 18, 35, tzinfo=UTC),
        )

        self.assertEqual(status.state, "closed_no_action_needed")
        self.assertIn("no follow-up", status.note)

    def test_parse_suppressed_emails(self) -> None:
        suppressed = parse_suppressed_emails(
            "| 2026-05-03 | EndiSukaj@gmail.com | STOP reply |\n"
        )

        self.assertEqual(suppressed, {"endisukaj@gmail.com"})

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
        self.assertIn("| State | Lead | Owner | Sent | Cutoff | Timer | Policy |", markdown)
        self.assertIn("72h-bump", markdown)

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
