#!/usr/bin/env python3
"""
Content Autopilot — Daily draft generation pipeline.

Runs at 7am AEST daily via PM2 cron (21:00 UTC previous day).
Reads research from content_intelligence.py (daily_content_brief.json).
Generates 5 content drafts in Zac's voice using Claude API.
Saves drafts + manifest to data/content_drafts/{YYYY-MM-DD}/.

Output structure:
  data/content_drafts/2026-03-04/
    manifest.json          — index of all drafts + status
    1_reel_howto.md        — full draft content
    2_reel_mythbust.md
    3_carousel_tool.md
    4_linkedin_system.md
    5_text_results.md
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

AEST = timezone(timedelta(hours=10))
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
DRAFTS_DIR = DATA_DIR / "content_drafts"


# ── Env loader ────────────────────────────────────────────────────────────────

def _load_env() -> dict:
    env = dict(os.environ)
    for candidate in [ROOT / ".env", Path.home() / ".env"]:
        if candidate.exists():
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            break
    return env


env = _load_env()

ANTHROPIC_API_KEY = env.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env.get("TELEGRAM_GROUP_ID", "") or env.get("TELEGRAM_CHAT_ID", "")


# ── Weekly pillar schedule ────────────────────────────────────────────────────

# Maps weekday (0=Mon) to (primary_pillar, secondary_pillar, format_hint)
WEEKLY_SCHEDULE = {
    0: ("How-To Tutorial", "Myth Busting",     "howto",   "mythbust"),   # Monday
    1: ("Myth Busting",   "Tool Spotlight",    "mythbust","tool"),        # Tuesday
    2: ("Tool Spotlight",  "How-To Tutorial",  "tool",    "howto"),       # Wednesday
    3: ("Results & Proof", "System Reveal",    "results", "system"),      # Thursday
    4: ("System Reveal",   "Results & Proof",  "system",  "results"),     # Friday
    5: ("Myth Busting",   "Tool Spotlight",    "mythbust","tool"),        # Saturday
    6: ("How-To Tutorial", "System Reveal",    "howto",   "system"),      # Sunday
}

FUNNEL_MAP = {
    "How-To Tutorial": "TOFU",
    "Tool Spotlight":  "TOFU",
    "Myth Busting":    "MOFU",
    "System Reveal":   "BOFU",
    "Results & Proof": "BOFU",
    "Breaking News":   "TOFU",
}

TYPE_EMOJI = {
    "reel":     "🎬",
    "carousel": "🎠",
    "linkedin": "💼",
    "text":     "📝",
}


# ── Context loader ─────────────────────────────────────────────────────────────

def _read_file(path: Path, max_chars: int = 3000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        return text[:max_chars] if len(text) > max_chars else text
    except Exception:
        return ""


def _load_context() -> dict:
    """Load all reference context needed for content generation."""
    # Brand voice (cap at 2000 chars — just the rules, not the full doc)
    brand_voice = _read_file(KNOWLEDGE_DIR / "brand_voice.md", 2500)

    # Content pillars summary (cap at 1500 chars)
    pillars = _read_file(KNOWLEDGE_DIR / "content_pillars.md", 1500)

    # Top performing content — extract hooks and patterns
    top_content = []
    try:
        data = json.loads((DATA_DIR / "top_performing_content.json").read_text())
        for post in data.get("top_performing", [])[:5]:
            preview = post.get("caption_preview", "")[:120]
            fmt = post.get("media_type", "")
            er = post.get("engagement_rate", 0)
            top_content.append(f"  [{fmt} · ER {er:.2%}] {preview}")
    except Exception:
        pass

    # Daily content brief from content_intelligence.py
    brief_ideas = []
    try:
        brief = json.loads((DATA_DIR / "daily_content_brief.json").read_text())
        for idea in brief.get("content_ideas", [])[:3]:
            headline = idea.get("headline", "")[:100]
            angle = idea.get("angle", "")[:120]
            stage = idea.get("funnel_stage", "")
            brief_ideas.append(f"  [{stage}] {headline}\n    Angle: {angle}")
    except Exception:
        pass

    # Recent lessons from tasks/lessons.md (first 1000 chars)
    lessons = _read_file(ROOT / "tasks" / "lessons.md", 1000)

    return {
        "brand_voice": brand_voice,
        "pillars_summary": pillars,
        "top_performing_hooks": "\n".join(top_content) if top_content else "No data yet.",
        "todays_trending": "\n".join(brief_ideas) if brief_ideas else "No trending data today.",
        "lessons": lessons,
    }


# ── Agent-based generation ────────────────────────────────────────────────────

def _generate_all_drafts_via_agent(
    out_dir: Path,
    today: str,
    primary_pillar: str,
    secondary_pillar: str,
    primary_funnel: str,
    secondary_funnel: str,
    ctx: dict,
) -> list[dict]:
    """Use Claude Agent SDK to generate all 5 drafts in a single session.

    The agent reads context files directly and writes draft files to disk.
    Returns a list of draft metadata dicts (for building the manifest).
    Falls back to direct API if agent SDK is unavailable.
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock, query
    except ImportError:
        log.warning("claude_agent_sdk not available — trying direct API fallback")
        return _generate_all_drafts_via_api(
            out_dir, today, primary_pillar, secondary_pillar,
            primary_funnel, secondary_funnel, ctx,
        )

    workspace = str(ROOT)

    prompt = f"""You are generating content drafts for [YOUR_NAME], Elite Systems AI.
Date: {today}
Output directory: {out_dir}

TODAY'S BRIEF:
- Primary pillar: {primary_pillar} ({primary_funnel})
- Secondary pillar: {secondary_pillar} ({secondary_funnel})
- Trending angles: {ctx['todays_trending'][:500]}

BRAND VOICE RULES (enforce strictly):
- Never use: "dive into", "game-changer", "leverage", "it's that simple", "unlock", em dashes (—)
- Never start a sentence with "I" as the first word of the post
- One sentence per line in captions
- Hook must stop the scroll in 3 seconds
- Structure: Problem → Insight → System → CTA
- Max 3 hashtags

TOP PERFORMING HOOKS (use these patterns):
{ctx['top_performing_hooks'][:600]}

Generate EXACTLY 5 drafts and write each to the output directory as a .md file:

1. {out_dir}/1_reel_{_slugify(primary_pillar)}.md
   Type: Reel script (60-90 sec, talking-to-camera)
   Pillar: {primary_pillar} | Funnel: {primary_funnel}
   Include: HOOK, PROBLEM, INSIGHT, SYSTEM, CTA, CAPTION, then QUALITY SCORE: X/10, HOOK PREVIEW: ..., WORD COUNT: N

2. {out_dir}/2_reel_{_slugify(secondary_pillar)}.md
   Type: Reel script (60-90 sec, talking-to-camera)
   Pillar: {secondary_pillar} | Funnel: {secondary_funnel}
   Include same structure as draft 1.

3. {out_dir}/3_carousel_{_slugify(primary_pillar)}.md
   Type: Instagram carousel (6-8 slides)
   Pillar: {primary_pillar} | Funnel: {primary_funnel}
   Include: SLIDE 1 through SLIDE 8, CAPTION, then QUALITY SCORE: X/10, HOOK PREVIEW: ..., SLIDE COUNT: N

4. {out_dir}/4_linkedin_{_slugify(secondary_pillar)}.md
   Type: LinkedIn post (300-450 words)
   Pillar: {secondary_pillar} | Funnel: {secondary_funnel}
   Personal story arc: experience → lesson → system → takeaway. End with a question.
   No hashtags. Include QUALITY SCORE: X/10, HOOK PREVIEW: ..., WORD COUNT: N

5. {out_dir}/5_text_{_slugify(primary_pillar)}.md
   Type: Short text/image post (under 80 words, quotable)
   Pillar: {primary_pillar} | Funnel: MOFU
   One sentence per line. Bold take. Max 2 hashtags.
   Include QUALITY SCORE: X/10, HOOK PREVIEW: ..., WORD COUNT: N

Each file should start with a header block:
# Draft N — TYPE [FUNNEL] — PILLAR

**Date:** {today}
**Hook:** [hook text]
**Quality:** X/10
**Status:** pending

---

[then the draft content]

After writing all 5 files, output a JSON summary on the LAST line in this exact format (no other JSON):
MANIFEST_JSON: {{"drafts": [{{"n":1,"type":"reel","pillar":"{primary_pillar}","funnel":"{primary_funnel}","hook":"...","quality_score":8,"word_count":145,"file":"1_reel_{_slugify(primary_pillar)}.md","status":"pending"}}, ...]}}

Replace the ... with the actual hook text and correct values for each draft."""

    env_clean = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": "Generate content drafts for Elite Systems AI."},
        setting_sources=["project"],
        cwd=workspace,
        allowed_tools=["Write", "Read"],
        permission_mode="bypassPermissions",
        max_turns=20,
        max_budget_usd=3.00,
        model="sonnet",
        env=env_clean,
    )

    async def _run():
        result_text = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text = block.text
            elif isinstance(message, ResultMessage):
                pass
        return result_text

    try:
        result_text = asyncio.run(_run())
    except Exception:
        log.exception("Agent SDK run failed")
        return []

    # Parse manifest from agent output
    manifest_match = re.search(r"MANIFEST_JSON:\s*(\{.+\})", result_text, re.DOTALL)
    if manifest_match:
        try:
            data = json.loads(manifest_match.group(1))
            return data.get("drafts", [])
        except json.JSONDecodeError:
            log.warning("Could not parse manifest JSON from agent output")

    # Fall back: scan the output dir for generated files
    return _scan_drafts_from_dir(out_dir, today, primary_pillar, secondary_pillar,
                                 primary_funnel, secondary_funnel)


