import json
import subprocess
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from tools.github_repo_snapshot import (
    RepoSnapshot,
    fetch_snapshot,
    from_repo_payload,
    render_markdown,
)


class GitHubRepoSnapshotTests(unittest.TestCase):
    def test_repo_payload_handles_null_optional_fields(self) -> None:
        snapshot = from_repo_payload(
            {
                "nameWithOwner": "owner/repo",
                "description": "Tool | dashboard",
                "repositoryTopics": None,
                "latestRelease": None,
                "licenseInfo": None,
                "primaryLanguage": None,
                "issues": None,
            }
        )

        self.assertEqual(snapshot.name_with_owner, "owner/repo")
        self.assertEqual(snapshot.description, "Tool | dashboard")
        self.assertEqual(snapshot.topics, ())
        self.assertEqual(snapshot.latest_release_tag, "")
        self.assertEqual(snapshot.open_issue_count, 0)

    def test_fetch_snapshot_uses_gh_without_jq(self) -> None:
        def fake_run(cmd, check, capture_output, text):  # type: ignore[no-untyped-def]
            if cmd[:4] == ["gh", "repo", "view", "owner/repo"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps(
                        {
                            "nameWithOwner": "owner/repo",
                            "description": "Local agent dashboard",
                            "stargazerCount": 2,
                            "forkCount": 1,
                            "licenseInfo": {"spdxId": "MIT"},
                            "latestRelease": {"tagName": "v1", "url": "u"},
                            "primaryLanguage": {"name": "Python"},
                            "repositoryTopics": [{"name": "agents"}],
                            "issues": {"totalCount": 1},
                        }
                    ),
                    stderr="",
                )
            if cmd[:4] == ["gh", "issue", "list", "--repo"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps(
                        [
                            {
                                "number": 7,
                                "title": "Bug",
                                "url": "https://github.com/owner/repo/issues/7",
                                "state": "OPEN",
                                "labels": [{"name": "bug"}],
                                "updatedAt": "2026-05-02T00:00:00Z",
                            }
                        ]
                    ),
                    stderr="",
                )
            raise AssertionError(cmd)

        with patch("tools.github_repo_snapshot.subprocess.run", fake_run):
            snapshot = fetch_snapshot("owner/repo", issue_limit=3)

        self.assertEqual(snapshot.stars, 2)
        self.assertEqual(snapshot.topics, ("agents",))
        self.assertEqual(snapshot.open_issues[0].labels, ("bug",))

    def test_render_markdown_escapes_tables(self) -> None:
        markdown = render_markdown(
            RepoSnapshot(
                name_with_owner="owner/repo",
                description="A | B",
                topics=("x|y",),
            ),
            generated_at=datetime(2026, 5, 2, 13, 0, tzinfo=UTC),
            scout_note="Use as peer signal.",
        )

        self.assertIn("# GitHub Repo Snapshot - owner/repo", markdown)
        self.assertIn("A \\| B", markdown)
        self.assertIn("x\\|y", markdown)
        self.assertIn("Use as peer signal.", markdown)


if __name__ == "__main__":
    unittest.main()
