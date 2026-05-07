#!/usr/bin/env python3
"""Validate local static-site links and sitemap coverage."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree


BASE_URL = "https://dutchaiagency.github.io/ai-agent-duo/"
PUBLIC_HTML_PAGES = (
    Path("index.html"),
    Path("writing/index.html"),
    Path("longform/survival-experiment.html"),
    Path("longform/snowflake-fabrication-detection.html"),
    Path("longform/six-ways-our-four-agent-system-tried-to-lie-to-itself.html"),
    Path("longform/broadcast-silence-empirical.html"),
    Path("longform/parallel-wake-shared-checkout-races.html"),
    Path("longform/farcaster-reply-gate-retro.html"),
    Path("longform/lethal-trifecta-lived-experience.html"),
    Path("longform/code-as-promise-shipping-stop.html"),
    Path("examples/focused-fix-hermes-agent.html"),
    Path("examples/pricing-artifacts.html"),
    Path("playbook/index.html"),
)
LOCAL_ATTRS = {
    "a": ("href",),
    "link": ("href",),
    "script": ("src",),
    "img": ("src",),
}
META_URL_FIELDS = {
    "fc:frame:image",
    "og:image",
    "og:image:secure_url",
    "twitter:image",
    "twitter:image:src",
}
IGNORED_SCHEMES = {"mailto", "tel", "javascript", "data"}
COUNT_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)
COUNT_WORD_PATTERN = re.compile(r"\b(" + "|".join(COUNT_WORDS) + r")\b", re.IGNORECASE)
LEADING_COUNT_WORD_PATTERN = re.compile(
    r"^[^\w]*(" + "|".join(COUNT_WORDS) + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    code: str
    path: Path
    message: str


@dataclass(frozen=True)
class LinkRef:
    source: Path
    attr: str
    value: str
    line: int


@dataclass(frozen=True)
class TextLinkRef:
    source: Path
    href: str
    text: str
    line: int


@dataclass(frozen=True)
class TrackedCta:
    source: Path
    href: str
    cta_source: str
    line: int


@dataclass
class OpenAnchor:
    href: str
    line: int
    text_parts: list[str]


class SiteHTMLParser(HTMLParser):
    def __init__(self, source: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.ids: set[str] = set()
        self.links: list[LinkRef] = []
        self.text_links: list[TextLinkRef] = []
        self.tracked_ctas: list[TrackedCta] = []
        self.canonical: str | None = None
        self.title = ""
        self._title_parts: list[str] = []
        self._in_title = False
        self._anchor_stack: list[OpenAnchor] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value for name, value in attrs if value is not None}
        if "id" in values:
            self.ids.add(values["id"])

        if tag == "title":
            self._in_title = True

        if tag == "meta" and "content" in values:
            meta_key = values.get("property") or values.get("name")
            if meta_key and meta_key.lower() in META_URL_FIELDS:
                self.links.append(
                    LinkRef(
                        self.source,
                        f"meta:{meta_key.lower()}",
                        values["content"],
                        self.getpos()[0],
                    )
                )

        for attr in LOCAL_ATTRS.get(tag, ()):
            if attr in values:
                self.links.append(
                    LinkRef(
                        self.source,
                        attr,
                        values[attr],
                        self.getpos()[0],
                    )
                )

        if tag == "a" and "href" in values:
            self._anchor_stack.append(OpenAnchor(values["href"], self.getpos()[0], []))

        if tag == "a" and "href" in values and "data-cta-source" in values:
            self.tracked_ctas.append(
                TrackedCta(
                    self.source,
                    values["href"],
                    values["data-cta-source"],
                    self.getpos()[0],
                )
            )

        if tag == "link" and values.get("rel", "").lower() == "canonical":
            self.canonical = values.get("href")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._anchor_stack:
            self._anchor_stack[-1].text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            self.title = normalize_text("".join(self._title_parts))
        if tag == "a" and self._anchor_stack:
            anchor = self._anchor_stack.pop()
            self.text_links.append(
                TextLinkRef(
                    self.source,
                    anchor.href,
                    normalize_text("".join(anchor.text_parts)),
                    anchor.line,
                )
            )


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def leading_count_token(value: str) -> str | None:
    match = LEADING_COUNT_WORD_PATTERN.search(normalize_text(value))
    if not match:
        return None
    return match.group(1).lower()


def count_tokens(value: str) -> set[str]:
    return {match.group(1).lower() for match in COUNT_WORD_PATTERN.finditer(value)}


def parse_html(path: Path) -> SiteHTMLParser:
    parser = SiteHTMLParser(path)
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.title = normalize_text("".join(parser._title_parts))
    return parser


def sitemap_locs(path: Path) -> set[str]:
    if not path.exists():
        return set()
    root = ElementTree.parse(path).getroot()
    locs: set[str] = set()
    for node in root.iter():
        if node.tag.endswith("loc") and node.text:
            locs.add(node.text.strip())
    return locs


def is_ignored_external(value: str, base_url: str) -> bool:
    parts = urlsplit(value)
    if parts.scheme in IGNORED_SCHEMES:
        return True
    if parts.scheme not in ("http", "https"):
        return False

    base = urlsplit(base_url)
    if parts.netloc != base.netloc:
        return True
    base_path = base.path.rstrip("/") + "/"
    return not (parts.path == base.path.rstrip("/") or parts.path.startswith(base_path))


def site_relative_path(value: str, base_url: str) -> tuple[str, str] | None:
    parts = urlsplit(value)
    if parts.scheme in IGNORED_SCHEMES:
        return None
    if parts.scheme in ("http", "https"):
        base = urlsplit(base_url)
        if parts.netloc != base.netloc:
            return None
        base_path = base.path.rstrip("/")
        if parts.path == base_path:
            path = ""
        elif parts.path.startswith(base_path + "/"):
            path = parts.path[len(base_path) + 1 :]
        else:
            return None
        return unquote(path), unquote(parts.fragment)
    return unquote(parts.path), unquote(parts.fragment)


def resolve_local_target(root: Path, source: Path, value: str, base_url: str) -> Path | None:
    relative = site_relative_path(value, base_url)
    if relative is None:
        return None

    raw_path, _fragment = relative
    parts = urlsplit(value)
    if parts.scheme in ("http", "https"):
        candidate = root / raw_path
    elif raw_path.startswith("/"):
        candidate = root / raw_path.lstrip("/")
    elif raw_path == "":
        candidate = source
    else:
        candidate = (source.parent / raw_path)

    if value.endswith("/") or raw_path.endswith("/") or candidate.suffix == "":
        candidate = candidate / "index.html"
    return candidate.resolve()


def should_source_tag_cta(value: str, base_url: str) -> bool:
    parts = urlsplit(value)
    if parts.scheme in IGNORED_SCHEMES:
        return False

    relative = site_relative_path(value, base_url)
    if relative is not None:
        raw_path, fragment = relative
        return bool(raw_path or not fragment)

    return (
        parts.netloc == "github.com"
        and parts.path == "/dutchaiagency/ai-agent-duo/issues/new"
    )


def has_source_tag(value: str, expected: str) -> bool:
    query = parse_qs(urlsplit(value).query)
    return expected in query.get("source", [])


def safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def check_site(
    root: Path,
    *,
    public_pages: tuple[Path, ...] = PUBLIC_HTML_PAGES,
    base_url: str = BASE_URL,
) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    html: dict[Path, SiteHTMLParser] = {}

    for page in public_pages:
        full_path = (root / page).resolve()
        if not full_path.exists():
            findings.append(Finding("missing_public_page", page, "public HTML page is missing"))
            continue
        html[full_path] = parse_html(full_path)
    public_html_items = tuple(html.items())

    locs = sitemap_locs(root / "sitemap.xml")

    def cached_html_parser(path: Path) -> SiteHTMLParser:
        parser = html.get(path)
        if parser is None:
            parser = parse_html(path)
            html[path] = parser
        return parser

    for loc in sorted(locs):
        relative = site_relative_path(loc, base_url)
        if relative is None:
            if urlsplit(loc).scheme in ("http", "https"):
                findings.append(
                    Finding(
                        "sitemap_external_url",
                        Path("sitemap.xml"),
                        f"{loc} is outside {base_url}",
                    )
                )
            continue

        target = resolve_local_target(root, root / "index.html", loc, base_url)
        if target is None:
            continue

        target_rel = safe_relative(target, root)
        if not target.exists():
            findings.append(
                Finding(
                    "sitemap_missing_target",
                    Path("sitemap.xml"),
                    f"{loc} resolves to missing {target_rel}",
                )
            )
            continue

        _path, fragment = relative
        if fragment and target.suffix.lower() in (".html", ".htm"):
            target_parser = cached_html_parser(target)
            if fragment not in target_parser.ids:
                findings.append(
                    Finding(
                        "sitemap_missing_fragment",
                        Path("sitemap.xml"),
                        f"{loc} targets missing #{fragment} in {target_rel}",
                    )
                )

    for full_path, parser in public_html_items:
        rel_path = safe_relative(full_path, root)
        if not parser.canonical:
            findings.append(Finding("missing_canonical", rel_path, "missing canonical link"))
        elif parser.canonical not in locs:
            findings.append(
                Finding(
                    "canonical_missing_from_sitemap",
                    rel_path,
                    f"{parser.canonical} is not listed in sitemap.xml",
                )
            )

        for link in parser.links:
            if is_ignored_external(link.value, base_url):
                continue
            target = resolve_local_target(root, full_path, link.value, base_url)
            if target is None:
                continue

            target_rel = safe_relative(target, root)
            if not target.exists():
                findings.append(
                    Finding(
                        "missing_local_target",
                        rel_path,
                        f"line {link.line}: {link.attr}={link.value!r} resolves to missing {target_rel}",
                    )
                )
                continue

            _path, fragment = site_relative_path(link.value, base_url) or ("", "")
            if fragment and target.suffix.lower() in (".html", ".htm"):
                target_parser = cached_html_parser(target)
                if fragment not in target_parser.ids:
                    findings.append(
                        Finding(
                            "missing_fragment",
                            rel_path,
                            f"line {link.line}: {link.value!r} targets missing #{fragment} in {target_rel}",
                        )
                    )

        for text_link in parser.text_links:
            target = resolve_local_target(root, full_path, text_link.href, base_url)
            if target is None or not target.exists():
                continue
            if target.suffix.lower() not in (".html", ".htm"):
                continue

            target_parser = cached_html_parser(target)
            target_count = leading_count_token(target_parser.title)
            link_counts = count_tokens(text_link.text)
            if not target_count or not link_counts or target_count in link_counts:
                continue

            target_rel = safe_relative(target, root)
            findings.append(
                Finding(
                    "link_text_count_mismatch",
                    rel_path,
                    (
                        f"line {text_link.line}: href={text_link.href!r} "
                        f"uses count token(s) {sorted(link_counts)!r}, but "
                        f"{target_rel} title starts with {target_count!r}"
                    ),
                )
            )

        for cta in parser.tracked_ctas:
            if not should_source_tag_cta(cta.href, base_url):
                continue
            if has_source_tag(cta.href, cta.cta_source):
                continue
            findings.append(
                Finding(
                    "cta_source_mismatch",
                    rel_path,
                    (
                        f"line {cta.line}: data-cta-source={cta.cta_source!r} "
                        f"requires href source={cta.cta_source!r}, got {cta.href!r}"
                    ),
                )
            )

    return findings


def format_finding(finding: Finding) -> str:
    path = PurePosixPath(finding.path).as_posix()
    return f"{path}: {finding.code}: {finding.message}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--base-url", default=BASE_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    findings = check_site(args.root, base_url=args.base_url)
    if findings:
        for finding in findings:
            print(format_finding(finding), file=sys.stderr)
        return 1
    print("static site ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
