import unittest
from io import BytesIO
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError

from tools import github_bounty_priority_scan as scan


def issue(
    number: int,
    labels: tuple[str, ...],
    *,
    title: str = "Example bounty",
) -> scan.GithubIssue:
    return scan.GithubIssue(
        number=number,
        title=title,
        url=f"https://github.com/org/repo/issues/{number}",
        labels=labels,
        updated_at="2026-05-02T13:52:00Z",
        comments=2,
    )


class GithubBountyPriorityScanTests(unittest.TestCase):
    def test_build_query_filters_repo_open_state_and_bounty_label(self) -> None:
        self.assertEqual(
            scan.build_query("midnightntwrk/contributor-hub", "bounty"),
            'repo:midnightntwrk/contributor-hub type:issue state:open label:"bounty"',
        )

    def test_prioritizes_by_configured_label_order_before_issue_number(self) -> None:
        results = scan.prioritize_issues(
            [
                issue(319, ("bounty", "medium-priority")),
                issue(308, ("bounty", "high-priority")),
                issue(298, ("bounty", "low-priority")),
                issue(330, ("bounty",)),
            ]
        )

        self.assertEqual([result.issue.number for result in results], [308, 319, 298, 330])
        self.assertEqual([result.priority for result in results], ["high-priority", "medium-priority", "low-priority", "unprioritized"])

    def test_priority_matching_is_case_insensitive_but_preserves_label_text(self) -> None:
        priority, rank = scan.priority_for_labels(("Bounty", "High-Priority"))

        self.assertEqual(priority, "High-Priority")
        self.assertEqual(rank, 0)

    def test_render_markdown_summarizes_high_and_medium_candidates(self) -> None:
        results = scan.prioritize_issues(
            [
                issue(308, ("bounty", "high-priority"), title="Proof Server and Indexer"),
                issue(319, ("bounty", "medium-priority"), title="When Proofs Fail"),
                issue(298, ("bounty", "low-priority"), title="REST Proof API"),
            ]
        )

        markdown = scan.render_markdown(
            results,
            repo="midnightntwrk/contributor-hub",
            generated_at=datetime(2026, 5, 2, 14, 10, tzinfo=UTC),
        )

        self.assertIn("Higher-than-low candidates: 2", markdown)
        self.assertIn("priority candidates present", markdown)
        self.assertIn("#308", markdown)
        self.assertIn("| high-priority |", markdown)

    def test_render_markdown_marks_low_only_board_as_watch_hold(self) -> None:
        results = scan.prioritize_issues(
            [
                issue(298, ("bounty", "low-priority"), title="REST Proof API"),
                issue(330, ("bounty",), title="Unlabeled"),
            ]
        )

        markdown = scan.render_markdown(
            results,
            repo="org/repo",
            generated_at=datetime(2026, 5, 2, 14, 10, tzinfo=UTC),
        )

        self.assertIn("Higher-than-low candidates: 0", markdown)
        self.assertIn("zero higher-than-low candidates", markdown)
        self.assertIn("watch/hold", markdown)

    def test_render_markdown_tracks_review_label_and_named_issues(self) -> None:
        results = scan.prioritize_issues(
            [
                issue(232, ("bounty", "low-priority", "in-review"), title="Private state tutorial"),
                issue(311, ("bounty", "low-priority"), title="Node proof integration"),
                issue(313, ("bounty", "low-priority"), title="MCP tutorial"),
            ]
        )

        markdown = scan.render_markdown(
            results,
            repo="midnightntwrk/contributor-hub",
            tracked_numbers=(232, 311, 313),
            generated_at=datetime(2026, 5, 3, 2, 54, tzinfo=UTC),
        )

        self.assertIn("in-review issues: 1", markdown)
        self.assertIn("Review signal: active jury/review queue (#232).", markdown)
        self.assertIn("#232 low-priority/in-review", markdown)
        self.assertIn("#311 low-priority/no in-review", markdown)
        self.assertIn("tracked issue has review label", markdown)

    def test_fetch_open_bounty_issues_requests_updated_sort(self) -> None:
        captured: dict[str, str] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self) -> bytes:
                return b'{"items":[]}'

        def fake_urlopen(request, timeout: int):
            captured["url"] = request.full_url
            captured["timeout"] = str(timeout)
            return FakeResponse()

        original = scan.urlopen
        self.addCleanup(setattr, scan, "urlopen", original)
        scan.urlopen = fake_urlopen

        issues = scan.fetch_open_bounty_issues(repo="org/repo", limit=10)

        self.assertEqual(issues, [])
        self.assertIn("sort=updated", captured["url"])
        self.assertIn("order=desc", captured["url"])
        self.assertIn("per_page=10", captured["url"])

    def test_state_snapshot_path_is_heartbeat_parseable(self) -> None:
        path = scan.state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 14, 10, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/github-bounty-priority-scan-2026-05-02-codex-agent-1410.md",
        )

    def test_main_writes_error_snapshot_when_github_search_fails(self) -> None:
        def fake_urlopen(request, timeout: int):
            raise HTTPError(
                request.full_url,
                422,
                "Unprocessable Entity",
                hdrs=None,
                fp=BytesIO(b'{"message":"Validation Failed"}'),
            )

        original = scan.urlopen
        self.addCleanup(setattr, scan, "urlopen", original)
        scan.urlopen = fake_urlopen

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "scan.md"
            exit_code = scan.main(
                [
                    "--repo",
                    "bad/repo",
                    "--write",
                    str(output_path),
                    "--now",
                    "2026-05-03T06:00Z",
                ]
            )

            markdown = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertIn("Fetch state: error", markdown)
        self.assertIn("no executable bounty candidate", markdown)
        self.assertIn("HTTP 422 Unprocessable Entity", markdown)
        self.assertIn("Validation Failed", markdown)


if __name__ == "__main__":
    unittest.main()
