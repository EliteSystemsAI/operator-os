#!/usr/bin/env python3
"""
Elite Systems AI — Content Intelligence Agent

Runs daily at 6am AEST via pm2 cron.
Scrapes trending AI/business news + Slack context.
Writes data/daily_content_brief.json.
Sends Telegram briefing with top 3 content opportunities.

Sources:
  - Google News RSS (AI + automation + business)
  - Reddit JSON API (r/entrepreneur, r/artificial, r/ChatGPT)
  - HackerNews Algolia API (AI stories in last 24h)
  - Slack (last 24h messages from work channels)

Usage:
  python ops/content_intelligence.py        -- run once
  Triggered by pm2 cron at 6am AEST daily
"""

import sys
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def load_env():
    import os
    env = dict(os.environ)
    for candidate in [Path(__file__).parent.parent / ".env", Path.home() / ".env"]:
        if candidate.exists():
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            break
    return env


env = load_env()

TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")
SLACK_TOKEN = env.get("SLACK_BOT_TOKEN", "")

AEST = timezone(timedelta(hours=10))

DATA_DIR = Path(__file__).parent.parent / "data"
BRIEF_FILE = DATA_DIR / "daily_content_brief.json"

# ICA relevance keywords — stories matching these score higher
ICA_KEYWORDS = [
    "ai", "artificial intelligence", "automation", "chatgpt", "claude", "openai",
    "coach", "consultant", "agency", "revenue", "scale", "productivity",
    "workflow", "saas", "startup", "entrepreneur", "small business",
    "layoff", "replace", "job", "hiring", "efficiency", "roi",
    "gpt", "llm", "agent", "n8n", "zapier", "make.com",
]

# Slack channel names to pull context from (work/client channels)
SLACK_CHANNELS_TO_MONITOR = ["general", "builds", "clients", "projects", "wins"]


def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def score_story(title: str, description: str = "") -> int:
    """Score a story 0-10 for ICA relevance."""
    text = (title + " " + description).lower()
    score = sum(2 if kw in text else 0 for kw in ICA_KEYWORDS[:10])  # top keywords worth 2
    score += sum(1 if kw in text else 0 for kw in ICA_KEYWORDS[10:])  # rest worth 1
    return min(score, 10)


def generate_angle(title: str) -> str:
    """Generate a polarising content angle from a news story title."""
    title_lower = title.lower()
    if any(w in title_lower for w in ["layoff", "replace", "job", "fired"]):
        return f"Strong take: What this actually means for service businesses (not what the headline says)"
    elif any(w in title_lower for w in ["raise", "funding", "billion", "valuation"]):
        return f"Contrarian: Why this level of investment means the window for early adopters is closing"
    elif any(w in title_lower for w in ["release", "launch", "announce", "new model"]):
        return f"Honest review angle: Should coaches/consultants actually care? Real answer:"
    elif any(w in title_lower for w in ["regulation", "law", "ban", "rule"]):
        return f"Practical impact: What this regulation actually changes for your automation stack"
    elif any(w in title_lower for w in ["fail", "shut down", "closure", "dead"]):
        return f"Lesson: What to learn from this before it happens to the tools you rely on"
    else:
        return f"POV: What this means for coaches and consultants who use AI in their business"


# ── Sources ────────────────────────────────────────────────────────────────────


def fetch_google_news(query: str, max_items: int = 5) -> list[dict]:
    """Fetch from Google News RSS — no API key needed."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-AU&gl=AU&ceid=AU:en"
    stories = []
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:max_items]
        for item in items:
            title = item.findtext("title", "").strip()
            desc = item.findtext("description", "").strip()
            # Strip HTML from description
            desc = re.sub(r"<[^>]+>", "", desc)[:200]
            pub_date = item.findtext("pubDate", "")
            link = item.findtext("link", "")
            if title:
                stories.append({
                    "title": title,
                    "description": desc,
                    "url": link,
                    "published": pub_date,
                    "source": "google_news",
                    "query": query,
                    "score": score_story(title, desc),
                    "angle": generate_angle(title),
                })
    except Exception as e:
        log.warning(f"Google News fetch failed for '{query}': {e}")
    return stories


def fetch_reddit(subreddit: str, max_items: int = 5) -> list[dict]:
    """Fetch hot posts from a subreddit — no auth needed for public subs."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={max_items}"
    stories = []
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "EliteSystems/1.0"})
        r.raise_for_status()
        posts = r.json().get("data", {}).get("children", [])
        for post in posts:
            d = post.get("data", {})
            title = d.get("title", "").strip()
            score = d.get("score", 0)
            if title and score > 10:  # filter low-engagement posts
                stories.append({
                    "title": title,
                    "description": d.get("selftext", "")[:200],
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "published": "",
                    "source": f"reddit_{subreddit}",
                    "upvotes": score,
                    "score": score_story(title),
                    "angle": generate_angle(title),
                })
    except Exception as e:
        log.warning(f"Reddit fetch failed for r/{subreddit}: {e}")
    return stories


