import json
import io
import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from unittest.mock import patch

from tools.github_pr_watch import (
    PullStatus,
    PullTarget,
    classify_pr,
    check_targets,
    default_output_path,
    fetch_pr,
    gh_json,
    main,
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
    target_url: str = "",
) -> dict:
    return {
        "name": name,
        "conclusion": conclusion,
        "status": status,
        "completedAt": completed_at,
        "targetUrl": target_url,
    }


def status_context(
    context: str,
    *,
    state: str = "SUCCESS",
    started_at: str = "2026-05-02T19:00:00Z",
) -> dict:
    return {
        "__typename": "StatusContext",
        "context": context,
        "state": state,
        "startedAt": started_at,
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

    def test_closed_pr_with_ship_comment_is_shipped(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "CLOSED",
                "comments": [
                    comment("maintainer", "2026-05-02T19:00:00Z", "Shipped in v1.2.3. The fix is now live."),
                ],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "shipped")
        self.assertEqual(status.latest_signal_author, "maintainer")
        self.assertIn("ship/release signal", status.note)

    def test_merged_pr_with_maintainer_comment_is_shipped(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "MERGED",
                "comments": [
                    comment("maintainer", "2026-05-02T19:00:00Z", "LGTM, thanks.")
                ],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "shipped")
        self.assertEqual(status.latest_signal_author, "maintainer")
        self.assertIn("PR is merged", status.note)

    def test_merged_pr_without_non_agent_signal_is_shipped(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "updatedAt": "2026-05-02T19:00:00Z",
                "mergedAt": "2026-05-02T19:00:00Z",
                "mergedBy": {"login": "maintainer"},
                "state": "MERGED",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "shipped")
        self.assertEqual(status.latest_signal_author, "maintainer")
        self.assertEqual(status.latest_signal_excerpt, "merged")

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

    def test_closed_pr_with_missing_cla_bot_is_policy_gate(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-06T11:10:00Z",
                "state": "CLOSED",
                "comments": [
                    comment(
                        "owui-terminator",
                        "2026-05-06T11:10:04Z",
                        (
                            "STOP: MISSING CLA. @dutchaiagency, your PR "
                            "description is missing the Contributor License "
                            "Agreement confirmation. The CLA is required for "
                            "ALL PRs and this PR will be closed."
                        ),
                    )
                ],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "policy_gate")
        self.assertEqual(status.latest_signal_author, "owui-terminator")
        self.assertIn("human/legal review", status.note)

    def test_closed_pr_with_release_note_by_agent_is_shipped(self) -> None:
        def fake_fetch(_target):  # type: ignore[no-untyped-def]
            return {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T16:36:26Z",
                "state": "CLOSED",
                "title": "LM Studio config-driven classification",
                "url": "https://github.com/owner/repo/pull/1536",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
            }

        releases = [
            {
                "tag_name": "v0.50.281",
                "published_at": "2026-05-03T17:18:00Z",
                "html_url": "https://github.com/owner/repo/releases/tag/v0.50.281",
                "body": (
                    "LM Studio config-driven classification "
                    "(#1536 by @dutchaiagency)"
                ),
            }
        ]

        with (
            patch("tools.github_pr_watch.fetch_pr", fake_fetch),
            patch("tools.github_pr_watch.fetch_recent_releases", return_value=releases),
        ):
            statuses = check_targets(
                [PullTarget("owner/repo", 1536)],
                agent_login="dutchaiagency",
            )

        self.assertEqual(statuses[0].state, "shipped")
        self.assertEqual(statuses[0].latest_signal_author, "github-release")
        self.assertIn("v0.50.281", statuses[0].latest_signal_excerpt)
        self.assertIn("#1536 by @dutchaiagency", statuses[0].note)

    def test_closed_pr_superseded_when_linked_issue_closed_by_other_pr(self) -> None:
        def fake_fetch(_target):  # type: ignore[no-untyped-def]
            return {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T19:38:21Z",
                "state": "CLOSED",
                "title": "fix(streaming): lock stale cleanup (#1533)",
                "body": "Closes #1533.",
                "url": "https://github.com/owner/repo/pull/1557",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
            }

        def fake_issue(repo, number):  # type: ignore[no-untyped-def]
            self.assertEqual(repo, "owner/repo")
            self.assertEqual(number, 1533)
            return {
                "number": 1533,
                "state": "CLOSED",
                "stateReason": "COMPLETED",
                "closedAt": "2026-05-03T20:44:45Z",
                "closedByPullRequestsReferences": [
                    {
                        "number": 1562,
                        "repository": {
                            "name": "repo",
                            "owner": {"login": "owner"},
                        },
                    }
                ],
            }

        with (
            patch("tools.github_pr_watch.fetch_pr", fake_fetch),
            patch("tools.github_pr_watch.fetch_recent_releases", return_value=[]),
            patch("tools.github_pr_watch.fetch_issue", fake_issue),
        ):
            statuses = check_targets(
                [PullTarget("owner/repo", 1557)],
                agent_login="dutchaiagency",
            )

        self.assertEqual(statuses[0].state, "superseded")
        self.assertEqual(statuses[0].latest_signal_author, "github-issue")
        self.assertIn("issue #1533", statuses[0].latest_signal_excerpt)
        self.assertIn("owner/repo #1562", statuses[0].note)

    def test_release_note_before_agent_activity_does_not_mark_shipped(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1536),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T16:36:26Z",
                "state": "CLOSED",
                "comments": [
                    comment("dutchaiagency", "2026-05-03T18:00:00Z", "follow-up")
                ],
                "reviews": [],
                "latestReviews": [],
            },
            agent_login="dutchaiagency",
        )

        with patch(
            "tools.github_pr_watch.fetch_recent_releases",
            return_value=[
                {
                    "tag_name": "v0.50.281",
                    "published_at": "2026-05-03T17:18:00Z",
                    "body": "(#1536 by @dutchaiagency)",
                }
            ],
        ):
            from tools.github_pr_watch import apply_release_ship_signal

            updated = apply_release_ship_signal(
                PullTarget("owner/repo", 1536),
                status,
                agent_login="dutchaiagency",
            )

        self.assertEqual(updated.state, "closed_no_signal")

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

    def test_action_required_workflow_run_is_not_plain_waiting(self) -> None:
        def fake_fetch(_target):  # type: ignore[no-untyped-def]
            return {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-04T06:39:43Z",
                "state": "OPEN",
                "title": "Fix CI",
                "url": "https://github.com/owner/repo/pull/14",
                "headRefName": "codex/fix-ci",
                "headRefOid": "abc123",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
                "statusCheckRollup": [],
            }

        runs = [
            {
                "workflowName": "CI",
                "conclusion": "action_required",
                "status": "completed",
                "updatedAt": "2026-05-04T06:39:47Z",
                "headSha": "abc123",
            }
        ]

        with (
            patch("tools.github_pr_watch.fetch_pr", fake_fetch),
            patch("tools.github_pr_watch.fetch_recent_pr_workflow_runs", return_value=runs),
        ):
            statuses = check_targets(
                [PullTarget("owner/repo", 14)],
                agent_login="dutchaiagency",
            )

        self.assertEqual(statuses[0].state, "workflow_action_required")
        self.assertEqual(statuses[0].latest_signal_author, "github-actions")
        self.assertIn("CI", statuses[0].latest_signal_excerpt)
        self.assertEqual(statuses[0].check_summary, "workflow approval required")

    def test_status_context_success_counts_as_passed(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-02T18:00:00Z",
                "state": "OPEN",
                "comments": [],
                "reviews": [],
                "latestReviews": [],
                "statusCheckRollup": [status_context("CodeRabbit", state="SUCCESS")],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.check_summary, "0 failed, 0 pending, 1 passed/skipped")

    def test_status_context_failure_counts_as_check_signal(self) -> None:
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
                    status_context(
                        "legacy-ci",
                        state="FAILURE",
                        started_at="2026-05-02T19:00:00Z",
                    )
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "check_signal")
        self.assertEqual(status.latest_signal_author, "github-checks")
        self.assertIn("legacy-ci", status.latest_signal_excerpt)
        self.assertEqual(status.check_summary, "1 failed, 0 pending, 0 passed/skipped")

    def test_ignores_vercel_deploy_authorization_noise(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T01:16:56Z",
                "state": "OPEN",
                "comments": [
                    comment(
                        "vercel",
                        "2026-05-03T01:16:59Z",
                        "@dutchaiagency is attempting to deploy a commit to the team. "
                        "A member of the Team first needs to authorize it.",
                    )
                ],
                "reviews": [],
                "latestReviews": [],
                "statusCheckRollup": [
                    check(
                        "Vercel",
                        conclusion="FAILURE",
                        completed_at="2026-05-03T01:16:59Z",
                        target_url="https://vercel.com/git/authorize?job=abc",
                    )
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.check_summary, "none reported")

    def test_ignores_coderabbit_review_in_progress_noise(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T05:44:07Z",
                "state": "OPEN",
                "comments": [
                    comment(
                        "coderabbitai",
                        "2026-05-03T05:44:20Z",
                        "<!-- This is an auto-generated comment: review in progress "
                        "by coderabbit.ai --> Currently processing new changes in "
                        "this PR. This may take a few minutes, please wait...",
                    )
                ],
                "reviews": [],
                "latestReviews": [],
                "statusCheckRollup": [
                    check("CodeRabbit", status="PENDING"),
                    check("semgrep-cloud-platform/scan", status="QUEUED"),
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.check_summary, "0 failed, 2 pending, 0 passed/skipped")

    def test_ignores_coderabbit_no_action_summary_and_approval(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T05:44:07Z",
                "state": "OPEN",
                "comments": [
                    comment(
                        "coderabbitai",
                        "2026-05-03T05:44:20Z",
                        "<!-- This is an auto-generated comment: summarize by "
                        "coderabbit.ai --> No actionable comments were generated "
                        "in the recent review.",
                    )
                ],
                "reviews": [
                    review(
                        "coderabbitai",
                        "2026-05-03T05:46:10Z",
                        "",
                        state="APPROVED",
                    )
                ],
                "latestReviews": [],
                "statusCheckRollup": [
                    check("CodeRabbit", conclusion="SUCCESS"),
                    check("semgrep-cloud-platform/scan", conclusion="SUCCESS"),
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.check_summary, "0 failed, 0 pending, 2 passed/skipped")

    def test_ignores_cubic_no_issues_review(self) -> None:
        status = classify_pr(
            PullTarget(repo="owner/repo", number=1),
            {
                "author": {"login": "dutchaiagency"},
                "createdAt": "2026-05-03T06:49:20Z",
                "state": "OPEN",
                "comments": [],
                "reviews": [
                    review(
                        "cubic-dev-ai",
                        "2026-05-03T06:51:27Z",
                        "**No issues found** across 1 file",
                    )
                ],
                "latestReviews": [],
                "statusCheckRollup": [
                    check("Cursor Bugbot", conclusion="SUCCESS"),
                    check("Cubic", conclusion="SUCCESS"),
                ],
            },
            agent_login="dutchaiagency",
        )

        self.assertEqual(status.state, "waiting")
        self.assertEqual(status.check_summary, "0 failed, 0 pending, 2 passed/skipped")

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

    def test_main_reports_written_path_to_stderr(self) -> None:
        output_path = self.tmp_path("pr-watch.md", "")
        status = PullStatus(repo="owner/repo", number=1, state="waiting")
        stderr = io.StringIO()
        stdout = io.StringIO()

        with (
            patch("tools.github_pr_watch.check_targets", return_value=[status]),
            redirect_stderr(stderr),
            redirect_stdout(stdout),
        ):
            exit_code = main(
                [
                    "--pr",
                    "owner/repo#1",
                    "--write",
                    str(output_path),
                    "--agent-login",
                    "dutchaiagency",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(f"wrote {output_path}", stderr.getvalue())
        self.assertIn("owner/repo #1", output_path.read_text(encoding="utf-8"))

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
            patch("tools.github_pr_watch.subprocess.run", fake_run),
        ):
            self.assertEqual(gh_json(["gh", "pr", "view"]), {"ok": True})

        self.assertEqual(len(calls), 2)

    def test_repo_not_found_is_unavailable_not_generic_error(self) -> None:
        def fake_fetch(_target):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(
                1,
                ["gh", "pr", "view"],
                stderr=(
                    "GraphQL: Could not resolve to a Repository with the name "
                    "'owner/repo'. (repository)"
                ),
            )

        with patch("tools.github_pr_watch.fetch_pr", fake_fetch):
            statuses = check_targets(
                [PullTarget("owner/repo", 7)], agent_login="dutchaiagency"
            )

        self.assertEqual(statuses[0].state, "unavailable")
        self.assertIn("no longer readable", statuses[0].note)

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
