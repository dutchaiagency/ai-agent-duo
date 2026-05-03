import unittest
from html.parser import HTMLParser
from pathlib import Path

from tools.static_site_check import (
    BASE_URL,
    PUBLIC_HTML_PAGES,
    resolve_local_target,
    safe_relative,
)


HUMAN_VISIBLE_INDEX_PAGES = (Path("index.html"), Path("writing/index.html"))


class AnchorHrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        values = {name.lower(): value for name, value in attrs if value is not None}
        href = values.get("href")
        if href:
            self.hrefs.append(href)


def anchor_hrefs(path: Path) -> list[str]:
    parser = AnchorHrefParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.hrefs


class LongformIndexCompletenessTests(unittest.TestCase):
    def test_public_html_pages_are_linked_from_human_visible_indexes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        linked_pages: set[Path] = set()

        for index_page in HUMAN_VISIBLE_INDEX_PAGES:
            source = (root / index_page).resolve()
            for href in anchor_hrefs(source):
                target = resolve_local_target(root, source, href, BASE_URL)
                if target is None:
                    continue
                linked_pages.add(safe_relative(target, root))

        missing = sorted(
            set(PUBLIC_HTML_PAGES) - linked_pages,
            key=lambda path: path.as_posix(),
        )

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
