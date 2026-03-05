"""OperatorOS — Telegram bot entry point.

Simplified boot sequence:
1. Load config from .env
2. Print boot banner with system checks
3. Clear stale Telegram polling lock
4. Wire up orchestrator, task registry, cost tracker
5. Register router and start polling
6. Start APScheduler with daily proactive jobs
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import requests as _requests

# Remove CLAUDECODE env var so Agent SDK can spawn Claude Code subprocesses.
# When developing inside a Claude Code session this var is set and blocks
# subprocess spawning — popping it here ensures clean agent launches.
os.environ.pop("CLAUDECODE", None)

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .bot import router, set_orchestrator
from .config import load_config
from .cost_tracker import CostTracker
from .orchestrator import Orchestrator
from apps.command import supabase_memory
from apps.command import topic_router


# ── Logging Setup ────────────────────────────────────────────────────────────

class _C:
    """ANSI color codes."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    CYAN    = "\033[36m"
    GREY    = "\033[90m"
    BRIGHT_CYAN   = "\033[96m"
    BRIGHT_GREEN  = "\033[92m"


class SystemCheck(NamedTuple):
    name: str
    passed: bool
    detail: str


def _setup_logging() -> None:
    """Configure root logger with timestamped format and suppress noisy libs."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        f"{_C.GREY}%(asctime)s{_C.RESET} | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for name in ("aiogram", "aiogram.dispatcher", "aiogram.event",
                 "httpx", "httpcore", "anthropic", "openai", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _print_banner() -> None:
    """Print the branded boot banner."""
    banner = f"""\
{_C.BRIGHT_CYAN}{_C.BOLD}
   \u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
   \u2551                                              \u2551
   \u2551       O P E R A T O R   O S                  \u2551
   \u2551       Telegram + Claude Code    v2.0          \u2551
   \u2551                                              \u2551
   \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d
{_C.RESET}"""
    print(banner, flush=True)


def _print_checks(checks: list[SystemCheck]) -> None:
    """Print system readiness checks with pass/fail indicators."""
    log = logging.getLogger("boot")
    for check in checks:
        if check.passed:
            log.info(f"{_C.GREEN}\u2713{_C.RESET} {check.name} {_C.GREY}({check.detail}){_C.RESET}")
        else:
            log.error(f"{_C.RED}\u2717{_C.RESET} {check.name} {_C.GREY}({check.detail}){_C.RESET}")


def _print_separator() -> None:
    """Print a visual separator line."""
    print(f"   {_C.GREY}{'─' * 46}{_C.RESET}", flush=True)


# ── Scheduled Job Functions ───────────────────────────────────────────────────

_DASHBOARD_URL = "https://internal.elitesystems.ai/operations"


def _supabase_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def _job_morning_ping(bot: Bot, group_id: int, workspace_dir: str, topic_id: int | None = None) -> None:
    """Daily 8:00am AEST — queue counts from Supabase + MRR delta."""
    log = logging.getLogger("scheduler")
    log.info("Morning ping starting")
    try:
        import json
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        headers = _supabase_headers(sb_key)

        # Tasks completed since midnight AEST
        aest = ZoneInfo("Australia/Brisbane")
        midnight_aest = datetime.now(aest).replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_utc = midnight_aest.astimezone(timezone.utc)

        done_r = _requests.get(
            f"{sb_url}/rest/v1/work_queue", headers=headers,
            params={"status": "eq.done", "completed_at": f"gte.{midnight_utc.isoformat()}", "limit": "100"},
            timeout=10,
        )
        ready_r = _requests.get(
            f"{sb_url}/rest/v1/work_queue", headers=headers,
            params={"status": "eq.ready", "limit": "100"}, timeout=10,
        )
        in_prog_r = _requests.get(
            f"{sb_url}/rest/v1/work_queue", headers=headers,
            params={"status": "eq.in_progress", "limit": "10"}, timeout=10,
        )
        top_r = _requests.get(
            f"{sb_url}/rest/v1/work_queue", headers=headers,
            params={"status": "eq.ready", "order": "priority.asc", "limit": "1"}, timeout=10,
        )

        done_count = len(done_r.json()) if done_r.ok else "?"
        ready_count = len(ready_r.json()) if ready_r.ok else "?"
        in_prog_count = len(in_prog_r.json()) if in_prog_r.ok else "?"
        top_tasks = top_r.json() if top_r.ok else []
        top_task = top_tasks[0]["title"] if top_tasks else "none"

        today_str = datetime.now(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m-%d")

        # MRR delta from revenue_history.json
        mrr_line = ""
        try:
            history_path = Path(workspace_dir) / "data" / "revenue_history.json"
            if history_path.exists():
                history = json.loads(history_path.read_text(encoding="utf-8"))
                if history:
                    sorted_dates = sorted(history.keys(), reverse=True)
                    latest_date = sorted_dates[0]
                    latest_mrr = history[latest_date].get("mrr", 0)
                    seven_days_ago = (
                        datetime.fromisoformat(latest_date) - timedelta(days=7)
                    ).strftime("%Y-%m-%d")
                    old_mrr = history.get(seven_days_ago, {}).get("mrr")
                    if old_mrr is not None:
                        delta = latest_mrr - old_mrr
                        arrow = "▲" if delta >= 0 else "▼"
                        sign = "+" if delta >= 0 else ""
                        mrr_line = f"\nMRR: ${latest_mrr:,.0f} ({arrow} {sign}${abs(delta):,.0f} vs 7d ago)"
                    else:
                        mrr_line = f"\nMRR: ${latest_mrr:,.0f}"
        except Exception:
            pass

        # Hours saved from time_savings_summary view
        hours_line = ""
        try:
            savings = supabase_memory.get_time_savings_total()
            if savings["total_systems"] > 0:
                hours_line = (
                    f"\nHours saved to date: {savings['total_hours_saved']:,.0f}h "
                    f"across {savings['total_clients']} client(s), "
                    f"{savings['total_systems']} system(s)"
                )
        except Exception:
            pass

        msg = (
            f"🟢 <b>OperatorOS alive — {today_str}</b>\n\n"
            f"Tasks completed overnight: {done_count}\n"
            f"Queue: {ready_count} ready, {in_prog_count} in_progress\n"
            f"Biggest constraint: <i>{top_task}</i>"
            f"{mrr_line}"
            f"{hours_line}\n\n"
            f"<a href='{_DASHBOARD_URL}'>View queue →</a>"
        )
    except Exception as e:
        log.exception("Morning ping failed")
        msg = f"⚠️ <b>Morning ping failed</b> — Supabase may be unreachable\nError: {e}"

    await bot.send_message(chat_id=group_id, text=msg, message_thread_id=topic_id)
    log.info("Morning ping sent")


async def _job_revenue_snapshot(workspace_dir: str) -> None:
    """Daily 8:01am AEST — save Stripe MRR to data/revenue_history.json."""
    import json
    from zoneinfo import ZoneInfo
    log = logging.getLogger("scheduler")
    log.info("Revenue snapshot starting")
    try:
        import stripe  # type: ignore
        stripe.api_key = os.getenv("STRIPE_API_KEY", "")
        if not stripe.api_key:
            log.warning("Revenue snapshot: STRIPE_API_KEY not set — skipping")
            return

        mrr_cents = 0.0
        active_count = 0
        for sub in stripe.Subscription.list(status="active", limit=100).auto_paging_iter():
            for item in sub["items"]["data"]:
                price = item["price"]
                qty = item.get("quantity") or 1
                amount = price.get("unit_amount") or 0  # cents
                interval = (price.get("recurring") or {}).get("interval", "month")
                monthly_cents = (amount / 12) if interval == "year" else amount
                mrr_cents += monthly_cents * qty
            active_count += 1

        mrr_dollars = round(mrr_cents / 100, 2)
        today = datetime.now(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m-%d")

        history_path = Path(workspace_dir) / "data" / "revenue_history.json"
        try:
            history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {}
        except Exception:
            history = {}

        history[today] = {"mrr": mrr_dollars, "active_subs": active_count}
        history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
        log.info("Revenue snapshot saved: $%.2f MRR (%d subs)", mrr_dollars, active_count)
    except Exception:
        log.exception("Revenue snapshot failed — skipping silently")


async def _job_business_state_update(workspace_dir: str) -> None:
    """Daily 8:05am AEST — write memory/business_state.md with real metrics."""
    import json
    from zoneinfo import ZoneInfo
    log = logging.getLogger("scheduler")
    log.info("Business state update starting")
    try:
        aest = ZoneInfo("Australia/Brisbane")
        today = datetime.now(aest).strftime("%Y-%m-%d")

        # MRR from revenue history
        mrr = "unknown"
        active_subs = "unknown"
        try:
            history_path = Path(workspace_dir) / "data" / "revenue_history.json"
            if history_path.exists():
                history = json.loads(history_path.read_text(encoding="utf-8"))
                entry = history.get(today, {})
                if entry:
                    mrr = f"${entry['mrr']:,.2f}"
                    active_subs = entry.get("active_subs", "unknown")
        except Exception:
            pass

        # Work queue from Supabase
        ready_count = "?"
        in_prog_count = "?"
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if sb_url and sb_key:
            try:
                headers = _supabase_headers(sb_key)
                ready_r = _requests.get(
                    f"{sb_url}/rest/v1/work_queue", headers=headers,
                    params={"status": "eq.ready", "limit": "100"}, timeout=10,
                )
                in_prog_r = _requests.get(
                    f"{sb_url}/rest/v1/work_queue", headers=headers,
                    params={"status": "eq.in_progress", "limit": "10"}, timeout=10,
                )
                ready_count = len(ready_r.json()) if ready_r.ok else "?"
                in_prog_count = len(in_prog_r.json()) if in_prog_r.ok else "?"
            except Exception:
                pass

        # Content drafts
        drafts_count = 0
        pending_drafts = 0
        manifest_path = Path(workspace_dir) / "data" / "content_drafts" / today / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                drafts = manifest.get("drafts", [])
                drafts_count = len(drafts)
                pending_drafts = sum(1 for d in drafts if d.get("status", "pending") == "pending")
            except Exception:
                pass

        # Client health snapshot
        active_clients = "unknown"
        at_risk = "unknown"
        try:
            client_path = Path(workspace_dir) / "data" / "client_health_snapshot.json"
            if client_path.exists():
                snapshot = json.loads(client_path.read_text(encoding="utf-8"))
                if snapshot:
                    active_clients = snapshot.get("active_clients", "unknown")
                    at_risk = snapshot.get("at_risk_count", "unknown")
        except Exception:
            pass

        lines = [
            f"# Business State — {today}",
            "_Auto-updated by OperatorOS at 8:05am AEST_",
            "",
            "## Revenue",
            f"- MRR: {mrr}",
            f"- Active subscriptions: {active_subs}",
            "",
            "## Work Queue (Supabase)",
            f"- Ready: {ready_count}",
            f"- In progress: {in_prog_count}",
            "",
            "## Content",
            f"- Drafts today: {drafts_count} ({pending_drafts} pending approval)",
            "",
            "## Clients",
            f"- Active clients: {active_clients}",
            f"- At-risk: {at_risk}",
        ]

        memory_dir = Path(workspace_dir) / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "business_state.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info("Business state written to memory/business_state.md")
    except Exception:
        log.exception("Business state update failed")


async def _job_client_health(bot: Bot, group_id: int, workspace_dir: str, topic_id: int | None = None) -> None:
    """Daily 9:00am AEST — query GHL for stalled opps and send Telegram summary."""
    import json
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    log = logging.getLogger("scheduler")
    log.info("Client health check starting")
    try:
        ghl_key = os.getenv("GHL_API_KEY", "")
        ghl_location = os.getenv("GHL_LOCATION_ID", "")
        if not ghl_key or not ghl_location:
            log.warning("Client health: GHL_API_KEY or GHL_LOCATION_ID not set")
            await bot.send_message(
                chat_id=group_id,
                text="⚠️ <b>Client Health</b> — GHL credentials not configured.",
                message_thread_id=topic_id,
            )
            return

        headers = {
            "Authorization": f"Bearer {ghl_key}",
            "Version": "2021-07-28",
        }

        r = _requests.get(
            "https://services.leadconnectorhq.com/opportunities/search",
            headers=headers,
            params={"location_id": ghl_location, "status": "open", "limit": 100},
            timeout=15,
        )

        if not r.ok:
            log.error("GHL opportunities fetch failed: %s %s", r.status_code, r.text[:200])
            await bot.send_message(
                chat_id=group_id,
                text=f"⚠️ <b>Client Health</b> — GHL API error: {r.status_code}",
                message_thread_id=topic_id,
            )
            return

        opps = r.json().get("opportunities", [])
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        at_risk = []
        for opp in opps:
            updated_str = opp.get("updatedAt") or opp.get("lastActivityAt", "")
            if not updated_str:
                continue
            try:
                updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if updated < seven_days_ago:
                    days_stalled = (now - updated).days
                    contact = opp.get("contact") or {}
                    at_risk.append({
                        "name": contact.get("name") or opp.get("name", "Unknown"),
                        "stage": opp.get("pipelineStageName") or opp.get("pipelineStageId", "Unknown stage"),
                        "days_stalled": days_stalled,
                        "value": opp.get("monetaryValue") or 0,
                    })
            except Exception:
                continue

        at_risk.sort(key=lambda x: x["days_stalled"], reverse=True)

        today_str = datetime.now(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m-%d")
        snapshot = {
            "updated_at": now.isoformat(),
            "date": today_str,
            "active_clients": len(opps),
            "at_risk_count": len(at_risk),
            "at_risk": at_risk[:10],
        }
        client_path = Path(workspace_dir) / "data" / "client_health_snapshot.json"
        client_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

        lines = [f"👥 <b>Client Health — {today_str}</b>", ""]
        lines.append(f"Open pipeline: {len(opps)} opps")
        lines.append(f"At-risk (7+ days no update): {len(at_risk)}")

        if at_risk:
            lines.append("")
            lines.append("<b>Stalled opps:</b>")
            for opp in at_risk[:5]:
                val = f"${opp['value']:,.0f}" if opp["value"] else "no value set"
                lines.append(
                    f"• {opp['name']} — {opp['stage']} ({opp['days_stalled']}d stalled, {val})"
                )
        else:
            lines.append("")
            lines.append("✅ No stalled opps — pipeline healthy")

        await bot.send_message(chat_id=group_id, text="\n".join(lines), message_thread_id=topic_id)
        log.info("Client health sent: %d open, %d at-risk", len(opps), len(at_risk))
    except Exception as e:
        log.exception("Client health check failed")
        await bot.send_message(
            chat_id=group_id,
            text=f"⚠️ <b>Client Health</b> — check failed: {e}",
            message_thread_id=topic_id,
        )


async def _job_content_digest(bot: Bot, group_id: int, workspace_dir: str, topic_id: int | None = None) -> None:
    """Daily 8:30am AEST — send today's content drafts to Telegram with approval buttons."""
    import json
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    log = logging.getLogger("scheduler")
    log.info("Content digest starting")

    aest = ZoneInfo("Australia/Brisbane")
    today = datetime.now(aest).strftime("%Y-%m-%d")
    manifest_path = Path(workspace_dir) / "data" / "content_drafts" / today / "manifest.json"

    # Build cadence header from ig_today.json
    cadence_line = ""
    best_format_line = ""
    try:
        ig_today_path = Path(workspace_dir) / "data" / "ig_today.json"
        if ig_today_path.exists():
            ig_data = json.loads(ig_today_path.read_text(encoding="utf-8"))
            posted = ig_data.get("posted", {})
            reel_ok = "✅" if posted.get("reel", 0) > 0 else "❌"
            carousel_ok = "✅" if posted.get("carousel", 0) > 0 else "❌"
            quote_ok = "✅" if posted.get("quote", 0) > 0 else "❌"
            total = sum(posted.values())
            cadence_line = f"📊 Posted today: {total}/3 — reel {reel_ok} carousel {carousel_ok} quote {quote_ok}\n"
    except Exception:
        pass
    try:
        top_path = Path(workspace_dir) / "data" / "top_performing_content.json"
        if top_path.exists():
            top_data = json.loads(top_path.read_text(encoding="utf-8"))
            insights = top_data.get("insights", {})
            best_fmt = insights.get("best_format", "")
            avg_eng = insights.get("avg_engagement_rate", "")
            if best_fmt and avg_eng:
                best_format_line = f"🏆 Best format this week: {best_fmt} at {avg_eng}% avg engagement\n"
    except Exception:
        pass

    if cadence_line or best_format_line:
        await bot.send_message(
            chat_id=group_id,
            text=(cadence_line + best_format_line).strip(),
        )

    if not manifest_path.exists():
        await bot.send_message(
            chat_id=group_id,
            text=(
                f"📭 <b>No content drafts for {today}</b>\n"
                "The autopilot may not have run yet. Check <code>pm2 logs elite-content-autopilot</code>"
            ),
            message_thread_id=topic_id,
        )
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        drafts = manifest.get("drafts", [])
    except Exception as e:
        await bot.send_message(chat_id=group_id, text=f"⚠️ Failed to read content manifest: {e}", message_thread_id=topic_id)
        return

    if not drafts:
        await bot.send_message(chat_id=group_id, text=f"📭 No drafts in manifest for {today}.", message_thread_id=topic_id)
        return

    await bot.send_message(
        chat_id=group_id,
        text=f"📝 <b>Content Drafts — {today}</b>\n{len(drafts)} draft(s) ready for approval:",
        message_thread_id=topic_id,
    )

    for i, draft in enumerate(drafts, 1):
        caption = draft.get("caption", draft.get("content", draft.get("hook", "")))[:600]
        platform = draft.get("platform", draft.get("type", "IG"))
        funnel = draft.get("funnel_stage", draft.get("funnel", "TOFU"))
        post_type = draft.get("type", "reel")

        # Log each draft to workflow_logs
        log_id = supabase_memory.create_workflow_log(
            workflow="content",
            input_data=draft,
            claude_analysis=f"[{funnel}] {platform} {post_type}",
            action_taken="Schedule via GHL on approval.",
        )

        msg_text = (
            f"<b>Draft {i}/{len(drafts)}</b>  [{funnel}] {platform}\n\n"
            f"{caption}"
            f"\n\n<i>Approve to schedule, reject to discard.</i>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Approve", callback_data=f"approve_content_{log_id}"),
            InlineKeyboardButton(text="Reject", callback_data=f"reject_content_{log_id}"),
        ]])

        sent = await bot.send_message(
            chat_id=group_id,
            text=msg_text,
            reply_markup=keyboard,
            message_thread_id=topic_id,
        )

        if log_id:
            supabase_memory.update_workflow_telegram_message_id(log_id, sent.message_id)

    log.info("Content digest sent for %s (%d drafts with approval buttons)", today, len(drafts))


