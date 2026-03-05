#!/usr/bin/env python3
"""
System Card Carousel Generator
Generates Instagram carousel slides in the style of Tyler Germain's viral
"9 Claude Code Skills" post — dark bokeh background, system cards, premium feel.

Usage:
    python3 scripts/system-card-carousel.py \
        --slides '<JSON_ARRAY>' \
        --output data/command/carousels/YYYY-MM-DD/ \
        --handle itszacnielsen
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Background: dark bokeh CSS (reused across all slide types)
# ---------------------------------------------------------------------------

BOKEH_BG_CSS = """
  body {
    width: 1080px;
    height: 1080px;
    background: #080810;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    position: relative;
    overflow: hidden;
    margin: 0;
    padding: 0;
  }

  /* Bokeh / city-light radial gradient overlays */
  body::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 60% 50% at 15% 20%, rgba(37,99,235,0.18) 0%, transparent 60%),
      radial-gradient(ellipse 50% 60% at 80% 75%, rgba(0,212,255,0.10) 0%, transparent 55%),
      radial-gradient(ellipse 40% 40% at 55% 10%, rgba(139,92,246,0.14) 0%, transparent 50%),
      radial-gradient(ellipse 35% 35% at 20% 80%, rgba(0,255,136,0.06) 0%, transparent 45%),
      radial-gradient(ellipse 45% 30% at 90% 30%, rgba(59,130,246,0.09) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
  }

  /* Subtle grid/noise texture overlay */
  body::after {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px);
    background-size: 54px 54px;
    pointer-events: none;
    z-index: 0;
  }

  .slide-root {
    position: relative;
    z-index: 1;
    width: 1080px;
    height: 1080px;
    display: flex;
    flex-direction: column;
    padding: 64px 72px;
    box-sizing: border-box;
  }
"""

# ---------------------------------------------------------------------------
# Full HTML wrapper
# ---------------------------------------------------------------------------

SLIDE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
{bokeh_css}
{extra_css}
</style>
</head>
<body>
<div class="slide-root">
{inner_html}
</div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Bottom handle + save row (shared)
# ---------------------------------------------------------------------------

def _bottom_row(handle: str) -> str:
    return f"""
    <div class="bottom-row">
      <span class="bottom-text">@{handle}</span>
      <span class="bottom-text">save for later</span>
    </div>"""

BOTTOM_ROW_CSS = """
  .bottom-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
  }
  .bottom-text {
    font-size: 15px;
    color: #3a3a4a;
    font-weight: 500;
    letter-spacing: 0.3px;
  }
"""

# ---------------------------------------------------------------------------
# COVER SLIDE
# ---------------------------------------------------------------------------

COVER_CSS = """
  .cover-inner {
    display: flex;
    flex-direction: column;
    height: 952px;
  }

  .cover-top {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding-bottom: 40px;
  }

  .cover-eyebrow {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #4a6fa0;
    margin-bottom: 28px;
  }

  .cover-title {
    font-size: 72px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.08;
    letter-spacing: -2px;
    margin-bottom: 36px;
  }

  .cover-title .accent {
    color: #00ff88;
  }

  .cover-subtitle {
    font-size: 24px;
    color: #8892a4;
    font-weight: 400;
    line-height: 1.5;
    max-width: 720px;
  }

  .cover-swipe {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 44px;
    font-size: 17px;
    font-weight: 600;
    color: #00ff88;
    opacity: 0.8;
  }

  .cover-arrow {
    font-size: 20px;
  }
