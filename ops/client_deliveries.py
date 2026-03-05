#!/usr/bin/env python3
"""
Elite Systems AI — Client Intelligence Pipeline

Core delivery pipeline:
  1. Find client's Working Doc in Google Drive
  2. Pull existing systems from Supabase (context for Claude)
  3. Generate next system suggestion via Claude API
  4. Append delivery entry to client's Google Doc
  5. Save record to Supabase client_systems table
  6. Return Telegram-formatted confirmation

Entry points:
  process_delivery(client_name, system_name, description, call_summary, source)
  get_client_snapshot(client_name)

Can be run standalone for testing:
  python ops/client_deliveries.py
"""

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# ── Credentials ───────────────────────────────────────────────────────────────


def load_env():
    import os
    env = dict(os.environ)
    for candidate in [
        Path(__file__).parent.parent / ".env",
        Path.home() / ".env",
    ]:
        if candidate.exists():
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            break
    return env


env = load_env()

SUPABASE_URL = env.get("SUPABASE_URL", "")
SUPABASE_KEY = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
ANTHROPIC_API_KEY = env.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")

# Google OAuth — loaded from env var (Railway) or token file (local)
_GOOGLE_CREDS_JSON = env.get("GOOGLE_TOKEN_JSON", "")
_GOOGLE_TOKEN_FILE = Path.home() / ".config" / "gspread" / "token.json"

AEST = timezone(timedelta(hours=10))

# ── Google OAuth helpers ──────────────────────────────────────────────────────


def _load_google_token() -> dict:
    """Load token dict from GOOGLE_TOKEN_JSON env var or local file."""
    if _GOOGLE_CREDS_JSON:
        return json.loads(_GOOGLE_CREDS_JSON)
    if _GOOGLE_TOKEN_FILE.exists():
        return json.loads(_GOOGLE_TOKEN_FILE.read_text())
    raise RuntimeError(
        "No Google credentials found. Set GOOGLE_TOKEN_JSON env var "
        "or ensure ~/.config/gspread/token.json exists."
    )


def _get_google_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    token_data = _load_google_token()
    access_token = token_data.get("token", "")

    # Check if token is still valid (expiry is ISO string)
    expiry_str = token_data.get("expiry", "")
    if expiry_str:
        try:
            # Remove trailing 'Z' and parse
            expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < expiry - timedelta(minutes=5):
                return access_token
        except ValueError:
            pass

    # Refresh the token
    r = requests.post(
        token_data["token_uri"],
        json={
            "client_id":     token_data["client_id"],
            "client_secret": token_data["client_secret"],
            "refresh_token": token_data["refresh_token"],
            "grant_type":    "refresh_token",
        },
        timeout=15,
    )
    r.raise_for_status()
    new_token = r.json()

    # Persist refreshed token locally if file exists
    if _GOOGLE_TOKEN_FILE.exists():
        token_data["token"] = new_token["access_token"]
        token_data["expiry"] = (
            datetime.now(timezone.utc) + timedelta(seconds=new_token["expires_in"])
        ).isoformat()
        _GOOGLE_TOKEN_FILE.write_text(json.dumps(token_data, indent=2))

    return new_token["access_token"]


def _google_headers() -> dict:
    return {"Authorization": f"Bearer {_get_google_access_token()}"}


# ── Supabase helpers ──────────────────────────────────────────────────────────


def _supabase_headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
    }


def _supabase_get(table: str, params: dict) -> list:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers=_supabase_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _supabase_post(table: str, payload: dict, upsert_on: str | None = None) -> dict:
    headers = _supabase_headers()
    if upsert_on:
        headers["Prefer"] = f"resolution=merge-duplicates,return=representation"
        url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={upsert_on}"
    else:
        headers["Prefer"] = "return=representation"
        url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) and result else result


# ── Google Drive / Docs helpers ───────────────────────────────────────────────


def find_client_doc(client_name: str) -> str | None:
    """
    Search Google Drive for '[client_name] - Working Doc'.
    Returns the file ID or None if not found.
    Falls back to client_profiles table in Supabase if Drive search fails.
    """
    # Try Supabase cache first (fast)
    try:
        rows = _supabase_get("client_profiles", {
            "client_name": f"eq.{client_name}",
            "select": "gdrive_doc_id",
        })
        if rows and rows[0].get("gdrive_doc_id"):
            return rows[0]["gdrive_doc_id"]
    except Exception:
        pass

    # Drive full-text search
    try:
        query = f"name contains '{client_name}' and name contains 'Working Doc' and mimeType = 'application/vnd.google-apps.document'"
        r = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            params={"q": query, "fields": "files(id,name)", "pageSize": "5"},
            headers=_google_headers(),
            timeout=15,
        )
        r.raise_for_status()
        files = r.json().get("files", [])
        if files:
            doc_id = files[0]["id"]
            # Cache in Supabase for next time
            try:
                _supabase_post("client_profiles", {
                    "client_name": client_name,
                    "gdrive_doc_id": doc_id,
                }, upsert_on="client_name")
            except Exception:
                pass
            return doc_id
    except Exception as e:
        print(f"  [Drive search error] {e}")

    return None


