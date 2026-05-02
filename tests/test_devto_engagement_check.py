import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from tools import devto_engagement_check as devto


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class DevtoEngagementCheckTests(unittest.TestCase):
    def test_fetch_articles_requests_username_and_per_page_100(self) -> None:
        payload = [
            {
                "title": "First",
                "published_at": "2026-05-02T07:18:15Z",
                "public_reactions_count": 2,
                "comments_count": 1,
                "url": "https://dev.to/dutchaiagents/first",
            }
        ]

        with patch("tools.devto_engagement_check.urlopen", return_value=FakeResponse(payload)) as mocked:
            articles = devto.fetch_articles("dutchaiagents")

        request = mocked.call_args.args[0]
        self.assertIn("username=dutchaiagents", request.full_url)
        self.assertIn("per_page=100", request.full_url)
        self.assertEqual(articles[0].title, "First")
        self.assertEqual(articles[0].reactions, 2)
        self.assertEqual(articles[0].comments, 1)

    def test_render_markdown_includes_totals_and_rows(self) -> None:
        output = devto.render_markdown(
            [
                devto.DevtoArticle(
                    title="A | title",
                    published_at="2026-05-02T07:18:15Z",
                    reactions=2,
                    comments=3,
                    url="https://dev.to/dutchaiagents/a",
                ),
                devto.DevtoArticle(
                    title="B",
                    published_at="2026-05-02T08:01:00Z",
                    reactions=4,
                    comments=0,
                    url="https://dev.to/dutchaiagents/b",
                ),
            ],
            username="dutchaiagents",
            per_page=100,
            generated_at=datetime(2026, 5, 2, 9, 45, tzinfo=UTC),
        )

        self.assertIn("# Dev.to engagement - 2026-05-02 09:45 UTC", output)
        self.assertIn("Total visible posts: 2", output)
        self.assertIn("Total reactions: 6", output)
        self.assertIn("Total comments: 3", output)
        self.assertIn("A \\| title", output)

    def test_rejects_non_list_api_response(self) -> None:
        with patch("tools.devto_engagement_check.urlopen", return_value=FakeResponse({"error": "no"})):
            with self.assertRaises(ValueError):
                devto.fetch_articles("dutchaiagents")

    def test_state_snapshot_path_uses_literal_agent_name(self) -> None:
        path = devto.state_snapshot_path(
            devto.Path("state"),
            "codex",
            datetime(2026, 5, 2, 9, 34, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/devto-engagement-2026-05-02-codex-0934.md",
        )

    def test_main_can_write_timestamped_state_file(self) -> None:
        payload = [
            {
                "title": "First",
                "published_at": "2026-05-02T07:18:15Z",
                "public_reactions_count": 0,
                "comments_count": 0,
                "url": "https://dev.to/dutchaiagents/first",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.devto_engagement_check.urlopen", return_value=FakeResponse(payload)):
                with redirect_stdout(StringIO()):
                    rc = devto.main(
                        [
                            "--state-dir",
                            tmp,
                            "--agent",
                            "codex",
                            "--now",
                            "2026-05-02T09:34Z",
                        ]
                    )

            path = devto.Path(tmp) / "devto-engagement-2026-05-02-codex-0934.md"

            self.assertEqual(rc, 0)
            self.assertTrue(path.exists())
            self.assertIn("Total visible posts: 1", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
