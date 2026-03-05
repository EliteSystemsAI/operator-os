#!/usr/bin/env python3
"""
Follow-Up Nurture — Context-Aware Lead Nudge

Goes through every pending lead in the database, pulls email history,
researches context gaps, and generates personalized follow-up emails.

Usage:
    # List pending leads
    python follow_up_nurture.py --list-pending

    # Generate follow-up emails
    python follow_up_nurture.py --generate

    # Review emails
    python follow_up_nurture.py --review

    # Send approved emails (requires Gmail auth)
    python follow_up_nurture.py --send

Environment Variables:
    ANTHROPIC_API_KEY: For generating follow-up emails
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).parent.parent / "data" / "leads_database.json"
DRAFTS_PATH = Path(__file__).parent.parent / "data" / "followup_emails.json"
CONFIG_DIR = Path(__file__).parent.parent / "config"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SENDER_INBOX = {
    "email": "nickolassaraev@gmail.com",
    "token": CONFIG_DIR / "token_nicksaraev.json",
    "credentials": CONFIG_DIR / "credentials.json",
}


def load_database() -> dict:
    """Load the leads database."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(DB_PATH) as f:
        return json.load(f)


def save_database(db: dict) -> None:
    """Save the leads database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def get_pending_leads(db: dict) -> list:
    """Get all leads with status 'pending'."""
    return [
        lead for lead in db.get("leads", [])
        if lead.get("status") == "pending"
    ]


def should_skip_lead(lead: dict) -> tuple[bool, str]:
    """Check if a lead should be skipped."""
    status = lead.get("status", "")
    if status in ("closed", "lost", "won"):
        return True, f"Status is '{status}'"

    # Check if they replied recently (< 48h)
    emails = lead.get("email_history", [])
    if emails:
        last_email = emails[-1]
        if last_email.get("direction") == "inbound":
            last_date = datetime.fromisoformat(last_email.get("date", "2000-01-01"))
            if datetime.now() - last_date < timedelta(hours=48):
                return True, "Replied within 48h"

    # Check if no prior emails exist
    if not emails:
        return True, "No prior emails (needs intro, not follow-up)"

    return False, ""


def generate_email(lead: dict) -> dict:
    """Generate a follow-up email for a lead using Claude."""
    import requests

    emails = lead.get("email_history", [])
    email_context = "\n".join([
        f"[{e['date']}] {'Me' if e['direction'] == 'outbound' else lead['first_name']}: {e['subject']} — {e['body']}"
        for e in emails[-5:]  # Last 5 emails
    ])

    notes = lead.get("notes", "")

    prompt = f"""Write a follow-up email to {lead['first_name']} using ONE of these three templates. Pick whichever feels most natural for this thread — do NOT always pick the same one.

Template A (lowercase casual):
hey {lead['first_name'].lower()}, circling back on {{topic}}. let me know if I can answer any q's?

- nick

Template B (title case, slightly formal):
Hey {lead['first_name']},

Just checking in on {{topic}}. How are things going? Let me know if you need me.

Thanks,
Nick

Template C (warm/friendly):
Hi {lead['first_name']}—hope you had a great week. Checking in on {{topic}}. Let me know where we're at.

Thanks,
Nick

Rules:
- Replace {{topic}} with a SHORT casual phrase (2-4 words). Good: "the proposal", "the contract", "that SOW", "our conversation". Bad: "AI-powered incident response automation for your DevOps team"
- If the last email in the thread was already a follow-up/nudge from us, pick a DIFFERENT template and phrasing than what we used last time. Never send the same email twice
- Do NOT add any extra sentences, value props, or CTAs beyond the template
- Do NOT modify the template structure — only fill in {{topic}}
- Return ONLY the final email text

