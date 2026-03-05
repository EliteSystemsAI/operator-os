#!/usr/bin/env python3
"""
Elite Systems AI — Analyst Brain

Runs every 2 hours via pm2 cron on Mac Mini.
Monitors 7 business areas. Auto-creates work_queue tasks for constraints found.
Priority 1 tasks also send a Telegram ping.

Monitors:
  1. GHL       — at-risk clients (0 new contacts in 7 days)
  2. Stripe    — churn events
  3. Meta      — underperforming ads
  4. Content   — content queue gaps
  5. Queue     — stuck in_progress tasks
  6. Calendar  — upcoming client calls (needs Google OAuth token)
  7. Gmail     — stale unread threads + unsent drafts (needs Google OAuth token)

Google OAuth setup (run once on MacBook):
  python scripts/setup_google_auth.py
  # then sync ~/.config/elite-os/google-token.json to Mac Mini

Usage:
  python ops/analyst.py        — run once (standalone)
  Triggered by pm2 cron        — every 2 hours automatically
"""

import sys
import json
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
GHL_AGENCY_KEY = env.get("GHL_AGENCY_API_KEY", "")
GHL_KEY = env.get("GHL_API_KEY", "")
GHL_LOCATION_ID = env.get("GHL_LOCATION_ID", "")
STRIPE_KEY = env.get("STRIPE_API_KEY", "")
META_TOKEN = env.get("META_ACCESS_TOKEN", "")
META_ACCOUNT = env.get("META_AD_ACCOUNT_ID", "")

AEST = timezone(timedelta(hours=10))

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Internal accounts to exclude from GHL client checks
GHL_EXCLUDE = {"Demo AI", "Ejey", "ELITE SYSTEMS AI PTY LTD", "Elite Systems Ai"}
GHL_EXCLUDE_PREFIXES = ("Elite ",)
GHL_EXCLUDE_SUFFIXES = ("'s Account",)


def is_real_client(name: str) -> bool:
    if name in GHL_EXCLUDE:
        return False
    if any(name.startswith(p) for p in GHL_EXCLUDE_PREFIXES):
        return False
    if any(name.endswith(s) for s in GHL_EXCLUDE_SUFFIXES):
        return False
    return True


# ── Supabase helpers ──────────────────────────────────────────────────────────


def queue_task(title: str, description: str, priority: int, area: str) -> bool:
    """
    Add task to work_queue as 'ready'.
    Deduplicates: skips if active task with same area+title exists.
    Returns True if added, False if skipped.
    """
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
            log.info(f"[{area}] Skipping duplicate: {title}")
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
        log.info(f"[{area}] Queued (P{priority}): {title}")
        return True
    except Exception as e:
        log.warning(f"queue_task failed for [{area}]: {e}")
        return False


