"""Render products/agent-playbook/playbook.md to a styled PDF for sale delivery.

Path-independent: same artifact ships through Gumroad upload, Lemon Squeezy
upload, or self-hosted USDC checkout.

Usage:
    python tools/playbook_to_pdf.py
    -> writes products/agent-playbook/playbook.pdf

Requires: python-markdown, Playwright (already installed for Farcaster lane).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import markdown
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "products" / "agent-playbook" / "playbook.md"
OUT_PDF = ROOT / "products" / "agent-playbook" / "playbook.pdf"
OUT_HTML = ROOT / "products" / "agent-playbook" / "playbook.html"

CSS = """
@page { size: A4; margin: 22mm 20mm; }
html, body {
  font-family: 'Charter', 'Iowan Old Style', Georgia, serif;
  color: #1a1a1a;
  font-size: 11pt;
  line-height: 1.55;
}
h1, h2, h3 { font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: #0b0b0b; }
h1 { font-size: 24pt; margin: 0 0 0.4em 0; line-height: 1.2; }
h2 { font-size: 16pt; margin: 1.6em 0 0.5em 0; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
h3 { font-size: 12.5pt; margin: 1.2em 0 0.3em 0; }
p, li { margin: 0 0 0.6em 0; }
em { color: #444; }
hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
code {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 0.9em;
  background: #f3f3f3;
  padding: 1px 4px;
  border-radius: 3px;
}
pre code { display: block; padding: 10px 12px; overflow-wrap: break-word; }
blockquote {
  border-left: 3px solid #888;
  margin: 0.8em 0;
  padding: 0.2em 0 0.2em 1em;
  color: #333;
  font-style: italic;
}
ul, ol { padding-left: 1.4em; }
"""

HTML_TMPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Operating Playbook for a 4-Agent Shared Wallet</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


async def render() -> None:
    md_text = SRC.read_text(encoding="utf-8")
    body_html = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    full_html = HTML_TMPL.format(css=CSS, body=body_html)
    OUT_HTML.write_text(full_html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(OUT_HTML.as_uri())
        await page.emulate_media(media="print")
        await page.pdf(
            path=str(OUT_PDF),
            format="A4",
            margin={"top": "22mm", "bottom": "22mm", "left": "20mm", "right": "20mm"},
            print_background=True,
        )
        await browser.close()
    print(f"wrote {OUT_HTML.relative_to(ROOT)} ({OUT_HTML.stat().st_size} B)")
    print(f"wrote {OUT_PDF.relative_to(ROOT)} ({OUT_PDF.stat().st_size} B)")


if __name__ == "__main__":
    asyncio.run(render())
