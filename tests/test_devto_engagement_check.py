import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import BytesIO
from io import StringIO
from unittest.mock import patch
from urllib.error import HTTPError

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

    def test_fetch_articles_can_include_per_slug_fallback(self) -> None:
        username_payload = [
            {
                "title": "Older",
                "published_at": "2026-05-02T07:18:15Z",
                "public_reactions_count": 2,
                "comments_count": 1,
                "url": "https://dev.to/dutchaiagents/older",
            }
        ]
        slug_payload = {
            "title": "Fresh",
            "published_at": "2026-05-03T07:43:08Z",
            "public_reactions_count": 0,
            "comments_count": 0,
            "url": "https://dev.to/dutchaiagents/fresh",
        }

        with patch(
            "tools.devto_engagement_check.urlopen",
            side_effect=[FakeResponse(username_payload), FakeResponse(slug_payload)],
        ) as mocked:
            articles = devto.fetch_articles("dutchaiagents", slugs=["fresh"])

        username_request = mocked.call_args_list[0].args[0]
        slug_request = mocked.call_args_list[1].args[0]
        self.assertIn("username=dutchaiagents", username_request.full_url)
        self.assertTrue(slug_request.full_url.endswith("/dutchaiagents/fresh"))
        self.assertEqual([article.title for article in articles], ["Fresh", "Older"])

    def test_fetch_articles_skips_missing_slug_fallback(self) -> None:
        missing: list[str] = []

        def fake_urlopen(request, timeout: int = 20):
            if request.full_url.endswith("/dutchaiagents/missing"):
                raise HTTPError(
                    request.full_url,
                    404,
                    "Not Found",
                    hdrs=None,
                    fp=BytesIO(b'{"error":"not found"}'),
                )
            return FakeResponse(
                [
                    {
                        "title": "Older",
                        "published_at": "2026-05-02T07:18:15Z",
                        "public_reactions_count": 2,
                        "comments_count": 1,
                        "url": "https://dev.to/dutchaiagents/older",
                    }
                ]
            )

        with patch("tools.devto_engagement_check.urlopen", side_effect=fake_urlopen):
            articles = devto.fetch_articles(
                "dutchaiagents",
                slugs=["missing"],
                missing_slugs=missing,
            )

        self.assertEqual([article.title for article in articles], ["Older"])
        self.assertEqual(missing, ["missing"])

    def test_fetch_articles_deduplicates_per_slug_fallback(self) -> None:
        payload = {
            "title": "Fresh",
            "published_at": "2026-05-03T07:43:08Z",
            "public_reactions_count": 0,
            "comments_count": 0,
            "url": "https://dev.to/dutchaiagents/fresh",
        }

        with patch(
            "tools.devto_engagement_check.urlopen",
            side_effect=[FakeResponse([payload]), FakeResponse(payload)],
        ):
            articles = devto.fetch_articles("dutchaiagents", slugs=["fresh"])

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Fresh")

    def test_fetch_article_by_slug_rejects_non_object_response(self) -> None:
        with patch("tools.devto_engagement_check.urlopen", return_value=FakeResponse([])):
            with self.assertRaises(ValueError):
                devto.fetch_article_by_slug("dutchaiagents", "fresh")

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

    def test_render_markdown_notes_missing_slug_fallbacks(self) -> None:
        output = devto.render_markdown(
            [],
            username="dutchaiagents",
            per_page=100,
            slugs=["missing"],
            missing_slugs=["missing"],
            generated_at=datetime(2026, 5, 2, 9, 45, tzinfo=UTC),
        )

        self.assertIn("Missing fallback slugs skipped: `missing` (404)", output)

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
