import json
import unittest
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools import pages_traffic_check as traffic


REPO_ROOT = Path(__file__).resolve().parents[1]
SKIPPED_HTML_DIRS = {
    ".git",
    ".pytest_cache",
    "bounties",
    "dist",
    "evidence",
    "logs",
    "node_modules",
    "state",
    "__pycache__",
}


class HitsBadgeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        src = dict(attrs).get("src")
        if src and urlsplit(src).netloc == "hits.sh":
            self.sources.append(src)


def public_html_paths() -> list[Path]:
    paths = []
    for path in REPO_ROOT.rglob("*.html"):
        relative_parts = path.relative_to(REPO_ROOT).parts
        if SKIPPED_HTML_DIRS.intersection(relative_parts):
            continue
        paths.append(path)
    return sorted(paths)


def hits_sh_urn_from_src(src: str) -> str | None:
    parsed = urlsplit(src)
    if parsed.netloc != "hits.sh":
        return None
    path = unquote(parsed.path.lstrip("/"))
    if not path.endswith(".svg"):
        return None
    return path[:-4]


class PagesTrafficCheckTests(unittest.TestCase):
    def test_payload_counts_today_and_rolling_window(self) -> None:
        page = traffic.PageCounter(
            "playbook",
            "Playbook",
            "https://example.test/playbook/",
            "example.test/playbook",
        )
        payload = {
            "total": 99,
            "monthly": 40,
            "weekly": 20,
            "items": [
                {
                    "from": "2026-04-25",
                    "to": "2026-05-02",
                    "data": [
                        {"day": "2026-05-02", "value": 3},
                        {"day": "2026-05-01", "value": 4},
                        {"day": "2026-04-27", "value": 5},
                        {"day": "2026-04-25", "value": 100},
                    ],
                }
            ],
        }

        result = traffic.page_traffic_from_payload(
            page,
            payload,
            today=date(2026, 5, 2),
            window_days=7,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.total, 99)
        self.assertEqual(result.window_hits, 12)
        self.assertEqual(result.today_hits, 3)

    def test_pages_tuple_tracks_all_installed_hits_sh_badges(self) -> None:
        installed_urns: set[str] = set()
        for path in public_html_paths():
            parser = HitsBadgeParser()
            parser.feed(path.read_text(encoding="utf-8"))
            for src in parser.sources:
                urn = hits_sh_urn_from_src(src)
                if urn is not None:
                    installed_urns.add(urn)

        tracked_urns = {page.urn for page in traffic.PAGES}
        self.assertEqual(tracked_urns, installed_urns)

    def test_render_markdown_includes_machine_readable_snapshot(self) -> None:
        pages = [
            traffic.PageTraffic(
                key="index",
                label="Home",
                public_url="https://example.test/",
                urn="example.test/index",
                api_url="https://hits.sh/api/urns/example.test/index",
                status="ok",
                total=10,
                monthly=10,
                weekly=5,
                window_hits=5,
                today_hits=1,
            )
        ]

        markdown = traffic.render_markdown(
            pages,
            generated_at=datetime(2026, 5, 2, 11, 30, tzinfo=UTC),
            window_days=7,
            bot_baseline_7d=210,
        )
        blob = markdown.split("```json", 1)[1].split("```", 1)[0]
        data = json.loads(blob)

        self.assertEqual(data["provider"], "hits.sh")
        self.assertFalse(data["counter_endpoint_increments"])
        self.assertEqual(data["pages"][0]["window_hits"], 5)


if __name__ == "__main__":
    unittest.main()