async def _job_bottleneck_hunter(bot: Bot, group_id: int, topic_id: int | None = None) -> None:
    """Daily 9:05am AEST — queue a bottleneck-finding task in Supabase."""
    log = logging.getLogger("scheduler")
    log.info("Bottleneck Hunter: queuing task")
    try:
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        headers = {**_supabase_headers(sb_key), "Prefer": "return=representation"}

        description = (
            "You are the Bottleneck Hunter. Your job: identify the single biggest constraint "
            "on Elite Systems AI's revenue growth today and suggest the fix.\n\n"
            "Review in this order:\n"
            "1. GHL pipeline — what's stalled? What's the most valuable opp at risk?\n"
            "2. Meta ad performance — are any campaigns throttling lead flow?\n"
            "3. Stripe MRR — any trend down? Failed payments?\n"
            "4. Work queue — any tasks blocking others?\n"
            "5. Client health — any client at risk of churn?\n\n"
            "Output format:\n"
            "🎯 Today's bottleneck: [X]\n"
            "Root cause: [Y]\n"
            "Suggested fix: [Z]\n"
            "Queued for execution: [Yes/No — if yes, queue it]\n\n"
            "Send result via Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_GROUP_ID in .env)."
        )
        r = _requests.post(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            json={
                "title": "Bottleneck Hunter — find and fix today's biggest constraint",
                "description": description,
                "status": "ready",
                "priority": 2,
                "source": "telegram",
            },
            timeout=10,
        )
        r.raise_for_status()
        await bot.send_message(
            chat_id=group_id,
            text="🎯 <b>Bottleneck Hunter queued</b> — scanning for today's biggest constraint.",
            message_thread_id=topic_id,
        )
        log.info("Bottleneck Hunter task queued")
    except Exception as e:
        log.exception("Bottleneck Hunter failed to queue")
        await bot.send_message(
            chat_id=group_id,
            text=f"⚠️ Bottleneck Hunter failed to queue: {e}",
            message_thread_id=topic_id,
        )