"""


def render_cover(slide: dict, handle: str) -> tuple:
    """Returns (extra_css, inner_html)"""
    title = slide.get("title", "")
    accent = slide.get("title_accent", "")
    subtitle = slide.get("subtitle", "")

    # Replace accent words with green span
    if accent:
        highlighted_title = title.replace(accent, f'<span class="accent">{accent}</span>')
    else:
        highlighted_title = title

    inner = f"""
    <div class="cover-inner">
      <div class="cover-top">
        <div class="cover-eyebrow">Elite Systems AI</div>
        <div class="cover-title">{highlighted_title}</div>
        <div class="cover-subtitle">{subtitle}</div>
        <div class="cover-swipe">
          <span>Swipe through</span>
          <span class="cover-arrow">&#8594;</span>
        </div>
      </div>
      {_bottom_row(handle)}
    </div>"""

    extra_css = COVER_CSS + BOTTOM_ROW_CSS
    return extra_css, inner


# ---------------------------------------------------------------------------
# SYSTEM CARD SLIDE
# ---------------------------------------------------------------------------

SYSTEM_CSS = """
  .system-inner {
    display: flex;
    flex-direction: column;
    height: 952px;
    position: relative;
  }

  /* Faint large number anchored bottom-right for depth */
  .bg-number {
    position: absolute;
    right: -24px;
    bottom: 20px;
    font-size: 520px;
    font-weight: 900;
    color: rgba(255,255,255,0.05);
    line-height: 1;
    pointer-events: none;
    user-select: none;
    letter-spacing: -30px;
  }

  /* Three-section layout — tightly grouped and centered */
  .system-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 52px;
    position: relative;
    z-index: 1;
  }

  /* ── TOP: label + stars ── */
  .system-header {
    text-align: center;
    padding-top: 8px;
  }

  .system-label {
    font-size: 22px;
    font-style: italic;
    color: #4a4a68;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  .star-row {
    display: flex;
    justify-content: center;
    gap: 10px;
    margin-top: 18px;
  }

  .star {
    color: #00c853;
    font-size: 38px;
    line-height: 1;
  }

  /* ── MIDDLE: hero card ── */
  .app-card {
    background: #0c0c1c;
    border: 1px solid #1c1c34;
    border-radius: 24px;
    padding: 52px 48px;
    display: flex;
    align-items: flex-start;
    gap: 36px;
    box-shadow: 0 20px 80px rgba(0,0,0,0.7);
  }

  .app-icon {
    width: 100px;
    height: 100px;
    border-radius: 20px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 52px;
    margin-top: 4px;
  }

  .app-meta {
    flex: 1;
    min-width: 0;
  }

  .app-name {
    font-size: 42px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 10px;
    letter-spacing: -0.5px;
  }

  .app-path {
    font-size: 19px;
    color: #32324e;
    font-family: 'SF Mono', 'Fira Code', monospace;
    margin-bottom: 20px;
  }

  /* Big metric highlight */
  .app-metric {
    font-size: 28px;
    font-weight: 700;
    color: #00c853;
    letter-spacing: -0.3px;
  }

  .app-metric-label {
    font-size: 21px;
    color: #44445e;
    font-weight: 500;
    margin-top: 8px;
  }

  .app-card-right {
    display: flex;
    align-items: flex-start;
    flex-shrink: 0;
    padding-top: 6px;
  }

  .install-btn {
    background: rgba(0,255,136,0.10);
    border: 1px solid rgba(0,255,136,0.22);
    color: #00ff88;
    font-size: 17px;
    font-weight: 700;
    padding: 14px 28px;
    border-radius: 100px;
    letter-spacing: 0.8px;
  }

  /* ── BOTTOM: description ── */
  .system-description {
    font-size: 33px;
    line-height: 1.75;
    color: #aab4c8;
    font-weight: 400;
    letter-spacing: -0.2px;
  }
