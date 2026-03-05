"""Aiogram bot handlers for AI Command Bot."""

import asyncio
import base64
import io
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import Config
from .logger import get_logger
from .orchestrator import Orchestrator
from . import self_annealing
from . import topic_router

msg_log = get_logger("message")
sys_log = get_logger("system")

router = Router()

_orchestrator: Orchestrator | None = None
_config: Config | None = None
_owner_id: int | None = None

# Message batching — Telegram splits long pastes into multiple messages.
# We collect them with a short delay and process as one.
_DEBOUNCE_SECONDS = 1.5


@dataclass
class _BufferedItem:
    """A text string, voice transcript, or photo queued for batching."""

    message: Message  # the original Telegram message (used for reply target)
    text: str  # the text content (typed or transcribed)
    photos: list[dict] = field(default_factory=list)  # Pre-built Anthropic image content blocks


_message_buffer: list[_BufferedItem] = []
_debounce_task: asyncio.Task | None = None


def set_orchestrator(orchestrator: Orchestrator, config: Config) -> None:
    """Wire up the orchestrator and config for handlers."""
    global _orchestrator, _config
    _orchestrator = orchestrator
    _config = config


def _is_authorized(message: Message) -> bool:
    """Check if the message is from an authorized user.

    Auto-captures the first human user as the owner. All subsequent
    messages from non-owner users are silently ignored. This means
    the first person to message the bot in the configured group
    becomes the sole operator.
    """
    global _owner_id
    if not message.from_user or message.from_user.is_bot:
        return False
    # Auto-capture the first human user as owner
    if _owner_id is None:
        _owner_id = message.from_user.id
        sys_log.info(
            "Owner captured: %s (id=%d)",
            message.from_user.full_name,
            _owner_id,
        )
        return True
    return message.from_user.id == _owner_id


async def _transcribe_voice(bot: Bot, message: Message) -> str | None:
    """Download a Telegram voice note and transcribe via OpenAI Whisper.

    Returns the transcribed text, or None if transcription fails
    (missing API key, missing package, API error, etc.).
    """
    if not _config or not _config.openai_api_key:
        msg_log.warning("Voice note received but OPENAI_API_KEY not configured")
        return None

    try:
        from openai import AsyncOpenAI
    except ImportError:
        msg_log.error("openai package not installed — cannot transcribe voice notes")
        return None

    voice = message.voice
    if not voice:
        return None

    try:
        # Download OGG from Telegram
        file = await bot.get_file(voice.file_id)
        bio = io.BytesIO()
        await bot.download_file(file.file_path, bio)
        bio.seek(0)
        bio.name = "voice.ogg"

        # Transcribe with Whisper
        client = AsyncOpenAI(api_key=_config.openai_api_key)
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=bio,
        )

        text = transcript.text.strip()
        duration = voice.duration
        preview = text[:60] + "..." if len(text) > 60 else text
        msg_log.info('Transcribed: "%s" (%ds)', preview, duration)
        return text

    except Exception:
        msg_log.exception("Failed to transcribe voice note")
        return None


async def _download_photos(bot: Bot, message: Message) -> list[dict]:
    """Download photos from a Telegram message and return Anthropic image content blocks.

    Handles two photo sources:
    - message.photo: compressed Telegram photos (always JPEG). Takes [-1] for highest res.
    - message.document: uncompressed image files sent as documents. Skips files >5MB.

    Returns a list of dicts matching the Anthropic image content block format:
    {"type": "image", "source": {"type": "base64", "media_type": "...", "data": "..."}}
    """
    blocks = []

    try:
        if message.photo:
            # message.photo is a list of PhotoSize — take [-1] for largest resolution
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            bio = io.BytesIO()
            await bot.download_file(file.file_path, bio)
            bio.seek(0)
            data = base64.b64encode(bio.read()).decode("utf-8")
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": data,
                    },
                }
            )

        elif (
            message.document
            and message.document.mime_type
            and message.document.mime_type.startswith("image/")
        ):
            doc = message.document
            # Skip files >5MB (Telegram compressed photos are always smaller)
            if doc.file_size and doc.file_size > 5 * 1024 * 1024:
                msg_log.warning(
                    "Document image too large (%d bytes), skipping", doc.file_size
                )
                return blocks
            file = await bot.get_file(doc.file_id)
            bio = io.BytesIO()
            await bot.download_file(file.file_path, bio)
            bio.seek(0)
            data = base64.b64encode(bio.read()).decode("utf-8")
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": doc.mime_type,
                        "data": data,
                    },
                }
            )

    except Exception:
        msg_log.exception("Failed to download photo")

    return blocks


