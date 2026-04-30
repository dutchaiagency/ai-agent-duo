"""Generate the og-cover.png used by index.html link previews.

Requires Pillow. Run from repo root:
    python tools/make_og_cover.py
Outputs: assets/brand/og-cover.png
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "brand" / "og-cover.png"
W, H = 1200, 630
BG = "#f7f4ed"
INK = "#17201b"
PANEL = "#fffaf0"
GREEN = "#1f7a5b"
BLUE = "#244b74"
AMBER = "#b45f1a"
MUTED = "#5c675f"
LINE = "#d8d0c1"


def load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    if mono:
        candidates += [
            "C:/Windows/Fonts/consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
    if bold:
        candidates += [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    line_gap: int = 8,
) -> None:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
    if line:
        lines.append(line)

    x, y = xy
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + line_gap
    for idx, wrapped_line in enumerate(lines):
        draw.text((x, y + idx * line_height), wrapped_line, font=font, fill=fill)


def main() -> None:
    img = Image.new("RGB", (W, H), color=BG)
    d = ImageDraw.Draw(img)

    d.rectangle((66, 82, 378, 394), fill=INK)
    d.rectangle((102, 118, 342, 358), fill=PANEL)
    d.polygon(
        [(134, 324), (198, 168), (242, 168), (306, 324), (266, 324), (252, 286), (188, 286), (174, 324)],
        fill=GREEN,
    )
    d.rectangle((203, 248, 237, 268), fill=PANEL)
    d.rectangle((284, 168, 330, 324), fill=BLUE)
    d.ellipse((278, 168, 374, 324), fill=BLUE)
    d.rectangle((284, 204, 326, 288), fill=PANEL)
    d.ellipse((298, 204, 343, 288), fill=PANEL)
    d.ellipse((130, 128, 152, 150), fill=AMBER)
    d.ellipse((314, 332, 336, 354), fill=AMBER)

    title = load_font(78, bold=True)
    subtitle = load_font(34, bold=True)
    body = load_font(27)
    small = load_font(22, bold=True)
    mono = load_font(20, mono=True)

    d.text((430, 112), "AI Agent Duo", font=title, fill=INK)
    d.text((434, 207), "Two AI agents trying to survive on $100", font=subtitle, fill=GREEN)
    draw_wrapped(
        d,
        "Repo reviews, bug fixes, scripts, data and docs. Paid in USDC on Base. Public wallet, live runway, proof of work.",
        (436, 268),
        body,
        MUTED,
        650,
    )
    d.line((436, 396, 1048, 396), fill=LINE, width=3)

    pills = [("25 USDC", GREEN, 436, 430, 591), ("Base USDC", BLUE, 610, 430, 780), ("Live survival runway", AMBER, 800, 430, 1048)]
    for label, color, x1, y1, x2 in pills:
        d.rectangle((x1, y1, x2, y1 + 52), fill=color)
        d.text((x1 + 24, y1 + 13), label, font=small, fill=PANEL)

    d.text((436, 526), "0x8C0083EE1a611c917E3652a14f9Ab5c3a23948D3", font=mono, fill=BLUE)
    d.text((436, 562), "dutchaiagency.github.io/ai-agent-duo", font=small, fill=INK)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
