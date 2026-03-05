#!/usr/bin/env python3
"""
Elite Systems AI — Client Health Check

Fetches all sub-account locations from GHL agency API, filters to real clients,
and reports new contacts (7d) + open pipeline opps per client.

Can be run standalone OR imported by telegram_bot.py:
    from ops.client_health_check import run_health_check
"""

from datetime import datetime, timedelta, timezone
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
GHL_AGENCY_KEY = env.get("GHL_AGENCY_API_KEY", "")

AEST = timezone(timedelta(hours=10))

# ── Client filters ────────────────────────────────────────────────────────────

# Exact names to exclude — internal/demo/partner accounts
EXCLUDE_EXACT = {
    "Demo AI",
    "Ejey",
    "ELITE SYSTEMS AI PTY LTD",
    "Elite Systems Ai",
}

# Accounts whose names end with these strings are test/partner accounts
EXCLUDE_SUFFIXES = ("'s Account",)

# Demo snapshot sub-accounts are named "Elite [Industry]" (e.g. "Elite Gym")
EXCLUDE_PREFIXES = ("Elite ",)


def is_real_client(location: dict) -> bool:
    name = (location.get("name") or "").strip()
    if name in EXCLUDE_EXACT:
        return False
    if any(name.endswith(s) for s in EXCLUDE_SUFFIXES):
        return False
    if any(name.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    return True


# ── GHL Agency API ────────────────────────────────────────────────────────────


def agency_get(path: str, params: dict | None = None) -> dict:
    r = requests.get(
        f"https://rest.gohighlevel.com/v1{path}",
        params=params or {},
        headers={"Authorization": f"Bearer {GHL_AGENCY_KEY}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_all_locations() -> list[dict]:
    """Paginate all sub-account locations via agency API."""
    locations: list[dict] = []
    skip = 0
    limit = 100
    while True:
        data = agency_get("/locations/", {"skip": skip, "limit": limit})
        batch = data.get("locations", [])
        locations.extend(batch)
        if len(batch) < limit:
            break
        skip += limit
    return locations


def get_location_contacts_7d(location_id: str) -> int:
    """Count new contacts in the last 7 days for this location."""
    seven_days_ago = (datetime.now(AEST) - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        data = agency_get(
            "/contacts/",
            {"locationId": location_id, "startDate": seven_days_ago, "limit": 100},
        )
        return len(data.get("contacts", []))
    except Exception:
        return 0


def get_location_open_opps(location_id: str) -> int:
    """Count open pipeline opportunities for this location."""
    try:
        data = agency_get(
            "/opportunities/",
            {"locationId": location_id, "status": "open", "limit": 100},
        )
        return len(data.get("opportunities", []))
    except Exception:
        return 0


# ── Health logic ──────────────────────────────────────────────────────────────


def health_status(new_contacts: int, open_opps: int) -> tuple[str, str]:
    """Return (status_emoji, label)."""
    if new_contacts >= 1:
        return "🟢", "Active"
    elif open_opps >= 1:
        return "🟡", "Slow"
    else:
        return "🔴", "At-risk"


def run_health_check() -> str:
    """
    Run the full client health check.
    Returns a Telegram-formatted string ready to send.
    Can be called from the bot or standalone.
    """
    now_aest = datetime.now(AEST)
    date_str = now_aest.strftime("%-d %b %Y")

    try:
        locations = get_all_locations()
    except Exception as e:
        return f"❌ *CLIENT HEALTH CHECK*\n\nFailed to fetch locations: {e}"

    real_clients = [loc for loc in locations if is_real_client(loc)]

    if not real_clients:
        return (
            f"⚠️ *CLIENT HEALTH CHECK*\n"
            f"_{date_str}_\n\n"
            f"No real clients found after filtering."
        )

    # Fetch health data for each client
    results: list[tuple[str, str, int, int, str]] = []  # (emoji, name, contacts, opps, label)
    for loc in real_clients:
        loc_id = loc.get("id") or loc.get("_id", "")
        name = (loc.get("name") or "Unknown").strip()
        new_contacts = get_location_contacts_7d(loc_id)
        open_opps = get_location_open_opps(loc_id)
        emoji, label = health_status(new_contacts, open_opps)
        results.append((emoji, name, new_contacts, open_opps, label))

    # Sort: at-risk first, then slow, then active
    order = {"At-risk": 0, "Slow": 1, "Active": 2}
    results.sort(key=lambda r: order[r[4]])

    # Build report
    lines = [
        f"🏥 *CLIENT HEALTH CHECK*",
        f"_{date_str} | {len(real_clients)} clients_",
        "",
    ]
    for emoji, name, contacts, opps, _label in results:
        lines.append(f"{emoji} *{name}*")
        lines.append(f"   New contacts (7d): {contacts}  |  Open opps: {opps}")

    # Summary line
    green_count = sum(1 for r in results if r[4] == "Active")
    yellow_count = sum(1 for r in results if r[4] == "Slow")
    red_count = sum(1 for r in results if r[4] == "At-risk")

    lines += [
        "",
        f"🟢 {green_count} Active  🟡 {yellow_count} Slow  🔴 {red_count} At-risk",
    ]

    if red_count == 0:
        lines.append("✅ All clients healthy")
    else:
        lines.append(f"⚠️ {red_count} client{'s' if red_count > 1 else ''} need attention")

    return "\n".join(lines)


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    print(run_health_check())