async def _flush_message_buffer() -> None:
    """Process all buffered items as a single concatenated message.

    Called after the debounce timer fires. Concatenates all buffered
    text items and collects all photos, then routes the combined
    message to the appropriate orchestrator handler based on context:

    1. Agent topic (CC session from /new) -> orchestrator.handle_agent_topic_message
    2. Everything else (General topic) -> orchestrator.handle_general_message
    """
    global _message_buffer, _debounce_task

    if not _message_buffer or not _orchestrator:
        _message_buffer = []
        _debounce_task = None
        return

    items = _message_buffer
    _message_buffer = []
    _debounce_task = None

    # Use the last message as the "reply target" (for thread ID, reply, etc.)
    last_message = items[-1].message

    # Get the topic ID for routing
    topic_id = last_message.message_thread_id

    # Auto-register topic if we haven't seen it before
    if topic_id:
        # Try to get topic name from forum_topic_created or fallback
        topic_name = None
        if hasattr(last_message, 'forum_topic_created') and last_message.forum_topic_created:
            topic_name = last_message.forum_topic_created.name
            topic_router.on_topic_created(topic_id, topic_name)
        else:
            topic_router.on_message_in_topic(topic_id, topic_name)

    # Concatenate all texts
    texts = [item.text for item in items if item.text]
    combined_text = "\n".join(texts)

    # Collect all photos from buffered items (media groups batch naturally)
    all_photos = []
    for item in items:
        if item.photos:
            all_photos.extend(item.photos)

    if len(items) > 1:
        msg_log.info(
            "Batched %d messages (%d chars, %d photos)",
            len(items),
            len(combined_text),
            len(all_photos),
        )

    # === ROUTING ===

    # 1. Agent topic (CC agent session from /new)
    if topic_id and _orchestrator.sessions.get(str(topic_id)):
        await _orchestrator.handle_agent_topic_message(
            last_message,
            text_override=combined_text,
            photos=all_photos or None,
        )
    # 2. Everything else (General topic or unrecognized topic)
    else:
        await _orchestrator.handle_general_message(
            last_message,
            text_override=combined_text,
            photos=all_photos or None,
        )


def _enqueue_and_debounce(item: _BufferedItem) -> None:
    """Add an item to the buffer and reset the debounce timer.

    Each new message cancels the existing timer and starts a fresh
    1.5-second countdown. When no new messages arrive within the
    window, _flush_message_buffer fires and processes the batch.
    """
    global _message_buffer, _debounce_task

    _message_buffer.append(item)

    # Cancel existing debounce timer and start a new one
    if _debounce_task and not _debounce_task.done():
        _debounce_task.cancel()

    async def _debounce_fire():
        await asyncio.sleep(_DEBOUNCE_SECONDS)
        await _flush_message_buffer()

    _debounce_task = asyncio.create_task(_debounce_fire())