def _scan_drafts_from_dir(
    out_dir: Path, today: str,
    primary_pillar: str, secondary_pillar: str,
    primary_funnel: str, secondary_funnel: str,
) -> list[dict]:
    """Build manifest by scanning files in out_dir (fallback if agent JSON fails)."""
    drafts = []
    type_map = {"reel": "reel", "carousel": "carousel", "linkedin": "linkedin", "text": "text"}
    pillar_map = {
        1: (primary_pillar, primary_funnel),
        2: (secondary_pillar, secondary_funnel),
        3: (primary_pillar, primary_funnel),
        4: (secondary_pillar, secondary_funnel),
        5: (primary_pillar, "MOFU"),
    }
    for n in range(1, 6):
        pattern = f"{n}_*"
        matches = list(out_dir.glob(pattern))
        if not matches:
            continue
        f = matches[0]
        content = f.read_text(encoding="utf-8")
        dtype = next((t for t in type_map if f"_{t}_" in f.name), "reel")
        pillar, funnel = pillar_map.get(n, (primary_pillar, primary_funnel))
        hook = _extract_field(content, "Hook", fallback=_extract_first_line(content))
        quality = _extract_quality(content)
        word_count = _count_words(content)
        drafts.append({
            "n": n, "type": dtype, "pillar": pillar, "funnel": funnel,
            "hook": hook, "quality_score": quality, "word_count": word_count,
            "file": f.name, "status": "pending",
        })
    return drafts


