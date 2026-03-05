"""Persistent conversation memory for OperatorOS Telegram bot.

Each Telegram topic gets its own JSONL log at data/command/memory/{topic_key}.jsonl.
Turns are appended on every successful agent response and loaded when a new
session starts — giving the agent context from previous conversations.
"""

import fcntl
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("memory")

_MEMORY_DIR = "data/command/memory"
_MAX_TURNS_TO_LOAD = 20   # how many past turns to inject on session start
_MAX_USER_CHARS = 1500    # cap per user message stored (avoid bloat)
_MAX_AGENT_CHARS = 2500   # cap per agent response stored
_MAX_INJECT_CHARS = 10000 # hard cap on total injected history


def _safe_key(topic_key: str) -> str:
    """Convert topic_key to a safe filename component."""
    return topic_key.replace("/", "_").replace(":", "_").replace("-", "_")[:50]


def _log_path(workspace_dir: str, topic_key: str) -> Path:
    return Path(workspace_dir) / _MEMORY_DIR / f"{_safe_key(topic_key)}.jsonl"


def log_turn(
    workspace_dir: str,
    topic_key: str,
    user_msg: str,
    assistant_response: str,
) -> None:
    """Append a conversation turn to the topic's memory log.

    Silently ignores errors — memory logging should never break the bot.
    """
    try:
        path = _log_path(workspace_dir, topic_key)
        path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "user": user_msg[:_MAX_USER_CHARS],
            "agent": assistant_response[:_MAX_AGENT_CHARS],
        }

        with open(path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    except Exception:
        log.exception("Failed to log turn for topic %s", topic_key)


def get_recent_context(
    workspace_dir: str,
    topic_key: str,
    max_turns: int = _MAX_TURNS_TO_LOAD,
) -> str | None:
    """Load recent conversation history as a formatted string for injection.

    Returns None if no history exists or loading fails.
    The returned string is prepended to the first user message of a new
    session so the agent has context from previous conversations.
    """
    try:
        path = _log_path(workspace_dir, topic_key)
        if not path.exists():
            return None

        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None

        lines = raw.splitlines()
        recent_lines = lines[-max_turns:]

        turns = []
        for line in recent_lines:
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if not turns:
            return None

        parts = [
            "## Previous Conversation Context\n"
            "_Loaded from memory — new session starting, but here's what we last discussed:_\n"
        ]

        total_chars = 0
        for t in turns:
            ts = t.get("ts", "")
            user = t.get("user", "").strip()
            agent = t.get("agent", "").strip()

            block = f"**[{ts}] Zac:** {user}\n**Agent:** {agent}\n"
            if total_chars + len(block) > _MAX_INJECT_CHARS:
                parts.append("_...earlier history truncated to fit context_\n")
                break
            parts.append(block)
            total_chars += len(block)

        parts.append("---\n_End of history. Continue naturally from here._\n")

        result = "\n".join(parts)
        log.info(
            "Injecting %d turns of history for topic %s (%d chars)",
            len(turns), topic_key, len(result),
        )
        return result

    except Exception:
        log.exception("Failed to load history for topic %s", topic_key)
        return None