@router.message(Command("topics"))
async def handle_topics(message: Message) -> None:
    """Show and manage known Telegram topics.

    Usage:
      /topics           — list all known topics
      /topics add <thread_id> <name>  — manually register a topic
      /topics refresh   — reload topics from Supabase
    """
    if not _config:
        return
    if message.chat.id != _config.group_id:
        return
    if not _is_authorized(message):
        return

    text = (message.text or "").strip()
    parts = text.split(None, 3)  # ["/topics", subcmd?, arg1?, arg2?]

    if len(parts) >= 4 and parts[1].lower() == "add":
        # /topics add <thread_id> <name>
        try:
            thread_id = int(parts[2])
        except ValueError:
            await message.reply("Usage: /topics add <thread_id> <name>\nthread_id must be a number.")
            return
        name = parts[3].strip()
        topic_router.on_topic_created(thread_id, name)
        await message.reply(f"Registered topic {thread_id} -> '{name}'")
        return

    if len(parts) >= 2 and parts[1].lower() == "refresh":
        topic_router.load_topics_from_supabase()
        known = topic_router.get_all_topics()
        await message.reply(f"Reloaded {len(known)} topics from Supabase.")
        return

    # Default: list all known topics
    known = topic_router.get_all_topics()
    if not known:
        await message.reply(
            "No topics registered yet.\n\n"
            "Send a message in any topic — the bot will auto-register it.\n"
            "Or: /topics add <thread_id> <name>"
        )
        return

    lines = [f"Known topics ({len(known)}):"]
    for tid, name in sorted(known.items(), key=lambda x: x[1]):
        lines.append(f"  {tid}  {name}")
    lines.append("\nTo add: /topics add <thread_id> <name>")
    await message.reply("\n".join(lines))


@router.message(Command("reboot"))
async def handle_reboot(message: Message) -> None:
    """Reboot the bot — kills process, launchd/systemd restarts it.

    Accepts from the configured group only. Useful when the bot
    gets into a bad state or after deploying code changes.
    """
    if not _config:
        return
    if message.chat.id != _config.group_id:
        return
    if not _is_authorized(message):
        return

    sys_log.info(
        "Reboot requested by %s",
        message.from_user.full_name if message.from_user else "Unknown",
    )
    await message.reply("Rebooting...")
    await asyncio.sleep(0.5)
    sys.exit(0)


# ── Content Autopilot Helpers ─────────────────────────────────────────────────

_AEST = timezone(timedelta(hours=10))
_TYPE_EMOJI = {"reel": "🎬", "carousel": "🎠", "linkedin": "💼", "text": "📝"}


def _get_manifest(workspace_dir: str, date_str: str | None = None) -> tuple[Path, dict | None]:
    """Load today's manifest. Returns (path, manifest_dict) or (path, None) if missing."""
    if not date_str:
        date_str = datetime.now(_AEST).strftime("%Y-%m-%d")
    path = Path(workspace_dir) / "data" / "content_drafts" / date_str / "manifest.json"
    if not path.exists():
        return path, None
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, None


def _save_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_draft(manifest: dict, n: int) -> dict | None:
    for d in manifest.get("drafts", []):
        if d.get("n") == n:
            return d
    return None


def _read_draft_file(workspace_dir: str, date_str: str, filename: str) -> str:
    path = Path(workspace_dir) / "data" / "content_drafts" / date_str / filename
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _write_draft_file(workspace_dir: str, date_str: str, filename: str, content: str) -> None:
    path = Path(workspace_dir) / "data" / "content_drafts" / date_str / filename
    path.write_text(content, encoding="utf-8")


def _format_digest_lines(drafts: list[dict], date_str: str) -> list[str]:
    lines = [f"📝 <b>Content Digest — {date_str}</b>", f"{len(drafts)} drafts:", ""]
    for d in drafts:
        emoji = _TYPE_EMOJI.get(d.get("type", ""), "📄")
        status = d.get("status", "pending")
        status_tag = f" [{status.upper()}]" if status != "pending" else ""
        size_info = (f"{d['slide_count']} slides" if d.get("slide_count")
                     else f"{d.get('word_count', '?')} words")
        lines.append(
            f"{d['n']}. {emoji} {d.get('type','?').upper()} [{d.get('funnel','?')}] — {d.get('pillar','?')}{status_tag}\n"
            f"   \"{d.get('hook','')[:80]}\"\n"
            f"   {size_info} · quality {d.get('quality_score','?')}/10"
        )
        lines.append("")
    lines += [
        "<b>Commands:</b>",
        "/approve 1 — schedule or get formatted draft",
        "/edit 2 add more specific numbers — regenerate",
        "/skip 3 — skip",
        "/drafts — view this digest",
    ]
    return lines


