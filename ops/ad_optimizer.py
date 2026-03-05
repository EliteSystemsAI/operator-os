"""
ops/ad_optimizer.py — Daily ad performance analysis + approval workflow.

Called by APScheduler in main.py at 8:15am AEST.
Pulls Meta Ads data → Claude analysis → workflow_logs → Telegram approval.
"""
import os
import json
import logging
import asyncio
import requests

log = logging.getLogger(__name__)

META_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Fields to pull per ad set
AD_FIELDS = "name,spend,impressions,clicks,ctr,cpc,status"
DATE_PRESET = "last_7d"


def _fetch_meta_ad_performance() -> list:
    """Pull last 7 days of ad set performance from Meta Ads API."""
    url = f"https://graph.facebook.com/v20.0/act_{META_ACCOUNT_ID}/insights"
    params = {
        "access_token": META_TOKEN,
        "level": "adset",
        "fields": AD_FIELDS,
        "date_preset": DATE_PRESET,
        "limit": 50,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def _fetch_recent_ad_decisions() -> list:
    """Get last 5 ad workflow summaries for context."""
    try:
        from apps.command import supabase_memory as sm
        rows = sm._get(
            "workflow_logs",
            params={"workflow": "eq.ads", "order": "ran_at.desc", "limit": 5},
        )
        return [r.get("claude_analysis", "")[:300] for r in rows if r.get("claude_analysis")]
    except Exception as e:
        log.warning(f"Failed to fetch recent ad decisions: {e}")
        return []


def _analyse_with_claude(ad_data: list, context: dict, recent_decisions: list) -> str:
    """Send ad data to Claude for analysis. Returns analysis text."""
    from anthropic import Anthropic

    biz = context
    try:
        benchmarks = json.loads(biz.get("ad_benchmarks", "{}"))
    except (json.JSONDecodeError, TypeError):
        benchmarks = {}

    client = Anthropic(api_key=ANTHROPIC_KEY)

    system = (
        "You are an expert Meta Ads analyst for Elite Systems AI. "
        "Be direct, specific, and outcome-focused. No fluff. "
        f"Target benchmarks: CPL < ${benchmarks.get('target_cpl', 25)}, "
        f"ROAS > {benchmarks.get('target_roas', 3)}, "
        f"CTR > {float(benchmarks.get('target_ctr', 0.015)) * 100:.1f}%."
    )

    recent_ctx = ""
    if recent_decisions:
        recent_ctx = "\n\nRecent decisions made:\n" + "\n".join(f"- {d}" for d in recent_decisions)

    prompt = (
        f"Analyse this Meta Ads performance data for the last 7 days:\n\n"
        f"{json.dumps(ad_data, indent=2)}"
        f"{recent_ctx}\n\n"
        "Identify:\n"
        "1. Which ad sets are underperforming vs benchmarks (and why)\n"
        "2. Which are performing well (double down candidates)\n"
        "3. Specific recommended actions: budget shifts, pauses, copy changes\n\n"
        "Keep your response under 400 words. Be specific with numbers."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def run_ad_optimization(bot, chat_id: int) -> None:
    """
    Main entry point. Called by APScheduler via _job_ad_optimizer in main.py.
    Pulls data, analyses with Claude, logs to workflow_logs, sends Telegram approval message.
    """
    from apps.command import supabase_memory
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    log.info("Ad optimizer: starting daily run")

    if not META_TOKEN or not META_ACCOUNT_ID:
        log.warning("Ad optimizer: META_ACCESS_TOKEN or META_AD_ACCOUNT_ID not set — skipping")
        return

    try:
        ad_data = _fetch_meta_ad_performance()
    except Exception as e:
        log.error(f"Ad optimizer: failed to fetch Meta Ads data: {e}")

        async def _send_error():
            await bot.send_message(
                chat_id=chat_id,
                text=f"Ad optimizer: failed to fetch Meta Ads data.\n<code>{e}</code>",
            )

        asyncio.get_event_loop().run_until_complete(_send_error())
        return

    if not ad_data:
        log.info("Ad optimizer: no ad data returned (no active campaigns?)")
        return

    biz_context = supabase_memory.get_business_context()
    recent = _fetch_recent_ad_decisions()

    if ANTHROPIC_KEY:
        try:
            analysis = _analyse_with_claude(ad_data, biz_context, recent)
        except Exception as e:
            log.error(f"Ad optimizer: Claude analysis failed: {e}")
            analysis = f"Analysis failed: {e}"
    else:
        log.warning("Ad optimizer: ANTHROPIC_API_KEY not set — sending raw data summary")
        analysis = (
            f"Raw ad data ({len(ad_data)} ad sets). "
            "ANTHROPIC_API_KEY not configured — set it to enable Claude analysis."
        )

    action_summary = "Pending review — approve to authorise recommended changes."

    # Create workflow log (no telegram_message_id yet)
    log_id = supabase_memory.create_workflow_log(
        workflow="ads",
        input_data={"ad_sets": ad_data, "period": DATE_PRESET},
        claude_analysis=analysis,
        action_taken=action_summary,
    )

    # Build Telegram message
    msg_text = (
        f"<b>Daily Ad Report</b>\n\n"
        f"{analysis}\n\n"
        f"<i>Approve to authorise changes. Reject to skip.</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Approve", callback_data=f"approve_ads_{log_id}"),
        InlineKeyboardButton(text="Reject", callback_data=f"reject_ads_{log_id}"),
    ]])

    async def _send():
        sent = await bot.send_message(
            chat_id=chat_id,
            text=msg_text,
            reply_markup=keyboard,
        )
        if log_id:
            supabase_memory.update_workflow_telegram_message_id(log_id, sent.message_id)

    asyncio.get_event_loop().run_until_complete(_send())
    log.info(f"Ad optimizer: sent approval message for log_id={log_id}")