def send_telegram(text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram failed: {e}")


# ── Monitor: GHL clients ──────────────────────────────────────────────────────


def monitor_ghl() -> list[dict]:
    """Check for at-risk clients (0 new contacts in 7 days)."""
    tasks = []
    seven_days_ago = (datetime.now(AEST) - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        r = requests.get(
            "https://rest.gohighlevel.com/v1/locations/",
            headers={"Authorization": f"Bearer {GHL_AGENCY_KEY}"},
            params={"limit": 100},
            timeout=30,
        )
        if not r.ok:
            log.warning(f"GHL locations fetch failed: {r.status_code}")
            return tasks

        locations = r.json().get("locations", [])
        at_risk = []

        for loc in locations:
            name = (loc.get("name") or "").strip()
            if not is_real_client(name):
                continue
            loc_id = loc.get("id") or loc.get("_id", "")
            try:
                cr = requests.get(
                    "https://rest.gohighlevel.com/v1/contacts/",
                    headers={"Authorization": f"Bearer {GHL_AGENCY_KEY}"},
                    params={"locationId": loc_id, "startDate": seven_days_ago, "limit": 10},
                    timeout=15,
                )
                contacts = len(cr.json().get("contacts", [])) if cr.ok else 0
                if contacts == 0:
                    at_risk.append(name)
            except Exception:
                pass

        if at_risk:
            names_str = ", ".join(at_risk[:5])
            suffix = f" (+{len(at_risk) - 5} more)" if len(at_risk) > 5 else ""
            tasks.append({
                "title": f"GHL: {len(at_risk)} clients at-risk — build re-engagement sequences",
                "description": (
                    f"These clients have had 0 new contacts in 7 days: {names_str}{suffix}.\n\n"
                    f"For each at-risk client, check their GHL sub-account and recommend or build "
                    f"a re-engagement automation sequence. Use GHL_AGENCY_API_KEY to access their accounts."
                ),
                "priority": 2,
                "area": "ghl",
            })
            log.info(f"GHL: {len(at_risk)} at-risk clients found")
        else:
            log.info("GHL: All clients healthy")

    except Exception as e:
        log.warning(f"GHL monitor error: {e}")

    return tasks


# ── Monitor: Stripe ───────────────────────────────────────────────────────────


def monitor_stripe() -> list[dict]:
    """Check for churn events in the last 7 days."""
    tasks = []
    week_start = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())

    try:
        r = requests.get(
            "https://api.stripe.com/v1/events",
            auth=(STRIPE_KEY, ""),
            params={
                "type": "customer.subscription.deleted",
                "created[gte]": str(week_start),
                "limit": "10",
            },
            timeout=20,
        )
        if r.ok:
            events = r.json().get("data", [])
            if events:
                tasks.append({
                    "title": f"Stripe: {len(events)} churn event(s) this week — analyse and respond",
                    "description": (
                        f"{len(events)} subscription(s) cancelled in the last 7 days. "
                        f"Fetch customer details from Stripe (STRIPE_API_KEY in .env), "
                        f"identify any patterns, and draft a win-back strategy or process improvement."
                    ),
                    "priority": 1,
                    "area": "stripe",
                })
                log.info(f"Stripe: {len(events)} churn events found")
            else:
                log.info("Stripe: No churn this week")
    except Exception as e:
        log.warning(f"Stripe monitor error: {e}")

    return tasks


# ── Monitor: Meta Ads ─────────────────────────────────────────────────────────


def monitor_meta() -> list[dict]:
    """Check for underperforming ads (CTR < 1% or CPM > $15 AUD)."""
    tasks = []

    try:
        r = requests.get(
            f"https://graph.facebook.com/v20.0/{META_ACCOUNT}/insights",
            params={
                "fields": "spend,impressions,clicks,ctr,cpm",
                "date_preset": "last_7d",
                "access_token": META_TOKEN,
            },
            timeout=20,
        )
        if r.ok:
            data = r.json().get("data", [{}])
            if data:
                d = data[0]
                ctr = float(d.get("ctr", 0))
                cpm = float(d.get("cpm", 0))
                spend = float(d.get("spend", 0))

                issues = []
                if spend > 5 and ctr < 1.0:
                    issues.append(f"CTR {ctr:.2f}% (below 1%)")
                if spend > 5 and cpm > 15:
                    issues.append(f"CPM ${cpm:.2f} (above $15)")

                if issues:
                    tasks.append({
                        "title": f"Meta Ads: underperforming — {', '.join(issues)}",
                        "description": (
                            f"7-day ad stats: CTR={ctr:.2f}%, CPM=${cpm:.2f}, Spend=${spend:.2f} AUD. "
                            f"Issues: {', '.join(issues)}. "
                            f"Review active ads via META_ACCESS_TOKEN, identify weak performers, "
                            f"suggest creative or targeting improvements. Use v20.0 API (not v21.0)."
                        ),
                        "priority": 2,
                        "area": "meta",
                    })
                    log.info(f"Meta: Issues found — {', '.join(issues)}")
                else:
                    log.info(f"Meta: Ads healthy (CTR={ctr:.2f}%, CPM=${cpm:.2f})")
    except Exception as e:
        log.warning(f"Meta monitor error: {e}")

    return tasks


# ── Monitor: Content Queue ────────────────────────────────────────────────────


def monitor_content() -> list[dict]:
    """Check content queue gaps + 72h Instagram posting gap."""
    tasks = []
    ig_token = env.get("INSTAGRAM_ACCESS_TOKEN", "")
    ig_account = env.get("INSTAGRAM_ACCOUNT_ID", "")

    # ── Existing: content queue gap check ─────────────────────────────────────
    queue_path = Path(__file__).parent.parent / "data" / "content_queue.json"
    if queue_path.exists():
        try:
            with open(queue_path) as f:
                data = json.load(f)
            queue = data.get("queue", [])
            targets = data.get("current_week_target", {})
            tofu = sum(1 for p in queue if p.get("funnel") == "TOFU")
            mofu = sum(1 for p in queue if p.get("funnel") == "MOFU")
            bofu = sum(1 for p in queue if p.get("funnel") == "BOFU")
            missing = []
            if tofu < targets.get("tofu", 2): missing.append(f"TOFU ({tofu}/{targets.get('tofu', 2)})")
            if mofu < targets.get("mofu", 1): missing.append(f"MOFU ({mofu}/{targets.get('mofu', 1)})")
            if bofu < targets.get("bofu", 3): missing.append(f"BOFU ({bofu}/{targets.get('bofu', 3)})")
            if missing:
                tasks.append({
                    "title": f"Content: missing {', '.join(missing)} scripts this week",
                    "description": (
                        f"Content queue is short: {', '.join(missing)}. "
                        f"Generate missing scripts following brand voice in knowledge/brand_voice.md. "
                        f"Check data/top_performing_content.json for winning hook patterns. "
                        f"Save scripts to content/ folder and update data/content_queue.json."
                    ),
                    "priority": 3,
                    "area": "content",
                })
                log.info(f"Content: Missing {', '.join(missing)}")
            else:
                log.info(f"Content: Queue healthy (TOFU:{tofu} MOFU:{mofu} BOFU:{bofu})")
        except Exception as e:
            log.warning(f"Content queue check error: {e}")

    # ── New: 72h Instagram posting gap check ──────────────────────────────────
    if ig_token and ig_account:
        try:
            r = requests.get(
                f"https://graph.facebook.com/v20.0/{ig_account}/media",
                params={
                    "fields": "timestamp,media_type",
                    "limit": "1",
                    "access_token": ig_token,
                },
                timeout=15,
            )
            if r.ok:
                media = r.json().get("data", [])
                if media:
                    last_post_ts = media[0].get("timestamp", "")
                    if last_post_ts:
                        from datetime import datetime as _dt
                        last_post = _dt.fromisoformat(last_post_ts.replace("Z", "+00:00"))
                        hours_since = (datetime.now(timezone.utc) - last_post).total_seconds() / 3600
                        if hours_since >= 72:
                            tasks.append({
                                "title": f"Instagram: {int(hours_since)}h posting gap — generate 3 Reel ideas",
                                "description": (
                                    f"Last Instagram post was {int(hours_since)} hours ago.\n\n"
                                    f"Generate 3 Reel script ideas + captions for [YOUR_INSTAGRAM_HANDLE]. "
                                    f"Follow brand voice in knowledge/brand_voice.md. "
                                    f"Check data/top_performing_content.json for winning hooks. "
                                    f"Include hook, body, CTA, and funnel stage [TOFU/MOFU/BOFU] for each. "
                                    f"Save to content/ folder."
                                ),
                                "priority": 2,
                                "area": "content",
                            })
                            log.info(f"Instagram: {int(hours_since)}h posting gap — queued content task")
                        else:
                            log.info(f"Instagram: Last post {int(hours_since)}h ago — OK")
                else:
                    log.info("Instagram: No media found")
        except Exception as e:
            log.warning(f"Instagram gap check error: {e}")
    else:
        log.info("Content: No INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID — skipping 72h check")

    return tasks


# ── Monitor: Work Queue health ────────────────────────────────────────────────


def monitor_work_queue() -> list[dict]:
    """Reset tasks stuck in_progress > 2 hours and alert Telegram."""
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers=SUPABASE_HEADERS,
            params={
                "status": "eq.in_progress",
                "started_at": f"lt.{two_hours_ago}",
                "limit": "5",
            },
            timeout=10,
        )
        if r.ok:
            stuck = r.json()
            if stuck:
                titles = [t["title"] for t in stuck]
                for t in stuck:
                    requests.patch(
                        f"{SUPABASE_URL}/rest/v1/work_queue",
                        headers=SUPABASE_HEADERS,
                        params={"id": f"eq.{t['id']}"},
                        json={"status": "ready", "started_at": None},
                        timeout=10,
                    )
                send_telegram(
                    f"⚠️ *Worker Alert*\n"
                    f"{len(stuck)} task(s) stuck in_progress >2h — reset to ready:\n"
                    + "\n".join(f"• {t}" for t in titles)
                )
                log.info(f"Queue: Reset {len(stuck)} stuck tasks")
            else:
                log.info("Queue: No stuck tasks")
    except Exception as e:
        log.warning(f"Queue monitor error: {e}")

    return []  # No new tasks from this monitor — just resets + alerts


