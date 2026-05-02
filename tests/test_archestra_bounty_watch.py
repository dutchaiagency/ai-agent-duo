import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools import archestra_bounty_watch as watch


def issue(
    number: int,
    labels: tuple[str, ...],
    *,
    assignees: tuple[str, ...] = (),
    title: str = "Example bounty",
) -> watch.GithubIssue:
    return watch.GithubIssue(
        number=number,
        title=title,
        url=f"https://github.com/archestra-ai/archestra/issues/{number}",
        labels=labels,
        assignees=assignees,
        updated_at="2026-05-02T11:50:00Z",
        comments=3,
    )


class ArchestraBountyWatchTests(unittest.TestCase):
    def test_classifies_only_unreserved_unassigned_high_value_as_candidate(self) -> None:
        results = watch.classify_issues(
            [
                issue(3858, ("\U0001F48E Bounty", "$450", "Reserved for SE interview")),
                issue(3857, ("\U0001F48E Bounty", "$200"), assignees=("someone",)),
                issue(4225, ("\U0001F48E Bounty", "$80")),
                issue(3796, ("\U0001F48E Bounty", "$200")),
            ],
            min_amount=200,
        )

        by_number = {result.issue.number: result for result in results}
        self.assertEqual(by_number[3796].decision, "candidate")
        self.assertEqual(by_number[3858].note, "reserved for SE interview")
        self.assertEqual(by_number[3857].note, "already assigned")
        self.assertIn("below $200", by_number[4225].note)

    def test_render_zero_candidate_snapshot_has_router_zero_phrase(self) -> None:
        results = watch.classify_issues(
            [
                issue(4225, ("\U0001F48E Bounty", "$80")),
                issue(3858, ("\U0001F48E Bounty", "$450", "Reserved for SE interview")),
            ],
            min_amount=200,
        )

        markdown = watch.render_markdown(
            results,
            min_amount=200,
            generated_at=datetime(2026, 5, 2, 11, 55, tzinfo=UTC),
        )

        self.assertIn("zero immediate candidates", markdown)
        self.assertIn("0 fresh unreserved $200+ candidates", markdown)
        self.assertIn("| watch | $80 |", markdown)

    def test_state_snapshot_path_is_heartbeat_parseable(self) -> None:
        path = watch.state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 11, 55, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/archestra-bounty-label-watch-2026-05-02-codex-agent-1155.md",
        )


if __name__ == "__main__":
    unittest.main()
