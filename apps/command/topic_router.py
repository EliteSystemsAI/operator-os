"""
Telegram topic auto-discovery and intelligent message routing.

Topics are self-registering — the bot learns them when:
1. A forum_topic_created service message arrives (new topic)
2. Any message arrives in an unknown topic (existing topic, unknown name)

Topic name → thread_id mapping stored in Supabase telegram_topics table.
Routing uses keyword matching on topic name to decide where scheduled
messages (morning ping, content digest, etc.) should go.
"""

import logging
import os
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

log = logging.getLogger(__name__)

# In-memory cache: thread_id (int) → topic name (str)
_TOPIC_CACHE: dict[int, str] = {}
# Reverse: normalised name fragment → thread_id
_NAME_INDEX: dict[str, int] = {}


# ── Supabase persistence ──────────────────────────────────────────────────────

def _sb_headers() -> dict:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _sb_url(path: str) -> str:
    return f"{os.getenv('SUPABASE_URL', '')}/rest/v1/{path}"


def load_topics_from_supabase() -> dict[int, str]:
    """Load all known topics into cache. Call on bot startup."""
    try:
        r = requests.get(
            _sb_url("telegram_topics"),
            headers=_sb_headers(),
            params={"select": "thread_id,name", "limit": "200"},
            timeout=10,
        )
        if not r.ok:
            log.warning("topic_router: failed to load topics: %s", r.text[:200])
            return {}
        rows = r.json()
        for row in rows:
            _register(row["thread_id"], row["name"], persist=False)
        log.info("topic_router: loaded %d topics from Supabase", len(rows))
        return _TOPIC_CACHE.copy()
    except Exception as e:
        log.warning("topic_router: load error: %s", e)
        return {}


def _register(thread_id: int, name: str, persist: bool = True) -> None:
    """Add or update a topic in cache (and optionally Supabase)."""
    _TOPIC_CACHE[thread_id] = name
    # Index normalised words for fuzzy matching
    for word in name.lower().split():
        _NAME_INDEX[word] = thread_id

    if not persist:
        return
    try:
        requests.post(
            _sb_url("telegram_topics"),
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates"},
            json={
                "thread_id": thread_id,
                "name": name,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=10,
        )
        log.info("topic_router: registered topic %d → '%s'", thread_id, name)
    except Exception as e:
        log.warning("topic_router: persist error: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

def on_topic_created(thread_id: int, name: str) -> None:
    """Call when a forum_topic_created service message arrives."""
    _register(thread_id, name)


def on_message_in_topic(thread_id: int, topic_name_hint: str | None = None) -> None:
    """
    Call for every incoming message that has a thread_id.
    If we haven't seen this topic before and a name hint is available, register it.
    """
    if thread_id not in _TOPIC_CACHE:
        if topic_name_hint:
            _register(thread_id, topic_name_hint)
        else:
            # Unknown topic — store with placeholder until we get the real name
            _register(thread_id, f"topic_{thread_id}")


def find_topic(query: str) -> int | None:
    """
    Find the best matching thread_id for a routing query like 'content', 'sales', 'morning'.
    Returns thread_id or None if no confident match.
    """
    if not _TOPIC_CACHE:
        return None

    query_words = query.lower().split()

    # Exact word match first
    for word in query_words:
        if word in _NAME_INDEX:
            return _NAME_INDEX[word]

    # Fuzzy match against full topic names
    best_score = 0.0
    best_id = None
    for thread_id, name in _TOPIC_CACHE.items():
        score = SequenceMatcher(None, query.lower(), name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_id = thread_id

    if best_score > 0.4:
        return best_id
    return None


def get_all_topics() -> dict[int, str]:
    """Return all known topics."""
    return _TOPIC_CACHE.copy()


def route_for(purpose: str) -> int | None:
    """
    Route a scheduled message to the right topic based on purpose.
    Examples: 'morning', 'content', 'clients', 'revenue', 'anneal'
    Falls back to None (sends to group root) if no match.
    """
    return find_topic(purpose)