def _generate_all_drafts_via_api(
    out_dir: Path, today: str,
    primary_pillar: str, secondary_pillar: str,
    primary_funnel: str, secondary_funnel: str,
    ctx: dict,
) -> list[dict]:
    """Direct API fallback. Tries Anthropic first, then OpenAI."""
    openai_key = env.get("OPENAI_API_KEY", "")

    client = None
    call_fn = None  # signature: (system, user) -> str

    if ANTHROPIC_API_KEY:
        try:
            import anthropic as _anthropic
            _ac = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            def call_fn(system, user):  # noqa: E306
                msg = _ac.messages.create(
                    model="claude-sonnet-4-6", max_tokens=1200,
                    system=system, messages=[{"role": "user", "content": user}],
                )
                return msg.content[0].text.strip()
        except ImportError:
            log.warning("anthropic package not installed, trying OpenAI")

    if call_fn is None and openai_key:
        try:
            import openai as _openai
            _oc = _openai.OpenAI(api_key=openai_key)
            def call_fn(system, user):  # noqa: E306
                resp = _oc.chat.completions.create(
                    model="gpt-4o", max_tokens=1200,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return resp.choices[0].message.content.strip()
        except ImportError:
            log.warning("openai package not installed")

    if call_fn is None:
        log.error("No API key available (ANTHROPIC_API_KEY or OPENAI_API_KEY required)")
        return []

    system = """You are the content writer for [YOUR_NAME], Elite Systems AI.
Write in Zac's exact voice. Direct. Grounded. Specific.
NEVER use: "dive into", "game-changer", "leverage", "it's that simple", "unlock", em dashes.
One sentence per line. Max 3 hashtags. Hook stops scroll in 3 seconds.
Structure: Problem → Insight → System → CTA."""

    slots = [
        (1, "reel",     primary_pillar,   primary_funnel,   "60-90 sec reel script"),
        (2, "reel",     secondary_pillar, secondary_funnel, "60-90 sec reel script"),
        (3, "carousel", primary_pillar,   primary_funnel,   "6-8 slide carousel"),
        (4, "linkedin", secondary_pillar, secondary_funnel, "300-450 word LinkedIn post"),
        (5, "text",     primary_pillar,   "MOFU",           "under 80 word text post"),
    ]

    drafts = []
    for n, dtype, pillar, funnel, fmt_hint in slots:
        user = (
            f"Write a {fmt_hint} for [YOUR_NAME].\n"
            f"Pillar: {pillar} | Funnel: {funnel}\n"
            f"Trending: {ctx['todays_trending'][:300]}\n\n"
            f"At the end include:\nQUALITY SCORE: X/10\nHOOK PREVIEW: ...\nWORD COUNT: N"
        )
        try:
            content = call_fn(system, user)
        except Exception:
            log.exception("API call failed for draft %d", n)
            continue

        filename = f"{n}_{dtype}_{_slugify(pillar)}.md"
        header = (
            f"# Draft {n} — {dtype.upper()} [{funnel}] — {pillar}\n\n"
            f"**Date:** {today}\n**Hook:** {_extract_field(content, 'HOOK PREVIEW', fallback=_extract_first_line(content))}\n"
            f"**Quality:** {_extract_quality(content)}/10\n**Status:** pending\n\n---\n\n"
        )
        (out_dir / filename).write_text(header + content, encoding="utf-8")

        drafts.append({
            "n": n, "type": dtype, "pillar": pillar, "funnel": funnel,
            "hook": _extract_field(content, "HOOK PREVIEW", fallback=_extract_first_line(content)),
            "quality_score": _extract_quality(content),
            "word_count": _count_words(content),
            "file": filename, "status": "pending",
        })
        log.info("  Draft %d saved: %s", n, filename)

    return drafts


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_field(text: str, label: str, fallback: str = "") -> str:
    m = re.search(rf"{re.escape(label)}:\s*(.+)", text)
    return m.group(1).strip()[:100] if m else fallback


def _extract_quality(text: str) -> int:
    m = re.search(r"QUALITY SCORE:\s*(\d+)", text)
    return int(m.group(1)) if m else 7


def _extract_int_field(text: str, label: str, fallback: int = 0) -> int:
    m = re.search(rf"{re.escape(label)}:\s*(\d+)", text)
    return int(m.group(1)) if m else fallback


def _extract_first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("```") and len(line) > 10:
            return line[:80]
    return ""


def _count_words(text: str) -> int:
    return len(text.split())


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower())[:20]


