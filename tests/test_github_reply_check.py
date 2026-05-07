import io
import os
import unittest
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from unittest.mock import patch

from tools.github_reply_check import (
    IssueUnavailable,
    ReplyStatus,
    Target,
    classify_thread,
    default_output_path,
    fetch_issue,
    gh_json,
    main,
    normalize_rest_issue,
    parse_target_spec,
    parse_targets,
    render_markdown,
    target_slug,
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

    def test_parse_ad_hoc_target_specs(self) -> None:
        self.assertEqual(
            parse_target_spec("owner/repo#3"),
            Target(repo="owner/repo", number=3),
        )
        self.assertEqual(
            parse_target_spec("https://github.com/owner/repo/issues/42"),
            Target(repo="owner/repo", number=42),
        )
        self.assertEqual(
            parse_target_spec("https://github.com/owner/repo/pull/43"),
            Target(repo="owner/repo", number=43),
        )

    def test_parse_ad_hoc_target_rejects_ambiguous_values(self) -> None:
        with self.assertRaises(ValueError):
            parse_target_spec("owner/repo")

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

    def test_default_output_path_uses_generated_utc_minute(self) -> None:
        state_dir = self.tmp_path("marker", "").parent / "state"
        path = default_output_path(
            state_dir,
            "codex",
            datetime(2026, 5, 2, 15, 16, 59, tzinfo=UTC),
        )

        self.assertEqual(
            path,
            state_dir / "github-replies-2026-05-02-codex-1516.md",
        )

    def test_default_output_path_keeps_ad_hoc_targets_out_of_paid_reply_cooldown(
        self,
    ) -> None:
        state_dir = self.tmp_path("marker", "").parent / "state"
        path = default_output_path(
            state_dir,
            "codex",
            datetime(2026, 5, 2, 15, 16, 59, tzinfo=UTC),
            ad_hoc_targets=[Target(repo="Sambigeara/pollen", number=3)],
        )

        self.assertEqual(
            path,
            state_dir
            / "github-ad-hoc-replies-sambigeara-pollen-3-2026-05-02-codex-1516.md",
        )

    def test_main_reports_written_path_to_stderr(self) -> None:
        output_path = self.tmp_path("reply-check.md", "")
        status = ReplyStatus(repo="owner/repo", number=1, state="waiting")
        stderr = io.StringIO()
        stdout = io.StringIO()

        with (
            patch("tools.github_reply_check.check_targets", return_value=[status]),
            patch(
                "sys.argv",
                [
                    "github_reply_check.py",
                    "--target",
                    "owner/repo#1",
                    "--write",
                    str(output_path),
                    "--agent-login",
                    "dutchaiagency",
                ],
            ),
            redirect_stderr(stderr),
            redirect_stdout(stdout),
        ):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(f"wrote {output_path}", stderr.getvalue())
        self.assertIn("owner/repo #1", output_path.read_text(encoding="utf-8"))

    def test_target_slug_is_stable_for_multiple_ad_hoc_targets(self) -> None:
        self.assertEqual(
            target_slug(
                [
                    Target(repo="owner/repo", number=1),
                    Target(repo="Example/repo.two", number=2),
                ]
            ),
            "multi-2",
        )

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

    def test_gh_json_retries_without_invalid_token_env(self) -> None:
        calls: list[dict[str, str] | None] = []

        def fake_run(cmd, check, capture_output, text, env=None):  # type: ignore[no-untyped-def]
            calls.append(env)
            if len(calls) == 1:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr=(
                        "X Failed to log in to github.com using token "
                        "(GITHUB_TOKEN)\n"
                        "- The token in GITHUB_TOKEN is invalid."
                    ),
                )
            self.assertIsNotNone(env)
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertNotIn("GH_TOKEN", env)
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout='{"ok": true}',
                stderr="",
            )

        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "bad", "GH_TOKEN": "bad"}),
            patch("tools.github_reply_check.subprocess.run", fake_run),
        ):
            self.assertEqual(gh_json(["gh", "issue", "view"]), {"ok": True})

        self.assertEqual(len(calls), 2)

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