async def _surface_pending_approvals(bot: Bot, group_id: int, topic_id: int | None = None) -> None:
    """On startup, re-surface any unapproved workflow_logs from previous sessions."""
    pending = supabase_memory.get_pending_approvals()
    if not pending:
        return
    lines = [f"⏳ *{len(pending)} pending approval(s) from last session:*\n"]
    for p in pending:
        wf = p["workflow"].upper()
        ran = p["ran_at"][:16].replace("T", " ")
        preview = (p.get("action_taken") or "")[:120]
        lines.append(f"• [{wf}] {ran} — {preview}")
    lines.append("\n_Reply with the workflow type to review and approve._")
    await bot.send_message(chat_id=group_id, text="\n".join(lines), parse_mode="Markdown", message_thread_id=topic_id)


async def _job_ig_snapshot(workspace_dir: str) -> None:
    """Daily 7:00am AEST — fetch IG media, count today's posts by type, update ig_today.json."""
    import json
    from zoneinfo import ZoneInfo
    log = logging.getLogger("scheduler")
    log.info("IG snapshot starting")
    try:
        ig_token = os.getenv("IG_ACCESS_TOKEN", "")
        ig_account = os.getenv("IG_ACCOUNT_ID", "")
        if not ig_token or not ig_account:
            log.warning("IG snapshot: IG_ACCESS_TOKEN or IG_ACCOUNT_ID not set — skipping")
            return

        aest = ZoneInfo("Australia/Brisbane")
        today_str = datetime.now(aest).strftime("%Y-%m-%d")
        today_date = datetime.now(aest).date()

        # Fetch last 7 days of media
        from datetime import timedelta
        since_ts = int((datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) -
                        timedelta(days=7)).timestamp())
        r = _requests.get(
            f"https://graph.facebook.com/v20.0/{ig_account}/media",
            params={
                "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink",
                "since": since_ts,
                "limit": 50,
                "access_token": ig_token,
            },
            timeout=15,
        )
        posts = r.json().get("data", []) if r.ok else []

        # Count today's posts by type
        today_counts: dict[str, int] = {"reel": 0, "carousel": 0, "quote": 0}
        today_posts = []
        for post in posts:
            ts_str = post.get("timestamp", "")
            if not ts_str:
                continue
            try:
                post_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                post_date = post_dt.astimezone(aest).date()
                if post_date != today_date:
                    continue
            except Exception:
                continue

            mtype = post.get("media_type", "IMAGE").upper()
            if mtype == "VIDEO":
                today_counts["reel"] += 1
            elif mtype == "CAROUSEL_ALBUM":
                today_counts["carousel"] += 1
            else:
                today_counts["quote"] += 1

            today_posts.append({
                "id": post["id"],
                "type": mtype,
                "caption_preview": (post.get("caption") or "")[:80],
                "permalink": post.get("permalink", ""),
                "likes": post.get("like_count", 0),
                "comments": post.get("comments_count", 0),
            })

        ig_today = {
            "date": today_str,
            "posted": today_counts,
            "posts": today_posts,
        }
        ig_today_path = Path(workspace_dir) / "data" / "ig_today.json"
        ig_today_path.write_text(json.dumps(ig_today, indent=2), encoding="utf-8")
        log.info("IG snapshot done: %s", today_counts)

        # Also update top_performing_content.json with fresh engagement data
        top_file = Path(workspace_dir) / "data" / "top_performing_content.json"
        try:
            existing = json.loads(top_file.read_text(encoding="utf-8")) if top_file.exists() else {}
            existing["last_updated"] = today_str
            existing["_note"] = "Updated by _job_ig_snapshot; run instagram_analytics.py for full refresh"
            top_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            pass

    except Exception:
        log.exception("IG snapshot failed")


