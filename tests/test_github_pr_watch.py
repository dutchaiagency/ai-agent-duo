import json
import subprocess
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from tools.github_pr_watch import (
    PullTarget,
    classify_pr,
    default_output_path,
    fetch_pr,
    parse_target_spec,
    parse_watch_targets,
    render_markdown,
)


PIPELINE = """
## Active GitHub PR Watch

| PR | Status | Source | Next action |
| --- | --- | --- | --- |
| NousResearch/hermes-agent #18931 | Open proof PR | Hermes #1452 | Wait. |
| [owner/repo #4](https://github.com/owner/repo/pull/4) | Open | x | Wait. |

## Reply Handling
"""


def comment(author: str, created_at: str, body: str = "body") -> dict:
    return {
        "author": {"login": author},
        "createdAt": created_at,
        "body": body,
    }


def review(author: str, submitted_at: str, body: str = "", state: str = "COMMENTED"):
    return {
        "author": {"login": author},
        "submittedAt": submitted_at,
        "body": body,
        "state": state,
    }


def check(
    name: str,
    *,
    conclusion: str = "",
    status: str = "COMPLETED",
    completed_at: str = "2026-05-02T19:00:00Z",
) -> dict:
    return {
        "name": name,
        "conclusion": conclusion,
        "status": status,
        "completedAt": completed_at,
    }


class GitHubPRWatchTests(unittest.TestCase):
    def test_parse_watch_targets_from_pipeline_section(self) -> None:
        self.assertEqual(
            parse_watch_targets(PIPELINE),
            [
                PullTarget(repo="NousResearch/hermes-agent", number=18931),
                PullTarget(repo="owner/repo", number=4),
            ],
        )

    def test_parse_target_specs(self) -> None:
        self.assertEqual(
            parse_target_spec("owner/repo#3"),
            PullTarget(repo="owner/repo", number=3),
        )
        self.assertEqual(
            parse_target_spec("owner/repo #3"),
            PullTarget(repo="owner/repo", number=3),
        )
        self.assertEqual(
            parse_target_spec("https://github.com/owner/repo/pull/3"),
            PullTarget(repo="owner/repo", number=3),
        )

    def test_waiting_when_no_non_agent_activity_after_pr_creation(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "title": "Fix",
                "url": "https://github.com/owner/repo/pull/1",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.last_agent_activity_at, "2026-05-02T18:00:00Z")

    def test_detects_comment_after_latest_agent_activity(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "comments": [
                    comment("dutchaiagency", "2026-05-02T18:30:00Z", "updated"),
                    comment("maintainer", "2026-05-02T19:00:00Z", "Looks good."),
                ],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "signal")
        self.assertEqual(status.latest_signal_author, "maintainer")
        self.assertIn("Looks good", status.latest_signal_excerpt)

    def test_detects_review_after_latest_agent_activity(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "comments": [],
                "reviews": [review("maintainer", "2026-05-02T19:00:00Z", "Change x")],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "signal")
        self.assertIn("review:", status.latest_signal_excerpt)

    def test_closed_without_non_agent_activity_is_not_waiting(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "CLOSED",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "closed_no_signal")

    def test_detects_failing_check_after_latest_agent_activity(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
                "statusCheckRollup": [
                    check(
                        "pytest",
                        conclusion="FAILURE",
                        completed_at="2026-05-02T19:00:00Z",
                    )
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "check_signal")
        self.assertEqual(status.latest_signal_author, "github-checks")
        self.assertEqual(status.latest_signal_at, "2026-05-02T19:00:00Z")
        self.assertIn("pytest", status.latest_signal_excerpt)
        self.assertEqual(status.check_summary, "1 failed, 0 pending, 0 passed/skipped")

    def test_pending_check_stays_waiting_with_summary(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
                "statusCheckRollup": [check("ci", status="IN_PROGRESS")],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.check_summary, "0 failed, 1 pending, 0 passed/skipped")

    def test_render_markdown_escapes_signal_tables(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "url": "https://github.com/owner/repo/pull/1",
                "comments": [
                    comment("maintainer", "2026-05-02T19:00:00Z", "A | B")
                ],
                "reviews": [],
                "latestReviews": [],
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "UNSTABLE",
            },
            agent_login="dutchaiagency",
        )

        markdown = render_markdown(
            [status], generated_at=datetime(2026, 5, 2, 19, 5, tzinfo=UTC)
        )

        self.assertIn("# GitHub PR Watch - 2026-05-02 19:05 UTC", markdown)
        self.assertIn("A \\| B", markdown)
        self.assertIn("REVIEW_REQUIRED / UNSTABLE", markdown)

    def test_default_output_path_uses_generated_minute(self) -> None:
        state_dir = self.tmp_path("marker", "").parent / "state"
        path = default_output_path(
            state_dir,
            "codex",
            datetime(2026, 5, 2, 19, 5, 59, tzinfo=UTC),
        )

        self.assertEqual(path, state_dir / "github-pr-watch-2026-05-02-codex-1905.md")

    def test_fetch_pr_uses_gh_without_jq(self) -> None:
        def fake_run(cmd, check, capture_output, text):  # type: ignore[no-untyped-def]
            if cmd[:3] == ["gh", "pr", "view"]:
                fields = cmd[cmd.index("--json") + 1]
                self.assertIn("statusCheckRollup", fields)
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps({"number": 7, "state": "OPEN"}),
                    stderr="",
                )
            raise AssertionError(cmd)

        with patch("tools.github_pr_watch.subprocess.run", fake_run):
            self.assertEqual(fetch_pr(PullTarget("owner/repo", 7))["number"], 7)

    def tmp_path(self, name: str, content: str):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / name
        path.write_text(content, encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
