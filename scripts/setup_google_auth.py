#!/usr/bin/env python3
"""
One-time Google OAuth2 setup for Calendar + Gmail access.

Run this on Zac's MacBook (needs a browser):
  python scripts/setup_google_auth.py

It will:
  1. Open a browser for Google OAuth2 consent (elite-scripts-478911 project)
  2. Save the token to ~/.config/elite-os/google-token.json
  3. Print a reminder to sync that file to the Mac Mini

Then sync to Mac Mini:
  scp ~/.config/elite-os/google-token.json YOUR_SERVER_USER@YOUR_SERVER_IP
"""

import json
import os
import sys
from pathlib import Path

TOKEN_PATH = Path.home() / ".config" / "elite-os" / "google-token.json"
ENV_PATH = Path(__file__).parent.parent / ".env"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",   # archive, trash, label
    "https://www.googleapis.com/auth/gmail.send",     # send drafts
]


def load_env_var(key):
    """Read a single-line var from .env without requiring dotenv."""
    if not ENV_PATH.exists():
        return None
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


def main():
    client_id = load_env_var("ELITE_SCRIPTS_CLIENT_ID")
    client_secret = load_env_var("ELITE_SCRIPTS_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: ELITE_SCRIPTS_CLIENT_ID or ELITE_SCRIPTS_CLIENT_SECRET not found in .env")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    # Build the OAuth config inline from .env vars — no JSON file needed
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Opening browser for Google authorization (elite-scripts-478911)...")
    print("Grant access to: Google Calendar (read-only) + Gmail (read + modify + send)")
    print()

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"\nToken saved to {TOKEN_PATH}")
    print()
    print("Sync to Mac Mini:")
    print(f"  ssh YOUR_SERVER_USER@YOUR_SERVER_IP 'mkdir -p ~/.config/elite-os'")
    print(f"  scp {TOKEN_PATH} YOUR_SERVER_USER@YOUR_SERVER_IP
    print()
    print("Then the Calendar + Gmail monitors in analyst.py will activate automatically.")


if __name__ == "__main__":
    main()
