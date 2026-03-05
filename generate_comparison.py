#!/usr/bin/env python3
"""
Comparison Caricature Generator
Generates "Some vs Others" style Instagram comparison images.
Uses Gemini Imagen for image generation + Pillow for text overlay.
Output: 1080 x 1350 PNG (two 1080x675 panels stacked vertically)
Also generates a CTA slide: single 1080x1350 panel.
"""

import os
import sys
import base64
import textwrap
import requests
from datetime import date
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Load credentials
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GDRIVE_COMPARISONS_ID = os.environ.get("GDRIVE_COMPARISONS_ID")

PANEL_W = 1080
PANEL_H = 675
SLIDE_H = 1350  # Full-height CTA slide
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "comparisons")

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"

COLOR_WHITE = (255, 255, 255)
COLOR_CYAN  = (0, 255, 255)
COLOR_GREY  = (160, 160, 160)


# ─── Image Generation ────────────────────────────────────────────────────────

def generate_panel_image(prompt: str, aspect_ratio: str = "16:9") -> Image.Image:
    """Generate a single panel using Gemini Imagen 4."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "imagen-4.0-generate-001:predict"
    )
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
        },
    }

    print(f"  Generating image...")
    resp = requests.post(url, headers=headers, params=params, json=body)

    if resp.status_code != 200:
        print(f"  API error {resp.status_code}: {resp.text}")
        raise RuntimeError(f"Imagen API error: {resp.status_code}")

    data = resp.json()
    b64 = data["predictions"][0]["bytesBase64Encoded"]
    img_bytes = base64.b64decode(b64)
    return Image.open(BytesIO(img_bytes)).convert("RGB")


# ─── Text Overlay ─────────────────────────────────────────────────────────────

def _draw_lines(draw, lines, font, start_y, line_spacing, stroke_width,
                fill_color=COLOR_WHITE):
    """Draw a block of lines centred horizontally with black stroke + fill."""
    line_heights = [draw.textbbox((0, 0), ln, font=font)[3] for ln in lines]
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (PANEL_W - text_w) // 2
        y = start_y + sum(line_heights[:i]) + line_spacing * i
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill_color)
    return sum(line_heights) + line_spacing * (len(lines) - 1)


def add_text_overlay(image: Image.Image, label: str, body: str,
                     label_color=COLOR_WHITE, panel_h: int = PANEL_H) -> Image.Image:
    """
    Two-line format:
      LABEL — large all-caps identity tag (e.g. "TOP OPERATORS")
      body  — smaller specific behaviour text

    Both blocks are centred horizontally, anchored ~68% down the panel.
    label_color: colour tuple for the label (default white; CTA uses CYAN).
    panel_h: height of the panel used for anchor calculation.
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)

    stroke_width = 3
    label_spacing = 8
    body_spacing = 10
    block_gap = 18

    label_size = 64
    body_size = 40
    try:
        label_font = ImageFont.truetype(FONT_PATH, label_size)
        body_font = ImageFont.truetype(FONT_PATH, body_size)
    except Exception:
        label_font = body_font = ImageFont.load_default()

    label_lines = [label.upper()]
    body_lines = []
    for raw in body.split("\\n"):
        wrapped = textwrap.wrap(raw, width=24)
        body_lines.extend(wrapped if wrapped else [""])

    lh_label = [draw.textbbox((0, 0), ln, font=label_font)[3] for ln in label_lines]
    lh_body = [draw.textbbox((0, 0), ln, font=body_font)[3] for ln in body_lines]
    total_h = (
        sum(lh_label) + label_spacing * (len(label_lines) - 1)
        + block_gap
        + sum(lh_body) + body_spacing * (len(body_lines) - 1)
    )

    anchor_y = int(panel_h * 0.68) - total_h // 2

    label_block_h = _draw_lines(draw, label_lines, label_font, anchor_y,
                                label_spacing, stroke_width, fill_color=label_color)

    body_start_y = anchor_y + label_block_h + block_gap
    _draw_lines(draw, body_lines, body_font, body_start_y, body_spacing,
                stroke_width, fill_color=COLOR_WHITE)

    return img


