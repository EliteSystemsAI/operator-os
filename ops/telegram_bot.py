#!/usr/bin/env python3
"""
Elite Systems AI — Always-On Telegram Bot

Runs as a Railway worker process (long polling — no webhook needed).

Commands:
  /digest                      → Full weekly ops digest (inline)
  /clients                     → Client health check across all GHL sub-accounts
  /leads                       → GHL pipeline snapshot
  /delivered [client] [system] → Log a delivered system + get next suggestion
  /client [name]               → Full client snapshot (systems + last suggestion)
  /status                      → Instant system snapshot
  /kill                        → Emergency stop worker + clear queue
  /start                       → Restart worker on Mac Mini
  /version                     → List recent brain versions
  /help                        → List available commands

Scheduled jobs:
  Daily 8am AEST  → Morning system ping (health + overnight summary)
  Daily 9am AEST  → Client health check (sends alert only if 🔴 clients found)
  Monday 8am AEST → Full weekly ops digest (always fires)
"""

import asyncio
import logging
import re as _re
import requests as _requests
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── Path setup so sibling modules resolve correctly ───────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Import business logic from existing modules (no duplication) ──────────────

from ops.weekly_ops_digest import (  # noqa: E402
    AEST,
    TELEGRAM_CHAT_ID,
    TELEGRAM_TOKEN,
    build_digest,
    get_content_status,
    get_new_leads,
    get_pipeline_data,
    get_stripe_data,
    send_telegram,
    write_to_scorecard,
)
from ops.client_health_check import run_health_check  # noqa: E402
from ops.client_deliveries import process_delivery, get_client_snapshot  # noqa: E402

# ── Work Queue helpers ────────────────────────────────────────────────────────

_DASHBOARD_URL = "https://internal.elitesystems.ai/operations"

# Conversation history per chat_id — keeps context across messages within a session
_CHAT_HISTORY: dict[int, list[dict]] = {}
_MAX_HISTORY = 20  # max messages to keep (10 exchanges)


def _wq_headers() -> dict:
    from ops.weekly_ops_digest import load_env as _load_env
    e = _load_env()
    key = e.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _wq_url() -> str:
    from ops.weekly_ops_digest import load_env as _load_env
    return _load_env().get("SUPABASE_URL", "")


def _load_env_data() -> dict:
    from ops.weekly_ops_digest import load_env as _load_env
    return _load_env()


def _add_to_queue(title: str, priority: int = 3, description: str = "") -> str:
    """Add task to work_queue. Returns task id or raises."""
    headers = {**_wq_headers(), "Prefer": "return=representation"}
    r = _requests.post(
        f"{_wq_url()}/rest/v1/work_queue",
        headers=headers,
        json={
            "title": title,
            "description": description,
            "status": "ready",
            "priority": priority,
            "source": "telegram",
        },
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0]["id"] if rows else "unknown"


def _fetch_queue() -> list[dict]:
    """Fetch active (non-done) tasks ordered by priority."""
    r = _requests.get(
        f"{_wq_url()}/rest/v1/work_queue",
        headers=_wq_headers(),
        params={
            "status": "in.(backlog,ready,in_progress)",
            "order": "priority.asc,created_at.asc",
            "limit": "15",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _claude_chat(chat_id: int, user_message: str) -> tuple[str, bool, str | None]:
    """
    Send message to Claude API with conversation history. Returns (reply_text, should_queue, task_title_or_None).
    Claude decides whether to answer directly or suggest queuing as a task.
    """
    from ops.weekly_ops_digest import load_env as _load_env
    api_key = _load_env().get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ ANTHROPIC_API_KEY not set in .env", False, None

    system = """You are the Elite Systems AI Operator Bot — Zac's always-on AI assistant running on a Mac Mini.

[YOUR_NAME] runs Elite Systems AI, a fractional CTO + AI automation agency on the Gold Coast, Australia.
He helps coaches, consultants, and service businesses ($200K-$2M/year) build AI systems.

You have two modes:
1. ANSWER: Answer the question directly (for questions, status checks, advice, analysis)
2. QUEUE: If the message is a task that requires building/coding/research that takes more than a minute, respond with JSON: {"queue": true, "title": "brief task title", "reply": "your message to Zac"}

Rules:
- Be direct, no fluff. Zac's brand voice is punchy and outcome-focused.
- NEVER say "dive into", "game-changer", "leverage", "it's that simple"
- Timezone is AEST (Gold Coast, QLD — no daylight saving)
- For coding/building tasks, prefer QUEUE mode so the Mac Mini worker handles it
- For questions, analysis, advice — answer directly in ANSWER mode
- Keep direct answers under 300 words unless detail is genuinely needed
- You have memory of this conversation — use prior messages for context"""

    # Build messages list with history
    history = _CHAT_HISTORY.get(chat_id, [])
    messages = history + [{"role": "user", "content": user_message}]

    r = _requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "system": system,
            "messages": messages,
        },
        timeout=30,
    )
    r.raise_for_status()
    content = r.json()["content"][0]["text"]

    # Update history — append user message + assistant reply, trim to max
    updated = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": content},
    ]
    _CHAT_HISTORY[chat_id] = updated[-_MAX_HISTORY:]

    # Check if Claude wants to queue a task
    import json as _json
    try:
        json_match = _re.search(r'\{[^}]*"queue"\s*:\s*true[^}]*\}', content, _re.DOTALL)
        if json_match:
            parsed = _json.loads(json_match.group())
            if parsed.get("queue"):
                return parsed.get("reply", "Queuing that now..."), True, parsed.get("title", user_message[:80])
    except Exception:
        pass

    return content, False, None


# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Sync helpers (wrapped with asyncio.to_thread to stay non-blocking) ────────


def _get_digest_sync() -> str:
    """Pull all business data and assemble the weekly ops digest string."""
    stripe = get_stripe_data()
    pipeline = get_pipeline_data()
    leads = get_new_leads()
    content = get_content_status()
    write_to_scorecard(stripe, pipeline, leads)
    return build_digest(stripe, pipeline, leads, content)


def _get_pipeline_snapshot_sync() -> str:
    """Minimal pipeline snapshot for /leads."""
    pipeline = get_pipeline_data()
    leads = get_new_leads()
    lines = [
        "📥 *GHL PIPELINE SNAPSHOT*",
        "",
        f"Open opps:     {pipeline['total_open']}",
        f"Total value:   ${pipeline['total_value']:,}",
        f"New this week: {pipeline['new_this_week']}",
        f"New leads:     {leads}",
    ]
    return "\n".join(lines)


# ── Command handlers ──────────────────────────────────────────────────────────


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /run [task]   → priority 3 (normal)
    /run! [task]  → priority 2 (high)
    /run!! [task] → priority 1 (critical)
    """
    raw_cmd = (update.message.text or "").split()[0].lstrip("/")
    if raw_cmd == "run!!":
        priority, badge = 1, "🔴 Critical"
    elif raw_cmd in ("run!", "run_"):  # telegram normalises !
        priority, badge = 2, "🟠 High"
    else:
        priority, badge = 3, "⚪ Normal"

    task_text = " ".join(context.args) if context.args else ""
    if not task_text:
        await update.message.reply_text(
            "Usage: `/run [task description]`\nExample: `/run Build a Stripe MRR report`",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("⏳ Queuing...", parse_mode="Markdown")
    try:
        task_id = await asyncio.to_thread(_add_to_queue, task_text, priority)
        await update.message.reply_text(
            f"✅ *Queued* ({badge})\n_{task_text}_\n\nWorker picks it up within 30s.\n[View queue →]({_DASHBOARD_URL})",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to queue: {e}")
        log.exception("cmd_run error")


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current backlog and in-progress tasks."""
    try:
        tasks = await asyncio.to_thread(_fetch_queue)
    except Exception as e:
        await update.message.reply_text(f"❌ Queue fetch failed: {e}")
        return

    if not tasks:
        await update.message.reply_text(
            f"📭 *Queue is empty*\nUse `/run [task]` to add work.\n[Dashboard →]({_DASHBOARD_URL})",
            parse_mode="Markdown",
        )
        return

    status_icons = {"backlog": "📦", "ready": "🟢", "in_progress": "⚙️"}
    priority_icons = {1: "🔴", 2: "🟠", 3: "⚪", 4: "🔵"}

    lines = ["📋 *WORK QUEUE*\n"]
    for t in tasks:
        icon = status_icons.get(t["status"], "•")
        p = priority_icons.get(t.get("priority", 3), "•")
        source = t.get("source", "manual")
        lines.append(f"{icon} {p} {t['title']} _{source}_")

    lines.append(f"\n[Open dashboard →]({_DASHBOARD_URL})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the highest-priority ready task."""
    try:
        r = _requests.get(
            f"{_wq_url()}/rest/v1/work_queue",
            headers=_wq_headers(),
            params={"status": "eq.ready", "order": "priority.asc,created_at.asc", "limit": "1"},
            timeout=10,
        )
        r.raise_for_status()
        tasks = r.json()
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")
        return

    if not tasks:
        await update.message.reply_text("📭 No tasks queued.", parse_mode="Markdown")
        return

    t = tasks[0]
    priority_labels = {1: "🔴 Critical", 2: "🟠 High", 3: "⚪ Normal", 4: "🔵 Low"}
    await update.message.reply_text(
        f"⚡ *Next up:*\n_{t['title']}_\n\n"
        f"{priority_labels.get(t.get('priority', 3), '')}\n"
        f"Source: {t.get('source', 'manual')}",
        parse_mode="Markdown",
    )


async def cmd_analyst(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger analyst scan immediately."""
    await update.message.reply_text("🔍 *Running analyst scan...*", parse_mode="Markdown")
    try:
        from ops.analyst import run_analyst
        result = await asyncio.to_thread(run_analyst)
        await update.message.reply_text(result, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Analyst failed: {e}")
        log.exception("cmd_analyst error")


async def cmd_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Free-text message handler — lets Zac chat naturally with the bot.
    Claude decides: answer directly OR queue as a task.
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text or text.startswith("/"):
        return  # ignore commands (handled by CommandHandlers)

    # Show typing indicator
    await update.message.reply_text("💭 _Thinking..._", parse_mode="Markdown")

    chat_id = update.effective_chat.id
    try:
        reply, should_queue, task_title = await asyncio.to_thread(_claude_chat, chat_id, text)
    except Exception as e:
        await update.message.reply_text(f"❌ Claude error: {e}")
        log.exception("cmd_message error")
        return

    if should_queue and task_title:
        try:
            task_id = await asyncio.to_thread(_add_to_queue, task_title, 3, text)
            await update.message.reply_text(
                f"{reply}\n\n✅ *Queued:* _{task_title}_\n[View queue →]({_DASHBOARD_URL})",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"{reply}\n\n❌ Queue failed: {e}", parse_mode="Markdown")
    else:
        await update.message.reply_text(reply, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *Elite Operator Bot*\n\n"
        "*Control*\n"
        "/status — instant system snapshot\n"
        "/kill — emergency stop worker + clear queue\n"
        "/start — restart worker\n"
        "/version — list brain versions\n\n"
        "*Work Queue*\n"
        "/run [task] — queue task (normal priority)\n"
        "/run! [task] — queue task (high priority)\n"
        "/run!! [task] — queue task (critical)\n"
        "/queue — view current queue\n"
        "/next — what's up next\n"
        "/analyst — run analyst scan now\n\n"
        "*Business Intel*\n"
        "/digest — weekly ops digest\n"
        "/clients — client health check\n"
        "/leads — pipeline snapshot\n"
        "/delivered [client] [system] — log delivery\n"
        "/client [name] — client snapshot\n\n"
        "💬 _Or just chat with me — I can answer questions or queue tasks automatically._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Pulling ops digest...", parse_mode="Markdown")
    try:
        text = await asyncio.to_thread(_get_digest_sync)
    except Exception as e:
        text = f"❌ Digest failed: {e}"
        log.exception("cmd_digest error")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Checking client health...", parse_mode="Markdown")
    try:
        text = await asyncio.to_thread(run_health_check)
    except Exception as e:
        text = f"❌ Health check failed: {e}"
        log.exception("cmd_clients error")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Fetching pipeline...", parse_mode="Markdown")
    try:
        text = await asyncio.to_thread(_get_pipeline_snapshot_sync)
    except Exception as e:
        text = f"❌ Pipeline fetch failed: {e}"
        log.exception("cmd_leads error")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_delivered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /delivered [client] [system description]
    Examples:
      /delivered "Acme Fitness" Lead qualification bot
      /delivered AcmeFitness "Lead bot"
    """
    raw = " ".join(context.args) if context.args else ""
    if not raw:
        await update.message.reply_text(
            "Usage: `/delivered [client name] [system description]`\n"
            "Example: `/delivered \"Acme Fitness\" Lead qualification bot`",
            parse_mode="Markdown",
        )
        return

    # Parse: quoted client name OR first word as client name
    import re
    quoted = re.match(r'^"([^"]+)"\s+(.+)$', raw)
    if quoted:
        client_name = quoted.group(1).strip()
        system_name = quoted.group(2).strip()
    else:
        parts = raw.split(None, 1)
        client_name = parts[0]
        system_name = parts[1] if len(parts) > 1 else "System delivery"

    await update.message.reply_text(
        f"⏳ Logging *{system_name}* for *{client_name}*...",
        parse_mode="Markdown",
    )
    try:
        text = await asyncio.to_thread(
            process_delivery,
            client_name=client_name,
            system_name=system_name,
            source="manual",
        )
    except Exception as e:
        text = f"❌ Delivery pipeline failed: {e}"
        log.exception("cmd_delivered error")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /client [name]
    Shows full client snapshot: all systems delivered + last suggestion.
    """
    client_name = " ".join(context.args) if context.args else ""
    if not client_name:
        await update.message.reply_text(
            "Usage: `/client [client name]`\nExample: `/client Acme Fitness`",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"⏳ Looking up *{client_name}*...",
        parse_mode="Markdown",
    )
    try:
        text = await asyncio.to_thread(get_client_snapshot, client_name)
    except Exception as e:
        text = f"❌ Client lookup failed: {e}"
        log.exception("cmd_client error")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Instant system snapshot."""
    import requests as _req
    try:
        env_data = _load_env_data()
        sb_url = env_data.get("SUPABASE_URL", "")
        sb_key = env_data.get("SUPABASE_SERVICE_ROLE_KEY", "")
        headers = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
        }
        ready_r = _req.get(f"{sb_url}/rest/v1/work_queue", headers=headers,
                           params={"status": "eq.ready", "limit": "100"}, timeout=10)
        prog_r = _req.get(f"{sb_url}/rest/v1/work_queue", headers=headers,
                          params={"status": "eq.in_progress", "limit": "10"}, timeout=10)
        last_r = _req.get(f"{sb_url}/rest/v1/work_queue", headers=headers,
                          params={"status": "eq.done", "order": "completed_at.desc", "limit": "1"}, timeout=10)
        ready = len(ready_r.json()) if ready_r.ok else "?"
        prog = len(prog_r.json()) if prog_r.ok else "?"
        sb_status = "✅" if ready_r.ok else "❌"
        last_tasks = last_r.json() if last_r.ok else []
        if last_tasks:
            lt = last_tasks[0]
            from datetime import datetime as _dt
            comp = _dt.fromisoformat(lt["completed_at"].replace("Z", "+00:00"))
            mins_ago = int((datetime.now(timezone.utc) - comp).total_seconds() / 60)
            last_task_str = f"_{lt['title'][:50]}_ — done {mins_ago}min ago"
        else:
            last_task_str = "none"
        google_token_path = Path.home() / ".config" / "elite-os" / "google-token.json"
        gmail_status = "✅" if google_token_path.exists() else "❌"
        text = (
            f"📊 *OPERATOR OS STATUS*\n\n"
            f"Supabase: {sb_status}\n"
            f"Queue: {ready} ready, {prog} in_progress\n"
            f"Last task: {last_task_str}\n"
            f"Gmail OAuth: {gmail_status}\n\n"
            f"[Dashboard →]({_DASHBOARD_URL})"
        )
    except Exception as e:
        text = f"❌ Status fetch failed: {e}"
        log.exception("cmd_status error")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Emergency stop — mark all in_progress tasks as failed, stop elite-worker via SSH."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return  # silently ignore — don't reveal bot to others
    await update.message.reply_text("⛔ *Kill switch engaged...*", parse_mode="Markdown")
    import subprocess as _sp
    try:
        env_data = _load_env_data()
        sb_url = env_data.get("SUPABASE_URL", "")
        sb_key = env_data.get("SUPABASE_SERVICE_ROLE_KEY", "")
        headers = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        r = _requests.patch(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            params={"status": "eq.in_progress"},
            json={"status": "failed", "result_summary": "Killed via /kill command"},
            timeout=10,
        )
        rows_cleared = len(r.json()) if r.ok else 0
        ssh_result = _sp.run(
            ["ssh", "YOUR_SERVER_USER@YOUR_SERVER_IP "pm2 stop elite-worker"],
            capture_output=True, text=True, timeout=15,
        )
        worker_stopped = ssh_result.returncode == 0
        status = "⛔ Worker stopped." if worker_stopped else "⚠️ Worker stop failed — check manually."
        await update.message.reply_text(
            f"{status} {rows_cleared} task(s) cleared.\nUse /start to resume.",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.exception("cmd_kill error")
        await update.message.reply_text("❌ Kill failed — check Railway logs")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restart elite-worker on Mac Mini via SSH."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return
    await update.message.reply_text("🚀 *Starting worker...*", parse_mode="Markdown")
    import subprocess as _sp
    try:
        result = _sp.run(
            ["ssh", "YOUR_SERVER_USER@YOUR_SERVER_IP "pm2 start elite-worker"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            await update.message.reply_text("✅ Worker started. Queue polling resumed within 30s.")
        else:
            await update.message.reply_text(f"❌ SSH start failed:\n`{result.stderr[:200]}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Start failed: {e}")
        log.exception("cmd_start error")


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent brain versions on Mac Mini."""
    import subprocess as _sp
    try:
        result = _sp.run(
            ["ssh", "YOUR_SERVER_USER@YOUR_SERVER_IP "ls -1t ~/operatoros/versions/ 2>/dev/null | head -10"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            versions = result.stdout.strip().split("\n")
            lines = ["📦 *Brain Versions* (latest first)\n"] + [f"• {v}" for v in versions]
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("📦 No brain versions saved yet.\nWorker saves versions before major code changes.")
    except Exception as e:
        await update.message.reply_text(f"❌ Version fetch failed: {e}")
        log.exception("cmd_version error")


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive Telegram voice note → Whisper transcription → queue as task."""
    if not update.message or not update.message.voice:
        return
    await update.message.reply_text("🎙️ _Transcribing..._", parse_mode="Markdown")
    import tempfile
    import os
    try:
        env_data = _load_env_data()
        openai_key = env_data.get("OPENAI_API_KEY", "")
        if not openai_key:
            await update.message.reply_text("❌ OPENAI_API_KEY not set in .env — voice commands unavailable")
            return
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await voice_file.download_to_drive(tmp_path)
            with open(tmp_path, "rb") as audio_file:
                resp = _requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    files={"file": ("voice.ogg", audio_file, "audio/ogg")},
                    data={"model": "whisper-1"},
                    timeout=30,
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if not resp.ok:
            await update.message.reply_text(f"❌ Whisper transcription failed: {resp.text[:200]}")
            return
        text = resp.json().get("text", "").strip()
        if not text:
            await update.message.reply_text("❌ Could not transcribe voice message — try again")
            return
        task_id = await asyncio.to_thread(_add_to_queue, text, 3, "Queued via voice command")
        await update.message.reply_text(
            f"🎙️ *Heard:* _{text}_\n\n✅ Queued as priority 3. Worker picks up within 30s.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Voice command failed: {e}")
        log.exception("cmd_voice error")


# ── Scheduled job callbacks ───────────────────────────────────────────────────


async def job_health_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily 9am AEST — send health report only when 🔴 clients exist."""
    log.info("Scheduled: client health check starting")
    try:
        report = await asyncio.to_thread(run_health_check)
    except Exception as e:
        report = f"❌ Scheduled health check failed: {e}"
        log.exception("job_health_check error")

    # Check for at-risk clients — look for the red circle in the summary line
    # The summary format is "🔴 N At-risk" so "🔴 0" means all clear
    has_atrisk = "🔴" in report and "🔴 0 " not in report
    if has_atrisk:
        await asyncio.to_thread(send_telegram, report)
        log.info("Health alert sent — at-risk clients found")
    else:
        log.info("Health check complete — all clients healthy, no alert sent")


async def job_weekly_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monday 8am AEST — full weekly ops digest, always fires."""
    log.info("Scheduled: weekly ops digest starting")
    try:
        text = await asyncio.to_thread(_get_digest_sync)
    except Exception as e:
        text = f"❌ Scheduled digest failed: {e}"
        log.exception("job_weekly_digest error")
    await asyncio.to_thread(send_telegram, text)
    log.info("Weekly digest sent")


async def job_morning_ping(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily 8am AEST — system health + overnight summary."""
    log.info("Scheduled: morning status ping starting")
    import requests as _req
    try:
        env_data = _load_env_data()
        sb_url = env_data.get("SUPABASE_URL", "")
        sb_key = env_data.get("SUPABASE_SERVICE_ROLE_KEY", "")
        headers = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
        }
        from datetime import date as _date
        midnight_aest = datetime.combine(datetime.now(AEST).date(), time(0, 0), tzinfo=AEST).astimezone(timezone.utc)
        done_r = _req.get(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            params={
                "status": "eq.done",
                "completed_at": f"gte.{midnight_aest.isoformat()}",
                "limit": "100",
            },
            timeout=10,
        )
        done_count = len(done_r.json()) if done_r.ok else "?"
        ready_r = _req.get(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            params={"status": "eq.ready", "limit": "100"},
            timeout=10,
        )
        in_prog_r = _req.get(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            params={"status": "eq.in_progress", "limit": "10"},
            timeout=10,
        )
        ready_count = len(ready_r.json()) if ready_r.ok else "?"
        in_prog_count = len(in_prog_r.json()) if in_prog_r.ok else "?"
        top_r = _req.get(
            f"{sb_url}/rest/v1/work_queue",
            headers=headers,
            params={"status": "eq.ready", "order": "priority.asc", "limit": "1"},
            timeout=10,
        )
        top_tasks = top_r.json() if top_r.ok else []
        top_task = top_tasks[0]["title"] if top_tasks else "none"
        today_str = datetime.now(AEST).strftime("%Y-%m-%d")
        msg = (
            f"🟢 *Operator OS alive — {today_str}*\n\n"
            f"Tasks completed overnight: {done_count}\n"
            f"Queue: {ready_count} ready, {in_prog_count} in_progress\n"
            f"Biggest constraint: _{top_task}_\n\n"
            f"[View queue →]({_DASHBOARD_URL})"
        )
    except Exception as e:
        msg = f"⚠️ *Morning ping failed* — Supabase may be unreachable\nError: {e}\n\nCheck: `pm2 status` on Mac Mini"
        log.exception("job_morning_ping error")
    await asyncio.to_thread(send_telegram, msg)
    log.info("Morning ping sent")


async def job_bottleneck_hunter(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily 9:05am AEST — queue the Bottleneck Hunter task."""
    log.info("Scheduled: queuing Bottleneck Hunter task")
    try:
        await asyncio.to_thread(
            _add_to_queue,
            "Bottleneck Hunter — find and fix today's biggest constraint",
            2,
            (
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
                "Send result via Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env)."
            ),
        )
        log.info("Bottleneck Hunter queued")
    except Exception as e:
        log.exception(f"job_bottleneck_hunter error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    log.info("Starting Elite Operator Bot (long polling)...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("digest",    cmd_digest))
    app.add_handler(CommandHandler("clients",   cmd_clients))
    app.add_handler(CommandHandler("leads",     cmd_leads))
    app.add_handler(CommandHandler("delivered", cmd_delivered))
    app.add_handler(CommandHandler("client",    cmd_client))
    app.add_handler(CommandHandler("run",       cmd_run))
    app.add_handler(CommandHandler("queue",     cmd_queue))
    app.add_handler(CommandHandler("next",      cmd_next))
    app.add_handler(CommandHandler("analyst",   cmd_analyst))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("kill",      cmd_kill))
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("version",   cmd_version))

    # Free-text message handler (must be last — catches everything non-command)
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_message))
    app.add_handler(MessageHandler(filters.VOICE, cmd_voice))

    # Scheduled jobs (AEST = UTC+10, Queensland — no DST ever)
    jq = app.job_queue

    # Daily 9am AEST
    jq.run_daily(
        job_health_check,
        time(9, 0, tzinfo=AEST),
        name="daily_health_check",
    )

    # Monday 8am AEST only (days=(0,) → Monday in ISO weekday convention)
    jq.run_daily(
        job_weekly_digest,
        time(8, 0, tzinfo=AEST),
        days=(0,),
        name="weekly_digest_monday",
    )

    # Daily 8am AEST — morning system ping
    jq.run_daily(
        job_morning_ping,
        time(8, 0, tzinfo=AEST),
        name="morning_ping",
    )

    # Daily 9:05am AEST — Bottleneck Hunter
    jq.run_daily(
        job_bottleneck_hunter,
        time(9, 5, tzinfo=AEST),
        name="bottleneck_hunter",
    )

    log.info("Handlers and scheduled jobs registered — entering polling loop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
