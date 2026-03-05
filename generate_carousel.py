#!/usr/bin/env python3
"""
Instagram Carousel Generator — Elite Systems AI

Generates branded 1080×1080 carousel slide images using Pillow.
Fonts: Arial Bold (headlines) + Arial Regular (body)
Output: output/carousels/{name}/slide_01.png ... slide_N.png
"""

import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

SLIDE_W = SLIDE_H = 1080
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "carousels")

# ─── Brand palette ────────────────────────────────────────────────────────────
BG      = (10, 10, 15)       # #0a0a0f
SURFACE = (18, 18, 26)       # #12121a
BORDER  = (30, 30, 46)       # #1e1e2e
ACCENT  = (37, 99, 235)      # #2563eb
CYAN    = (0, 212, 255)      # #00d4ff
WHITE   = (248, 250, 252)    # #f8fafc
MUTED   = (148, 163, 184)    # #94a3b8

FONT_BOLD    = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BLACK   = "/System/Library/Fonts/Supplemental/Arial Black.ttf"

MARGIN = 80          # left/right padding
BAR_H  = 7          # top accent bar height
FOOT_Y = SLIDE_H - 68  # y for footer text


# ─── Helpers ─────────────────────────────────────────────────────────────────

def fnt(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    paths = {
        "bold":    FONT_BOLD,
        "regular": FONT_REGULAR,
        "black":   FONT_BLACK,
    }
    try:
        return ImageFont.truetype(paths.get(weight, FONT_BOLD), size)
    except Exception:
        try:
            return ImageFont.truetype(FONT_REGULAR, size)
        except Exception:
            return ImageFont.load_default()


def wrap(draw: ImageDraw.Draw, text: str, font, max_w: int) -> list[str]:
    """Word-wrap text to fit max_w pixels, respecting explicit \\n."""
    out = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            out.append("")
            continue
        line: list[str] = []
        for word in words:
            test = " ".join(line + [word])
            if draw.textbbox((0, 0), test, font=font)[2] > max_w and line:
                out.append(" ".join(line))
                line = [word]
            else:
                line.append(word)
        if line:
            out.append(" ".join(line))
    return out


def draw_lines(draw, lines, font, x, y, color, spacing=14) -> int:
    """Draw lines left-aligned from (x, y). Returns y after last line."""
    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        y += draw.textbbox((0, 0), line, font=font)[3] + spacing
    return y


def base(slide_num: int, total: int) -> tuple[Image.Image, ImageDraw.Draw]:
    """Create blank slide with top bar, slide number, and handle."""
    img  = Image.new("RGB", (SLIDE_W, SLIDE_H), BG)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([(0, 0), (SLIDE_W, BAR_H)], fill=ACCENT)

    # Footer
    foot = fnt(26, "regular")
    draw.text((MARGIN, FOOT_Y), f"{slide_num} / {total}", font=foot, fill=MUTED)
    handle = "[YOUR_INSTAGRAM_HANDLE]"
    hw = draw.textbbox((0, 0), handle, font=foot)[2]
    draw.text((SLIDE_W - hw - MARGIN, FOOT_Y), handle, font=foot, fill=MUTED)

    return img, draw


# ─── Slide templates ──────────────────────────────────────────────────────────

def hook_slide(n: int, total: int, headline: str, subtext: str) -> Image.Image:
    """Slide 1 — large centered hook with subtext below."""
    img, draw = base(n, total)
    max_w = SLIDE_W - MARGIN * 2

    h_font = fnt(78, "black")
    s_font = fnt(40, "regular")

    h_lines = wrap(draw, headline, h_font, max_w)
    s_lines = wrap(draw, subtext,  s_font, max_w)

    h_line_h = draw.textbbox((0, 0), "Ag", font=h_font)[3] + 16
    s_line_h = draw.textbbox((0, 0), "Ag", font=s_font)[3] + 12
    block_h  = len(h_lines) * h_line_h + 36 + len(s_lines) * s_line_h

    y = (SLIDE_H - block_h) // 2

    y = draw_lines(draw, h_lines, h_font, MARGIN, y, WHITE,  spacing=16)
    y += 36
    draw_lines(draw, s_lines, s_font, MARGIN, y, MUTED, spacing=12)

    # Swipe hint — bottom centre above footer
    sw_font  = fnt(24, "regular")
    sw_text  = "swipe →"
    sw_w     = draw.textbbox((0, 0), sw_text, font=sw_font)[2]
    draw.text(((SLIDE_W - sw_w) // 2, FOOT_Y - 2), sw_text, font=sw_font, fill=BORDER)

    return img


def body_slide(n: int, total: int, label: str, headline: str, body: str) -> Image.Image:
    """Slides 2-5 — label + headline + body copy."""
    img, draw = base(n, total)
    max_w = SLIDE_W - MARGIN * 2

    l_font = fnt(28, "regular")
    h_font = fnt(62, "bold")
    b_font = fnt(38, "regular")

    y = BAR_H + 70

    # Label
    draw.text((MARGIN, y), label.upper(), font=l_font, fill=ACCENT)
    y += draw.textbbox((0, 0), label, font=l_font)[3] + 20

    # Short blue rule
    draw.rectangle([(MARGIN, y), (MARGIN + 56, y + 3)], fill=ACCENT)
    y += 28

    # Headline
    h_lines = wrap(draw, headline, h_font, max_w)
    y = draw_lines(draw, h_lines, h_font, MARGIN, y, WHITE, spacing=16)
    y += 38

    # Body
    b_lines = wrap(draw, body, b_font, max_w)
    draw_lines(draw, b_lines, b_font, MARGIN, y, MUTED, spacing=18)

    return img


def cta_slide(n: int, total: int, keyword: str, headline: str, body: str) -> Image.Image:
    """Final CTA slide — centred card with keyword in cyan."""
    img, draw = base(n, total)
    max_w = SLIDE_W - MARGIN * 2

    # Subtle inner card
    pad = 64
    draw.rounded_rectangle(
        [(pad, pad + 14), (SLIDE_W - pad, SLIDE_H - pad)],
        radius=28, fill=SURFACE, outline=BORDER, width=2,
    )

    inner_x = MARGIN + pad - 30
    inner_w  = SLIDE_W - inner_x * 2

    kw_font  = fnt(96, "black")
    h_font   = fnt(48, "bold")
    b_font   = fnt(38, "regular")

    kw_lines = wrap(draw, keyword,  kw_font, inner_w)
    h_lines  = wrap(draw, headline, h_font,  inner_w)
    b_lines  = wrap(draw, body,     b_font,  inner_w)

    kw_lh = draw.textbbox((0, 0), "Ag", font=kw_font)[3] + 14
    h_lh  = draw.textbbox((0, 0), "Ag", font=h_font)[3]  + 12
    b_lh  = draw.textbbox((0, 0), "Ag", font=b_font)[3]  + 14

    total_h = (
        len(kw_lines) * kw_lh + 28
        + len(h_lines) * h_lh  + 24
        + len(b_lines) * b_lh
    )
    y = (SLIDE_H - total_h) // 2

    y = draw_lines(draw, kw_lines, kw_font, inner_x, y, CYAN,  spacing=14)
    y += 28
    y = draw_lines(draw, h_lines,  h_font,  inner_x, y, WHITE, spacing=12)
    y += 24
    draw_lines(draw, b_lines, b_font, inner_x, y, MUTED, spacing=14)

    return img


# ─── Carousel definitions ─────────────────────────────────────────────────────

CAROUSELS = [
    {
        "name": "bottleneck",
        "slides": [
            {
                "type": "hook",
                "headline": "I was making $50K/month and working 80-hour weeks.",
                "subtext": "Here's the 3 systems I built to fix it.",
            },
            {
                "type": "body",
                "label": "The Reality",
                "headline": "Every system was me.",
                "body": (
                    "Leads waited on me to follow up.\n"
                    "Clients waited on me to report.\n"
                    "Onboarding waited on me to show up.\n"
                    "I was the bottleneck in my own business."
                ),
            },
            {
                "type": "body",
                "label": "The Cost",
                "headline": "Revenue grew. Freedom didn't.",
                "body": (
                    "$50K months felt harder than $20K months.\n"
                    "More clients meant more chaos.\n"
                    "I was scaling the wrong thing — my own hours."
                ),
            },
            {
                "type": "body",
                "label": "The Shift",
                "headline": "I stopped hiring people and started building systems.",
                "body": (
                    "3 AI systems. 6 weeks.\n"
                    "The business stopped needing me\n"
                    "to keep it running."
                ),
            },
            {
                "type": "body",
                "label": "The Result",
                "headline": "Now I work 30 hours a week. Make more.",
                "body": (
                    "→ Leads qualified automatically\n"
                    "→ Client reports generated weekly\n"
                    "→ Onboarding runs without me\n"
                    "→ I show up when I choose to"
                ),
            },
            {
                "type": "cta",
                "keyword": "DM me 'SYSTEMS'",
                "headline": "I'll send you the exact 3 systems I'd build first in your business.",
                "body": "No pitch. Just the framework.",
            },
        ],
    },
]


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def generate_carousel(carousel: dict):
    name   = carousel["name"]
    slides = carousel["slides"]
    total  = len(slides)

    out_dir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'─'*52}")
    print(f"Carousel: {name}  ({total} slides)")
    print(f"{'─'*52}")

    paths = []
    for i, s in enumerate(slides, 1):
        stype = s["type"]
        print(f"  Rendering slide {i}/{total} ({stype})...")

        if stype == "hook":
            img = hook_slide(i, total, s["headline"], s["subtext"])
        elif stype == "body":
            img = body_slide(i, total, s["label"], s["headline"], s["body"])
        elif stype == "cta":
            img = cta_slide(i, total, s["keyword"], s["headline"], s["body"])
        else:
            raise ValueError(f"Unknown slide type: {stype}")

        path = os.path.join(out_dir, f"slide_{i:02d}.png")
        img.save(path, "PNG")
        paths.append(path)

    print(f"\n✅ {total} slides saved to: {out_dir}")
    return paths


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    all_paths = []
    for c in CAROUSELS:
        if target != "all" and c["name"] != target:
            continue
        all_paths.extend(generate_carousel(c))

    print(f"\n{'─'*52}")
    print(f"Done. {len(all_paths)} slide(s) generated:")
    for p in all_paths:
        print(f"  → {p}")
