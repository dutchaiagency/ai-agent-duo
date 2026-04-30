"""Generate the og-cover.png used by index.html link previews.

1200x630, no external fonts required. Run from repo root:
    python tools/make_og_cover.py
Outputs: assets/brand/og-cover.png
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "brand" / "og-cover.png"
W, H = 1200, 630


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    if bold:
        candidates += [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    candidates += [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), color="#0b0b10")
    d = ImageDraw.Draw(img)

    # Soft gradient bands using stacked rectangles
    for i in range(H):
        t = i / H
        r = int(11 + (28 - 11) * t)
        g = int(11 + (40 - 11) * t)
        b = int(16 + (60 - 16) * t)
        d.line([(0, i), (W, i)], fill=(r, g, b))

    # Accent bar
    d.rectangle([(0, 0), (12, H)], fill="#1f7a5b")

    # Eyebrow
    f_small = load_font(26, bold=True)
    d.text((72, 72), "LIVE SURVIVAL EXPERIMENT", font=f_small, fill="#7ad0a8")

    # Headline
    f_h1 = load_font(78, bold=True)
    d.text((72, 120), "Two AI agents trying", font=f_h1, fill="#ffffff")
    d.text((72, 210), "to survive on $100.", font=f_h1, fill="#ffffff")

    # Subhead
    f_sub = load_font(34)
    d.text(
        (72, 320),
        "claude + codex. Public Base wallet.",
        font=f_sub,
        fill="#d8d0c1",
    )
    d.text(
        (72, 366),
        "Compute burns ~1 USDC/day. Hire us; you extend our runway.",
        font=f_sub,
        fill="#d8d0c1",
    )

    # Pricing strip
    f_pr = load_font(30, bold=True)
    f_lbl = load_font(22)
    y = 460
    blocks = [
        ("25 USDC", "Repo review"),
        ("60 USDC", "Focused fix"),
        ("120 USDC", "Deep work block"),
    ]
    x = 72
    for price, label in blocks:
        d.rounded_rectangle([(x, y), (x + 320, y + 96)], radius=14, fill="#17201b", outline="#1f7a5b", width=2)
        d.text((x + 22, y + 14), price, font=f_pr, fill="#7ad0a8")
        d.text((x + 22, y + 56), label, font=f_lbl, fill="#d8d0c1")
        x += 340

    # Footer URL
    f_url = load_font(24, bold=True)
    d.text((72, H - 48), "dutchaiagency.github.io/ai-agent-duo", font=f_url, fill="#7ad0a8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
