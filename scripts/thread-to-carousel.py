#!/usr/bin/env python3
"""
Thread-to-Carousel Generator
Renders tweet-style Instagram carousel slides as PNG images.

Usage:
    python3 scripts/thread-to-carousel.py --topic "AI automation for coaches" --slides '[...]'
    python3 scripts/thread-to-carousel.py --input slides.json --output-dir output/carousel/
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

SLIDE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    width: 1080px;
    height: 1080px;
    background: {bg};
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }}

  .card {{
    width: 980px;
    background: {card_bg};
    border-radius: 24px;
    padding: 56px 64px;
    position: relative;
  }}

  /* Header row */
  .header {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 32px;
  }}

  .avatar {{
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 700;
    color: white;
    flex-shrink: 0;
    overflow: hidden;
  }}

  .avatar img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}

  .name-block {{
    flex: 1;
  }}

  .display-name {{
    font-size: 18px;
    font-weight: 700;
    color: {text_primary};
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .verified {{
    display: inline-flex;
    align-items: center;
    margin-left: 2px;
  }}

  .verified svg {{
    width: 20px;
    height: 20px;
    vertical-align: middle;
  }}

  .handle {{
    font-size: 15px;
    color: {text_muted};
    margin-top: 2px;
  }}

  .slide-num {{
    font-size: 15px;
    color: {text_muted};
    font-weight: 500;
    letter-spacing: 0.5px;
  }}

  /* Main content */
  .content {{
    margin-bottom: 40px;
  }}

  .main-text {{
    font-size: {font_size}px;
    font-weight: 700;
    color: {text_primary};
    line-height: 1.35;
    letter-spacing: -0.3px;
  }}

  .sub-text {{
    font-size: 22px;
    font-weight: 400;
    color: {text_secondary};
    line-height: 1.5;
    margin-top: 20px;
  }}

  /* Tag / label */
  .tag {{
    display: inline-block;
    background: {tag_bg};
    color: {tag_color};
    font-size: 14px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 100px;
    margin-bottom: 24px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}

  /* Footer */
  .footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 28px;
    border-top: 1px solid {border};
  }}

  .footer-brand {{
    font-size: 15px;
    font-weight: 600;
    color: {text_muted};
    letter-spacing: 0.3px;
  }}

  .engagement {{
    display: flex;
    gap: 28px;
  }}

  .eng-item {{
    display: flex;
    align-items: center;
    gap: 7px;
    color: {text_muted};
    font-size: 15px;
  }}

  .eng-item svg {{
    width: 18px;
    height: 18px;
    fill: {text_muted};
  }}

  /* Cover slide specific */
  .cover-eyebrow {{
    font-size: 16px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: {accent};
    margin-bottom: 20px;
  }}

  .cover-title {{
    font-size: {cover_size}px;
    font-weight: 800;
    color: {text_primary};
    line-height: 1.15;
    letter-spacing: -0.5px;
    margin-bottom: 24px;
  }}

  .cover-subtitle {{
    font-size: 22px;
    color: {text_secondary};
    line-height: 1.5;
    margin-bottom: 40px;
  }}

  .swipe-cta {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 17px;
    font-weight: 600;
    color: {accent};
  }}

  .swipe-arrow {{
    font-size: 20px;
  }}

  /* CTA slide specific */
  .cta-label {{
    font-size: 16px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: {accent};
    margin-bottom: 16px;
  }}

  .cta-headline {{
    font-size: 42px;
    font-weight: 800;
    color: {text_primary};
    line-height: 1.2;
    margin-bottom: 20px;
  }}

  .cta-body {{
    font-size: 21px;
    color: {text_secondary};
    line-height: 1.55;
    margin-bottom: 36px;
  }}

  .cta-button {{
    display: inline-block;
    background: {accent};
    color: white;
    font-size: 18px;
    font-weight: 700;
    padding: 16px 32px;
    border-radius: 100px;
    letter-spacing: 0.3px;
  }}

  /* Bullet list */
  .bullet-list {{
    list-style: none;
    padding: 0;
    margin-top: 24px;
  }}

  .bullet-list li {{
    display: flex;
    align-items: flex-start;
    gap: 14px;
    font-size: 22px;
    color: {text_secondary};
    line-height: 1.4;
    margin-bottom: 16px;
  }}

  .bullet-list li::before {{
    content: attr(data-num);
    color: {accent};
    font-weight: 700;
    font-size: 20px;
    min-width: 28px;
    padding-top: 2px;
  }}
</style>
</head>
<body>
<div class="card" id="slide">
{inner_html}
</div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Theme palettes
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#0f0f0f",
        "card_bg": "#161616",
        "text_primary": "#f0f0f0",
        "text_secondary": "#aaaaaa",
        "text_muted": "#666666",
        "accent": "#2562eb",
        "tag_bg": "rgba(37,98,235,0.15)",
        "tag_color": "#2562eb",
        "border": "#242424",
        "cover_size": "54",
        "font_size": "38",
    },
    "light": {
        "bg": "#f5f5f5",
        "card_bg": "#ffffff",
        "text_primary": "#0f0f0f",
        "text_secondary": "#555555",
        "text_muted": "#999999",
        "accent": "#1a56db",
        "tag_bg": "rgba(26,86,219,0.08)",
        "tag_color": "#1a56db",
        "border": "#e8e8e8",
        "cover_size": "54",
        "font_size": "38",
    },
    "black": {
        "bg": "#000000",
        "card_bg": "#111111",
        "text_primary": "#ffffff",
        "text_secondary": "#888888",
        "text_muted": "#555555",
        "accent": "#ffffff",
        "tag_bg": "rgba(255,255,255,0.1)",
        "tag_color": "#ffffff",
        "border": "#1f1f1f",
        "cover_size": "56",
        "font_size": "40",
    },
}

# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def _header_html(slide: dict, theme: dict, slide_num: int, total: int, handle: str, name: str, avatar_b64: str = "") -> str:
    if avatar_b64:
        avatar_inner = f'<img src="data:image/png;base64,{avatar_b64}" alt="{name}" />'
    else:
        avatar_inner = f'<span>{name[0].upper()}</span>'
    return f"""
    <div class="header">
      <div class="avatar">{avatar_inner}</div>
      <div class="name-block">
        <div class="display-name">{name} <span class="verified"><svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 3L24.5 7.2L30.5 6L32.5 12L38 15L36 21L38 27L32.5 30L30.5 36L24.5 34.8L20 39L15.5 34.8L9.5 36L7.5 30L2 27L4 21L2 15L7.5 12L9.5 6L15.5 7.2L20 3Z" fill="#3797F0"/><path d="M13 20.5L17.5 25L27 15" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span></div>
        <div class="handle">@{handle}</div>
      </div>
      <div class="slide-num">{slide_num} / {total}</div>
    </div>"""


def _footer_html(theme: dict, brand: str) -> str:
    return f"""
    <div class="footer">
      <div class="footer-brand">{brand}</div>
      <div class="engagement">
        <div class="eng-item">
          <svg viewBox="0 0 24 24"><path d="M16.697 5.5c-1.222-.06-2.679.51-3.89 2.16l-.805 1.09-.806-1.09C9.984 6.01 8.526 5.44 7.304 5.5c-1.243.07-2.349.78-2.91 1.91-.552 1.12-.633 2.78.479 4.82 1.074 1.97 3.257 4.27 7.129 6.61 3.87-2.34 6.052-4.64 7.126-6.61 1.111-2.04 1.03-3.7.477-4.82-.561-1.13-1.666-1.84-2.908-1.91zm4.187 7.69c-1.351 2.48-4.001 5.12-8.379 7.67l-.503.3-.504-.3c-4.379-2.55-7.029-5.19-8.382-7.67-1.36-2.5-1.41-4.86-.514-6.67.887-1.79 2.647-2.91 4.601-3.01 1.651-.09 3.368.56 4.798 2.01 1.429-1.45 3.146-2.1 4.796-2.01 1.954.1 3.714 1.22 4.601 3.01.896 1.81.846 4.17-.514 6.67z"/></svg>
          <span>4.2K</span>
        </div>
        <div class="eng-item">
          <svg viewBox="0 0 24 24"><path d="M4.5 3.88l4.432 4.14-1.364 1.46L5.5 7.55V16c0 1.1.896 2 2 2H13v2H7.5c-2.209 0-4-1.79-4-4V7.55L1.432 9.48.068 8.02 4.5 3.88zM16.5 6H11V4h5.5c2.209 0 4 1.79 4 4v8.45l2.068-1.93 1.364 1.46-4.432 4.14-4.432-4.14 1.364-1.46 2.068 1.93V8c0-1.1-.896-2-2-2z"/></svg>
          <span>891</span>
        </div>
        <div class="eng-item">
          <svg viewBox="0 0 24 24"><path d="M1.751 10c0-4.42 3.584-8 8.005-8h4.366c4.49 0 7.498 3.67 7.498 8 0 4.43-3.135 8-7.502 8h-.24c-.301 0-.595.13-.805.35l-2.832 3.09a.75.75 0 01-1.24-.55v-2.94c0-.232-.17-.42-.401-.44C3.96 17.57 1.751 14.1 1.751 10zm8.005-6c-3.317 0-6.005 2.69-6.005 6 0 3.33 2.378 6.06 5.8 6.29.79.05 1.405.71 1.405 1.5v1.33l1.81-1.97c.44-.48 1.07-.76 1.73-.76h.24c2.883 0 5.502-2.56 5.502-6s-2.51-6-5.498-6h-4.484z"/></svg>
          <span>213</span>
        </div>
      </div>
    </div>"""


def render_cover(slide: dict, theme: dict, slide_num: int, total: int, handle: str, name: str, brand: str, avatar_b64: str = "") -> str:
    inner = f"""
    {_header_html(slide, theme, slide_num, total, handle, name, avatar_b64)}
    <div class="content">
      <div class="cover-eyebrow">{slide.get('eyebrow', 'Thread')}</div>
      <div class="cover-title">{slide['title']}</div>
      <div class="cover-subtitle">{slide.get('subtitle', '')}</div>
      <div class="swipe-cta">
        <span>Swipe to learn</span>
        <span class="swipe-arrow">→</span>
      </div>
    </div>
    {_footer_html(theme, brand)}"""
    return inner


def render_point(slide: dict, theme: dict, slide_num: int, total: int, handle: str, name: str, brand: str, avatar_b64: str = "") -> str:
    tag = f'<div class="tag">{slide["tag"]}</div>' if slide.get("tag") else ""
    sub = f'<div class="sub-text">{slide["sub_text"]}</div>' if slide.get("sub_text") else ""

    text_len = len(slide.get("main_text", ""))
    if text_len > 120:
        font_override = "28"
    elif text_len > 80:
        font_override = "32"
    else:
        font_override = theme["font_size"]

    inner = f"""
    {_header_html(slide, theme, slide_num, total, handle, name, avatar_b64)}
    <div class="content">
      {tag}
      <div class="main-text" style="font-size:{font_override}px">{slide['main_text']}</div>
      {sub}
    </div>
    {_footer_html(theme, brand)}"""
    return inner


def render_list(slide: dict, theme: dict, slide_num: int, total: int, handle: str, name: str, brand: str, avatar_b64: str = "") -> str:
    items = "".join(
        f'<li data-num="{i+1:02d}">{item}</li>'
        for i, item in enumerate(slide.get("items", []))
    )
    inner = f"""
    {_header_html(slide, theme, slide_num, total, handle, name, avatar_b64)}
    <div class="content">
      <div class="main-text">{slide['main_text']}</div>
      <ul class="bullet-list">{items}</ul>
    </div>
    {_footer_html(theme, brand)}"""
    return inner


def render_cta(slide: dict, theme: dict, slide_num: int, total: int, handle: str, name: str, brand: str, avatar_b64: str = "") -> str:
    inner = f"""
    {_header_html(slide, theme, slide_num, total, handle, name, avatar_b64)}
    <div class="content">
      <div class="cta-label">Want this for your business?</div>
      <div class="cta-headline">{slide.get('headline', 'Book a free strategy call')}</div>
      <div class="cta-body">{slide.get('body', '')}</div>
      <div class="cta-button">{slide.get('button', 'DM me "AI" to start')}</div>
    </div>"""
    return inner


RENDERERS = {
    "cover": render_cover,
    "point": render_point,
    "list": render_list,
    "cta": render_cta,
}

# ---------------------------------------------------------------------------
# Screenshot engine
# ---------------------------------------------------------------------------

def screenshot_slides(slides_data: list, output_dir: Path, theme_name: str, handle: str, name: str, brand: str, headshot: str = ""):
    from playwright.sync_api import sync_playwright

    theme = THEMES.get(theme_name, THEMES["dark"])
    total = len(slides_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load headshot as base64 if provided
    avatar_b64 = ""
    if headshot and Path(headshot).exists():
        with open(headshot, "rb") as f:
            avatar_b64 = base64.b64encode(f.read()).decode("utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})

        for i, slide in enumerate(slides_data):
            slide_type = slide.get("type", "point")
            renderer = RENDERERS.get(slide_type, render_point)
            inner = renderer(slide, theme, i + 1, total, handle, name, brand, avatar_b64)

            html = SLIDE_HTML.format(inner_html=inner, **theme)
            page.set_content(html)
            page.wait_for_load_state("networkidle")

            out_path = output_dir / f"Slide {i+1:02d}.png"
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 1080, "height": 1080})
            print(f"  ✓ Slide {i+1:02d} → {out_path}")

        browser.close()

    return list(output_dir.glob("*.png"))


# ---------------------------------------------------------------------------
# Preview stitcher
# ---------------------------------------------------------------------------

def stitch_preview(png_files: list, output_dir: Path):
    from PIL import Image

    png_files = sorted(png_files)
    if not png_files:
        return None

    cols = min(len(png_files), 5)
    rows = (len(png_files) + cols - 1) // cols
    thumb_w, thumb_h = 360, 360
    gap = 8

    canvas = Image.new("RGB", (cols * thumb_w + (cols - 1) * gap, rows * thumb_h + (rows - 1) * gap), (20, 20, 20))

    for idx, path in enumerate(png_files):
        img = Image.open(path).resize((thumb_w, thumb_h), Image.LANCZOS)
        col = idx % cols
        row = idx // cols
        canvas.paste(img, (col * (thumb_w + gap), row * (thumb_h + gap)))

    preview_path = output_dir / "00_preview.png"
    canvas.save(preview_path)
    print(f"\n  ✓ Preview → {preview_path}")
    return preview_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Thread-to-Carousel PNG generator")
    parser.add_argument("--input", help="JSON file with slides array")
    parser.add_argument("--slides", help="JSON string with slides array")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: auto-dated)")
    parser.add_argument("--theme", default="dark", choices=list(THEMES.keys()), help="Visual theme")
    parser.add_argument("--handle", default="itszacnielsen", help="Twitter/X handle")
    parser.add_argument("--name", default="[YOUR_NAME]", help="Display name")
    parser.add_argument("--brand", default="elitesystems.ai", help="Footer brand text")
    parser.add_argument("--headshot", default="assets/headshots/zac-nielsen.png", help="Path to profile photo PNG")
    parser.add_argument("--no-preview", action="store_true", help="Skip stitched preview")
    args = parser.parse_args()

    # Load slides
    if args.input:
        with open(args.input) as f:
            slides = json.load(f)
    elif args.slides:
        slides = json.loads(args.slides)
    else:
        print("Error: provide --input <file.json> or --slides '<json>'", file=sys.stderr)
        sys.exit(1)

    if isinstance(slides, dict) and "slides" in slides:
        slides = slides["slides"]

    # Output dir
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        topic_slug = slides[0].get("title", "carousel")[:30].lower().replace(" ", "-").replace("'", "")
        out_dir = Path(f"output/carousels/{date_str}--{topic_slug}")

    print(f"\n  Rendering {len(slides)} slides → {out_dir}/\n")

    png_files = screenshot_slides(slides, out_dir, args.theme, args.handle, args.name, args.brand, args.headshot)

    if not args.no_preview:
        stitch_preview(png_files, out_dir)

    print(f"\n  Done. {len(png_files)} slides in {out_dir}/\n")
    print(out_dir)  # last line = path for skill to pick up


if __name__ == "__main__":
    main()