# ── Google credentials helper ─────────────────────────────────────────────────

_GOOGLE_TOKEN_PATH = Path.home() / ".config" / "elite-os" / "google-token.json"


def _get_google_creds():
    """
    Load and auto-refresh Google OAuth2 credentials from the elite-os token file.
    Returns creds object, or None if token doesn't exist or scopes are missing.
    """
    if not _GOOGLE_TOKEN_PATH.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        creds = Credentials.from_authorized_user_file(str(_GOOGLE_TOKEN_PATH))
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
            with open(_GOOGLE_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        return creds if creds.valid else None
    except Exception as e:
        log.warning(f"Google creds load failed: {e}")
        return None


# ── Monitor: Google Calendar ───────────────────────────────────────────────────


def monitor_calendar() -> list[dict]:
    """
    Check Google Calendar for client calls in the next 6 hours.
    Queues a prep task for each one (priority 2), with Telegram ping if < 2 hours away.
    Skips gracefully if no Google token is set up.
    """
    creds = _get_google_creds()
    if creds is None:
        log.info("Calendar: No Google token at ~/.config/elite-os/google-token.json — skipping")
        return []

    tasks = []
    try:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        now_utc = datetime.now(timezone.utc)
        window_end = now_utc + timedelta(hours=6)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now_utc.isoformat(),
                timeMax=window_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        # Keywords that indicate a client call (case-insensitive)
        CALL_KEYWORDS = {"call", "consult", "catch up", "meet", "zoom", "teams", "sync", "discovery"}

        for event in events:
            summary = event.get("summary", "")
            description = event.get("description", "") or ""
            combined = (summary + " " + description).lower()

            is_call = any(kw in combined for kw in CALL_KEYWORDS)
            if not is_call:
                continue

            # Parse start time
            start_raw = event["start"].get("dateTime") or event["start"].get("date")
            if "T" in start_raw:
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            else:
                continue  # all-day event, skip

            start_aest = start_dt.astimezone(AEST)
            time_str = start_aest.strftime("%-I:%M%p AEST")
            minutes_away = int((start_dt - now_utc).total_seconds() / 60)

            # Attendees (exclude self)
            attendees = [
                a.get("email", "")
                for a in event.get("attendees", [])
                if not a.get("self") and a.get("email")
            ]
            attendee_str = ", ".join(attendees[:3]) if attendees else "no external attendees listed"

            # Check for existing prep task to avoid duplicates
            task_title = f"Call prep: {summary} at {time_str}"

            # Immediate Telegram ping if call is within 2 hours and very soon
            if minutes_away <= 120:
                send_telegram(
                    f"📅 *Call in {minutes_away} min*\n"
                    f"*{summary}* at {time_str}\n"
                    f"Attendees: {attendee_str}\n"
                    f"_Queuing prep brief..._"
                )

            tasks.append({
                "title": task_title,
                "description": (
                    f"Upcoming call: {summary} at {time_str}.\n"
                    f"Attendees: {attendee_str}\n\n"
                    f"Prepare a call brief:\n"
                    f"1. Search Gmail for recent threads with these attendees (source ~/.env for GOOGLE credentials)\n"
                    f"2. Check GHL for any open opportunities, pipeline stage, last activity\n"
                    f"3. Pull the last proposal or deliverable sent to this client\n"
                    f"4. List 3 key talking points based on context\n"
                    f"5. Note any open action items or follow-ups\n\n"
                    f"Send the full prep brief via Telegram "
                    f"(TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in ~/operatoros/.env)."
                ),
                "priority": 2,
                "area": "calendar",
            })
            log.info(f"Calendar: Queuing prep for '{summary}' at {time_str} (in {minutes_away}min)")

        if not tasks:
            log.info("Calendar: No calls in next 6 hours")

    except Exception as e:
        log.warning(f"Calendar monitor error: {e}")

    return tasks


# ── Monitor: Gmail inbox ───────────────────────────────────────────────────────


def monitor_gmail() -> list[dict]:
    """
    Check Gmail for:
    - Unread threads in primary inbox older than 24 hours
    - Drafts sitting unsent for 48+ hours
    Skips gracefully if no Google token is set up.
    """
    creds = _get_google_creds()
    if creds is None:
        log.info("Gmail: No Google token at ~/.config/elite-os/google-token.json — skipping")
        return []

    tasks = []
    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        # ── Unread threads older than 24h ─────────────────────────────────────
        cutoff_epoch = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
        result = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=f"is:unread before:{cutoff_epoch} -from:me category:primary",
                maxResults=20,
            )
            .execute()
        )
        messages = result.get("messages", [])
        if messages:
            # Grab subjects of first 5 to include in description
            subjects = []
            for msg in messages[:5]:
                try:
                    detail = (
                        service.users()
                        .messages()
                        .get(userId="me", id=msg["id"], format="metadata",
                             metadataHeaders=["Subject", "From"])
                        .execute()
                    )
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in detail.get("payload", {}).get("headers", [])
                    }
                    subj = headers.get("subject", "(no subject)")
                    sender = headers.get("from", "")
                    subjects.append(f"• {subj} — from: {sender}")
                except Exception:
                    pass

            tasks.append({
                "title": f"Gmail: {len(messages)} unread thread(s) need response (>24h old)",
                "description": (
                    f"{len(messages)} unread email(s) in primary inbox older than 24h.\n\n"
                    f"Threads (first 5):\n" + "\n".join(subjects) + "\n\n"
                    f"For each thread:\n"
                    f"1. Read the full thread content\n"
                    f"2. Determine if it needs a reply from Zac\n"
                    f"3. Draft a reply in Zac's voice: direct, no fluff, outcome-focused\n"
                    f"4. Create Gmail draft (or flag via Telegram if urgent)\n"
                    f"Credentials: ~/operatoros/.env has ANTHROPIC_API_KEY.\n"
                    f"Google token: ~/.config/elite-os/google-token.json"
                ),
                "priority": 2,
                "area": "gmail",
            })
            log.info(f"Gmail: {len(messages)} unread threads >24h found")
        else:
            log.info("Gmail: No stale unread threads")

        # ── Drafts sitting unsent ─────────────────────────────────────────────
        drafts_result = (
            service.users().drafts().list(userId="me", maxResults=15).execute()
        )
        drafts = drafts_result.get("drafts", [])

        if drafts:
            draft_subjects = []
            old_draft_count = 0
            cutoff_48h = datetime.now(timezone.utc) - timedelta(hours=48)

            for draft in drafts[:10]:
                try:
                    detail = (
                        service.users()
                        .drafts()
                        .get(userId="me", id=draft["id"], format="metadata")
                        .execute()
                    )
                    msg = detail.get("message", {})
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in msg.get("payload", {}).get("headers", [])
                    }
                    subject = headers.get("subject", "(no subject)")
                    date_str = headers.get("date", "")

                    # Parse date if available
                    try:
                        from email.utils import parsedate_to_datetime
                        draft_dt = parsedate_to_datetime(date_str)
                        if draft_dt.tzinfo is None:
                            draft_dt = draft_dt.replace(tzinfo=timezone.utc)
                        if draft_dt < cutoff_48h.replace(tzinfo=timezone.utc):
                            old_draft_count += 1
                            draft_subjects.append(f"• {subject}")
                    except Exception:
                        draft_subjects.append(f"• {subject} (date unknown)")
                        old_draft_count += 1
                except Exception:
                    pass

            if old_draft_count > 0:
                tasks.append({
                    "title": f"Gmail: {old_draft_count} unsent draft(s) sitting >48h",
                    "description": (
                        f"{old_draft_count} email draft(s) haven't been sent in 48+ hours:\n"
                        + "\n".join(draft_subjects[:5]) + "\n\n"
                        f"Review each draft: send if still relevant, discard if stale.\n"
                        f"Google token: ~/.config/elite-os/google-token.json"
                    ),
                    "priority": 3,
                    "area": "gmail",
                })
                log.info(f"Gmail: {old_draft_count} old unsent drafts found")
            else:
                log.info(f"Gmail: {len(drafts)} drafts exist but none are >48h old")
        else:
            log.info("Gmail: No drafts found")

    except Exception as e:
        log.warning(f"Gmail monitor error: {e}")

    return tasks