def _add_handle(image: Image.Image, handle: str = "[YOUR_INSTAGRAM_HANDLE]",
                font_size: int = 28) -> Image.Image:
    """Draw handle text bottom-right, muted grey."""
    img = image.copy()
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), handle, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    margin = 24
    x = img.width - text_w - margin
    y = img.height - text_h - margin
    draw.text((x, y), handle, font=font, fill=COLOR_GREY)
    return img


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def create_comparison(
    top_prompt: str,
    bottom_prompt: str,
    top_label: str,
    top_body: str,
    bottom_label: str,
    bottom_body: str,
    output_name: str,
):
    """Full pipeline: generate → resize → overlay → stack → export."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{output_name}.png")

    print(f"\n{'─'*50}")
    print(f"Generating: {output_name}")
    print(f"{'─'*50}")

    raw_dir = os.path.join(OUTPUT_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    top_raw_path = os.path.join(raw_dir, f"{output_name}_top_raw.png")
    bottom_raw_path = os.path.join(raw_dir, f"{output_name}_bottom_raw.png")

    if os.path.exists(top_raw_path) and os.path.exists(bottom_raw_path):
        print("\nUsing cached raw panels (skip API call)...")
        top_img = Image.open(top_raw_path).convert("RGB")
        bottom_img = Image.open(bottom_raw_path).convert("RGB")
    else:
        print("\n[TOP PANEL]")
        top_img = generate_panel_image(top_prompt)
        top_img.save(top_raw_path)

        print("\n[BOTTOM PANEL]")
        bottom_img = generate_panel_image(bottom_prompt)
        bottom_img.save(bottom_raw_path)

    print("\nResizing panels...")
    top_img = top_img.resize((PANEL_W, PANEL_H), Image.LANCZOS)
    bottom_img = bottom_img.resize((PANEL_W, PANEL_H), Image.LANCZOS)

    print("Adding text overlays...")
    top_img = add_text_overlay(top_img, top_label, top_body)
    bottom_img = add_text_overlay(bottom_img, bottom_label, bottom_body)

    final = Image.new("RGB", (PANEL_W, PANEL_H * 2))
    final.paste(top_img, (0, 0))
    final.paste(bottom_img, (0, PANEL_H))

    final.save(output_path, "PNG")
    print(f"\n✅ Saved: {output_path}")
    return output_path


def create_cta_slide(prompt: str, label: str, body: str, output_name: str):
    """
    Full pipeline for the CTA slide.
    Single 1080×1350 panel — no stacking.
    Label rendered in CYAN. Handle [YOUR_INSTAGRAM_HANDLE] added bottom-right.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{output_name}.png")

    print(f"\n{'─'*50}")
    print(f"Generating CTA slide: {output_name}")
    print(f"{'─'*50}")

    raw_dir = os.path.join(OUTPUT_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{output_name}_raw.png")

    if os.path.exists(raw_path):
        print("\nUsing cached raw panel (skip API call)...")
        img = Image.open(raw_path).convert("RGB")
    else:
        print("\n[CTA PANEL]")
        # 4:5 aspect ratio → 1080×1350
        img = generate_panel_image(prompt, aspect_ratio="3:4")
        img.save(raw_path)

    print("\nResizing panel...")
    img = img.resize((PANEL_W, SLIDE_H), Image.LANCZOS)

    print("Adding text overlay (CYAN label)...")
    img = add_text_overlay(img, label, body,
                           label_color=COLOR_CYAN, panel_h=SLIDE_H)

    print("Adding handle...")
    img = _add_handle(img)

    img.save(output_path, "PNG")
    print(f"\n✅ Saved: {output_path}")
    return output_path


# ─── Content Definitions ──────────────────────────────────────────────────────

COMPARISONS = [
    {
        "name": "lead_followup",
        "top_prompt": (
            "Comic book illustration, cel shaded style, athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, sitting relaxed at a clean modern desk, laptop screen "
            "showing a CRM dashboard with green notification bubbles stacking up, "
            "phone propped showing '3 New Leads' notification, calm confident smile, "
            "leaning back in chair. Warm golden orange lighting, confident expression, "
            "clean modern office environment, rich detail, no text in image."
        ),
        "bottom_prompt": (
            "Comic book illustration, cel shaded style, same athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, hunched over a cluttered desk, laptop showing a messy "
            "spreadsheet with yellow rows and half-typed notes, sticky notes on monitor "
            "edge, phone in one hand mid-text, cold coffee, dark window in background "
            "showing evening. Cool blue-grey lighting, stressed exhausted expression, "
            "cluttered manual work environment, rich detail, no text in image."
        ),
        "top_label": "TOP OPERATORS",
        "top_body": "AI follows up every lead\\nwithin 60 seconds",
        "bottom_label": "MOST PEOPLE",
        "bottom_body": "Chasing leads from a\\nspreadsheet at 9pm",
    },
    {
        "name": "monday_morning",
        "top_prompt": (
            "Comic book illustration, cel shaded style, athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, sitting relaxed in a clean bright home office, holding "
            "a coffee mug, phone showing a Telegram notification '2 New Qualified "
            "Leads', laptop beside him showing a content dashboard with green "
            "Published indicators, calm peaceful morning expression. Warm golden "
            "orange lighting, confident relaxed expression, clean modern environment, "
            "rich detail, no text in image."
        ),
        "bottom_prompt": (
            "Comic book illustration, cel shaded style, same athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, sitting at a messy desk in the morning, laptop showing "
            "inbox with '47 unread' badge, phone with stacked app notifications, "
            "hand pressed to forehead, notepad full of scrawled tasks, untouched "
            "coffee on desk. Cool blue-grey lighting, stressed overwhelmed expression, "
            "cluttered work environment, rich detail, no text in image."
        ),
        "top_label": "TOP OPERATORS",
        "top_body": "Monday: business runs\\nwhile they sleep",
        "bottom_label": "MOST PEOPLE",
        "bottom_body": "Monday: inbox at 47 unread\\nbefore coffee",
    },
    {
        "name": "content_creation",
        "top_prompt": (
            "Comic book illustration, cel shaded style, athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, leaning back at a clean modern desk, laptop showing a "
            "content scheduler with 7 posts queued and green Published badges, phone "
            "on a stand beside the laptop, relaxed smile. Warm golden orange lighting, "
            "confident expression, clean modern office environment, rich detail, no text in image."
        ),
        "bottom_prompt": (
            "Comic book illustration, cel shaded style, same athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, hunched forward at a desk, scrubbing through phone footage, "
            "CapCut open on laptop, sticky note with question marks on monitor, empty "
            "coffee cup, phone showing 0 notifications. Cool blue-grey lighting, "
            "stressed exhausted expression, cluttered manual work environment, rich detail, "
            "no text in image."
        ),
        "top_label": "TOP OPERATORS",
        "top_body": "AI scripts, edits and\\nschedules content while they work",
        "bottom_label": "MOST PEOPLE",
        "bottom_body": "Manually editing reels\\nat 11pm with no plan",
    },
    {
        "name": "client_onboarding",
        "top_prompt": (
            "Comic book illustration, cel shaded style, athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, sitting relaxed at a desk, laptop showing an automated "
            "onboarding checklist with green tick marks running down the screen, "
            "phone showing 'New client onboarded' notification. Warm golden orange "
            "lighting, calm confident expression, clean modern office environment, "
            "rich detail, no text in image."
        ),
        "bottom_prompt": (
            "Comic book illustration, cel shaded style, same athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, typing frantically at a desk, three browser tabs open, "
            "copy-pasting from a Google Doc into Gmail on screen, sticky notes "
            "everywhere, slightly panicked expression. Cool blue-grey lighting, "
            "stressed overwhelmed expression, cluttered manual work environment, "
            "rich detail, no text in image."
        ),
        "top_label": "TOP OPERATORS",
        "top_body": "New client onboards\\nwithout them lifting a finger",
        "bottom_label": "MOST PEOPLE",
        "bottom_body": "Copy-pasting welcome emails\\nfrom a Google Doc every time",
    },
    {
        "name": "revenue_reporting",
        "top_prompt": (
            "Comic book illustration, cel shaded style, athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, leaning back holding a phone showing a clean revenue "
            "dashboard with an upward trending chart and green metrics, coffee mug "
            "in the other hand, calm confident expression. Warm golden orange "
            "lighting, relaxed confident pose, clean modern office environment, "
            "rich detail, no text in image."
        ),
        "bottom_prompt": (
            "Comic book illustration, cel shaded style, same athletic male entrepreneur "
            "with short styled brown hair swept to the side, light stubble, fitted "
            "black t-shirt, hunched over a spreadsheet with multiple tabs open, "
            "manually entering numbers, calculator beside the keyboard, frustrated "
            "squinting expression. Cool blue-grey lighting, stressed exhausted "
            "expression, cluttered manual work environment, rich detail, no text in image."
        ),
        "top_label": "TOP OPERATORS",
        "top_body": "Automated dashboard lands\\nin their inbox every Monday",
        "bottom_label": "MOST PEOPLE",
        "bottom_body": "Manually building the\\nspreadsheet at month end",
    },
]

CTA_SLIDE = {
    "name": "cta_which_one",
    "prompt": (
        "Comic book illustration, cel shaded style, athletic male entrepreneur "
        "with short styled brown hair swept to the side, light stubble, fitted "
        "black t-shirt, standing confidently facing the camera, pointing directly "
        "at the viewer with one finger, slight smirk, clean modern studio backdrop. "
        "Warm golden orange lighting, bold confident composition, full body or 3/4 "
        "shot, rich detail, no text in image."
    ),
    "label": "WHICH ONE ARE YOU?",
    "body": "If you want the operator version —\\nComment 'AI' for a free AI roadmap",
}


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not found in .env")
        sys.exit(1)

    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    results = []

    # Generate comparison slides
    for comp in COMPARISONS:
        if target != "all" and comp["name"] != target:
            continue
        path = create_comparison(
            top_prompt=comp["top_prompt"],
            bottom_prompt=comp["bottom_prompt"],
            top_label=comp["top_label"],
            top_body=comp["top_body"],
            bottom_label=comp["bottom_label"],
            bottom_body=comp["bottom_body"],
            output_name=comp["name"],
        )
        results.append(path)

    # Generate CTA slide
    if target in ("all", CTA_SLIDE["name"]):
        path = create_cta_slide(
            prompt=CTA_SLIDE["prompt"],
            label=CTA_SLIDE["label"],
            body=CTA_SLIDE["body"],
            output_name=CTA_SLIDE["name"],
        )
        results.append(path)

    print(f"\n{'─'*50}")
    print(f"Done. {len(results)} image(s) generated:")
    for r in results:
        print(f"  → {r}")

    # ── Auto-upload to Google Drive ──────────────────────────────────────────
    if results and GDRIVE_COMPARISONS_ID:
        _upload_batch_to_drive(results)


def _upload_batch_to_drive(paths: list):
    """Upload a batch of images to Google Drive under a dated subfolder."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request
    except ImportError:
        print("\n⚠ google-api-python-client not installed — skipping Drive upload")
        print("  Run: pip3 install google-api-python-client google-auth")
        return

    token_path = os.path.expanduser("~/.config/gspread/token.json")
    if not os.path.exists(token_path):
        print("\n⚠ No Drive token found at ~/.config/gspread/token.json — skipping upload")
        return

    with open(token_path) as f:
        t = __import__("json").load(f)

    creds = Credentials(
        token=t.get("token") or t.get("access_token"),
        refresh_token=t["refresh_token"],
        token_uri=t["token_uri"],
        client_id=t["client_id"],
        client_secret=t["client_secret"],
        scopes=t["scopes"],
    )
    if not creds.valid:
        creds.refresh(Request())

    drive = build("drive", "v3", credentials=creds)

    # Create dated batch subfolder
    today = date.today().strftime("%Y-%m-%d")
    n = len(paths)
    batch_name = f"{today} — Comparison Carousel ({n} slides)"
    batch = drive.files().create(
        body={
            "name": batch_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [GDRIVE_COMPARISONS_ID],
        },
        fields="id",
    ).execute()
    batch_id = batch["id"]

    print(f"\n📁 Uploading to Drive: {batch_name}")
    for i, path in enumerate(paths, 1):
        filename = os.path.basename(path)
        label = filename.replace(".png", "").replace("_", " ").title()
        drive_name = f"Slide {i:02d} — {label}.png"
        media = MediaFileUpload(path, mimetype="image/png", resumable=False)
        drive.files().create(
            body={"name": drive_name, "parents": [batch_id]},
            media_body=media,
            fields="id",
        ).execute()
        print(f"  ✅ {drive_name}")

    print(f"\n🔗 https://drive.google.com/drive/folders/{batch_id}")