# ── Telegram ──────────────────────────────────────────────────────────────────

def _send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping notification")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    now_aest = datetime.now(AEST)
    today = now_aest.strftime("%Y-%m-%d")
    weekday = now_aest.weekday()

    log.info("Content Autopilot starting — %s (weekday %d)", today, weekday)

    # Create output dir
    out_dir = DRAFTS_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load context
    ctx = _load_context()
    log.info("Context loaded — brand voice: %d chars", len(ctx["brand_voice"]))

    # Determine pillar schedule for today
    primary_pillar, secondary_pillar, primary_slug, secondary_slug = WEEKLY_SCHEDULE[weekday]
    primary_funnel = FUNNEL_MAP.get(primary_pillar, "MOFU")
    secondary_funnel = FUNNEL_MAP.get(secondary_pillar, "MOFU")

    trending = ctx["todays_trending"]
    log.info("Generating for: %s (%s) + %s (%s)", primary_pillar, primary_funnel, secondary_pillar, secondary_funnel)

    # Generate all 5 drafts via agent SDK, fall back to direct API if SDK fails
    log.info("Launching agent to generate all 5 drafts...")
    drafts = _generate_all_drafts_via_agent(
        out_dir, today,
        primary_pillar, secondary_pillar,
        primary_funnel, secondary_funnel,
        ctx,
    )
    log.info("Agent generated %d drafts", len(drafts))

    if not drafts:
        log.warning("Agent SDK returned 0 drafts — falling back to direct API")
        drafts = _generate_all_drafts_via_api(
            out_dir, today,
            primary_pillar, secondary_pillar,
            primary_funnel, secondary_funnel,
            ctx,
        )
        log.info("API fallback generated %d drafts", len(drafts))

    # Save manifest
    manifest = {
        "date": today,
        "generated_at": now_aest.isoformat(),
        "drafts": drafts,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Manifest saved: %s (%d drafts)", manifest_path, len(drafts))

    # Send Telegram notification
    if drafts:
        lines = [f"✅ <b>Content drafts ready — {today}</b>", f"{len(drafts)} drafts generated. Digest arrives at 8:30am."]
        _send_telegram("\n".join(lines))
    else:
        _send_telegram(f"⚠️ <b>Content Autopilot failed</b> — no drafts generated for {today}. Check logs.")

    log.info("Content Autopilot complete")


if __name__ == "__main__":
    run()