# ── Monitor: Slack @zac mentions ──────────────────────────────────────────────


def monitor_slack() -> list[dict]:
    """
    Check Slack for @zac mentions and urgent keywords in client channels.
    Requires SLACK_BOT_TOKEN in .env with channels:history scope.
    """
    slack_token = env.get("SLACK_BOT_TOKEN", "")
    if not slack_token:
        log.info("Slack: No SLACK_BOT_TOKEN — skipping")
        return []

    tasks = []
    URGENT_KEYWORDS = {"broken", "help", "issue", "not working", "urgent", "error", "down", "failed"}
    CRITICAL_KEYWORDS = {"urgent", "down", "critical", "emergency"}
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())

    try:
        ch_r = requests.get(
            "https://slack.com/api/conversations.list",
            headers={"Authorization": f"Bearer {slack_token}"},
            params={"types": "public_channel,private_channel", "limit": "200"},
            timeout=15,
        )
        if not ch_r.ok or not ch_r.json().get("ok"):
            log.warning(f"Slack channels fetch failed: {ch_r.text[:200]}")
            return tasks

        channels = ch_r.json().get("channels", [])
        flagged_messages = []

        for ch in channels:
            ch_id = ch["id"]
            ch_name = ch.get("name", ch_id)

            hist_r = requests.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {slack_token}"},
                params={"channel": ch_id, "oldest": str(cutoff), "limit": "50"},
                timeout=15,
            )
            if not hist_r.ok or not hist_r.json().get("ok"):
                continue

            messages = hist_r.json().get("messages", [])
            for msg in messages:
                text_lower = (msg.get("text") or "").lower()
                is_zac_mention = "<@U" in msg.get("text", "") and "zac" in text_lower
                has_urgent = any(kw in text_lower for kw in URGENT_KEYWORDS)
                is_critical = any(kw in text_lower for kw in CRITICAL_KEYWORDS)

                if is_zac_mention or has_urgent:
                    flagged_messages.append({
                        "channel": ch_name,
                        "text": msg.get("text", "")[:200],
                        "critical": is_critical,
                    })

                    if is_critical:
                        send_telegram(
                            f"🚨 *Slack urgent message*\n"
                            f"Channel: #{ch_name}\n"
                            f"_{msg.get('text', '')[:150]}_"
                        )

        if flagged_messages:
            summary = "\n".join(
                f"• #{m['channel']}: {m['text'][:80]}{'🚨' if m['critical'] else ''}"
                for m in flagged_messages[:5]
            )
            tasks.append({
                "title": f"Slack: {len(flagged_messages)} message(s) need response",
                "description": (
                    f"{len(flagged_messages)} Slack message(s) mention @zac or contain urgent keywords.\n\n"
                    f"Messages:\n{summary}\n\n"
                    f"For each message:\n"
                    f"1. Read the full thread context\n"
                    f"2. Draft a reply in Zac's voice (direct, outcome-focused)\n"
                    f"3. Flag for Zac review via Telegram before sending\n"
                    f"Use SLACK_BOT_TOKEN from .env."
                ),
                "priority": 2,
                "area": "slack",
            })
            log.info(f"Slack: {len(flagged_messages)} flagged messages")
        else:
            log.info("Slack: No urgent messages")

    except Exception as e:
        log.warning(f"Slack monitor error: {e}")

    return tasks


