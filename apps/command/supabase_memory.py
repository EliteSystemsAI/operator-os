"""
supabase_memory.py — Supabase-backed memory for the Telegram bot.

Provides:
- log_message(session_id, role, content) — save a conversation turn
- get_recent_messages(session_id, limit) — fetch recent turns for context
- save_session_summary(summary, workflow) — write a mid-term summary
- get_recent_summaries(n) — fetch last n summaries for context injection
- get_business_context() — fetch all business_context rows as dict
- create_workflow_log(workflow, input_data, analysis, action) — log a workflow run
- get_pending_approvals() — fetch workflow_logs where pending and not yet decided
- set_approval(log_id, approved, telegram_message_id) — record approval decision
"""
import os, json, logging
import requests
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_SUPABASE_URL: str = ""
_SUPABASE_KEY: str = ""
_BIZ_CONTEXT_CACHE: dict = {}


def init(supabase_url: str, supabase_key: str) -> None:
    global _SUPABASE_URL, _SUPABASE_KEY
    _SUPABASE_URL = supabase_url
    _SUPABASE_KEY = supabase_key


def _headers() -> dict:
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _get(path: str, params: dict = None) -> list:
    r = requests.get(
        f"{_SUPABASE_URL}/rest/v1/{path}",
        headers=_headers(),
        params=params,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(
        f"{_SUPABASE_URL}/rest/v1/{path}",
        headers=_headers(),
        json=body,
        timeout=10,
    )
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) and result else {}


def _patch(path: str, params: dict, body: dict) -> None:
    r = requests.patch(
        f"{_SUPABASE_URL}/rest/v1/{path}",
        headers=_headers(),
        params=params,
        json=body,
        timeout=10,
    )
    r.raise_for_status()


# --- Short-term memory --------------------------------------------------------

def log_message(session_id: str, role: str, content: str) -> None:
    """Save a single conversation turn to Supabase."""
    try:
        _post("bot_messages", {"session_id": session_id, "role": role, "content": content})
    except Exception as e:
        log.warning(f"supabase_memory.log_message failed: {e}")


def get_recent_messages(session_id: str, limit: int = 20) -> list[dict]:
    """Return recent messages for a session, oldest first."""
    try:
        rows = _get(
            "bot_messages",
            params={
                "session_id": f"eq.{session_id}",
                "order": "created_at.asc",
                "limit": limit,
            },
        )
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    except Exception as e:
        log.warning(f"supabase_memory.get_recent_messages failed: {e}")
        return []


# --- Mid-term memory ----------------------------------------------------------

def save_session_summary(summary: str, workflow: str = "chat") -> str | None:
    """Save a session summary. Returns the new session id."""
    try:
        row = _post("bot_sessions", {"summary": summary, "workflow": workflow})
        return row.get("id")
    except Exception as e:
        log.warning(f"supabase_memory.save_session_summary failed: {e}")
        return None


def get_recent_summaries(n: int = 5) -> list[str]:
    """Return the last n session summaries as plain text strings."""
    try:
        rows = _get(
            "bot_sessions",
            params={"order": "created_at.desc", "limit": n},
        )
        return [r["summary"] for r in reversed(rows)]  # oldest first
    except Exception as e:
        log.warning(f"supabase_memory.get_recent_summaries failed: {e}")
        return []


# --- Long-term memory ---------------------------------------------------------

def get_business_context() -> dict[str, str]:
    """Return all business_context rows as a key->value dict."""
    try:
        rows = _get("business_context", params={"order": "key.asc"})
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        log.warning(f"supabase_memory.get_business_context failed: {e}")
        return {}