"""

SYSTEM_ICONS = {
    "lead": "&#x1F3AF;",      # Target
    "client": "&#x1F91D;",    # Handshake
    "follow": "&#x1F4AC;",    # Speech bubble
    "content": "&#x270D;&#xFE0F;",  # Writing hand
    "report": "&#x1F4CA;",    # Chart
    "onboard": "&#x1F680;",   # Rocket
    "invoice": "&#x1F4B0;",   # Money bag
    "default": "&#x2699;&#xFE0F;",  # Gear
}


def _pick_icon(name: str) -> str:
    name_lower = name.lower()
    for key, icon in SYSTEM_ICONS.items():
        if key in name_lower:
            return icon
    return SYSTEM_ICONS["default"]


def render_system(slide: dict, handle: str) -> tuple:
    number = slide.get("number", 1)
    name = slide.get("name", "system")
    path = slide.get("path", f"elite-systems/{name}")
    category = slide.get("category", "Automation")
    hours_saved = slide.get("hours_saved", 5)
    icon_color = slide.get("icon_color", "#2563eb")
    description = slide.get("description", "")

    icon_emoji = _pick_icon(name)

    # Format system name for display: "lead-qualifier" -> "Lead Qualifier"
    display_name = name.replace("-", " ").replace("_", " ").title()

    # Stars row (5 stars)
    stars = '<span class="star">&#9733;</span>' * 5

    bg_num = f"{number:02d}"
    inner = f"""
    <div class="system-inner">
      <div class="bg-number">{bg_num}</div>

      <div class="system-main">
        <div class="system-header">
          <div class="system-label">System #{number} <span class="emoji">&#x1F916;</span></div>
          <div class="star-row">{stars}</div>
        </div>

        <div class="app-card">
          <div class="app-icon" style="background: linear-gradient(135deg, {icon_color}40 0%, {icon_color}18 100%); border: 1px solid {icon_color}35;">
            {icon_emoji}
          </div>
          <div class="app-meta">
            <div class="app-name">{display_name}</div>
            <div class="app-path">{path}</div>
            <div class="app-metric">&#9733; {hours_saved} hours saved / week</div>
            <div class="app-metric-label">{category}</div>
          </div>
          <div class="app-card-right">
            <div class="install-btn">ACTIVE</div>
          </div>
        </div>

        <div class="system-description">
          {description}
        </div>
      </div>

      <div style="position: relative; z-index: 1;">{_bottom_row(handle)}</div>
    </div>"""

    extra_css = SYSTEM_CSS + BOTTOM_ROW_CSS
    return extra_css, inner


# ---------------------------------------------------------------------------
# CTA SLIDE
# ---------------------------------------------------------------------------

CTA_CSS = """
  .cta-inner {
    display: flex;
    flex-direction: column;
    height: 952px;
    justify-content: space-between;
  }

  /* CTA content flows with explicit spacing */
  .cta-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding-top: 200px;
  }

  .cta-eyebrow {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #00ff88;
    opacity: 0.7;
    margin-bottom: 52px;
  }

  .cta-headline {
    font-size: 80px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.05;
    letter-spacing: -3px;
    margin-bottom: 52px;
  }

  .cta-headline .accent {
    color: #00ff88;
  }

  .cta-body {
    font-size: 32px;
    color: #7882a0;
    line-height: 1.7;
    max-width: 840px;
    font-weight: 400;
    margin-bottom: 64px;
  }

  .cta-button {
    display: inline-block;
    background: linear-gradient(135deg, #00ff88 0%, #00d4aa 100%);
    color: #080810;
    font-size: 24px;
    font-weight: 800;
    padding: 26px 60px;
    border-radius: 100px;
    letter-spacing: 0.2px;
    width: fit-content;
    box-shadow: 0 0 70px rgba(0,255,136,0.4);
  }
"""


def render_cta(slide: dict, handle: str) -> tuple:
    headline = slide.get("headline", "Want these in your business?")
    body = slide.get("body", "")
    button = slide.get("button", "DM \"SYSTEMS\" to start")

    inner = f"""
    <div class="cta-inner">
      <div class="cta-main">
        <div class="cta-eyebrow">Ready to scale?</div>
        <div class="cta-headline">{headline}</div>
        <div class="cta-body">{body}</div>
        <div class="cta-button">{button}</div>
      </div>
      {_bottom_row(handle)}
    </div>"""

    extra_css = CTA_CSS + BOTTOM_ROW_CSS
    return extra_css, inner


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

RENDERERS = {
    "cover": render_cover,
    "system": render_system,
    "cta": render_cta,
}


def _slide_filename(index: int, slide: dict) -> str:
    slide_type = slide.get("type", "slide")
    if slide_type == "cover":
        return f"slide_{index:02d}_cover.png"
    elif slide_type == "system":
        num = slide.get("number", index)
        return f"slide_{index:02d}_system_{num:02d}.png"
    elif slide_type == "cta":
        return f"slide_{index:02d}_cta.png"
    else:
        return f"slide_{index:02d}_{slide_type}.png"


# ---------------------------------------------------------------------------
# Screenshot engine
# ---------------------------------------------------------------------------

def screenshot_slides(slides_data: list, output_dir: Path, handle: str) -> list:
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})

        for i, slide in enumerate(slides_data):
            slide_type = slide.get("type", "system")
            renderer = RENDERERS.get(slide_type)

            if renderer is None:
                print(f"  ! Unknown slide type '{slide_type}' at index {i}, skipping", file=sys.stderr)
                continue

            extra_css, inner_html = renderer(slide, handle)

            html = SLIDE_HTML.format(
                bokeh_css=BOKEH_BG_CSS,
                extra_css=extra_css,
                inner_html=inner_html,
            )

            page.set_content(html)

            # Wait for fonts to load (Inter from Google Fonts)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                # Fallback: short wait if network is unavailable
                page.wait_for_timeout(800)

            filename = _slide_filename(i, slide)
            out_path = output_dir / filename
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 1080, "height": 1080})
            saved_paths.append(out_path)
            print(f"  Slide {i+1:02d} -> {out_path.name}")

        browser.close()

    return saved_paths


# ---------------------------------------------------------------------------
# Preview strip
# ---------------------------------------------------------------------------

def stitch_preview(png_files: list, output_dir: Path) -> Path | None:
    try:
        from PIL import Image
    except ImportError:
        print("  ! Pillow not installed — skipping preview strip", file=sys.stderr)
        return None

    png_files = sorted(str(p) for p in png_files)
    if not png_files:
        return None

    thumb_h = 200
    gap = 6
    images = []
    for path in png_files:
        img = Image.open(path)
        aspect = img.width / img.height
        thumb_w = int(thumb_h * aspect)
        images.append(img.resize((thumb_w, thumb_h), Image.LANCZOS))

    total_w = sum(img.width for img in images) + gap * (len(images) - 1)
    canvas = Image.new("RGB", (total_w, thumb_h), (8, 8, 16))  # matches #080810

    x = 0
    for img in images:
        canvas.paste(img, (x, 0))
        x += img.width + gap

    preview_path = output_dir / "00_preview.png"
    canvas.save(str(preview_path))
    print(f"  Preview strip -> {preview_path.name}")
    return preview_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="System Card Carousel PNG generator")
    parser.add_argument("--slides", help="JSON array string of slide definitions")
    parser.add_argument("--input", help="Path to JSON file with slides array")
    parser.add_argument("--output", default=None, help="Output directory path")
    parser.add_argument("--handle", default="itszacnielsen", help="Instagram handle (without @)")
    parser.add_argument("--no-preview", action="store_true", help="Skip stitched preview strip")
    args = parser.parse_args()

    # Load slides
    if args.input:
        with open(args.input) as f:
            slides = json.load(f)
    elif args.slides:
        slides = json.loads(args.slides)
    else:
        print("Error: provide --slides '<json>' or --input <file.json>", file=sys.stderr)
        sys.exit(1)

    if isinstance(slides, dict) and "slides" in slides:
        slides = slides["slides"]

    if not slides:
        print("Error: no slides provided", file=sys.stderr)
        sys.exit(1)

    # Resolve output directory
    if args.output:
        out_dir = Path(args.output)
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        out_dir = Path(f"data/command/carousels/{date_str}")

    print(f"\nRendering {len(slides)} slides -> {out_dir}/\n")

    png_files = screenshot_slides(slides, out_dir, args.handle)

    if not args.no_preview and png_files:
        stitch_preview(png_files, out_dir)

    print(f"\nDone. {len(png_files)} slides saved.")
    print(str(out_dir))  # last line: absolute path for skill pickup


if __name__ == "__main__":
    main()