def get_client_systems(client_name: str) -> list[dict]:
    """Fetch all previously delivered systems from Supabase, newest first."""
    try:
        return _supabase_get("client_systems", {
            "client_name": f"eq.{client_name}",
            "order": "delivered_date.desc",
            "limit": "20",
            "select": "system_name,description,platform,delivered_date,next_suggestion",
        })
    except Exception as e:
        print(f"  [Supabase fetch error] {e}")
        return []


def get_client_profile(client_name: str) -> dict | None:
    """Fetch full client profile from Supabase."""
    try:
        rows = _supabase_get("client_profiles", {
            "client_name": f"eq.{client_name}",
        })
        return rows[0] if rows else None
    except Exception:
        return None


# ── Claude suggestion generator ───────────────────────────────────────────────


def generate_next_suggestion(
    client_name: str,
    systems_built: list[dict],
    call_summary: str = "",
) -> str:
    """
    Call Claude API to suggest the next best system for this client,
    given what's already been built and any call transcript context.
    """
    if not ANTHROPIC_API_KEY:
        return "No ANTHROPIC_API_KEY set — suggestion unavailable."

    systems_list = "\n".join(
        f"- {s['system_name']} ({s.get('platform', '?')}) — {s.get('delivered_date', '?')}"
        for s in systems_built
    ) or "No systems delivered yet."

    prompt = f"""You are an AI systems advisor for Elite Systems AI (fractional CTO + automation agency).

Client: {client_name}
Systems already built:
{systems_list}

Call context / transcript summary:
{call_summary or "(No call summary provided)"}

Based on what's been built and any context from the call, suggest the single most impactful next system to build for this client. Keep it to 2-3 sentences max. Be specific and direct — name the system, the platform (GHL, n8n, Railway, etc.), and the business outcome it unlocks."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-6",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        return f"Suggestion unavailable: {e}"


# ── Google Docs append ────────────────────────────────────────────────────────


def append_to_client_doc(
    doc_id: str,
    system_name: str,
    description: str,
    platform: str,
    next_suggestion: str,
    source: str,
) -> bool:
    """
    Append a formatted delivery entry to the client's Google Doc.
    Uses the Docs API batchUpdate → insertText at the end of the document.
    """
    today = date.today().strftime("%-d %b %Y")

    content = (
        f"\n\n---\n"
        f"✅ {system_name} — {today}\n"
        f"Platform: {platform or 'TBD'}\n"
        f"What it does: {description or 'See call notes.'}\n"
        f"Source: {source}\n"
        f"Next suggested system: {next_suggestion}\n"
        f"---"
    )

    try:
        # Get current document end index
        r = requests.get(
            f"https://docs.googleapis.com/v1/documents/{doc_id}",
            params={"fields": "body.content"},
            headers=_google_headers(),
            timeout=15,
        )
        r.raise_for_status()
        doc = r.json()

        # Find end index (last element's endIndex - 1 to avoid trailing newline)
        body_content = doc.get("body", {}).get("content", [])
        end_index = 1
        for element in body_content:
            end_index = max(end_index, element.get("endIndex", 1))
        # Insert before the final newline character
        insert_index = max(1, end_index - 1)

        # batchUpdate to insert text
        r2 = requests.post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            headers={**_google_headers(), "Content-Type": "application/json"},
            json={"requests": [{"insertText": {"location": {"index": insert_index}, "text": content}}]},
            timeout=15,
        )
        r2.raise_for_status()
        return True
    except Exception as e:
        print(f"  [Docs API error] {e}")
        return False


# ── Supabase write ────────────────────────────────────────────────────────────


def save_to_supabase(
    client_name: str,
    system_name: str,
    description: str,
    platform: str,
    source: str,
    call_summary: str,
    next_suggestion: str,
) -> str | None:
    """Write delivery record to client_systems. Returns the new record ID."""
    try:
        record = _supabase_post("client_systems", {
            "client_name":     client_name,
            "system_name":     system_name,
            "description":     description,
            "platform":        platform,
            "source":          source,
            "call_summary":    call_summary,
            "next_suggestion": next_suggestion,
            "delivered_date":  date.today().isoformat(),
        })
        return record.get("id")
    except Exception as e:
        print(f"  [Supabase write error] {e}")
        return None


# ── Main pipeline orchestrator ────────────────────────────────────────────────


def process_delivery(
    client_name: str,
    system_name: str,
    description: str = "",
    platform: str = "",
    call_summary: str = "",
    source: str = "manual",
) -> str:
    """
    Full delivery pipeline:
      1. Find client's Working Doc in Drive
      2. Get existing systems from Supabase (context for Claude)
      3. Generate Claude next suggestion
      4. Append entry to Google Doc
      5. Save to Supabase client_systems
    Returns a Telegram-formatted confirmation string.
    """
    print(f"\n[process_delivery] client={client_name!r} system={system_name!r} source={source}")

    # Step 1: Find Drive doc
    print("  → Looking up Google Drive doc...")
    doc_id = find_client_doc(client_name)
    doc_status = f"✅ Updated [{client_name} - Working Doc]" if doc_id else "⚠️ No Working Doc found in Drive"

    # Step 2: Get context
    print("  → Fetching existing systems from Supabase...")
    existing_systems = get_client_systems(client_name)

    # Step 3: Claude suggestion
    print("  → Generating Claude suggestion...")
    next_suggestion = generate_next_suggestion(client_name, existing_systems, call_summary)

    # Step 4: Append to Google Doc
    if doc_id:
        print("  → Appending to Google Doc...")
        doc_ok = append_to_client_doc(doc_id, system_name, description, platform, next_suggestion, source)
        if not doc_ok:
            doc_status = "⚠️ Drive write failed (check logs)"

    # Step 5: Save to Supabase
    print("  → Saving to Supabase...")
    record_id = save_to_supabase(
        client_name, system_name, description, platform, source, call_summary, next_suggestion
    )
    db_status = f"✅ Saved (ID: {record_id[:8]}...)" if record_id else "⚠️ DB write failed"

    today = datetime.now(AEST).strftime("%-d %b %Y")
    total_systems = len(existing_systems) + 1

    lines = [
        f"🚀 *System Delivered*",
        f"",
        f"👤 *Client:* {client_name}",
        f"⚙️ *System:* {system_name}",
        f"📅 *Date:* {today}",
        f"🔧 *Platform:* {platform or 'TBD'}",
        f"📊 *Total systems delivered:* {total_systems}",
        f"",
        f"💡 *Next suggested system:*",
        f"_{next_suggestion}_",
        f"",
        f"📁 {doc_status}",
        f"🗄️ {db_status}",
    ]
    if call_summary:
        lines.insert(4, f"📝 *From call:* {call_summary[:120]}{'...' if len(call_summary) > 120 else ''}")

    return "\n".join(lines)


# ── Client snapshot ───────────────────────────────────────────────────────────


def get_client_snapshot(client_name: str) -> str:
    """
    Return a Telegram-formatted full client snapshot:
    profile + all systems delivered + last suggestion.
    """
    systems = get_client_systems(client_name)
    profile = get_client_profile(client_name)

    if not systems and not profile:
        return f"❓ No data found for *{client_name}*. Check the spelling or add them to client_profiles."

    # Header
    lines = [f"👤 *{client_name}*"]
    if profile:
        if profile.get("business_type"):
            lines.append(f"📌 {profile['business_type']}")
        if profile.get("monthly_revenue"):
            lines.append(f"💰 MRR: {profile['monthly_revenue']}")
        if profile.get("slack_channel"):
            lines.append(f"💬 #{profile['slack_channel']}")
    lines.append("")

    # Systems list
    if systems:
        lines.append(f"⚙️ *Systems delivered ({len(systems)}):*")
        for s in systems:
            date_str = s.get("delivered_date", "?")
            platform = s.get("platform", "?")
            lines.append(f"  • {s['system_name']} ({platform}) — {date_str}")
        lines.append("")
        # Most recent suggestion
        latest = systems[0]
        if latest.get("next_suggestion"):
            lines.append(f"💡 *Last suggestion:*")
            lines.append(f"_{latest['next_suggestion']}_")
    else:
        lines.append("No systems delivered yet.")

    return "\n".join(lines)


# ── Standalone test ───────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("Elite Systems AI — Client Deliveries (standalone test)")
    print("=" * 60)

    # Validate credentials
    missing = []
    if not SUPABASE_URL:    missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:    missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not ANTHROPIC_API_KEY: missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"⚠️  Missing env vars: {', '.join(missing)}")
        print("   Add them to .env and retry.")
    else:
        print("✅ Credentials loaded")

    # Test with a demo client
    test_client = input("\nEnter client name to test (or press Enter for 'Test Client'): ").strip()
    if not test_client:
        test_client = "Test Client"

    test_system = input("Enter system name (or Enter for 'Lead Qualification Bot'): ").strip()
    if not test_system:
        test_system = "Lead Qualification Bot"

    result = process_delivery(
        client_name=test_client,
        system_name=test_system,
        description="Automated DM qualification via GHL workflow + AI response tree",
        platform="GHL",
        call_summary="Client wants to reduce time spent qualifying leads manually. Currently taking 2h/day.",
        source="manual",
    )

    print("\n" + "=" * 60)
    print("Telegram message preview:")
    print("=" * 60)
    print(result)