async def _job_content_research_and_draft(bot: Bot, group_id: int) -> None:
    """Daily 7:30am AEST — queue a content research + draft agent task to Supabase."""
    log = logging.getLogger("scheduler")
    log.info("Content research and draft: queuing task")
    try:
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        headers = {**_supabase_headers(sb_key), "Prefer": "return=representation"}

        description = (
            "Content research and draft. Do this in order:\n\n"
            "1. Read data/ig_today.json. Target: 1 reel + 1 carousel + 1 quote/winning format per day.\n"
            "   Identify which format is MISSING from today's count.\n\n"
            "2. Read data/top_performing_content.json. Note the top hook patterns and best performing format.\n\n"
            "3. Read knowledge/personal_anecdotes.md. Pick one anecdote that could pair with a content angle.\n\n"
            "4. Read knowledge/content_strategy.md. Confirm which pillar and funnel stage to hit for balance.\n\n"
            "5. Call Slack API: GET https://slack.com/api/conversations.list with the SLACK_BOT_TOKEN env var "
            "to find the EliteAnalyst bot's channel. Then GET /conversations.history for that channel. "
            "Read last 5 messages from EliteAnalyst for business insights.\n\n"
            "6. WebSearch: top AI news last 24 hours relevant to coaches, consultants, creators. "
            "Pick the 1 most relevant story.\n\n"
            "7. Generate the MISSING format post:\n"
            "   - Hook using a winning pattern from step 2\n"
            "   - Full script/copy in Zac's brand voice (read CLAUDE.md for voice rules)\n"
            "   - Self-score quality. If below 8/10, rewrite once.\n\n"
            "8. Send this exact message to Telegram group (TELEGRAM_GROUP_ID env var):\n"
            "   📲 Content draft — [FORMAT] | [PILLAR] | [TOFU/MOFU/BOFU]\n\n"
            "   Hook: [hook]\n\n"
            "   [Full content]\n\n"
            "   ─────────────\n"
            "   Research basis: [1 sentence on what insight/angle this came from]\n"
            "   ✅ approve | ✏️ edit [your notes] | ❌ skip\n\n"
            "When Zac replies 'approve':\n"
            "- Carousel / Quote → schedule to GHL Social Planner for [YOUR_INSTAGRAM_HANDLE] IG "
            "(accountId: 6683c5112360e3afa4416933_q3XoUHEaMYRwhdaMMJvS_17841436875055229). "
            "Use GHL_API_KEY + GHL_LOCATION_ID from .env. Next available scheduling slot.\n"
            "- Reel → reply: '🎬 Film brief: [hook]. Key points: [bullet points]. Reply with the video when filmed.'\n"
        )

        r = _requests.post(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            json={
                "title": "Content Research + Draft — generate missing format post",
                "description": description,
                "status": "ready",
                "priority": 1,
                "source": "scheduler",
            },
            timeout=10,
        )
        r.raise_for_status()
        log.info("Content research + draft task queued")
    except Exception:
        log.exception("Content research + draft failed to queue")


