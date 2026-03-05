#!/usr/bin/env python3
"""
Elite Systems AI — Weekly Ops Digest
Runs every Monday 8am AEST (Sunday 10pm UTC via GitHub Actions / Railway cron)

Pulls live data from Stripe, GHL, and content queue
→ Sends Telegram digest to Zac
→ Auto-writes to Supabase eos_scorecard so the dashboard fills itself
"""

import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Credentials ──────────────────────────────────────────────────────────────

def load_env():
    import os
    # Start with real environment variables (Railway, production)
    env = dict(os.environ)
    # Override/supplement with .env file if present (local development)
    for candidate in [
        Path(__file__).parent.parent / ".env",
        Path.home() / ".env",
    ]:
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

STRIPE_KEY          = env["STRIPE_API_KEY"]
GHL_KEY             = env["GHL_API_KEY"]
GHL_LOCATION_ID     = env["GHL_LOCATION_ID"]
GHL_PIPELINE_ID     = "5zdmBR6RzVuB4mDwZ4Sa"
TELEGRAM_TOKEN      = env["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = env["TELEGRAM_CHAT_ID"]
SUPABASE_URL        = env["SUPABASE_URL"]
SUPABASE_KEY        = env["SUPABASE_SERVICE_ROLE_KEY"]

# ── Time helpers (AEST = UTC+10, no DST in QLD) ──────────────────────────────

AEST = timezone(timedelta(hours=10))
now  = datetime.now(AEST)

def week_start_ts():
    """Unix timestamp for Monday 00:00 AEST this week"""
    monday = now - timedelta(days=now.weekday())
    return int(monday.replace(hour=0, minute=0, second=0, microsecond=0)
               .astimezone(timezone.utc).timestamp())

def month_start_ts():
    return int(datetime(now.year, now.month, 1, tzinfo=AEST)
               .astimezone(timezone.utc).timestamp())

def days_in_month():
    if now.month == 12:
        return (datetime(now.year + 1, 1, 1, tzinfo=AEST) -
                datetime(now.year, 12, 1, tzinfo=AEST)).days
    return (datetime(now.year, now.month + 1, 1, tzinfo=AEST) -
            datetime(now.year, now.month, 1, tzinfo=AEST)).days

WEEK_START = week_start_ts()
MONTH_START = month_start_ts()

# ── Stripe ────────────────────────────────────────────────────────────────────

def stripe_get(path, params=None):
    r = requests.get(f"https://api.stripe.com/v1{path}",
                     params=params or {}, auth=(STRIPE_KEY, ""), timeout=30)
    r.raise_for_status()
    return r.json()

def paginate_stripe(path, extra_params=None):
    items, params = [], {"limit": "100", **(extra_params or {})}
    for _ in range(20):
        data = stripe_get(path, params)
        items.extend(data.get("data", []))
        if not data.get("has_more"):
            break
        params["starting_after"] = data["data"][-1]["id"]
    return items

def get_stripe_data():
    # Active subscriptions → MRR + client count
    active_subs = paginate_stripe("/subscriptions", {"status": "active"})
    mrr = 0
    new_this_week = 0
    for sub in active_subs:
        if sub.get("created", 0) >= WEEK_START:
            new_this_week += 1
        for item in sub.get("items", {}).get("data", []):
            price = item.get("price", {})
            amount = price.get("unit_amount", 0) / 100
            interval = price.get("recurring", {}).get("interval", "")
            if interval == "month":   mrr += amount
            elif interval == "year":  mrr += amount / 12
            elif interval == "week":  mrr += amount * 4.33

    # Cancelled this week → use Events API (subscriptions list doesn't filter by canceled_at)
    cancelled_events = paginate_stripe("/events", {
        "type": "customer.subscription.deleted",
        "created[gte]": str(WEEK_START),
    })

    # MTD invoices → cash collected
    invoices = paginate_stripe("/invoices", {
        "status": "paid",
        "created[gte]": str(MONTH_START),
    })
    mtd = sum(inv.get("amount_paid", 0) / 100 for inv in invoices
              if inv.get("amount_paid", 0) > 0)

    elapsed = now.day
    total_days = days_in_month()
    run_rate = round((mtd / elapsed) * total_days) if elapsed > 0 else 0

    return {
        "mrr":            round(mrr),
        "active_clients": len(active_subs),
        "new_clients":    new_this_week,
        "churn":          len(cancelled_events),
        "mtd":            round(mtd),
        "run_rate":       run_rate,
        "elapsed":        elapsed,
        "total_days":     total_days,
    }

# ── GHL ───────────────────────────────────────────────────────────────────────

def ghl_get(path, params=None):
    r = requests.get(f"https://services.leadconnectorhq.com{path}",
                     params=params or {},
                     headers={"Authorization": f"Bearer {GHL_KEY}",
                               "Version": "2021-07-28"},
                     timeout=30)
    r.raise_for_status()
    return r.json()

def get_pipeline_data():
    opps, params = [], {
        "location_id": GHL_LOCATION_ID,
        "pipeline_id": GHL_PIPELINE_ID,
        "limit": "100",
        "status": "open",
    }
    for _ in range(10):
        data = ghl_get("/opportunities/search", params)
        batch = data.get("opportunities", [])
        opps.extend(batch)
        if len(batch) < 100 or not data.get("meta", {}).get("nextPageUrl"):
            break
        params["startAfterId"] = batch[-1]["id"]

    # createdAt is ISO string in GHL v2 (e.g. "2026-02-25T10:30:00.000Z")
    week_start_iso = datetime.fromtimestamp(WEEK_START, tz=timezone.utc).strftime("%Y-%m-%d")
    new_this_week = sum(
        1 for o in opps
        if (o.get("createdAt") or "") >= week_start_iso
    )
    total_value = sum(float(o.get("monetaryValue") or 0) for o in opps)

    return {
        "total_open":    len(opps),
        "new_this_week": new_this_week,
        "total_value":   round(total_value),
    }

def get_new_leads():
    """New contacts added to GHL this week"""
    start_str = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    try:
        data = ghl_get("/contacts/", {
            "locationId": GHL_LOCATION_ID,
            "limit": "100",
            "startDate": start_str,
        })
        return len(data.get("contacts", []))
    except Exception:
        return 0

# ── Content Queue ─────────────────────────────────────────────────────────────

def get_content_status():
    queue_path = Path(__file__).parent.parent / "data" / "content_queue.json"
    if not queue_path.exists():
        return {"scheduled": 0, "missing": [], "targets": {}}

    with open(queue_path) as f:
        data = json.load(f)

    queue   = data.get("queue", [])
    targets = data.get("current_week_target", {})

    tofu_count   = sum(1 for p in queue if p.get("funnel") == "TOFU")
    tofu_dd      = sum(1 for p in queue if p.get("funnel") == "TOFU_DOUBLE_DOWN")
    mofu_count   = sum(1 for p in queue if p.get("funnel") == "MOFU")
    bofu_count   = sum(1 for p in queue if p.get("funnel") == "BOFU")

    missing = []
    if tofu_count   < targets.get("tofu", 0):           missing.append("TOFU")
    if tofu_dd      < targets.get("tofu_double_down", 0): missing.append("Double Down")
    if mofu_count   < targets.get("mofu", 0):           missing.append("MOFU")
    if bofu_count   < targets.get("bofu", 0):           missing.append("BOFU")

    return {
        "scheduled": len(queue),
        "breakdown": f"TOFU:{tofu_count} DD:{tofu_dd} MOFU:{mofu_count} BOFU:{bofu_count}",
        "missing": missing,
        "target": targets.get("total", 7),
    }

# ── Supabase scorecard write ──────────────────────────────────────────────────

def write_to_scorecard(stripe, pipeline, leads):
    """
    Auto-fill the eos_scorecard table with whatever we can derive from APIs.
    Manual metrics (workflows_delivered, support_tickets, content_posts, ig_followers)
    are left for the team to fill in the dashboard.
    """
    week_ending = (now + timedelta(days=6 - now.weekday())).strftime("%Y-%m-%d")

    payload = {
        "week_ending":     week_ending,
        "mrr":             stripe["mrr"],
        "revenue":         stripe["mtd"],       # MTD cash collected
        "new_clients":     stripe["new_clients"],
        "churned_clients": stripe["churn"],
        "leads_generated": leads,
        "qualified_leads": pipeline["new_this_week"],  # new pipeline opps as proxy
        "updated_at":      datetime.now(timezone.utc).isoformat(),
    }

    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/eos_scorecard?on_conflict=week_ending",
        json=payload,
        headers=headers,
        timeout=15,
    )
    return r.status_code

