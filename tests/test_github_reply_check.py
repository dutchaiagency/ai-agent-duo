import unittest
from datetime import UTC, datetime

from tools.github_reply_check import (
    Target,
    classify_thread,
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


if __name__ == "__main__":
    unittest.main()