async def _job_meta_ads_report(bot: Bot, group_id: int, workspace_dir: str) -> None:
    """Daily 8:15am AEST — fetch Meta campaign performance and send Telegram report."""
    import json
    from zoneinfo import ZoneInfo
    log = logging.getLogger("scheduler")
    log.info("Meta ads report starting")
    try:
        meta_token = os.getenv("META_ACCESS_TOKEN", "")
        meta_account = os.getenv("META_AD_ACCOUNT_ID", "")
        if not meta_token or not meta_account:
            log.warning("Meta ads report: META_ACCESS_TOKEN or META_AD_ACCOUNT_ID not set — skipping")
            return

        today_str = datetime.now(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m-%d")

        r = _requests.get(
            f"https://graph.facebook.com/v20.0/act_{meta_account}/campaigns",
            params={
                "fields": "name,status,insights{spend,ctr,cpc,cpm,reach,impressions,actions}",
                "date_preset": "today",
                "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE"]}]',
                "access_token": meta_token,
                "limit": 50,
            },
            timeout=20,
        )
        if not r.ok:
            log.error("Meta campaigns fetch failed: %s", r.status_code)
            await bot.send_message(
                chat_id=group_id,
                text=f"⚠️ <b>Meta Ads</b> — API error {r.status_code}. Check META_ACCESS_TOKEN.",
            )
            return

        campaigns = r.json().get("data", [])
        if not campaigns:
            await bot.send_message(
                chat_id=group_id,
                text=f"📊 <b>Meta Ads — {today_str}</b>\nNo active campaigns today.",
            )
            return

        lines = [f"📊 <b>Meta Ads — {today_str}</b>", "━━━━━━━━━━━━━━━━━━━━━"]
        total_spend = 0.0
        best_name, best_ctr = "", 0.0
        ad_records = []

        for camp in campaigns:
            name = camp.get("name", "Unknown")
            insights_block = camp.get("insights", {})
            ins_data = insights_block.get("data", []) if isinstance(insights_block, dict) else []
            if not ins_data:
                lines.append(f"• {name} — no data today")
                continue

            d = ins_data[0]
            spend = float(d.get("spend", 0))
            ctr = float(d.get("ctr", 0))
            cpc = float(d.get("cpc", 0))
            cpm = float(d.get("cpm", 0))
            total_spend += spend

            # Count conversions
            actions = d.get("actions", [])
            conversions = sum(
                int(a.get("value", 0)) for a in (actions or [])
                if a.get("action_type") in ("purchase", "lead", "complete_registration")
            )

            # Flags
            flags = []
            if ctr < 1.8 and float(d.get("impressions", 0)) > 200:
                flags.append("⚠️ Low CTR")
            if cpm > 15:
                flags.append("⚠️ High CPM")
            if spend > 30 and conversions == 0:
                flags.append("❌ No conversions")

            flag_str = " " + " ".join(flags) if flags else ""
            lines.append(
                f"• {name} — ${spend:.2f} | CTR {ctr:.1f}% | CPC ${cpc:.2f} | CPM ${cpm:.2f}{flag_str}"
            )

            if ctr > best_ctr:
                best_ctr = ctr
                best_name = name

            ad_records.append({
                "campaign": name,
                "spend": spend,
                "ctr": ctr,
                "cpc": cpc,
                "cpm": cpm,
                "conversions": conversions,
                "flags": flags,
            })

        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💰 Total today: ${total_spend:.2f} AUD")
        if best_name:
            lines.append(f"🏆 Best: {best_name} — CTR {best_ctr:.1f}%")

        await bot.send_message(chat_id=group_id, text="\n".join(lines))
        log.info("Meta ads report sent: %d campaigns, $%.2f total", len(campaigns), total_spend)

        # Save to data/ad_performance.json
        ad_path = Path(workspace_dir) / "data" / "ad_performance.json"
        try:
            existing = json.loads(ad_path.read_text(encoding="utf-8")) if ad_path.exists() else {}
        except Exception:
            existing = {}
        existing[today_str] = {"campaigns": ad_records, "total_spend": total_spend}
        ad_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    except Exception as e:
        log.exception("Meta ads report failed")
        await bot.send_message(
            chat_id=group_id,
            text=f"⚠️ <b>Meta Ads Report</b> — failed: {e}",
        )


