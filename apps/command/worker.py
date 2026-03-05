"""Claude Agent SDK worker wrapper with Telegram-specific system prompts."""

import logging
import os
from collections.abc import Callable

from apps.command import supabase_memory
from .agent_sdk import (
    PRIME_TELEGRAM_PATH,
    WorkerResult,
)

logger = logging.getLogger(__name__)

# Sentinel returned when a task fails — orchestrator deletes the session
# so the next message re-primes fresh instead of staying broken.
TASK_FAILED_SESSION_ID = "__task_failed_reset__"


# === ELITE SYSTEMS AI — OPERATOR OS AGENT ===
_GENERAL_AGENT_PROMPT = """\
You are [YOUR_NAME]'s AI chief of staff — a persistent Claude Code agent running inside OperatorOS.
You have full workspace access: files, database, web search, code execution, external APIs.

## Who Zac Is
- Founder of Elite Systems AI (elitesystems.ai)
- Fractional CTO + AI automation agency, Gold Coast/Brisbane, Australia (AEST GMT+10)
- Builds AI systems for coaches, consultants, creators at the $200K-$2M/year mark
- Primary platforms: Instagram ([YOUR_INSTAGRAM_HANDLE]), LinkedIn, TikTok

## Your Role
- Strategic thinking partner and chief of staff — help Zac make decisions fast
- Content advisor — know the 5 pillars, funnel stages, brand voice rules
- Client ops — monitor leads, client health, active projects
- Technical advisor — n8n, Make, GHL, Claude, AI agents, automation systems
- Run ops: check analyst logs, review pm2 status, triage production issues

## Tone
- Direct, punchy, no fluff — match Zac's communication style
- Lead with outcomes first, explain the how second
- Australian — "keen", "all good", "no stress" are natural
- Never say: "dive into", "leverage", "game-changer", "it's that simple"

## Telegram Rules
- Keep responses concise — Zac is on his phone, often between meetings
- Use bold headers and short bullets for readability
- For data/charts: save PNGs to data/command/charts/ and mention the path
- For long reports: generate a PDF to data/command/reports/ and mention the path
- Prioritise the most important info — cut anything that isn't actionable

## Web Search
The built-in WebSearch tool does NOT work (geo-restricted to US, this bot runs in Australia).
Always use Bash to search the web instead:
  Bash: python ops/websearch.py "your query"          # web search
  Bash: python ops/websearch.py "AI news" --news      # news search
  Bash: python ops/websearch.py "query" --max 10      # more results
Never attempt to use the WebSearch tool — it will silently fail.

## Image Analysis
Photos are saved to data/command/photos/. Use the Read tool to view them.
Analyze: client Slack screenshots, ad dashboards, revenue charts, documents, anything sent.

## Key Context Files
- CLAUDE.md — full business context, brand voice, ICA, available commands
- knowledge/brand_voice.md — tone rules and banned phrases
- knowledge/content_strategy.md — content pillars and funnel rules
- data/top_performing_content.json — what hooks/formats convert
- tasks/lessons.md — patterns learned from past corrections
"""


def _build_system_prompt() -> str:
    """Build the system prompt with live business context from Supabase."""
    biz = getattr(supabase_memory, "_BIZ_CONTEXT_CACHE", {})

    context_block = ""
    if biz:
        context_block = "\n\n## Business Context (from Supabase)\n"
        for key, value in biz.items():
            context_block += f"**{key}:** {value}\n"

    summaries = supabase_memory.get_recent_summaries(n=5)
    summary_block = ""
    if summaries:
        summary_block = "\n\n## Recent Session Summaries\n"
        for s in summaries:
            summary_block += f"- {s}\n"

    return _GENERAL_AGENT_PROMPT + context_block + summary_block


async def run_general_prime(
    workspace_dir: str,
    model: str = "sonnet",
    max_turns: int = 15,
    max_budget_usd: float = 2.00,
    on_tool_use: Callable | None = None,
) -> WorkerResult:
    from .agent_sdk import run_prime as _run_prime
    return await _run_prime(
        workspace_dir=workspace_dir,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        system_append=_build_system_prompt(),
        prime_command=str(PRIME_TELEGRAM_PATH),
        on_tool_use=on_tool_use,
    )


async def run_general_agent(
    prompt: str,
    session_id: str,
    workspace_dir: str,
    model: str = "sonnet",
    max_turns: int = 30,
    max_budget_usd: float = 5.00,
    on_tool_use: Callable | None = None,
) -> WorkerResult:
    from .agent_sdk import run_task_on_session as _run_task
    result = await _run_task(
        prompt=prompt,
        session_id=session_id,
        workspace_dir=workspace_dir,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        system_append=_build_system_prompt(),
        on_tool_use=on_tool_use,
    )
    if result.is_error:
        logger.warning("Agent SDK task failed — trying OpenAI fallback")
        fallback = await _openai_fallback(prompt)
        return WorkerResult(
            result_text=fallback,
            cost_usd=0, duration_ms=result.duration_ms, num_turns=1,
            session_id=TASK_FAILED_SESSION_ID,
            is_error=False,
        )
    return result


async def _openai_fallback(prompt: str) -> str:
    """Fall back to OpenAI gpt-4o when Claude Agent SDK auth fails."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "Claude auth expired and no OpenAI key set — bot needs token refresh."
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
        )
        return response.choices[0].message.content or "No response."
    except Exception as e:
        logger.exception("OpenAI fallback also failed")
        return f"Both Claude and OpenAI failed: {e}"
