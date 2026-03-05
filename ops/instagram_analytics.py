#!/usr/bin/env python3
"""
Elite Systems AI — Instagram Analytics Monitor

Runs daily at 7am AEST via pm2 cron.
Fetches IG post performance via Meta Graph API.
Updates data/top_performing_content.json with real metrics.
Sends weekly Telegram summary on Sundays.

Requires IG_ACCESS_TOKEN (Meta user token) with instagram_basic, instagram_manage_insights,
pages_show_list, pages_read_engagement permissions.
Get this from developers.facebook.com/tools/explorer/ and exchange for a long-lived token.

Usage:
  python ops/instagram_analytics.py          -- run once
  python ops/instagram_analytics.py --setup  -- print IG account ID (run first time)
  Triggered by pm2 cron at 7am AEST daily
"""

import sys
import json
import logging
import argparse
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

META_TOKEN = env.get("IG_ACCESS_TOKEN", "")
TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")
# Set this after running --setup
IG_ACCOUNT_ID = env.get("IG_ACCOUNT_ID", "")
META_APP_ID = env.get("META_APP_ID", "")
META_APP_SECRET = env.get("META_APP_SECRET", "")

AEST = timezone(timedelta(hours=10))
GRAPH_BASE = "https://graph.facebook.com/v20.0"

DATA_DIR = Path(__file__).parent.parent / "data"
TOP_CONTENT_FILE = DATA_DIR / "top_performing_content.json"
ENV_FILE = next(
    (p for p in [Path(__file__).parent.parent / ".env", Path.home() / ".env"] if p.exists()),
    Path(__file__).parent.parent / ".env",
)


def refresh_token_if_needed() -> str:
    """Exchange long-lived token for a fresh one if within 10 days of expiry.
    Long-lived tokens last 60 days and can be refreshed before expiry.
    Updates .env in place with the new token.
    """
    if not META_TOKEN or not META_APP_ID or not META_APP_SECRET:
        return META_TOKEN

    try:
        debug = requests.get(
            f"{GRAPH_BASE}/debug_token",
            params={"input_token": META_TOKEN, "access_token": META_TOKEN},
            timeout=10,
        ).json().get("data", {})

        expires_at = debug.get("expires_at", 0)
        if expires_at == 0:
            return META_TOKEN  # non-expiring token

        days_left = (expires_at - datetime.now(timezone.utc).timestamp()) / 86400
        if days_left > 10:
            log.info(f"Token valid for {days_left:.0f} more days — no refresh needed")
            return META_TOKEN

        log.info(f"Token expires in {days_left:.0f} days — refreshing...")
        resp = requests.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": META_TOKEN,
            },
            timeout=15,
        ).json()

        new_token = resp.get("access_token")
        if not new_token:
            log.warning(f"Token refresh failed: {resp}")
            return META_TOKEN

        # Update .env in place
        env_text = ENV_FILE.read_text()
        env_text = "\n".join(
            f"IG_ACCESS_TOKEN={new_token}" if line.startswith("IG_ACCESS_TOKEN=") else line
            for line in env_text.splitlines()
        )
        ENV_FILE.write_text(env_text)
        log.info("Token refreshed and saved to .env")
        return new_token

    except Exception as e:
        log.warning(f"Token refresh check failed: {e}")
        return META_TOKEN


