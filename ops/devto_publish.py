#!/usr/bin/env python3
"""Publish a markdown file to dev.to via the v1 API.

Reads API key from vault (platform:devto.api_key). The source file should be a
plain markdown file; an optional YAML-style frontmatter block at the top is
stripped and merged with CLI overrides (CLI wins).

Usage:
    python ops/devto_publish.py --file research/longform-survival-experiment.md \
        --canonical https://dutchaiagency.github.io/ai-agent-duo/longform/survival-experiment.html?source=devto-2026-04-30 \
        --published

    python ops/devto_publish.py --file path.md --dry-run    # no POST, print payload
    python ops/devto_publish.py --file path.md --draft      # explicit draft
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://dev.to/api/articles"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def get_api_key() -> str:
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "ops" / "secret_vault.py"), "get", "platform:devto", "api_key"],
        text=True,
    ).strip()
    if not out:
        raise SystemExit("api_key not found in vault platform:devto")
    return out


def parse_frontmatter(md: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(md)
    if not m:
        return {}, md
    block = m.group(1)
    body = md[m.end():]
    fm: dict = {}
    for line in block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip().strip('"').strip("'")
        fm[k.strip()] = v
    return fm, body


def build_payload(args: argparse.Namespace) -> dict:
    md = Path(args.file).read_text(encoding="utf-8")
    fm, body = parse_frontmatter(md)
    title = args.title or fm.get("title")
    if not title:
        raise SystemExit("title missing (no frontmatter title and no --title)")
    tags_raw = args.tags or fm.get("tags", "")
    tags = [t.strip() for t in re.split(r"[,\s]+", tags_raw) if t.strip()]
    tags = tags[:4]  # dev.to max 4
    canonical = args.canonical or fm.get("canonical_url") or None
    description = args.description or fm.get("description") or None
    cover = args.cover or fm.get("cover_image") or None
    if args.draft:
        published = False
    elif args.published:
        published = True
    else:
        published = (fm.get("published", "").lower() == "true")
    article: dict = {
        "title": title,
        "body_markdown": body.strip() + "\n",
        "published": published,
        "tags": tags,
    }
    if canonical:
        article["canonical_url"] = canonical
    if description:
        article["description"] = description
    if cover:
        article["main_image"] = cover
    return {"article": article}


def post(payload: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "api-key": api_key,
            "content-type": "application/json",
            "accept": "application/vnd.forem.api-v1+json",
            # Varnish/WAF in front of dev.to returns 403 to UA-less requests.
            "user-agent": "dutchaiagents/1.0 (https://dutchaiagency.github.io/ai-agent-duo/)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code}: {body}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, help="markdown file path")
    ap.add_argument("--title", help="override title")
    ap.add_argument("--tags", help="comma-separated tag overrides (max 4)")
    ap.add_argument("--canonical", help="canonical_url override")
    ap.add_argument("--description", help="description override")
    ap.add_argument("--cover", help="cover image URL override")
    pub_g = ap.add_mutually_exclusive_group()
    pub_g.add_argument("--published", action="store_true")
    pub_g.add_argument("--draft", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    payload = build_payload(args)
    if args.dry_run:
        out = {**payload}
        body = out["article"]["body_markdown"]
        out["article"]["body_markdown"] = f"<{len(body)} chars>"
        print(json.dumps(out, indent=2))
        return 0
    api_key = get_api_key()
    resp = post(payload, api_key)
    print(json.dumps({
        "id": resp.get("id"),
        "slug": resp.get("slug"),
        "url": resp.get("url"),
        "canonical_url": resp.get("canonical_url"),
        "published": resp.get("published"),
        "tag_list": resp.get("tag_list"),
        "title": resp.get("title"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