def upsert_business_context(key: str, value: str) -> None:
    """Upsert a single key in business_context."""
    try:
        r = requests.post(
            f"{_SUPABASE_URL}/rest/v1/business_context",
            headers={**_headers(), "Prefer": "resolution=merge-duplicates"},
            json={"key": key, "value": value},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        log.warning(f"supabase_memory.upsert_business_context failed: {e}")


# --- Workflow logs ------------------------------------------------------------

def create_workflow_log(
    workflow: str,
    input_data: dict,
    claude_analysis: str,
    action_taken: str,
    telegram_message_id: int | None = None,
) -> str | None:
    """Create a workflow log entry. Returns the log id."""
    try:
        row = _post(
            "workflow_logs",
            {
                "workflow": workflow,
                "input_data": input_data,
                "claude_analysis": claude_analysis,
                "action_taken": action_taken,
                "pending_approval": True,
                "approved": None,
                "telegram_message_id": telegram_message_id,
            },
        )
        return row.get("id")
    except Exception as e:
        log.warning(f"supabase_memory.create_workflow_log failed: {e}")
        return None


def update_workflow_telegram_message_id(log_id: str, telegram_message_id: int) -> None:
    """After sending the Telegram approval message, record its message_id."""
    try:
        _patch(
            "workflow_logs",
            params={"id": f"eq.{log_id}"},
            body={"telegram_message_id": telegram_message_id},
        )
    except Exception as e:
        log.warning(f"supabase_memory.update_workflow_telegram_message_id failed: {e}")


def get_pending_approvals() -> list[dict]:
    """Return workflow_logs where pending_approval=TRUE and approved IS NULL."""
    try:
        return _get(
            "workflow_logs",
            params={
                "pending_approval": "eq.true",
                "approved": "is.null",
                "order": "ran_at.desc",
                "limit": 10,
            },
        )
    except Exception as e:
        log.warning(f"supabase_memory.get_pending_approvals failed: {e}")
        return []


def set_approval(log_id: str, approved: bool) -> None:
    """Record approval or rejection decision for a workflow log."""
    try:
        _patch(
            "workflow_logs",
            params={"id": f"eq.{log_id}"},
            body={
                "approved": approved,
                "pending_approval": False,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        log.warning(f"supabase_memory.set_approval failed: {e}")


# --- Time savings tracking ----------------------------------------------------

def log_time_savings(
    client_name: str,
    system_name: str,
    hours_per_week: float,
    weeks_active: float = 0,
    delivered_at: str | None = None,
    clickup_task_id: str | None = None,
) -> str | None:
    """Log a delivered system and its estimated weekly hours saved. Returns the new row id.

    If clickup_task_id is provided, also posts a comment on that ClickUp task
    summarising the time savings logged. Import is lazy so a missing clickup
    dependency never breaks the bot.
    """
    try:
        body: dict = {
            "client_name": client_name,
            "system_name": system_name,
            "hours_per_week": hours_per_week,
            "weeks_active": weeks_active,
        }
        if delivered_at:
            body["delivered_at"] = delivered_at
        row = _post("time_savings", body)
        row_id = row.get("id")

        # Mirror the log entry to ClickUp as a comment (lazy import — never raises)
        try:
            import sys
            import os
            # Ensure ops/ is importable regardless of working directory
            _ops_dir = os.path.join(os.path.dirname(__file__), "..", "..")
            if _ops_dir not in sys.path:
                sys.path.insert(0, _ops_dir)
            from ops import clickup  # noqa: PLC0415

            task_id = clickup_task_id
            if not task_id:
                # Try to find an existing task for this client in LIST_PROJECTS
                match = clickup.find_task_by_name(clickup.LIST_PROJECTS, client_name)
                if match:
                    task_id = match.get("id")

            if task_id:
                comment = (
                    f"Time savings logged: {system_name} for {client_name} "
                    f"— {hours_per_week}h/week saved. "
                    f"Supabase row id: {row_id}"
                )
                clickup.add_comment(task_id, comment)
            else:
                log.warning(
                    "supabase_memory.log_time_savings: no ClickUp task found for %s",
                    client_name,
                )
        except Exception as cu_err:
            log.warning("supabase_memory.log_time_savings ClickUp comment failed: %s", cu_err)

        return row_id
    except Exception as e:
        log.warning(f"supabase_memory.log_time_savings failed: {e}")
        return None


def get_time_savings_total() -> dict:
    """Return aggregate totals from time_savings_summary view.

    Returns a dict with keys: total_hours_saved, total_clients, total_systems.
    Falls back to zeros on error.
    """
    try:
        rows = _get("time_savings_summary", params={"select": "*"})
        if rows:
            row = rows[0]
            return {
                "total_hours_saved": float(row.get("total_hours_saved") or 0),
                "total_clients": int(row.get("total_clients") or 0),
                "total_systems": int(row.get("total_systems") or 0),
            }
    except Exception as e:
        log.warning(f"supabase_memory.get_time_savings_total failed: {e}")
    return {"total_hours_saved": 0.0, "total_clients": 0, "total_systems": 0}