# ── Monitor: GHL workflow failures ────────────────────────────────────────────


def monitor_ghl_workflows() -> list[dict]:
    """
    Check GHL workflow execution history for high failure rates.
    Surfaces top 3 failing workflows as priority 2 tasks.
    Requires GHL_API_KEY with workflows:read permission.
    """
    tasks = []
    if not GHL_KEY or not GHL_LOCATION_ID:
        log.info("GHL workflows: No GHL_API_KEY or GHL_LOCATION_ID — skipping")
        return tasks

    try:
        r = requests.get(
            "https://services.leadconnectorhq.com/workflows/",
            headers={
                "Authorization": f"Bearer {GHL_KEY}",
                "Version": "2021-07-28",
            },
            params={"locationId": GHL_LOCATION_ID, "limit": 50},
            timeout=20,
        )
        if not r.ok:
            log.warning(f"GHL workflows fetch failed: {r.status_code}")
            return tasks

        workflows = r.json().get("workflows", [])
        failing = []

        for wf in workflows:
            wf_id = wf.get("id", "")
            wf_name = wf.get("name", wf_id)

            stats_r = requests.get(
                f"https://services.leadconnectorhq.com/workflows/{wf_id}/executions/stats",
                headers={
                    "Authorization": f"Bearer {GHL_KEY}",
                    "Version": "2021-07-28",
                },
                params={"locationId": GHL_LOCATION_ID, "days": 7},
                timeout=15,
            )
            if not stats_r.ok:
                continue

            stats = stats_r.json()
            total = stats.get("total", 0)
            failed = stats.get("failed", 0)
            failure_rate = (failed / total * 100) if total > 0 else 0

            if total >= 5 and failure_rate > 20:
                failing.append({
                    "name": wf_name,
                    "id": wf_id,
                    "failure_rate": failure_rate,
                    "total": total,
                    "failed": failed,
                })

        failing.sort(key=lambda x: x["failure_rate"], reverse=True)
        for wf in failing[:3]:
            tasks.append({
                "title": f"GHL: Fix workflow '{wf['name'][:50]}' — {wf['failure_rate']:.0f}% failure rate",
                "description": (
                    f"Workflow '{wf['name']}' has a {wf['failure_rate']:.0f}% failure rate "
                    f"({wf['failed']}/{wf['total']} executions failed in last 7 days).\n"
                    f"Workflow ID: {wf['id']}\n\n"
                    f"1. Review recent failed executions in GHL\n"
                    f"2. Identify the failing step\n"
                    f"3. Fix the configuration or replace with working alternative\n"
                    f"4. Test with a sample contact\n"
                    f"Use GHL_API_KEY + GHL_LOCATION_ID from .env."
                ),
                "priority": 2,
                "area": "ghl",
            })

        if failing:
            log.info(f"GHL workflows: {len(failing)} workflows with >20% failure rate")
        else:
            log.info("GHL workflows: All workflows healthy")

    except Exception as e:
        log.warning(f"GHL workflow monitor error: {e}")

    return tasks