async def _job_ad_optimizer(bot: Bot, group_id: int) -> None:
    """Daily ad performance analysis and Telegram approval request."""
    try:
        from ops.ad_optimizer import run_ad_optimization
        run_ad_optimization(bot, group_id)
    except Exception as e:
        logging.getLogger(__name__).error(f"ad_optimizer job failed: {e}")


async def _job_self_anneal_scan(
    bot: Bot, group_id: int, workspace_dir: str, self_anneal_thread_id: int | None
) -> None:
    """Daily 6:30am AEST — proactive capability gap scan."""
    from .self_annealing import propose_build_with_config
    log = logging.getLogger("scheduler")
    log.info("Self-anneal scan starting")
    try:
        await propose_build_with_config(
            bot=bot,
            group_id=group_id,
            workspace_dir=workspace_dir,
            self_anneal_thread_id=self_anneal_thread_id,
            gap_description=None,
        )
    except Exception:
        log.exception("Self-anneal scan failed")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    # ── Boot banner ───────────────────────────────────────────────────────
    _setup_logging()
    _print_banner()

    boot = logging.getLogger("boot")
    system = logging.getLogger("system")

    # ── Load configuration ────────────────────────────────────────────────
    boot.info("Loading configuration...")
    config = load_config()
    config.log_dir.mkdir(parents=True, exist_ok=True)

    boot.info(
        "Model: %s  |  Budget: $%.2f/msg  |  Max turns: %d",
        config.general_agent_model, config.general_agent_max_budget, config.general_agent_max_turns,
    )
    _print_separator()

    # ── System checks ─────────────────────────────────────────────────────
    checks: list[SystemCheck] = []

    # Config loaded
    checks.append(SystemCheck(
        "Config loaded", True, f"model: {config.general_agent_model}",
    ))

    # Log directory
    checks.append(SystemCheck("Log directory", True, str(config.log_dir)))

    # ── Initialize bot ────────────────────────────────────────────────────
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Clear any stale webhook or getUpdates session before starting polling.
    # delete_webhook removes any webhook. A single get_updates(timeout=0) call
    # immediately claims the bot session without holding a server-side long-poll
    # open, which prevents 409 Conflict on start_polling().
    boot.info("Clearing webhook and claiming session...")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    try:
        await bot.get_updates(offset=-1, timeout=0)
    except Exception:
        pass

    # Verify Telegram connection
    try:
        me = await bot.get_me()
        checks.append(SystemCheck("Telegram", True, f"@{me.username}"))
    except Exception as e:
        checks.append(SystemCheck("Telegram", False, str(e)[:60]))

    _print_checks(checks)
    _print_separator()

    # Check for failures
    failed = [c for c in checks if not c.passed]
    if failed:
        boot.warning("Some checks failed — bot will start anyway")

    # ── Wire up components ────────────────────────────────────────────────
    cost_tracker = CostTracker(config.log_dir)
    orchestrator = Orchestrator(bot, config, cost_tracker)
    set_orchestrator(orchestrator, config)

    dp = Dispatcher()
    dp.include_router(router)

    # ── APScheduler setup ─────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone="Australia/Brisbane")

    # 6:30am — Self-anneal scan (proactive capability gap proposal)
    scheduler.add_job(
        _job_self_anneal_scan, "cron", hour=6, minute=30,
        args=[bot, config.group_id, config.workspace_dir, config.self_anneal_thread_id],
    )
    # 7:00am — IG snapshot (silent: updates ig_today.json + top_performing_content.json)
    scheduler.add_job(
        _job_ig_snapshot, "cron", hour=7, minute=0,
        args=[config.workspace_dir],
    )
    # 7:30am — Content research + draft (queues Supabase agent task)
    scheduler.add_job(
        _job_content_research_and_draft, "cron", hour=7, minute=30,
        args=[bot, config.group_id],
    )
    # 8:00am — Morning ping (queue counts + MRR delta)
    scheduler.add_job(
        _job_morning_ping, "cron", hour=8, minute=0,
        args=[bot, config.group_id, config.workspace_dir, topic_router.route_for("morning")],
    )
    # 8:01am — Revenue snapshot (Stripe MRR → revenue_history.json)
    scheduler.add_job(
        _job_revenue_snapshot, "cron", hour=8, minute=1,
        args=[config.workspace_dir],
    )
    # 8:05am — Business state update (writes memory/business_state.md)
    scheduler.add_job(
        _job_business_state_update, "cron", hour=8, minute=5,
        args=[config.workspace_dir],
    )
    # 8:15am — Meta ads report (daily campaign performance to Telegram)
    scheduler.add_job(
        _job_meta_ads_report, "cron", hour=8, minute=15,
        args=[bot, config.group_id, config.workspace_dir],
    )
    # 8:30am — Content digest (today's drafts + cadence gap)
    scheduler.add_job(
        _job_content_digest, "cron", hour=8, minute=30,
        args=[bot, config.group_id, config.workspace_dir, topic_router.route_for("content")],
    )
    # 9:00am — Client health push (GHL pipeline summary)
    scheduler.add_job(
        _job_client_health, "cron", hour=9, minute=0,
        args=[bot, config.group_id, config.workspace_dir, topic_router.route_for("clients")],
    )
    # 9:05am — Bottleneck hunter (queues Supabase task)
    scheduler.add_job(
        _job_bottleneck_hunter, "cron", hour=9, minute=5,
        args=[bot, config.group_id, topic_router.route_for("morning")],
    )

    @dp.startup()
    async def on_startup() -> None:
        system.info(
            f"{_C.BRIGHT_GREEN}{_C.BOLD}Online \u2014 polling for messages{_C.RESET}"
        )
        _print_separator()

        # ── Supabase memory init ──────────────────────────────────────────
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        supabase_memory.init(sb_url, sb_key)

        # Load auto-discovered Telegram topics from Supabase
        known_topics = topic_router.load_topics_from_supabase()
        if known_topics:
            system.info(f"Loaded {len(known_topics)} Telegram topics: {list(known_topics.values())}")
        else:
            system.info("No Telegram topics cached yet — will auto-discover from incoming messages")

        # Load long-term business context from Supabase
        biz_context = supabase_memory.get_business_context()
        if biz_context:
            system.info(f"Loaded {len(biz_context)} business context keys from Supabase")
        else:
            system.warning("No business context found in Supabase — run scripts/seed_business_context.py")

        # Store globally so worker.py can access it via supabase_memory._BIZ_CONTEXT_CACHE
        supabase_memory._BIZ_CONTEXT_CACHE = biz_context

        scheduler.start()
        system.info("APScheduler started — 10 jobs scheduled (6:30, 7:00, 7:30, 8:00, 8:01, 8:05, 8:15, 8:30, 9:00, 9:05 AEST)")
        try:
            await bot.send_message(
                chat_id=config.group_id,
                text="OperatorOS is online. What do you need?",
                message_thread_id=config.topic_general,
            )
        except Exception:
            system.warning("Could not send startup message to Telegram")

        # Surface any workflow approvals that were pending when the bot last shut down
        try:
            await _surface_pending_approvals(bot, config.group_id, config.topic_general)
        except Exception as e:
            system.warning(f"Could not surface pending approvals: {e}")

    @dp.shutdown()
    async def on_shutdown() -> None:
        system.info("Shutting down...")
        if scheduler.running:
            scheduler.shutdown(wait=False)

    await dp.start_polling(bot)


if __name__ == "__main__":
    _setup_logging()
    asyncio.run(main())
