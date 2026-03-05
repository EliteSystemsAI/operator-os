#!/usr/bin/env python3
"""
Elite Systems AI — Slack Listener + n8n Delivery Endpoint

FastAPI app with two endpoints:

  POST /api/deliver
    Called by n8n after Fathom webhook or Slack trigger.
    Body: { client_name, system_name, description, platform, call_summary, source }
    Runs process_delivery() and returns the Telegram-formatted result.

  POST /slack/events
    Slack Events API receiver.
    Listens for messages in #client-* channels containing delivery keywords
    (done, live, delivered, ✅, launched).
    Extracts client from channel name → calls process_delivery() in background
    → posts confirmation reply in Slack thread.

Deploy: uvicorn ops.slack_listener:app --host 0.0.0.0 --port $PORT
"""

import asyncio
import hashlib
import hmac
import logging
import re
import sys
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from ops.client_deliveries import (  # noqa: E402
    env,
    process_delivery,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN = env.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = env.get("SLACK_SIGNING_SECRET", "")

# Explicit delivery marker — messages must start with this prefix to trigger
# auto-detection from Slack. This prevents voice transcripts or general chat
# from accidentally triggering the delivery pipeline.
# Format: "DELIVERED: System Name"
_EXPLICIT_DELIVERY_PREFIX = re.compile(
    r"^DELIVERED:\s*(.+)",
    re.IGNORECASE,
)

app = FastAPI(title="Elite Systems — Delivery API", version="1.0.0")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slack_headers() -> dict:
    return {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


def _post_slack_message(channel: str, text: str, thread_ts: str | None = None) -> None:
    """Post a message to a Slack channel (optionally as a thread reply)."""
    import requests as req
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    try:
        r = req.post(
            "https://slack.com/api/chat.postMessage",
            headers=_slack_headers(),
            json=payload,
            timeout=10,
        )
        data = r.json()
        if not data.get("ok"):
            log.error(f"Slack postMessage error: {data.get('error')}")
    except Exception as e:
        log.error(f"Slack postMessage exception: {e}")


def _verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature to prevent spoofing."""
    if not SLACK_SIGNING_SECRET:
        log.warning("SLACK_SIGNING_SECRET not set — skipping verification")
        return True
    # Reject stale requests (>5 min old)
    if abs(time.time() - float(timestamp)) > 300:
        return False
    base = f"v0:{timestamp}:{request_body.decode()}"
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _channel_to_client_name(channel_name: str) -> str:
    """
    Convert Slack channel name to display client name.
    Examples:
      'acme-fitness'    → 'Acme Fitness'
      'pure-yoga-co'    → 'Pure Yoga Co'
      'client-bob-smith' → 'Bob Smith'  (strips leading 'client-')
    """
    name = channel_name.strip().lower()
    # Strip common prefixes
    for prefix in ("client-", "clients-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return " ".join(word.capitalize() for word in name.split("-"))



# ── Background tasks ──────────────────────────────────────────────────────────


def _run_delivery_and_notify(
    client_name: str,
    system_name: str,
    description: str,
    platform: str,
    call_summary: str,
    source: str,
    slack_channel: str | None = None,
    slack_thread_ts: str | None = None,
) -> None:
    """
    Run process_delivery() and optionally post result to Slack + Telegram.
    Designed to run in a background thread.
    """
    log.info(f"Background delivery: client={client_name!r} system={system_name!r}")
    try:
        result = process_delivery(
            client_name=client_name,
            system_name=system_name,
            description=description,
            platform=platform,
            call_summary=call_summary,
            source=source,
        )
        log.info("process_delivery completed")

        # Post to Slack thread if triggered from Slack
        if slack_channel and SLACK_BOT_TOKEN:
            slack_msg = f"✅ *{system_name}* logged for *{client_name}*.\n\n💡 Next: _{result.split('Next suggested system:')[1].strip().strip('_') if 'Next suggested system:' in result else 'See Telegram'}_"
            _post_slack_message(slack_channel, slack_msg, slack_thread_ts)

        # Always send to Telegram
        if env.get("TELEGRAM_BOT_TOKEN"):
            import requests as req
            req.post(
                f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage",
                json={"chat_id": env["TELEGRAM_CHAT_ID"], "text": result, "parse_mode": "Markdown"},
                timeout=15,
            )
    except Exception as e:
        log.exception(f"Background delivery failed: {e}")
        if slack_channel and SLACK_BOT_TOKEN:
            _post_slack_message(slack_channel, f"❌ Delivery pipeline failed: {e}", slack_thread_ts)


# ── Request models ────────────────────────────────────────────────────────────


class DeliverRequest(BaseModel):
    client_name: str
    system_name: str
    description: str = ""
    platform: str = ""
    call_summary: str = ""
    source: str = "n8n"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Railway health check."""
    return {"status": "ok", "service": "elite-systems-delivery-api"}


@app.post("/api/deliver")
async def api_deliver(payload: DeliverRequest, background_tasks: BackgroundTasks):
    """
    Called by n8n after Fathom webhook or Slack trigger.
    Immediately returns 202 and runs the pipeline in the background.
    """
    if not payload.client_name or not payload.system_name:
        raise HTTPException(status_code=400, detail="client_name and system_name are required")

    log.info(f"/api/deliver — client={payload.client_name!r} system={payload.system_name!r} source={payload.source}")

    background_tasks.add_task(
        _run_delivery_and_notify,
        client_name=payload.client_name,
        system_name=payload.system_name,
        description=payload.description,
        platform=payload.platform,
        call_summary=payload.call_summary,
        source=payload.source,
    )

    return {
        "status": "accepted",
        "message": f"Delivery pipeline started for '{payload.client_name}'",
    }


@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Slack Events API receiver.
    Handles URL verification challenge and message events.
    Only processes messages in #client-* channels with delivery keywords.
    """
    body_bytes = await request.body()

    # Verify Slack signature
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if SLACK_SIGNING_SECRET and not _verify_slack_signature(body_bytes, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    body = await request.json()

    # URL verification challenge (Slack sends this when first connecting)
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body["challenge"]})

    # Ignore retried events (already processed)
    if request.headers.get("X-Slack-Retry-Reason") == "http_timeout":
        return JSONResponse({"status": "ignored_retry"})

    event = body.get("event", {})
    event_type = event.get("type", "")

    # Only handle message events (not bot messages, edits, or deletions)
    if event_type != "message":
        return JSONResponse({"status": "ignored"})
    if event.get("bot_id") or event.get("subtype"):
        return JSONResponse({"status": "ignored_bot"})

    channel_id = event.get("channel", "")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    # Get channel name from Slack API to check if it's a #client-* channel
    channel_name = body.get("_channel_name", "")  # injected by n8n if available
    if not channel_name and SLACK_BOT_TOKEN:
        try:
            import requests as req
            r = req.get(
                "https://slack.com/api/conversations.info",
                params={"channel": channel_id},
                headers=_slack_headers(),
                timeout=10,
            )
            channel_info = r.json()
            channel_name = channel_info.get("channel", {}).get("name", "")
        except Exception:
            pass

    # Only process #client-* channels
    if not channel_name.startswith("client-"):
        return JSONResponse({"status": "ignored_channel"})

    # Only process messages with an explicit delivery marker ("DELIVERED: System Name").
    # Keyword-based detection (done/live/shipped/etc.) was removed because it
    # triggered on voice transcripts and general chat messages.
    delivery_match = _EXPLICIT_DELIVERY_PREFIX.match(text.strip())
    if not delivery_match:
        return JSONResponse({"status": "ignored_no_explicit_marker"})

    client_name = _channel_to_client_name(channel_name)
    system_name = delivery_match.group(1).strip() or "System delivery"

    log.info(f"Slack delivery trigger: channel=#{channel_name} client={client_name!r} system={system_name!r}")

    background_tasks.add_task(
        _run_delivery_and_notify,
        client_name=client_name,
        system_name=system_name,
        description=text[:500],  # full message as description
        platform="",
        call_summary="",
        source="slack",
        slack_channel=channel_id,
        slack_thread_ts=thread_ts,
    )

    # Must respond quickly to avoid Slack retrying
    return JSONResponse({"status": "accepted"})


# ── Dev server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(env.get("PORT", "8000"))
    log.info(f"Starting Delivery API on port {port}")
    uvicorn.run("ops.slack_listener:app", host="0.0.0.0", port=port, reload=False)