# ── Monitor: Stripe failed payments ───────────────────────────────────────────


def monitor_stripe_failed_payments() -> list[dict]:
    """Check Stripe for failed payments in last 48 hours."""
    tasks = []
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=48)).timestamp())

    try:
        r = requests.get(
            "https://api.stripe.com/v1/payment_intents",
            auth=(STRIPE_KEY, ""),
            params={
                "status": "requires_payment_method",
                "created[gte]": str(cutoff),
                "limit": "20",
            },
            timeout=20,
        )
        if not r.ok:
            log.warning(f"Stripe failed payments fetch failed: {r.status_code}")
            return tasks

        failed = r.json().get("data", [])
        if failed:
            customer_ids = [pi.get("customer", "unknown") for pi in failed[:3]]
            tasks.append({
                "title": f"Stripe: {len(failed)} failed payment(s) in last 48h — send recovery",
                "description": (
                    f"{len(failed)} failed payment intent(s) in the last 48 hours.\n"
                    f"Customer IDs (first 3): {', '.join(str(c) for c in customer_ids)}\n\n"
                    f"For each failed payment:\n"
                    f"1. Look up the customer in Stripe via STRIPE_API_KEY\n"
                    f"2. Check their email and subscription status\n"
                    f"3. Trigger GHL recovery automation if configured, OR\n"
                    f"4. Draft a follow-up email in Zac's voice and create Gmail draft\n"
                    f"Report back: how many were contacted and via what method."
                ),
                "priority": 2,
                "area": "stripe",
            })
            log.info(f"Stripe: {len(failed)} failed payments found")
        else:
            log.info("Stripe: No failed payments in last 48h")

    except Exception as e:
        log.warning(f"Stripe failed payments monitor error: {e}")

    return tasks


