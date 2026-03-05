#!/usr/bin/env python3
"""
Seed business_context table in Supabase with Elite Systems AI stable data.
Run once: python scripts/seed_business_context.py
"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

CONTEXT = {
    "business_name": "Elite Systems AI",
    "owner": "[YOUR_NAME]",
    "location": "Gold Coast / Brisbane, Australia (AEST GMT+10, Queensland — no daylight saving)",
    "positioning": "Fractional CTO + AI automation agency. Helps coaches, consultants, and creators at the 6-7 figure mark build AI-powered systems that eliminate operational bottlenecks.",
    "tagline": "Stop Trading Time for Money. Build Systems That Scale.",
    "services": json.dumps([
        "Fractional CTO services — embedded AI systems lead",
        "Done-for-you automation — n8n/Make/GHL workflows, AI agents, voice AI",
        "Education/community — content that teaches the systems mindset"
    ]),
    "pricing": "Standard: $3,000/month retainer. First month includes Audit + Discovery (2 weeks: mapping, roadmap, platform setup). 3-month minimum. 60 days notice to cancel after that.",
    "guarantee": "Every system must pay for itself within 12 months (time saved × hourly rate > investment).",
    "ica": "Coaches, consultants, creators. Revenue stage: $200k–$2M/year. Pain: drowning in manual ops — fulfillment, follow-up, reporting, admin. Fear: tech overwhelm. Desire: more time, less chaos, predictable systems.",
    "brand_voice": "Direct, punchy, confident. No fluff. No hype. Outcomes-first. Lead with the result, then explain the how. Never say: dive into, game-changer, leverage, unlock your potential, it's that simple, In today's fast-paced world. NO em dashes. NO hyphens in compound words in copy.",
    "social_handles": json.dumps({
        "instagram_personal": "[YOUR_INSTAGRAM_HANDLE] (1,102 followers — Stage 2)",
        "instagram_business": "@elite.systemsai (101 followers)",
        "linkedin": "[YOUR_NAME] (Elite Systems AI)",
        "tiktok": "[YOUR_INSTAGRAM_HANDLE]",
        "youtube": "Elite Systems AI"
    }),
    "content_pillars": json.dumps([
        "Tool Spotlights — AI tools ICA should know about",
        "System Reveals — behind-the-scenes of systems built",
        "Myth Busting — wrong beliefs about AI/automation",
        "Results and Proof — client wins + own metrics",
        "How-To — step-by-step tutorials"
    ]),
    "posting_targets": "Stage 2 (1k-10k followers). Weekly: 2x TOFU (1x follow CTA, 1x freebie), 1x TOFU double-down (remix best performer), 1x MOFU (follow CTA), 3x BOFU (2x follow, 1x paid offer).",
    "ad_benchmarks": json.dumps({
        "target_cpl": 25.00,
        "target_roas": 3.0,
        "target_ctr": 0.015,
        "monthly_budget_usd": 500
    }),
    "ghl_location_id": os.environ.get("GHL_LOCATION_ID", ""),
    "telegram_group_id": os.environ.get("TELEGRAM_GROUP_ID", ""),
}

def upsert(key, value):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/business_context",
        headers=headers(),
        json={"key": key, "value": value, "updated_at": "NOW()"}
    )
    if r.status_code not in (200, 201):
        print(f"ERROR {key}: {r.status_code} {r.text}")
    else:
        print(f"OK    {key}")

if __name__ == "__main__":
    print("Seeding business_context...")
    for k, v in CONTEXT.items():
        upsert(k, v)
    print("Done.")
