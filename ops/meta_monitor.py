#!/usr/bin/env python3
"""
Elite Systems AI — Hourly Meta Ads Monitor

Runs every hour via pm2 cron on Mac Mini.
Checks every active ad for: CTR < 1.8%, CPM > $15 AUD, spend > $20 with 0 conversions.
Flags to Telegram immediately + queues optimisation task.

Usage:
  pm2 start ecosystem.config.js --only elite-meta-monitor
  OR standalone: python ops/meta_monitor.py
"""

import sys
import logging
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

SUPABASE_URL = env.get("SUPABASE_URL", "")
SUPABASE_KEY = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")
META_TOKEN = env.get("META_ACCESS_TOKEN", "")
META_ACCOUNT = env.get("META_AD_ACCOUNT_ID", "")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Thresholds
CTR_THRESHOLD = 1.8      # flag if CTR < 1.8%
CPM_THRESHOLD = 15.0     # flag if CPM > $15 AUD
SPEND_CONV_THRESHOLD = 20.0  # flag if spend > $20 with 0 conversions

MONTHLY_BUDGET_AUD = float(env.get("META_MONTHLY_BUDGET_AUD", "3000"))


def send_telegram(text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def queue_task(title: str, description: str, priority: int, area: str = "meta") -> bool:
    """Add task to work_queue, skip if duplicate active task exists."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers=SUPABASE_HEADERS,
            params={
                "analyst_area": f"eq.{area}",
                "status": "in.(backlog,ready,in_progress)",
                "title": f"eq.{title}",
                "limit": "1",
            },
            timeout=10,
        )
        if r.ok and r.json():
            log.info(f"Skipping duplicate: {title}")
            return False

        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers={**SUPABASE_HEADERS, "Prefer": "return=minimal"},
            json={
                "title": title,
                "description": description,
                "status": "ready",
                "priority": priority,
                "source": "analyst",
                "analyst_area": area,
            },
            timeout=10,
        )
        r.raise_for_status()
        log.info(f"Queued (P{priority}): {title}")
        return True
    except Exception as e:
        log.warning(f"queue_task failed: {e}")
        return False


def check_individual_ads() -> int:
    """Check each active ad for underperformance. Returns count of flagged ads."""
    flagged = 0
    try:
        r = requests.get(
            f"https://graph.facebook.com/v20.0/{META_ACCOUNT}/ads",
            params={
                "fields": "id,name,status,adset_id,creative",
                "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE"]}]',
                "limit": "100",
                "access_token": META_TOKEN,
            },
            timeout=20,
        )
        if not r.ok:
            log.warning(f"Meta ads fetch failed: {r.status_code} {r.text[:200]}")
            return 0

        ads = r.json().get("data", [])
        log.info(f"Meta: checking {len(ads)} active ads")

        for ad in ads:
            ad_id = ad["id"]
            ad_name = ad.get("name", ad_id)
            adset_id = ad.get("adset_id", "")

            ins_r = requests.get(
                f"https://graph.facebook.com/v20.0/{ad_id}/insights",
                params={
                    "fields": "spend,impressions,clicks,ctr,cpm,actions",
                    "date_preset": "last_7d",
                    "access_token": META_TOKEN,
                },
                timeout=15,
            )
            if not ins_r.ok:
                continue

            ins_data = ins_r.json().get("data", [])
            if not ins_data:
                continue

            d = ins_data[0]
            spend = float(d.get("spend", 0))
            ctr = float(d.get("ctr", 0))
            cpm = float(d.get("cpm", 0))
            impressions = int(d.get("impressions", 0))

            actions = d.get("actions", [])
            conversions = sum(
                int(a.get("value", 0))
                for a in actions
                if a.get("action_type") in ("purchase", "lead", "complete_registration")
            )

            issues = []
            if impressions > 500 and ctr < CTR_THRESHOLD:
                issues.append(f"CTR {ctr:.1f}% < {CTR_THRESHOLD}%")
            if spend > 5 and cpm > CPM_THRESHOLD:
                issues.append(f"CPM ${cpm:.2f} > ${CPM_THRESHOLD}")
            if spend > SPEND_CONV_THRESHOLD and conversions == 0:
                issues.append(f"${spend:.0f} spent, 0 conversions")

            if issues:
                flagged += 1
                issue_str = ", ".join(issues)
                log.info(f"Meta flag: {ad_name} — {issue_str}")

                send_telegram(
                    f"🔴 *Ad underperforming*\n"
                    f"_{ad_name}_\n"
                    f"{issue_str}\n"
                    f"Spend (7d): ${spend:.2f} AUD"
                )

                queue_task(
                    title=f"Meta Ads: optimise '{ad_name}' — {issue_str}",
                    description=(
                        f"Ad '{ad_name}' (ID: {ad_id}) is underperforming.\n"
                        f"Ad set ID: {adset_id}\n"
                        f"7-day stats: CTR={ctr:.1f}%, CPM=${cpm:.2f}, Spend=${spend:.2f}, Conversions={conversions}\n"
                        f"Issues: {issue_str}\n\n"
                        f"You have full permission to:\n"
                        f"1. Pull the ad creative and copy via Meta Graph API v20.0\n"
                        f"2. Analyse what's weak (hook, CTA, audience, creative type)\n"
                        f"3. Write 2 new ad variation prompts with different angles\n"
                        f"4. Create them in Meta as new ads in ad set {adset_id}\n"
                        f"5. Pause the original if CTR < 1% AND spend > $50 AUD\n"
                        f"6. Report: what you changed and why\n"
                        f"7. Queue a follow-up task: 'Check 24h results for {ad_name} variants'\n"
                        f"Use META_ACCESS_TOKEN + META_AD_ACCOUNT_ID from .env. Always v20.0."
                    ),
                    priority=2,
                )

    except Exception as e:
        log.warning(f"check_individual_ads error: {e}")

    return flagged


def check_daily_spend_safety() -> None:
    """
    Check total Meta spend this month vs MONTHLY_BUDGET_AUD.
    Alert at 80%. Pause all ads + alert at 100%.
    """
    try:
        r = requests.get(
            f"https://graph.facebook.com/v20.0/{META_ACCOUNT}/insights",
            params={
                "fields": "spend",
                "date_preset": "this_month",
                "access_token": META_TOKEN,
            },
            timeout=20,
        )
        if not r.ok:
            log.warning(f"Meta monthly spend fetch failed: {r.status_code}")
            return

        data = r.json().get("data", [{}])
        spend = float(data[0].get("spend", 0)) if data else 0.0
        pct = (spend / MONTHLY_BUDGET_AUD * 100) if MONTHLY_BUDGET_AUD > 0 else 0

        log.info(f"Meta monthly spend: ${spend:.2f} / ${MONTHLY_BUDGET_AUD:.2f} ({pct:.0f}%)")

        if pct >= 100:
            try:
                pause_r = requests.get(
                    f"https://graph.facebook.com/v20.0/{META_ACCOUNT}/campaigns",
                    params={
                        "fields": "id,name,status",
                        "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE"]}]',
                        "access_token": META_TOKEN,
                    },
                    timeout=15,
                )
                campaigns = pause_r.json().get("data", []) if pause_r.ok else []
                for camp in campaigns:
                    requests.post(
                        f"https://graph.facebook.com/v20.0/{camp['id']}",
                        params={"access_token": META_TOKEN},
                        json={"status": "PAUSED"},
                        timeout=10,
                    )
                send_telegram(
                    f"🚨 *META BUDGET EXCEEDED*\n"
                    f"Spend: ${spend:.2f} AUD ({pct:.0f}% of ${MONTHLY_BUDGET_AUD:.0f} budget)\n"
                    f"*All campaigns paused automatically.*\n"
                    f"Review and reactivate manually in Meta Business Manager."
                )
            except Exception as e:
                send_telegram(
                    f"🚨 *META BUDGET EXCEEDED* — failed to auto-pause\n"
                    f"Spend: ${spend:.2f} AUD. Pause manually NOW.\nError: {e}"
                )

        elif pct >= 80:
            send_telegram(
                f"⚠️ *Meta budget at {pct:.0f}%*\n"
                f"Spend: ${spend:.2f} AUD of ${MONTHLY_BUDGET_AUD:.0f} this month.\n"
                f"Monitor closely — auto-pause triggers at 100%."
            )

    except Exception as e:
        log.warning(f"check_daily_spend_safety error: {e}")


def main():
    log.info("Meta Monitor starting hourly check...")

    if not META_TOKEN or not META_ACCOUNT:
        log.error("META_ACCESS_TOKEN or META_AD_ACCOUNT_ID not set — aborting")
        return

    flagged = check_individual_ads()
    log.info(f"Meta Monitor complete. Flagged: {flagged} ads.")


if __name__ == "__main__":
    main()