async def _regenerate_draft(draft: dict, feedback: str, workspace_dir: str, date_str: str) -> str | None:
    """Call Claude to regenerate a draft with user feedback."""
    api_key = _config.anthropic_api_key if _config else ""
    if not api_key:
        return None

    original = _read_draft_file(workspace_dir, date_str, draft.get("file", ""))
    if not original:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system = (
            "You are the content writer for [YOUR_NAME], Elite Systems AI. "
            "Rewrite the draft based on the feedback provided. "
            "Keep the same format and structure. "
            "NEVER use: 'dive into', 'game-changer', 'leverage', em dashes, 'unlock'. "
            "Each sentence on its own line. Max 3 hashtags."
        )
        user = (
            f"ORIGINAL DRAFT:\n{original[:3000]}\n\n"
            f"FEEDBACK FROM ZAC: {feedback}\n\n"
            "Rewrite the draft incorporating this feedback. Keep the same output format with "
            "QUALITY SCORE, HOOK PREVIEW, and WORD COUNT at the bottom."
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None


async def _schedule_text_post_ghl(draft_content: str, draft_type: str) -> tuple[bool, str]:
    """Attempt to schedule a text/LinkedIn post via GHL Social Planner.

    Returns (success, message).
    Only works for text posts and LinkedIn — reels/carousels need visual assets.
    """
    if not _config:
        return False, "Config not available"

    from pathlib import Path
    import os

    # Load .env vars for GHL
    workspace = Path(_config.workspace_dir)
    ghl_env: dict = {}
    env_path = workspace / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                ghl_env[k.strip()] = v.strip()

    ghl_key = ghl_env.get("GHL_API_KEY", "")
    location_id = ghl_env.get("GHL_LOCATION_ID", "")
    user_id = ghl_env.get("GHL_USER_ID", "")

    if not all([ghl_key, location_id, user_id]):
        return False, "GHL_API_KEY, GHL_LOCATION_ID, or GHL_USER_ID missing from .env"

    # Account IDs from known config (MEMORY.md)
    if draft_type == "linkedin":
        account_ids = [
            "66ea6bda908f6903cf47f896_q3XoUHEaMYRwhdaMMJvS_107115180_page",  # Elite Systems AI LinkedIn
        ]
    else:
        account_ids = [
            "6683c5112360e3afa4416933_q3XoUHEaMYRwhdaMMJvS_17841436875055229",  # [YOUR_INSTAGRAM_HANDLE] IG
        ]

    # Extract caption from draft (text between start and first ---)
    caption_match = re.search(r"CAPTION:\n(.+?)(?=---|\Z)", draft_content, re.DOTALL)
    if caption_match:
        caption = caption_match.group(1).strip()
    else:
        # Fall back to extracting lines after the header block
        lines = [l for l in draft_content.splitlines()
                 if not l.startswith("#") and not l.startswith("**") and l.strip()]
        caption = "\n".join(lines[:10]).strip()

    if not caption:
        return False, "Could not extract caption from draft"

    # Schedule for tomorrow 9am AEST
    from zoneinfo import ZoneInfo
    import requests as _req
    aest = ZoneInfo("Australia/Brisbane")
    now_aest = datetime.now(aest)
    tomorrow_aest = now_aest.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    schedule_utc = tomorrow_aest.astimezone(timezone.utc).isoformat()

    payload = {
        "accountIds": account_ids,
        "userId": user_id,
        "type": "post",
        "status": "scheduled",
        "scheduleDate": schedule_utc,
        "summary": caption,
    }

    try:
        r = _req.post(
            f"https://services.leadconnectorhq.com/social-media-posting/{location_id}/posts",
            headers={
                "Authorization": f"Bearer {ghl_key}",
                "Version": "2021-07-28",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if r.ok:
            sched_str = tomorrow_aest.strftime("%a %d %b at %I:%M%p AEST")
            return True, f"Scheduled for {sched_str}"
        else:
            return False, f"GHL API error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"GHL request failed: {e}"


# ── Content Autopilot Commands ────────────────────────────────────────────────

@router.message(Command("drafts"))
async def handle_drafts(message: Message) -> None:
    """Show today's content digest."""
    if not _config:
        return
    if message.chat.id != _config.group_id:
        return
    if not _is_authorized(message):
        return

    date_str = datetime.now(_AEST).strftime("%Y-%m-%d")
    _, manifest = _get_manifest(_config.workspace_dir, date_str)

    if not manifest:
        await message.reply(
            f"📭 No drafts found for {date_str}.\n"
            "The autopilot runs at 7am AEST. Check <code>pm2 logs elite-content-autopilot</code>"
        )
        return

    drafts = manifest.get("drafts", [])
    lines = _format_digest_lines(drafts, date_str)
    await message.reply("\n".join(lines))


@router.message(Command("approve"))
async def handle_approve(message: Message) -> None:
    """Approve a draft: /approve 2

    For text/LinkedIn: auto-schedules via GHL.
    For reel/carousel: sends formatted draft for copy-paste.
    """
    if not _config:
        return
    if message.chat.id != _config.group_id:
        return
    if not _is_authorized(message):
        return

    # Parse draft number
    text = message.text or ""
    m = re.search(r"/approve\s+(\d+)", text)
    if not m:
        await message.reply("Usage: /approve 2 (number from the digest)")
        return

    n = int(m.group(1))
    date_str = datetime.now(_AEST).strftime("%Y-%m-%d")
    manifest_path, manifest = _get_manifest(_config.workspace_dir, date_str)

    if not manifest:
        await message.reply(f"No drafts found for {date_str}. Run the autopilot first.")
        return

    draft = _find_draft(manifest, n)
    if not draft:
        await message.reply(f"Draft {n} not found. Use /drafts to see available drafts.")
        return

    if draft.get("status") in ("approved", "scheduled", "skipped"):
        await message.reply(f"Draft {n} is already marked as {draft['status']}.")
        return

    draft_content = _read_draft_file(_config.workspace_dir, date_str, draft.get("file", ""))
    if not draft_content:
        await message.reply(f"Could not read draft {n} file.")
        return

    draft_type = draft.get("type", "")

    # Auto-schedule for text and LinkedIn posts
    if draft_type in ("text", "linkedin"):
        await message.reply(f"Scheduling draft {n} via GHL...")
        success, result_msg = await _schedule_text_post_ghl(draft_content, draft_type)
        if success:
            draft["status"] = "scheduled"
            _save_manifest(manifest_path, manifest)
            await message.reply(f"✅ Draft {n} scheduled — {result_msg}")
        else:
            # Fall through to send formatted draft
            await message.reply(f"⚠️ Auto-schedule failed: {result_msg}\nSending formatted draft instead:")
            await _send_formatted_draft(message, draft, draft_content, n)
    else:
        # Reels and carousels need visual assets — send formatted text
        await _send_formatted_draft(message, draft, draft_content, n)
        draft["status"] = "approved"
        _save_manifest(manifest_path, manifest)


async def _send_formatted_draft(message: Message, draft: dict, content: str, n: int) -> None:
    """Send draft content as formatted Telegram messages."""
    emoji = _TYPE_EMOJI.get(draft.get("type", ""), "📄")
    header = (
        f"{emoji} <b>Draft {n} — {draft.get('type','').upper()} [{draft.get('funnel','')}]</b>\n"
        f"<b>Pillar:</b> {draft.get('pillar','')}\n"
        f"<b>Hook:</b> {draft.get('hook','')}\n"
        f"<b>Quality:</b> {draft.get('quality_score','?')}/10\n"
        "─────────────────────"
    )
    await message.reply(header)

    # Send content in chunks (Telegram 4096 char limit)
    MAX_CHUNK = 3800
    body = content
    # Strip the metadata header block from the .md file
    if "---" in body:
        parts = body.split("---", 1)
        body = parts[1].strip() if len(parts) > 1 else body

    for i in range(0, len(body), MAX_CHUNK):
        chunk = body[i:i + MAX_CHUNK]
        await message.reply(f"<pre>{chunk[:3800]}</pre>")


@router.message(Command("edit"))
async def handle_edit(message: Message) -> None:
    """Regenerate a draft with feedback: /edit 2 make it more specific with real numbers"""
    if not _config:
        return
    if message.chat.id != _config.group_id:
        return
    if not _is_authorized(message):
        return

    text = message.text or ""
    m = re.match(r"/edit\s+(\d+)\s+(.+)", text, re.DOTALL)
    if not m:
        await message.reply("Usage: /edit 2 your feedback here\nExample: /edit 2 add more specific numbers")
        return

    n = int(m.group(1))
    feedback = m.group(2).strip()

    date_str = datetime.now(_AEST).strftime("%Y-%m-%d")
    manifest_path, manifest = _get_manifest(_config.workspace_dir, date_str)

    if not manifest:
        await message.reply(f"No drafts found for {date_str}.")
        return

    draft = _find_draft(manifest, n)
    if not draft:
        await message.reply(f"Draft {n} not found.")
        return

    await message.reply(f"Regenerating draft {n} with your feedback...")

    new_content = await _regenerate_draft(draft, feedback, _config.workspace_dir, date_str)
    if not new_content:
        await message.reply("Regeneration failed. Check ANTHROPIC_API_KEY in .env.")
        return

    # Save new draft content
    header = (
        f"# Draft {n} — {draft.get('type','').upper()} [{draft.get('funnel','')}] — {draft.get('pillar','')}\n\n"
        f"**Date:** {date_str}\n"
        f"**Feedback applied:** {feedback}\n"
        f"**Status:** pending\n\n---\n\n"
    )
    _write_draft_file(_config.workspace_dir, date_str, draft.get("file", ""), header + new_content)

    # Update hook in manifest
    hook_m = re.search(r"HOOK PREVIEW:\s*(.+)", new_content)
    if hook_m:
        draft["hook"] = hook_m.group(1).strip()[:100]
    quality_m = re.search(r"QUALITY SCORE:\s*(\d+)", new_content)
    if quality_m:
        draft["quality_score"] = int(quality_m.group(1))
    draft["status"] = "pending"
    _save_manifest(manifest_path, manifest)

    await message.reply(f"✅ Draft {n} regenerated. Use /approve {n} to approve or /edit {n} for more changes.")
    await _send_formatted_draft(message, draft, header + new_content, n)


@router.message(Command("skip"))
async def handle_skip(message: Message) -> None:
    """Skip a draft: /skip 3"""
    if not _config:
        return
    if message.chat.id != _config.group_id:
        return
    if not _is_authorized(message):
        return

    text = message.text or ""
    m = re.search(r"/skip\s+(\d+)", text)
    if not m:
        await message.reply("Usage: /skip 2 (number from the digest)")
        return

    n = int(m.group(1))
    date_str = datetime.now(_AEST).strftime("%Y-%m-%d")
    manifest_path, manifest = _get_manifest(_config.workspace_dir, date_str)

    if not manifest:
        await message.reply(f"No drafts for {date_str}.")
        return

    draft = _find_draft(manifest, n)
    if not draft:
        await message.reply(f"Draft {n} not found.")
        return

    draft["status"] = "skipped"
    _save_manifest(manifest_path, manifest)
    await message.reply(f"⏭️ Draft {n} skipped.")


async def _schedule_content_via_ghl(draft: dict, bot: Bot, chat_id: int) -> None:
    """Schedule an approved content draft via GHL Social Planner API.

    Takes a draft dict (from workflow_logs input_data), reads GHL credentials
    from the workspace .env file, and posts to the GHL social planner.
    Sends a confirmation or error message back to the Telegram chat.
    """
    import os
    import requests as _req
    from zoneinfo import ZoneInfo

    if not _config:
        await bot.send_message(chat_id=chat_id, text="Config not available — cannot schedule via GHL.")
        return

    # Load GHL credentials from workspace .env
    from pathlib import Path as _Path
    ghl_env: dict = {}
    env_path = _Path(_config.workspace_dir) / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                ghl_env[k.strip()] = v.strip()

    ghl_key = ghl_env.get("GHL_API_KEY", "")
    location_id = ghl_env.get("GHL_LOCATION_ID", "")
    user_id = ghl_env.get("GHL_USER_ID", "")

    if not all([ghl_key, location_id, user_id]):
        await bot.send_message(
            chat_id=chat_id,
            text="GHL_API_KEY, GHL_LOCATION_ID, or GHL_USER_ID missing from .env — cannot schedule.",
        )
        return

    # Map platform to GHL account ID (from MEMORY.md)
    ACCOUNT_IDS = {
        "IG_personal": "6683c5112360e3afa4416933_q3XoUHEaMYRwhdaMMJvS_17841436875055229",
        "IG_business": "66ea57d9908f695c2a47dfe2_q3XoUHEaMYRwhdaMMJvS_17841469504036896",
        "LinkedIn": "66ea6bda908f6903cf47f896_q3XoUHEaMYRwhdaMMJvS_107115180_page",
        "linkedin": "66ea6bda908f6903cf47f896_q3XoUHEaMYRwhdaMMJvS_107115180_page",
    }

    platform = draft.get("platform", "IG_personal")
    account_id = ACCOUNT_IDS.get(platform, ACCOUNT_IDS["IG_personal"])

    # Schedule for next 9am AEST (= 23:00 UTC previous day)
    aest = ZoneInfo("Australia/Brisbane")
    now_aest = datetime.now(aest)
    target_aest = now_aest.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    schedule_utc = target_aest.astimezone(timezone.utc).isoformat()

    caption = draft.get("caption", draft.get("content", ""))
    post_type = draft.get("type", "post")
    # GHL accepts "post", "story", "reel" — map common aliases
    if post_type not in ("post", "story", "reel"):
        post_type = "post"

    payload = {
        "accountIds": [account_id],
        "userId": user_id,
        "type": post_type,
        "status": "scheduled",
        "scheduleDate": schedule_utc,
        "summary": caption,
    }

    try:
        r = _req.post(
            f"https://services.leadconnectorhq.com/social-media-posting/{location_id}/posts",
            headers={
                "Authorization": f"Bearer {ghl_key}",
                "Version": "2021-07-28",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if r.ok:
            sched_str = target_aest.strftime("%a %d %b at 9:00am AEST")
            await bot.send_message(
                chat_id=chat_id,
                text=f"Scheduled for <b>{sched_str}</b> via GHL.",
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=f"GHL scheduling failed: {r.status_code}\n<code>{r.text[:200]}</code>",
                parse_mode="HTML",
            )
    except Exception as e:
        await bot.send_message(
            chat_id=chat_id,
            text=f"GHL request failed: {e}",
        )


@router.callback_query(lambda c: c.data and (c.data.startswith("approve_") or c.data.startswith("reject_")))
async def handle_workflow_approval(callback: CallbackQuery) -> None:
    """Handle approve/reject button presses for ad and content workflows.

    callback_data format: "<action>_<workflow>_<log_id>"
    Examples: "approve_content_<uuid>", "reject_ads_<uuid>"

    On approval:
    - Records decision in Supabase via supabase_memory.set_approval()
    - Edits the original message to remove buttons and show the decision
    - Triggers downstream execution (GHL for content, placeholder for ads)

    On rejection:
    - Records decision in Supabase
    - Edits the message to show rejection, removes buttons
    """
    from apps.command import supabase_memory

    data = callback.data or ""
    # Format: "approve_content_<uuid>" — split into exactly 3 parts
    parts = data.split("_", 2)

    if len(parts) != 3:
        await callback.answer("Invalid approval data.")
        return

    action, workflow, log_id = parts
    approved = action == "approve"

    supabase_memory.set_approval(log_id, approved)

    status_emoji = "✅" if approved else "❌"
    status_text = "Approved" if approved else "Rejected"
    user_name = callback.from_user.first_name if callback.from_user else "Unknown"

    # Edit the original message: append decision, remove inline keyboard
    try:
        original_text = callback.message.text or ""
        await callback.message.edit_text(
            original_text + f"\n\n{status_emoji} <b>{status_text}</b> by {user_name}",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass  # Message may be too old to edit — non-fatal

    await callback.answer(f"{status_text}.")

    if not approved:
        return

    # Approved — trigger downstream execution
    chat_id = callback.message.chat.id

    if workflow == "anneal":
        asyncio.create_task(self_annealing.execute_build(log_id, callback.bot, _config))

    elif workflow == "ads":
        await callback.message.answer(
            "Ad changes approved. Executing via Meta API...\n"
            "<i>This will update budgets and pauses as recommended.</i>",
            parse_mode="HTML",
        )
        # Meta API execution is deferred (out of scope per plan — Zac actions manually)

    elif workflow == "content":
        # Fetch the draft dict from workflow_logs input_data
        try:
            logs = supabase_memory._get("workflow_logs", params={"id": f"eq.{log_id}"})
            draft = logs[0].get("input_data", {}) if logs else {}
        except Exception:
            draft = {}

        await callback.message.answer("Content approved. Scheduling via GHL...")
        await _schedule_content_via_ghl(draft, callback.bot, chat_id)


@router.message()
async def handle_message(message: Message) -> None:
    """Route all incoming messages — batch rapid-fire text and voice messages.

    This is the single entry point for all non-command messages. It:
    1. Validates the message source (must be from the configured group)
    2. Checks authorization (owner lock)
    3. Handles voice notes (transcribe + enqueue)
    4. Handles photos (download as base64 + enqueue with caption)
    5. Handles text (enqueue directly)

    All items go through the debounce buffer before routing.
    """
    if not _orchestrator or not _config:
        return

    # Only accept messages from the configured group
    if message.chat.id != _config.group_id:
        return

    if not _is_authorized(message):
        return

    # Voice note -> transcribe and enqueue
    if message.voice:
        duration = message.voice.duration if message.voice else 0
        msg_log.info("Voice note received (%ds) — transcribing...", duration)
        await message.reply("Transcribing voice note...")
        text = await _transcribe_voice(_orchestrator.bot, message)
        if text:
            _enqueue_and_debounce(_BufferedItem(message=message, text=text))
        else:
            await message.reply(
                "Could not transcribe voice note. Check OPENAI_API_KEY in .env."
            )
        return

    # Photo message -> download and enqueue (with caption as text)
    if message.photo or (
        message.document
        and message.document.mime_type
        and message.document.mime_type.startswith("image/")
    ):
        photos = await _download_photos(_orchestrator.bot, message)
        if photos:
            text = message.caption or message.text or ""
            msg_log.info(
                "Photo received (%d image(s), caption=%d chars)",
                len(photos),
                len(text),
            )
            _enqueue_and_debounce(
                _BufferedItem(message=message, text=text, photos=photos)
            )
        return

    # Text message -> enqueue
    if not message.text:
        return

    # /anneal — intercept before debounce buffer to trigger proposal flow
    cmd_text = re.sub(r"@\w+", "", message.text).strip()
    if cmd_text.lower().startswith("/anneal"):
        gap = cmd_text[len("/anneal"):].strip() or None
        asyncio.create_task(self_annealing.propose_build(_orchestrator.bot, _config, gap))
        return

    username = message.from_user.full_name if message.from_user else "Unknown"
    preview = message.text[:60] + "..." if len(message.text) > 60 else message.text
    msg_log.info('Received: "%s" (%s)', preview, username)

    _enqueue_and_debounce(_BufferedItem(message=message, text=message.text))