def fetch_hackernews(max_items: int = 5) -> list[dict]:
    """Fetch top HN stories from last 24h using Algolia API."""
    since = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
    url = (
        f"https://hn.algolia.com/api/v1/search?"
        f"query=AI+automation+productivity&tags=story"
        f"&numericFilters=created_at_i>{since},points>10"
        f"&hitsPerPage={max_items}"
    )
    stories = []
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        for hit in hits:
            title = hit.get("title", "").strip()
            if title:
                stories.append({
                    "title": title,
                    "description": "",
                    "url": hit.get("url", "") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "published": "",
                    "source": "hackernews",
                    "points": hit.get("points", 0),
                    "score": score_story(title),
                    "angle": generate_angle(title),
                })
    except Exception as e:
        log.warning(f"HackerNews fetch failed: {e}")
    return stories


def fetch_slack_context() -> list[dict]:
    """Pull last 24h messages from work Slack channels for personal context."""
    if not SLACK_TOKEN:
        return []

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
    context_items = []

    try:
        # Get list of channels
        r = requests.get(
            "https://slack.com/api/conversations.list",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
            params={"types": "public_channel,private_channel", "limit": 50},
            timeout=10,
        )
        channels = {
            c["name"]: c["id"]
            for c in r.json().get("channels", [])
            if c.get("name") in SLACK_CHANNELS_TO_MONITOR
        }

        for name, channel_id in channels.items():
            r = requests.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
                params={"channel": channel_id, "oldest": since, "limit": 20},
                timeout=10,
            )
            messages = r.json().get("messages", [])
            for msg in messages:
                text = msg.get("text", "").strip()
                if len(text) > 30 and not text.startswith("<"):  # skip bot messages/links
                    context_items.append({
                        "channel": name,
                        "text": text[:300],
                        "timestamp": msg.get("ts", ""),
                    })
    except Exception as e:
        log.warning(f"Slack fetch failed: {e}")

    return context_items


# ── Main ───────────────────────────────────────────────────────────────────────


def run():
    log.info("Starting content intelligence run")
    today = datetime.now(AEST).strftime("%Y-%m-%d")

    # Fetch stories from all sources
    all_stories = []

    # Google News: AI + automation focus
    for query in ["AI automation business 2026", "artificial intelligence replace jobs", "AI tools entrepreneurs"]:
        all_stories.extend(fetch_google_news(query, max_items=4))

    # Reddit
    for sub in ["artificial", "entrepreneur", "ChatGPT"]:
        all_stories.extend(fetch_reddit(sub, max_items=4))

    # HackerNews
    all_stories.extend(fetch_hackernews(max_items=5))

    # Deduplicate by title similarity
    seen_titles = set()
    unique_stories = []
    for s in all_stories:
        key = s["title"].lower()[:60]
        if key not in seen_titles:
            seen_titles.add(key)
            unique_stories.append(s)

    # Sort by ICA relevance score
    unique_stories.sort(key=lambda x: x["score"], reverse=True)
    top_stories = unique_stories[:10]

    # Pull Slack context
    slack_context = fetch_slack_context()

    # Build content ideas from top stories
    content_ideas = []
    for i, story in enumerate(top_stories[:5]):
        funnel = "TOFU" if i < 2 else "MOFU"
        content_ideas.append({
            "rank": i + 1,
            "headline": story["title"],
            "source": story["source"],
            "url": story.get("url", ""),
            "ica_score": story["score"],
            "angle": story["angle"],
            "funnel_stage": funnel,
            "content_types": ["reel", "carousel"] if i == 0 else ["reel"],
            "suggested_hook": f"[BREAKING] {story['title'][:80]}..." if story["score"] >= 7
                             else f"Hot take on {story['title'][:60]}...",
        })

    # Personal context from Slack
    personal_context = []
    for msg in slack_context[:5]:
        personal_context.append({
            "channel": msg["channel"],
            "context": msg["text"],
            "content_angle": "Document what you're building: turn this into a 'behind the build' carousel",
        })

    # Write brief
    brief = {
        "date": today,
        "generated_at": datetime.now(AEST).isoformat(),
        "top_stories": top_stories[:10],
        "content_ideas": content_ideas,
        "personal_context": personal_context,
        "daily_targets": {
            "reel": {"funnel": "TOFU", "approach": "Take the #1 story + strong polarising opinion"},
            "carousel": {"funnel": "MOFU", "approach": "Thread format — either top story breakdown OR personal build story from Slack"},
            "quote_or_caricature": {"funnel": "MOFU", "approach": "Extract one polarising line from content ideas"},
        },
    }

    DATA_DIR.mkdir(exist_ok=True)
    with open(BRIEF_FILE, "w") as f:
        json.dump(brief, f, indent=2)
    log.info(f"Brief written to {BRIEF_FILE}")

    # Send Telegram summary
    top3 = content_ideas[:3]
    lines = [f"<b>Content Intelligence — {today}</b>", ""]
    for idea in top3:
        lines.append(f"<b>#{idea['rank']} [{idea['funnel_stage']}]</b> {idea['headline'][:80]}")
        lines.append(f"  → {idea['angle'][:100]}")
        lines.append("")
    if personal_context:
        lines.append("<b>From your Slack (story fuel):</b>")
        for ctx in personal_context[:2]:
            lines.append(f"  #{ctx['channel']}: {ctx['context'][:80]}...")
        lines.append("")
    lines.append("Run /morning to get full briefing with script angles.")
    send_telegram("\n".join(lines))
    log.info("Done")


if __name__ == "__main__":
    run()
