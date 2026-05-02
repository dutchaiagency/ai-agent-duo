#!/usr/bin/env python3
"""Validate local static-site links and sitemap coverage."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


BASE_URL = "https://dutchaiagency.github.io/ai-agent-duo/"
PUBLIC_HTML_PAGES = (
    Path("index.html"),
    Path("writing/index.html"),
    Path("longform/survival-experiment.html"),
    Path("playbook/index.html"),
)
LOCAL_ATTRS = {
    "a": ("href",),
    "link": ("href",),
    "script": ("src",),
    "img": ("src",),
}
IGNORED_SCHEMES = {"mailto", "tel", "javascript", "data"}


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


class SiteHTMLParser(HTMLParser):
    def __init__(self, source: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.ids: set[str] = set()
        self.links: list[LinkRef] = []
        self.canonical: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs if value is not None}
        if "id" in values:
            self.ids.add(values["id"])

        for attr in LOCAL_ATTRS.get(tag.lower(), ()):
            if attr in values:
                self.links.append(
                    LinkRef(
                        self.source,
                        attr,
                        values[attr],
                        self.getpos()[0],
                    )
                )

        if tag.lower() == "link" and values.get("rel", "").lower() == "canonical":
            self.canonical = values.get("href")


def parse_html(path: Path) -> SiteHTMLParser:
    parser = SiteHTMLParser(path)
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
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

    locs = sitemap_locs(root / "sitemap.xml")
    for full_path, parser in html.items():
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
                target_parser = html.get(target) or parse_html(target)
                if fragment not in target_parser.ids:
                    findings.append(
                        Finding(
                            "missing_fragment",
                            rel_path,
                            f"line {link.line}: {link.value!r} targets missing #{fragment} in {target_rel}",
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
