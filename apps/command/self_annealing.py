"""Self-annealing loop — OperatorOS proposes and builds its own capability improvements.

Two-phase flow:
  Phase 1 (propose): CC agent audits codebase → writes proposal JSON → posts to Telegram with approval buttons
  Phase 2 (build):   On approval, CC agent reads proposal from Supabase → writes files → reports result
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.command import supabase_memory

log = logging.getLogger(__name__)


# ── Prompts ───────────────────────────────────────────────────────────────────

_PROPOSAL_PROMPT = """\
You are the OperatorOS self-improvement engine. Your job is to identify ONE capability gap \
and write a structured proposal.

Step 1 — Audit current capabilities:
- Read apps/command/orchestrator.py → look at _SLASH_COMMANDS dict (list all keys)
- Glob .claude/skills/**/*.md → read each skill's name and description frontmatter
- Glob ops/*.py → list existing helper scripts
- Read tasks/lessons.md → look for recurring errors, gaps, or friction points
- Glob data/anneal/proposals/*.json → read recent proposals (avoid duplicating them)

Step 2 — Identify the single most valuable missing capability.
Priority order:
  1. Missing slash commands for things Zac repeatedly asks for manually
  2. Missing skills for multi-step workflows that are currently done ad-hoc
  3. Missing ops scripts for recurring automation tasks
  4. Bug fixes or improvements to reduce known recurring errors from tasks/lessons.md

Step 3 — Write a proposal JSON to data/anneal/proposals/{timestamp}.json where {timestamp} \
is the current UTC timestamp in format YYYYMMDD_HHMMSS. The JSON must have these fields:
{
  "timestamp": "<ISO 8601 UTC>",
  "gap": "<What capability is missing — 1 clear sentence>",
  "type": "<one of: skill | command | ops_script | fix>",
  "value": "<Why this matters to Zac — what it enables or eliminates>",
  "files": [{"path": "<relative path>", "action": "<create|modify>", "description": "<what goes in this file>"}],
  "build_prompt": "<Complete verbatim prompt for the build agent — include exact file paths, full content spec, and implementation details. The build agent reads ONLY this field — be exhaustive.>"
}

Step 4 — Output ONLY this block and nothing else before or after it:
---PROPOSAL---
Gap: [gap in one sentence]
Type: [skill|command|ops_script|fix]
Value: [why this matters]
Files: [comma-separated relative file paths]
---END---
"""

_PROPOSAL_PROMPT_WITH_GAP = _PROPOSAL_PROMPT + "\n\nIMPORTANT: Focus specifically on this gap described by Zac: {gap_description}"

_BUILD_PROMPT_TEMPLATE = """\
Execute this OperatorOS capability build. Write all files exactly as specified in the proposal.

LOCKED — do NOT touch these files under any circumstances:
  bot.py, config.py, session_manager.py, worker.py, agent_sdk.py, supabase_memory.py, self_annealing.py

ALLOWED to create or modify:
  .claude/skills/**  — new skill folders and skill.md files (no restart needed)
  ops/*.py           — new helper scripts (no restart needed)
  knowledge/*.md     — new knowledge files (no restart needed)
  apps/command/orchestrator.py — ONLY the _SLASH_COMMANDS dict (restart needed)

Skill format: YAML front matter with name + description fields, then markdown steps.
The description field is critical — it must include specific trigger phrases users would say.

BUILD SPECIFICATION:
{build_prompt}

AFTER writing all files:
1. Run `python -m py_compile <path>` via Bash for every .py file you created or modified
2. List all files you created or modified (full relative paths from workspace root)
3. End your response with exactly one of these markers on its own line:
   NEEDS_RESTART   ← if any file inside apps/command/ was modified
   NO_RESTART      ← if only .claude/skills/, ops/, knowledge/ files were written
"""


# ── Core implementation ───────────────────────────────────────────────────────

async def _do_propose(
    bot: Bot,
    group_id: int,
    workspace_dir: str,
    self_anneal_thread_id: int | None,
    gap_description: str | None,
) -> None:
    """Core proposal logic — runs the audit agent, stores in Supabase, sends Telegram card."""
    from .agent_sdk import run_worker

    thread_id = self_anneal_thread_id  # None = main group thread

    # Status message
    try:
        await bot.send_message(
            chat_id=group_id,
            message_thread_id=thread_id,
            text="🔍 Scanning codebase for capability gaps...",
        )
    except Exception:
        log.warning("Could not send anneal status message")

    # Build prompt
    if gap_description:
        prompt = _PROPOSAL_PROMPT_WITH_GAP.format(gap_description=gap_description)
    else:
        prompt = _PROPOSAL_PROMPT

    result = await run_worker(
        prompt=prompt,
        workspace_dir=workspace_dir,
        allowed_tools=["Read", "Glob", "Grep", "Write", "Bash"],
        max_turns=20,
        max_budget_usd=3.00,
    )

    if result.is_error:
        await bot.send_message(
            chat_id=group_id,
            message_thread_id=thread_id,
            text=f"❌ Proposal agent failed: {result.result_text[:300]}",
        )
        return

    # Parse ---PROPOSAL--- block from agent output
    proposal_text = result.result_text
    gap = type_ = value = files_str = ""
    m = re.search(r"---PROPOSAL---\s*\n(.*?)---END---", proposal_text, re.DOTALL)
    if m:
        block = m.group(1)
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("Gap:"):
                gap = line[4:].strip()
            elif line.startswith("Type:"):
                type_ = line[5:].strip()
            elif line.startswith("Value:"):
                value = line[6:].strip()
            elif line.startswith("Files:"):
                files_str = line[6:].strip()

    # Also try to load the JSON the agent wrote
    proposals_dir = Path(workspace_dir) / "data" / "anneal" / "proposals"
    proposal_dict: dict = {}
    if proposals_dir.exists():
        jsons = sorted(proposals_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if jsons:
            import json
            try:
                proposal_dict = json.loads(jsons[0].read_text(encoding="utf-8"))
            except Exception:
                pass

    # Merge parsed fields into dict (agent output takes priority over parsed block)
    if not proposal_dict:
        proposal_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gap": gap,
            "type": type_,
            "value": value,
            "files": [{"path": p.strip(), "action": "create", "description": ""} for p in files_str.split(",") if p.strip()],
            "build_prompt": proposal_text,
        }
    else:
        # Fill in any missing fields from parsed block
        if not proposal_dict.get("gap") and gap:
            proposal_dict["gap"] = gap

    gap = proposal_dict.get("gap", "Unknown capability gap")
    type_ = proposal_dict.get("type", "unknown")
    value = proposal_dict.get("value", "")
    files = proposal_dict.get("files", [])

    # Store in Supabase
    log_id = supabase_memory.create_workflow_log(
        workflow="anneal",
        input_data=proposal_dict,
        claude_analysis=gap,
        action_taken="Build on approval",
    )

    if not log_id:
        await bot.send_message(
            chat_id=group_id,
            message_thread_id=thread_id,
            text=f"⚠️ Proposal scanned but Supabase log failed.\n\nGap: {gap}",
        )
        return

    # Format proposal card
    files_lines = "\n".join(f"• {f['path']} ({f['action']})" for f in files) if files else "• (see build_prompt)"
    msg = (
        f"🔧 <b>Self-Build Proposal</b>\n\n"
        f"<b>Gap:</b> {gap}\n"
        f"<b>Type:</b> {type_}\n"
        f"<b>Value:</b> {value}\n\n"
        f"<b>Files:</b>\n{files_lines}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Build it", callback_data=f"approve_anneal_{log_id}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_anneal_{log_id}"),
    ]])

    try:
        sent = await bot.send_message(
            chat_id=group_id,
            message_thread_id=thread_id,
            text=msg,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        supabase_memory.update_workflow_telegram_message_id(log_id, sent.message_id)
    except Exception:
        log.exception("Failed to send anneal proposal to Telegram")


async def propose_build(bot: Bot, config, gap_description: str | None = None) -> None:
    """Trigger a capability gap proposal — called from /anneal command handler."""
    await _do_propose(
        bot=bot,
        group_id=config.group_id,
        workspace_dir=config.workspace_dir,
        self_anneal_thread_id=config.self_anneal_thread_id,
        gap_description=gap_description,
    )


async def propose_build_with_config(
    bot: Bot,
    group_id: int,
    workspace_dir: str,
    self_anneal_thread_id: int | None,
    gap_description: str | None = None,
) -> None:
    """Called from the daily scheduler job (no Config object available)."""
    await _do_propose(
        bot=bot,
        group_id=group_id,
        workspace_dir=workspace_dir,
        self_anneal_thread_id=self_anneal_thread_id,
        gap_description=gap_description,
    )


async def execute_build(log_id: str, bot: Bot, config) -> None:
    """Execute an approved capability build — called from the callback approval handler."""
    from .agent_sdk import run_worker

    thread_id = config.self_anneal_thread_id

    try:
        await bot.send_message(
            chat_id=config.group_id,
            message_thread_id=thread_id,
            text="🔨 Building...",
        )
    except Exception:
        log.warning("Could not send build status message")

    # Fetch proposal from Supabase
    try:
        logs = supabase_memory._get("workflow_logs", params={"id": f"eq.{log_id}"})
        proposal_dict = logs[0].get("input_data", {}) if logs else {}
    except Exception:
        proposal_dict = {}

    build_prompt = proposal_dict.get("build_prompt", "")
    if not build_prompt:
        await bot.send_message(
            chat_id=config.group_id,
            message_thread_id=thread_id,
            text="❌ Build failed — no build_prompt found in proposal.",
        )
        return

    full_prompt = _BUILD_PROMPT_TEMPLATE.format(build_prompt=build_prompt)

    result = await run_worker(
        prompt=full_prompt,
        workspace_dir=config.workspace_dir,
        allowed_tools=["Read", "Glob", "Grep", "Write", "Edit", "Bash"],
        max_turns=30,
        max_budget_usd=5.00,
    )

    if result.is_error:
        await bot.send_message(
            chat_id=config.group_id,
            message_thread_id=thread_id,
            text=f"❌ Build failed — {result.result_text[:300]}",
        )
        return

    output = result.result_text

    # Extract file list from agent output (lines starting with bullet/path markers)
    file_lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("•") or stripped.startswith("-") or stripped.startswith("*"):
            candidate = stripped.lstrip("•-* ").strip()
            # Looks like a file path if it contains a slash and no spaces
            if "/" in candidate and " " not in candidate.split("/")[-1]:
                file_lines.append(f"• {candidate}")
    files_summary = "\n".join(file_lines[:20]) if file_lines else "(see agent output above)"

    needs_restart = "NEEDS_RESTART" in output
    no_restart = "NO_RESTART" in output

    if needs_restart:
        msg = (
            f"✅ <b>Build complete</b> — Python files changed.\n"
            f"Reply /reboot to apply changes.\n\n"
            f"<b>Modified:</b>\n{files_summary}"
        )
    elif no_restart:
        msg = (
            f"✅ <b>Build complete</b> — live immediately.\n\n"
            f"<b>Created:</b>\n{files_summary}"
        )
    else:
        # No explicit marker — show output summary
        msg = (
            f"✅ <b>Build complete</b>\n\n"
            f"<b>Files:</b>\n{files_summary}\n\n"
            f"<i>No restart marker found — check if changes need /reboot</i>"
        )

    try:
        await bot.send_message(
            chat_id=config.group_id,
            message_thread_id=thread_id,
            text=msg,
            parse_mode="HTML",
        )
    except Exception:
        log.exception("Failed to send build result to Telegram")