# ── Monitor: Cross-client pattern detection (weekly) ──────────────────────────


def monitor_cross_client() -> list[dict]:
    """
    Check for patterns across client tasks.
    Only meaningful when run weekly (not every 2h).
    Looks for: same fix applied to 3+ clients — suggest rollout.
    """
    tasks = []
    try:
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/work_queue",
            headers=SUPABASE_HEADERS,
            params={
                "status": "eq.done",
                "created_at": f"gte.{thirty_days_ago}",
                "limit": "200",
            },
            timeout=15,
        )
        if not r.ok:
            return tasks

        completed = r.json()
        from collections import Counter
        area_counts = Counter(t.get("analyst_area") for t in completed if t.get("analyst_area"))

        for area, count in area_counts.items():
            if count >= 3 and area in ("ghl", "stripe", "meta", "content"):
                title = f"Cross-client: {count} '{area}' fixes this month — consider rollout"
                dup_r = requests.get(
                    f"{SUPABASE_URL}/rest/v1/work_queue",
                    headers=SUPABASE_HEADERS,
                    params={
                        "title": f"eq.{title}",
                        "status": "in.(backlog,ready,in_progress)",
                        "limit": "1",
                    },
                    timeout=10,
                )
                if dup_r.ok and dup_r.json():
                    continue

                tasks.append({
                    "title": title,
                    "description": (
                        f"{count} completed tasks in '{area}' this month. "
                        f"Review the patterns: were these the same type of fix? "
                        f"If so, identify which clients might benefit from the same improvement "
                        f"and draft a rollout plan. "
                        f"Report: what the pattern is, which clients already have it, "
                        f"which ones don't, and a recommended action."
                    ),
                    "priority": 4,
                    "area": area,
                })

        if tasks:
            log.info(f"Cross-client: {len(tasks)} pattern(s) detected")
        else:
            log.info("Cross-client: No significant patterns")

    except Exception as e:
        log.warning(f"Cross-client monitor error: {e}")

    return tasks


# ── Main ──────────────────────────────────────────────────────────────────────


