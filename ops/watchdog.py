#!/usr/bin/env python3
"""
Elite Systems AI — Watchdog

Runs every 15 minutes via pm2 cron on Mac Mini.
Self-healing checks:
  1. elite-worker PM2 status — restart if not online
  2. Supabase connectivity — alert if unreachable
  3. Last analyst run — re-trigger if > 3 hours ago
  4. Repeated workflow failures — queue investigation if same task fails 3x

Usage:
  pm2 start ecosystem.config.js --only elite-watchdog
"""

import sys
import logging
import subprocess
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

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def send_telegram(text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def check_worker() -> None:
    """Check elite-worker PM2 status. Restart if not online."""
    try:
        result = subprocess.run(
            ["pm2", "show", "elite-worker"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout + result.stderr
        if "online" in output.lower():
            log.info("Worker: online")
        else:
            log.warning("Worker: not online — restarting...")
            subprocess.run(["pm2", "restart", "elite-worker"], timeout=15)
            send_telegram(
                "⚠️ *Watchdog: Worker was down — restarted*\n"
                "elite-worker was not online. Auto-restarted.\n"
                "Monitor: `pm2 logs elite-worker`"
            )
    except Exception as e:
        log.warning(f"Worker check failed: {e}")
        send_telegram(f"⚠️ *Watchdog: Worker check failed*\nError: {e}")


def check_supabase() -> None:
    """Check Supabase is reachable."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers=SUPABASE_HEADERS,
            params={"limit": "1"},
            timeout=10,
        )
        if r.ok:
            log.info("Supabase: reachable")
        else:
            log.warning(f"Supabase: HTTP {r.status_code}")
            send_telegram(
                f"⚠️ *Watchdog: Supabase returning {r.status_code}*\n"
                f"Check Supabase dashboard or network."
            )
    except Exception as e:
        log.warning(f"Supabase unreachable: {e}")
        send_telegram(f"🚨 *Watchdog: Supabase UNREACHABLE*\nError: {e}\nQueue is paused until connectivity restored.")


def check_analyst_freshness() -> None:
    """
    Check if analyst has run in the last 3 hours.
    Detect by checking if any analyst-sourced task was created recently.
    If not, trigger analyst manually.
    """
    three_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers=SUPABASE_HEADERS,
            params={
                "source": "eq.analyst",
                "created_at": f"gte.{three_hours_ago}",
                "limit": "1",
            },
            timeout=10,
        )
        if r.ok and r.json():
            log.info("Analyst: ran within last 3h")
        else:
            log.warning("Analyst: no tasks created in last 3h — triggering...")
            subprocess.Popen(
                ["python3", str(Path(__file__).parent / "analyst.py")],
                cwd=str(Path(__file__).parent.parent),
            )
            send_telegram("⚠️ *Watchdog: Analyst hadn't run in 3h — triggered manually*")
    except Exception as e:
        log.warning(f"Analyst freshness check failed: {e}")


def check_repeated_failures() -> None:
    """
    Find tasks that have failed 3+ times with the same title in the last 24h.
    Queue an investigation task for each.
    """
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers=SUPABASE_HEADERS,
            params={
                "status": "eq.failed",
                "order": "title.asc",
                "limit": "50",
                "created_at": f"gte.{(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}",
            },
            timeout=10,
        )
        if not r.ok:
            return

        tasks = r.json()
        from collections import Counter
        title_counts = Counter(t["title"] for t in tasks)

        for title, count in title_counts.items():
            if count >= 3:
                investigation_title = f"WATCHDOG: Investigate repeated failure — {title[:60]}"
                dup_r = requests.get(
                    f"{SUPABASE_URL}/rest/v1/work_queue",
                    headers=SUPABASE_HEADERS,
                    params={
                        "title": f"eq.{investigation_title}",
                        "status": "in.(backlog,ready,in_progress)",
                        "limit": "1",
                    },
                    timeout=10,
                )
                if dup_r.ok and dup_r.json():
                    continue

                requests.post(
                    f"{SUPABASE_URL}/rest/v1/work_queue",
                    headers={**SUPABASE_HEADERS, "Prefer": "return=minimal"},
                    json={
                        "title": investigation_title,
                        "description": (
                            f"Task '{title}' has failed {count} times in the last 24 hours.\n"
                            f"Investigate root cause: check logs, check API credentials, check if external service is down.\n"
                            f"Fix or replace the failing task."
                        ),
                        "status": "ready",
                        "priority": 2,
                        "source": "watchdog",
                        "analyst_area": "queue",
                    },
                    timeout=10,
                )
                send_telegram(
                    f"🔁 *Watchdog: Repeated failure detected*\n"
                    f"_{title[:60]}_\n"
                    f"Failed {count} times today. Investigation queued."
                )
                log.info(f"Queued investigation for repeated failure: {title}")

    except Exception as e:
        log.warning(f"check_repeated_failures error: {e}")


def main():
    log.info("Watchdog starting checks...")
    check_worker()
    check_supabase()
    check_analyst_freshness()
    check_repeated_failures()
    log.info("Watchdog complete.")


if __name__ == "__main__":
    main()
