---
name: instagram-thread-carousel
description: >
  Generate Instagram carousel slides styled as X/Twitter thread screenshots.
  Triggers on: /carousel thread [topic], /thread-carousel [topic], "make a carousel about",
  "create carousel slides", "generate carousel". Outputs 1080x1080 PNG files ready to post.
---

# Instagram Thread Carousel Generator

Generate a set of Instagram carousel slides that look like a Twitter/X thread.
Each slide is a 1080x1080 PNG, screenshot from a styled HTML template.

## Step 1 — Understand the topic

From the user's input, identify:
- The core topic / lesson
- The target audience (default: coaches & consultants at $200K–$2M/year)
- Slide count (default: 7 slides — 1 cover + 5 content + 1 CTA)
- Theme: `dark` (default), `light`, or `black`

## Step 2 — Generate the slides JSON

Write a JSON array with this structure. Output it as a code block:

```json
[
  {
    "type": "cover",
    "eyebrow": "Thread",
    "title": "5 AI Systems Every Coach Needs Running Before They Sleep",
    "subtitle": "Most coaches are doing this manually. Here's how to automate all of it."
  },
  {
    "type": "point",
    "tag": "01 / Lead Follow-Up",
    "main_text": "Your first follow-up should go out within 60 seconds of a lead opting in.",
    "sub_text": "Most coaches follow up within 24 hours. By then, 78% of leads have already talked to someone else."
  },
  {
    "type": "point",
    "tag": "02 / Discovery Calls",
    "main_text": "Stop manually booking discovery calls. Build a qualifier first.",
    "sub_text": "An AI qualifier asks 5 questions, scores the lead, and only books if they're a fit. You only talk to buyers."
  },
  {
    "type": "list",
    "main_text": "The 3 systems worth building first:",
    "items": [
      "Lead follow-up sequence (runs in under 60s, 24/7)",
      "AI call qualifier (filters tyre-kickers automatically)",
      "Weekly client check-in (zero manual effort)"
    ]
  },
  {
    "type": "point",
    "tag": "03 / Client Delivery",
    "main_text": "Weekly check-ins shouldn't take you 2 hours to send.",
    "sub_text": "One workflow pulls client data, generates a personalised update, and sends it. You review once a week instead of writing 20 emails."
  },
  {
    "type": "point",
    "tag": "The Real Cost",
    "main_text": "Every hour you spend on manual ops is an hour you're not spending on growth.",
    "sub_text": "The coaches I work with get back 8–12 hours a week in month one. That's time back in sales, content, or just switching off."
  },
  {
    "type": "cta",
    "headline": "Want these systems built for your business?",
    "body": "I build these once, they run forever. No VA needed. No extra software.",
    "button": "DM me \"AI\" to start"
  }
]
```

**Slide type rules:**
- `cover` — always slide 1. Has eyebrow, title, subtitle, swipe CTA.
- `point` — main insight. `tag` is optional label (e.g. "01 / Topic"). `sub_text` expands on it.
- `list` — numbered bullet list. `main_text` is the heading, `items` is an array of strings (3–5 max).
- `cta` — always last slide. headline, body, button text.

**Content rules (Zac's voice):**
- Lead with outcomes, not process
- Use specific numbers where possible ("78% of leads", "8–12 hours/week")
- No "dive into", no "game-changer", no em dashes
- Each slide should make sense standalone — someone screenshots individual slides
- `main_text` should be punchy and under 120 characters where possible
- `sub_text` is the "proof/expand" layer — 1–2 sentences max

## Step 3 — Run the generator

Once the JSON is finalised, run:

```bash
python3 scripts/thread-to-carousel.py \
  --slides '<JSON_ARRAY_HERE>' \
  --theme dark \
  --handle itszacnielsen \
  --name "[YOUR_NAME]" \
  --brand "elitesystems.ai" \
  --headshot assets/headshots/zac-nielsen.png
```

The script outputs PNG files and prints the output directory path on the last line.
Capture that path.

## Step 4 — Show results

After the script runs:
1. List the output files (Slide 01.png through Slide N.png + 00_preview.png)
2. Read and display `00_preview.png` so the user can see all slides at once
3. Report the output directory path

## Step 5 — Offer Drive upload

Ask: "Upload to Drive → Ads → Content Carousels?"
If yes, use the `drive` skill to upload the batch folder.

## Rules

- Always generate cover + CTA as bookends — never skip them
- Default to 7 slides (1 cover + 5 content + 1 CTA). User can request more/fewer.
- Default theme: `dark`. Only switch if user asks.
- If the user gives a topic but no detail, generate the full content yourself — don't ask clarifying questions for every slide
- The JSON must be valid — double-check bracket/quote matching before running the script
- If the script errors, read the error and fix the JSON or re-run