def graph_get(path: str, params: dict = {}) -> dict:
    params = {"access_token": META_TOKEN, **params}
    r = requests.get(f"{GRAPH_BASE}/{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def setup_mode():
    """Print IG account ID — run once to find the ID to add to .env.
    Use a User Access Token from Graph API Explorer with instagram_basic + instagram_manage_insights.
    """
    print("Fetching Facebook Pages and connected Instagram accounts...")
    try:
        resp = graph_get("me/accounts", {"fields": "name,id,instagram_business_account"})
        pages = resp.get("data", [])
        if not pages:
            print("  No Facebook Pages found for this token.")
            return
        found = False
        for page in pages:
            ig = page.get("instagram_business_account")
            if ig:
                found = True
                print(f"  Page: {page['name']} (ID: {page['id']})")
                print(f"  IG Business Account ID: {ig['id']}")
                print(f"  → Add to .env: IG_ACCOUNT_ID={ig['id']}")
        if not found:
            print("  No Instagram Business Accounts linked to any of your Pages.")
            print("  Connect your Instagram Business Account to a Facebook Page via Instagram Settings.")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure IG_ACCESS_TOKEN is a User Access Token with instagram_basic + instagram_manage_insights.")


def fetch_recent_posts(days: int = 30) -> list[dict]:
    """Fetch IG posts from the last N days."""
    if not IG_ACCOUNT_ID:
        log.error("IG_ACCOUNT_ID not set in .env — run with --setup first")
        return []

    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

    try:
        resp = graph_get(
            f"{IG_ACCOUNT_ID}/media",
            {
                "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink",
                "since": since,
                "limit": 50,
            },
        )
        return resp.get("data", [])
    except Exception as e:
        log.warning(f"Failed to fetch IG posts: {e}")
        return []


def fetch_post_insights(media_id: str, media_type: str) -> dict:
    """Fetch insights for a single post.
    Uses metrics supported post-2025 deprecation (impressions/video_views removed).
    likes/comments come from the media object directly, not insights.
    """
    # All types: reach + saved + shares work universally
    metrics = "reach,saved,shares"

    try:
        resp = graph_get(f"{media_id}/insights", {"metric": metrics})
        return {item["name"]: item["values"][0]["value"] for item in resp.get("data", [])}
    except Exception as e:
        log.debug(f"Insights fetch failed for {media_id}: {e}")
        return {}


def calculate_engagement_rate(insights: dict, followers: int = 1100) -> float:
    """Calculate engagement rate vs follower count."""
    engagement = (
        insights.get("likes", 0)
        + insights.get("comments", 0) * 2  # weight comments higher
        + insights.get("saved", 0) * 3     # saves are gold
        + insights.get("shares", 0) * 2
    )
    return round((engagement / max(followers, 1)) * 100, 2)


def run(setup: bool = False):
    if setup:
        setup_mode()
        return

    global META_TOKEN
    if not META_TOKEN:
        log.error("IG_ACCESS_TOKEN not set — get a user token from developers.facebook.com/tools/explorer/")
        return

    META_TOKEN = refresh_token_if_needed()

    log.info("Fetching IG post performance")
    posts = fetch_recent_posts(days=30)
    log.info(f"Found {len(posts)} posts in last 30 days")

    enriched = []
    for post in posts:
        media_id = post["id"]
        media_type = post.get("media_type", "IMAGE")
        insights = fetch_post_insights(media_id, media_type)

        enriched.append({
            "id": media_id,
            "caption_preview": (post.get("caption") or "")[:100],
            "media_type": media_type,
            "timestamp": post.get("timestamp", ""),
            "permalink": post.get("permalink", ""),
            "likes": post.get("like_count", 0),
            "comments": post.get("comments_count", 0),
            "impressions": insights.get("impressions", 0),
            "reach": insights.get("reach", 0),
            "saves": insights.get("saved", 0),
            "video_views": insights.get("video_views", 0),
            "engagement_rate": calculate_engagement_rate(insights),
        })

    # Sort by engagement rate
    enriched.sort(key=lambda x: x["engagement_rate"], reverse=True)

    # Identify patterns in top 5
    top5 = enriched[:5]
    formats = [p["media_type"] for p in top5]
    top_format = max(set(formats), key=formats.count) if formats else "IMAGE"

    today = datetime.now(AEST).strftime("%Y-%m-%d")
    output = {
        "last_updated": today,
        "account": "itszacnielsen",
        "total_posts_analysed": len(enriched),
        "top_performing": top5,
        "insights": {
            "best_format": top_format,
            "avg_engagement_rate": round(sum(p["engagement_rate"] for p in enriched) / max(len(enriched), 1), 2),
            "top_engagement_rate": enriched[0]["engagement_rate"] if enriched else 0,
        },
        "all_posts": enriched,
    }

    DATA_DIR.mkdir(exist_ok=True)
    with open(TOP_CONTENT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    log.info(f"Updated {TOP_CONTENT_FILE}")

    # Send weekly summary on Sundays
    if datetime.now(AEST).weekday() == 6:  # Sunday
        lines = [
            f"<b>Weekly IG Analytics — {today}</b>",
            f"Posts analysed: {len(enriched)}",
            f"Avg engagement rate: {output['insights']['avg_engagement_rate']}%",
            f"Best format: {top_format}",
            "",
            "<b>Top 3 posts this week:</b>",
        ]
        for i, p in enumerate(top5[:3], 1):
            lines.append(f"{i}. {p['media_type']} | {p['engagement_rate']}% eng | {p['caption_preview'][:60]}...")
        send_telegram("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Print IG account ID")
    args = parser.parse_args()
    run(setup=args.setup)