# ── Format digest ─────────────────────────────────────────────────────────────

def progress_bar(value, goal, width=10):
    pct = min(value / goal, 1.0) if goal > 0 else 0
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled), round(pct * 100)

def build_digest(stripe, pipeline, leads, content):
    date_str = now.strftime("%-d %b %Y")

    mrr_bar, mrr_pct = progress_bar(stripe["mrr"], 25000)
    mtd_bar, mtd_pct = progress_bar(stripe["mtd"], stripe["run_rate"] or 1)

    churn_icon = "✅" if stripe["churn"] == 0 else f"⚠️ {stripe['churn']}"
    content_icon = "✅" if not content["missing"] else f"⚠️ Missing: {', '.join(content['missing'])}"

    lines = [
        f"📊 *WEEKLY OPS DIGEST*",
        f"_{date_str} | Elite Systems AI_",
        "",
        f"💰 *REVENUE*",
        f"MRR:  ${stripe['mrr']:,}  /{25000:,} goal",
        f"`{mrr_bar}` {mrr_pct}%",
        f"MTD:  ${stripe['mtd']:,}  (run rate ${stripe['run_rate']:,})",
        f"Active clients: {stripe['active_clients']}",
        f"New this week:  +{stripe['new_clients']}  |  Churn: {churn_icon}",
        "",
        f"📥 *PIPELINE*",
        f"Open opps:  {pipeline['total_open']}  (${pipeline['total_value']:,} total value)",
        f"New this week: {pipeline['new_this_week']}",
        f"New leads:     {leads}",
        "",
        f"📱 *CONTENT*",
        f"Queue: {content['scheduled']}/{content['target']}  |  {content['breakdown']}",
        content_icon,
        "",
        f"🔗 internal.elitesystems.ai",
    ]

    return "\n".join(lines)

# ── Send Telegram ─────────────────────────────────────────────────────────────

def send_telegram(message):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown",
        },
        timeout=15,
    )
    return r.ok

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{now.strftime('%Y-%m-%d %H:%M')} AEST] Running Weekly Ops Digest...")

    print("  → Fetching Stripe data...")
    stripe = get_stripe_data()

    print("  → Fetching GHL pipeline...")
    pipeline = get_pipeline_data()

    print("  → Fetching new leads...")
    leads = get_new_leads()

    print("  → Reading content queue...")
    content = get_content_status()

    print("  → Writing to Supabase scorecard...")
    status = write_to_scorecard(stripe, pipeline, leads)
    print(f"     Supabase response: {status}")

    print("  → Building digest...")
    digest = build_digest(stripe, pipeline, leads, content)
    print("\n" + digest + "\n")

    print("  → Sending Telegram...")
    ok = send_telegram(digest)
    print(f"     Telegram: {'✓ sent' if ok else '✗ failed'}")

    print("Done.")

if __name__ == "__main__":
    main()
