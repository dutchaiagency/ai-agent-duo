import unittest
import subprocess
from datetime import UTC, datetime
from unittest.mock import patch

from tools.github_reply_check import (
    IssueUnavailable,
    Target,
    classify_thread,
    fetch_issue,
    normalize_rest_issue,
    parse_targets,
    render_markdown,
)


PIPELINE = """
## Active Non-Farcaster Target Queue

| Lead | Status | Intake tag | Next action |
| --- | --- | --- | --- |
| owner/repo-one #3 | Contacted 2026-04-29 | `tag` | Wait. |
| Example-Org/repo.two #42 | Contacted 2026-04-30 | `tag` | Ask. |

## Reply Handling
"""


def comment(author: str, created_at: str, body: str = "body") -> dict:
    return {
        "author": {"login": author},
        "createdAt": created_at,
        "body": body,
    }


class GitHubReplyCheckTests(unittest.TestCase):
    def test_parse_targets_from_active_queue(self) -> None:
        targets = parse_targets(PIPELINE)

        self.assertEqual(
            targets,
            [
                Target(repo="owner/repo-one", number=3),
                Target(repo="Example-Org/repo.two", number=42),
            ],
        )

    def test_waiting_when_no_reply_after_agent_comment(self) -> None:
        status = classify_thread(
            Target(repo="owner/repo", number=1),
            {
                "title": "Issue",
                "state": "OPEN",
                "url": "https://github.com/owner/repo/issues/1",
                "comments": [
                    comment("maintainer", "2026-04-30T10:00:00Z"),
                    comment("dutchaiagency", "2026-04-30T11:00:00Z"),
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.last_agent_comment_at, "2026-04-30T11:00:00Z")

    def test_closed_issue_without_reply_is_not_waiting(self) -> None:
        status = classify_thread(
            Target(repo="owner/repo", number=1),
            {
                "title": "Issue",
                "state": "CLOSED",
                "url": "https://github.com/owner/repo/issues/1",
                "comments": [
                    comment("maintainer", "2026-04-30T10:00:00Z"),
                    comment("dutchaiagency", "2026-04-30T11:00:00Z"),
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "closed_no_reply")
        self.assertIn("Issue is closed", status.note)

    def test_detects_reply_after_agent_comment(self) -> None:
        status = classify_thread(
            Target(repo="owner/repo", number=1),
            {
                "title": "Issue",
                "url": "https://github.com/owner/repo/issues/1",
                "comments": [
                    comment("dutchaiagency", "2026-04-30T11:00:00Z"),
                    comment("maintainer", "2026-04-30T12:00:00Z", "Yes, use notes."),
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "reply")
        self.assertEqual(status.latest_reply_author, "maintainer")
        self.assertIn("Yes, use notes.", status.latest_reply_excerpt)

    def test_no_agent_comment_is_reported(self) -> None:
        status = classify_thread(
            Target(repo="owner/repo", number=1),
            {
                "title": "Issue",
                "url": "https://github.com/owner/repo/issues/1",
                "comments": [comment("maintainer", "2026-04-30T12:00:00Z")],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "no_agent_comment")
        self.assertIn("No dutchaiagency comment", status.note)

    def test_render_markdown_is_stable(self) -> None:
        status = classify_thread(
            Target(repo="owner/repo", number=1),
            {
                "title": "Issue",
                "url": "https://github.com/owner/repo/issues/1",
                "comments": [
                    comment("dutchaiagency", "2026-04-30T11:00:00Z"),
                    comment("maintainer", "2026-04-30T12:00:00Z", "Use A | B."),
                ],
            },
            agent_login="dutchaiagency",
        )

        markdown = render_markdown(
            [status], generated_at=datetime(2026, 4, 30, 12, 30, tzinfo=UTC)
        )

        self.assertIn("# GitHub Reply Check - 2026-04-30 12:30 UTC", markdown)
        self.assertIn("[owner/repo #1]", markdown)
        self.assertIn("Use A \\| B.", markdown)

    def test_rest_issue_payload_is_normalized_for_classifier(self) -> None:
        payload = normalize_rest_issue(
            {
                "title": "Billing bug",
                "state": "open",
                "html_url": "https://github.com/owner/repo/issues/7",
            },
            [
                {
                    "user": {"login": "dutchaiagency"},
                    "created_at": "2026-04-30T11:00:00Z",
                    "body": "offer",
                },
                {
                    "user": {"login": "maintainer"},
                    "created_at": "2026-04-30T12:00:00Z",
                    "body": "Please send notes.",
                },
            ],
        )

        status = classify_thread(
            Target(repo="owner/repo", number=7),
            payload,
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "reply")
        self.assertEqual(status.latest_reply_author, "maintainer")

    def test_fetch_issue_uses_rest_fallback_after_graphql_failure(self) -> None:
        def fake_run(cmd, check, capture_output, text):  # type: ignore[no-untyped-def]
            if cmd[:3] == ["gh", "issue", "view"]:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="GraphQL: Could not resolve to a Repository",
                )
            if cmd == ["gh", "api", "repos/owner/repo/issues/7"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=(
                        '{"title":"Issue","state":"open",'
                        '"html_url":"https://github.com/owner/repo/issues/7"}'
                    ),
                    stderr="",
                )
            if cmd == ["gh", "api", "repos/owner/repo/issues/7/comments"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=(
                        '[{"user":{"login":"dutchaiagency"},'
                        '"created_at":"2026-04-30T11:00:00Z","body":"offer"}]'
                    ),
                    stderr="",
                )
            raise AssertionError(cmd)

        with patch("tools.github_reply_check.subprocess.run", fake_run):
            payload = fetch_issue(Target(repo="owner/repo", number=7))

        self.assertEqual(payload["state"], "OPEN")
        self.assertEqual(payload["comments"][0]["author"]["login"], "dutchaiagency")

    def test_fetch_issue_reports_unavailable_after_graphql_and_rest_failure(self) -> None:
        def fake_run(cmd, check, capture_output, text):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                stderr="Not Found",
            )

        with patch("tools.github_reply_check.subprocess.run", fake_run):
            with self.assertRaises(IssueUnavailable):
                fetch_issue(Target(repo="owner/missing", number=7))


if __name__ == "__main__":
    unittest.main()