Previous conversation (including any prior follow-ups we've sent):
{email_context}

{f'Notes: {notes}' if notes else ''}"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": "claude-opus-4-6",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    email_text = data["content"][0]["text"]

    return {
        "lead_id": lead["id"],
        "to": lead["email"],
        "to_name": f"{lead['first_name']} {lead['last_name']}",
        "company": lead.get("company", ""),
        "subject": f"Re: {emails[-1]['subject']}" if emails else "Quick follow up",
        "body": email_text,
        "generated_at": datetime.now().isoformat(),
        "approved": False,
    }


def list_pending(db: dict) -> None:
    """List all pending leads."""
    pending = get_pending_leads(db)
    if not pending:
        print("No pending leads found.")
        return

    print(f"\n{'='*60}")
    print(f"PENDING LEADS: {len(pending)}")
    print(f"{'='*60}\n")

    for lead in pending:
        skip, reason = should_skip_lead(lead)
        status_marker = f" [SKIP: {reason}]" if skip else ""
        emails_count = len(lead.get("email_history", []))
        last_contact = "never"
        if lead.get("email_history"):
            last_contact = lead["email_history"][-1].get("date", "unknown")

        print(f"  {lead['first_name']} {lead['last_name']} — {lead.get('company', '?')}")
        print(f"    Email: {lead['email']}")
        print(f"    Emails exchanged: {emails_count} | Last contact: {last_contact}{status_marker}")
        print()


def generate_emails(db: dict) -> None:
    """Generate follow-up emails for all eligible pending leads."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    pending = get_pending_leads(db)
    emails = []
    skipped = 0

    print(f"\nSending follow-ups to {len(pending)} pending leads...\n")

    for lead in pending:
        skip, reason = should_skip_lead(lead)
        if skip:
            print(f"  SKIP: {lead['first_name']} {lead['last_name']} — {reason}")
            skipped += 1
            continue

        print(f"  Sending: {lead['first_name']} {lead['last_name']} ({lead.get('company', '')})...", end=" ")
        try:
            email = generate_email(lead)
            emails.append(email)
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")

    # Save emails
    DRAFTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DRAFTS_PATH, "w") as f:
        json.dump({"emails": emails, "generated_at": datetime.now().isoformat()}, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Generated: {len(emails)} emails")
    print(f"Skipped: {skipped}")
    print(f"Saved to: {DRAFTS_PATH}")
    print(f"{'='*60}")


def get_gmail_service():
    """Authenticate and return a Gmail API service."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = SENDER_INBOX["token"]
    creds_path = SENDER_INBOX["credentials"]
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if not creds_path.exists():
            print(f"ERROR: Credentials file not found: {creds_path}", file=sys.stderr)
            return None
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(service, to: str, subject: str, body: str) -> dict:
    """Send an email via Gmail API."""
    message = MIMEText(body)
    message["to"] = to
    message["from"] = SENDER_INBOX["email"]
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()


def send_emails(db: dict) -> None:
    """Send all generated follow-up emails via Gmail."""
    if not DRAFTS_PATH.exists():
        print("No emails found. Run --generate first.")
        return

    with open(DRAFTS_PATH) as f:
        data = json.load(f)

    emails = data.get("emails", [])
    if not emails:
        print("No emails to send.")
        return

    service = get_gmail_service()
    if not service:
        print("ERROR: Could not authenticate with Gmail.", file=sys.stderr)
        return

    sent = 0
    print(f"\nSending {len(emails)} follow-up emails...\n")

    for email in emails:
        print(f"  Sending to {email['to_name']} <{email['to']}>...", end=" ")
        try:
            send_email(service, email["to"], email["subject"], email["body"])
            # Log to lead's email_history
            for lead in db.get("leads", []):
                if lead["id"] == email["lead_id"]:
                    lead.setdefault("email_history", []).append({
                        "date": datetime.now().isoformat(),
                        "direction": "outbound",
                        "subject": email["subject"],
                        "body": email["body"],
                    })
                    break
            sent += 1
            print("sent")
        except Exception as e:
            print(f"ERROR: {e}")

    save_database(db)
    print(f"\n{'='*60}")
    print(f"Sent: {sent}/{len(emails)} emails")
    print(f"Email history updated in {DB_PATH}")
    print(f"{'='*60}")


def review_emails() -> None:
    """Display all generated emails for review."""
    if not DRAFTS_PATH.exists():
        print("No emails found. Run --generate first.")
        return

    with open(DRAFTS_PATH) as f:
        data = json.load(f)

    emails = data.get("emails", [])
    if not emails:
        print("No emails to review.")
        return

    print(f"\n{'='*60}")
    print(f"FOLLOW-UP EMAILS SENT ({len(emails)})")
    print(f"Generated: {data.get('generated_at', 'unknown')}")
    print(f"{'='*60}\n")

    for i, email in enumerate(emails, 1):
        print(f"--- Email {i}/{len(emails)} ---")
        print(f"To: {email['to_name']} <{email['to']}>")
        print(f"Company: {email['company']}")
        print(f"Subject: {email['subject']}")
        print(f"\n{email['body']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Follow-Up Nurture")
    parser.add_argument("--list-pending", action="store_true", help="List pending leads")
    parser.add_argument("--generate", action="store_true", help="Generate follow-up emails")
    parser.add_argument("--review", action="store_true", help="Review generated emails")
    parser.add_argument("--send", action="store_true", help="Send approved emails")
    args = parser.parse_args()

    db = load_database()

    if args.list_pending:
        list_pending(db)
    elif args.generate:
        generate_emails(db)
    elif args.review:
        review_emails()
    elif args.send:
        send_emails(db)
    else:
        parser.print_help()