def run_analyst() -> str:
    """Run all monitors. Returns a Telegram-formatted summary string."""
    log.info("Analyst Brain starting scan...")
    now_str = datetime.now(AEST).strftime("%-d %b %Y %H:%M AEST")
    all_tasks: list[dict] = []

    monitors = [
        ("GHL", monitor_ghl),
        ("Stripe", monitor_stripe),
        ("Stripe Failed Payments", monitor_stripe_failed_payments),
        ("Meta", monitor_meta),
        ("Content", monitor_content),
        ("Queue", monitor_work_queue),
        ("Calendar", monitor_calendar),
        ("Gmail", monitor_gmail),
        ("Slack", monitor_slack),
        ("GHL Workflows", monitor_ghl_workflows),
    ]

    for name, fn in monitors:
        log.info(f"Scanning: {name}...")
        try:
            tasks = fn()
            all_tasks.extend(tasks)
        except Exception as e:
            log.warning(f"{name} scan failed: {e}")

    # Queue tasks, ping Telegram on critical
    queued = 0
    for task in all_tasks:
        added = queue_task(
            title=task["title"],
            description=task["description"],
            priority=task["priority"],
            area=task["area"],
        )
        if added:
            queued += 1
            if task["priority"] == 1:
                send_telegram(
                    f"🚨 *Critical constraint detected*\n"
                    f"{task['title']}\n\n"
                    f"_Auto-queued for immediate attention._"
                )

    summary = (
        f"🔍 *Analyst Scan Complete*\n"
        f"_{now_str}_\n\n"
        f"Areas scanned: {len(monitors)}\n"
        f"Tasks queued: {queued}\n"
        f"{'✅ No new constraints found' if queued == 0 else f'⚡ {queued} new constraint(s) queued'}"
    )

    log.info(f"Analyst done. Queued {queued} tasks.")
    return summary


def run_analyst_night() -> str:
    """
    Night Deep Mode — 11pm AEST predictive scan.
    Reviews today's data, identifies what's likely to break tomorrow.
    Queues fixes and sends a 'tomorrow's risks' summary.
    """
    log.info("Analyst Night Mode starting...")
    now_str = datetime.now(AEST).strftime("%-d %b %Y %H:%M AEST")
    all_tasks: list[dict] = []

    monitors = [
        ("GHL", monitor_ghl),
        ("Stripe", monitor_stripe),
        ("Stripe Failed Payments", monitor_stripe_failed_payments),
        ("Meta", monitor_meta),
        ("Content", monitor_content),
        ("Queue", monitor_work_queue),
        ("Calendar", monitor_calendar),
        ("Gmail", monitor_gmail),
        ("Slack", monitor_slack),
        ("GHL Workflows", monitor_ghl_workflows),
        ("Cross-Client", monitor_cross_client),
    ]

    for name, fn in monitors:
        log.info(f"Night scan: {name}...")
        try:
            tasks = fn()
            all_tasks.extend(tasks)
        except Exception as e:
            log.warning(f"{name} night scan failed: {e}")

    queued = 0
    for task in all_tasks:
        added = queue_task(
            title=task["title"],
            description=f"[NIGHT DEEP MODE] {task['description']}",
            priority=task["priority"],
            area=task["area"],
        )
        if added:
            queued += 1

    queue_task(
        title="Night Mode: Predictive summary — what might break tomorrow",
        description=(
            "Review today's business data and predict what's most likely to need attention tomorrow.\n\n"
            "Check:\n"
            "1. Any ads with declining CTR trend over last 48h\n"
            "2. GHL clients with 0 activity this week (churn risk)\n"
            "3. Stripe MRR trend — any at-risk subscriptions\n"
            "4. Content queue — will it run out before next post time?\n"
            "5. Any pending tasks that haven't started yet\n\n"
            "Output: A 'Tomorrow's Risks' summary — top 3 things to watch, "
            "and whether each has already been queued for action.\n"
            "Send summary via Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env)."
        ),
        priority=3,
        area="analyst",
    )
    queued += 1

    summary = (
        f"🌙 *Night Deep Mode Complete*\n"
        f"_{now_str}_\n\n"
        f"Areas scanned: {len(monitors)}\n"
        f"Tasks queued for tomorrow: {queued}\n"
        f"Sleep well — the system is watching. 👁️"
    )

    send_telegram(summary)
    log.info(f"Night mode done. Queued {queued} tasks.")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--night", action="store_true", help="Run night deep mode")
    args = parser.parse_args()
    if args.night:
        result = run_analyst_night()
    else:
        result = run_analyst()
    print(result)
