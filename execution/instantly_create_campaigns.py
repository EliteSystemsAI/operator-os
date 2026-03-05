"""
Instantly Campaign Creator

Creates 3 email campaigns in Instantly by finding the closest existing campaigns
in your Instantly account, then minimally rewriting them for the new brand/offer.

Process:
1. Fetch all campaign names from Instantly
2. Use Claude to pick the 3 closest analogues
3. Fetch full sequences from those 3 campaigns
4. Use Claude to minimally rewrite them for the new brand

Usage:
    python3 execution/instantly_create_campaigns.py \
        --client_name "ClientName" \
        --client_description "Description..." \
        --offers "Offer1|Offer2|Offer3" \
        --target_audience "Who we're targeting" \
        --social_proof "Credentials to mention"
"""

import os
import sys
import json
import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("instantly-campaigns")

# Constants
INSTANTLY_API_BASE = "https://api.instantly.ai/api/v2"


def get_instantly_headers() -> dict:
    """Get auth headers for Instantly API."""
    api_key = os.getenv("INSTANTLY_API_KEY")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def fetch_all_campaigns() -> list[dict]:
    """Fetch all campaign names and IDs from Instantly."""
    headers = get_instantly_headers()
    r = requests.get(f"{INSTANTLY_API_BASE}/campaigns", headers=headers, params={"limit": 100}, timeout=30)
    r.raise_for_status()
    data = r.json()
    campaigns = data if isinstance(data, list) else data.get("items", data.get("data", []))
    logger.info(f"Fetched {len(campaigns)} campaigns from Instantly")
    return [{"id": c["id"], "name": c.get("name", "unnamed")} for c in campaigns]


def pick_closest_campaigns(
    all_campaigns: list[dict],
    client_description: str,
    offers: list[str],
) -> list[str]:
    """Use Claude to pick the 3 closest analogue campaign IDs."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    campaign_list = "\n".join(f'- {c["name"]} (id: {c["id"]})' for c in all_campaigns)
    offers_text = "\n".join(f"- {o}" for o in offers)

    prompt = f"""Here are all campaigns in an Instantly account:

{campaign_list}

I need to create campaigns for a NEW client:
- Description: {client_description}
- Offers:
{offers_text}

Pick the 3 existing campaigns that are the CLOSEST analogues to the new client's offer. Choose campaigns that:
1. Have a similar offer structure (free deliverable, guarantee, outcome-based, etc.)
2. Are for a similar type of service business
3. Have clear, concrete offers (not generic ones)

Prefer campaigns with names that suggest a specific offer (e.g. "3 free patients", "15 Meetings in 30 Days") over generic names.
If multiple campaigns have the same name, pick just one of them.

Output ONLY a JSON array of exactly 3 campaign IDs, nothing else:
["id1", "id2", "id3"]"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].split("```")[0]
        if text.startswith("json"):
            text = text[4:]
    ids = json.loads(text.strip())
    logger.info(f"Selected {len(ids)} analogue campaigns")
    return ids


def fetch_campaign_sequences(campaign_ids: list[str]) -> list[dict]:
    """Fetch full campaign data (with sequences) for the given IDs."""
    headers = get_instantly_headers()
    results = []
    for cid in campaign_ids:
        r = requests.get(f"{INSTANTLY_API_BASE}/campaigns/{cid}", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            results.append({
                "name": data.get("name", "unnamed"),
                "sequences": data.get("sequences", [])
            })
            logger.info(f"Fetched sequences for: {data.get('name', cid)}")
        else:
            logger.warning(f"Failed to fetch campaign {cid}: {r.status_code}")
    return results


def format_source_campaigns(source_campaigns: list[dict]) -> str:
    """Format source campaign sequences as readable text for the prompt."""
    parts = []
    for camp in source_campaigns:
        parts.append(f"=== SOURCE CAMPAIGN: {camp['name']} ===")
        for seq in camp.get("sequences", []):
            for i, step in enumerate(seq.get("steps", [])):
                parts.append(f"  Step {i+1} (delay: {step.get('delay', 0)} days):")
                for j, var in enumerate(step.get("variants", [])):
                    parts.append(f"    Variant {j+1}:")
                    parts.append(f"      Subject: {var.get('subject', '')}")
                    parts.append(f"      Body: {var.get('body', '')}")
                    parts.append("")
        parts.append("")
    return "\n".join(parts)


def generate_campaigns_with_claude(
    client_name: str,
    client_description: str,
    offers: list[str],
    target_audience: str,
    social_proof: str,
    source_campaigns_text: str,
) -> list[dict]:
    """
    Use Claude to minimally rewrite source campaigns for the new brand.
    Returns list of campaign structures ready for Instantly API.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    offers_text = "\n".join(f"{i+1}. {offer}" for i, offer in enumerate(offers))

    prompt = f"""You are rewriting existing cold email campaigns for a new brand. Make MINIMAL changes.

NEW CLIENT INFO:
- Name: {client_name}
- Description: {client_description}
- Target Audience: {target_audience}
- Social Proof: {social_proof}
- Offers:
{offers_text}

SOURCE CAMPAIGNS TO REWRITE (these are proven campaigns — preserve their structure, tone, and pacing):
{source_campaigns_text}

RULES:
1. Make ONLY 5-10 word changes per email. Swap the brand name, industry noun, and offer noun. Keep EVERYTHING else identical — same sentences, same structure, same phrasing, same paragraph count.
2. Each campaign must have exactly 2 steps: the opener (2 A/B variants) and ONE follow-up.
3. If a source has 3 steps, drop the last step. Keep step 1 and step 2 only.
4. Every email (opener AND follow-up) MUST clearly state the offer.
5. Use these variables: {{{{firstName}}}}, {{{{icebreaker}}}}, {{{{sendingAccountFirstName}}}}, {{{{companyName}}}}, {{{{casualCompanyName}}}}
6. NEVER include links, URLs, or {{{{web_site}}}} variables. Cold emails with links get flagged as spam.
7. Do NOT rewrite sentences. Do NOT add new sentences. Do NOT rephrase. Only find-and-replace the industry-specific nouns (e.g. "patients" → "articles", "dental practice" → "business", "Dental Connect" → new brand name).
8. Preserve the source HTML tags exactly as they are (<p>, <div>, <br />, etc.).

OUTPUT FORMAT (valid JSON array):
[
  {{
    "campaign_name": "{client_name} | Brief Description",
    "source_campaign": "Name of source campaign used",
    "sequences": [
      {{
        "steps": [
          {{
            "type": "email",
            "delay": 0,
            "variants": [
              {{"subject": "subject A", "body": "body A"}},
              {{"subject": "subject B", "body": "body B"}}
            ]
          }},
          {{
            "type": "email",
            "delay": 3,
            "variants": [
              {{"subject": "Re: subject", "body": "Short follow-up with offer restated"}}
            ]
          }}
        ]
      }}
    ]
  }},
  ... (2 more)
]

Output ONLY the JSON array, no other text."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        # Parse JSON from response
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        campaigns = json.loads(result_text.strip())

        # Convert plain text to HTML paragraphs (Instantly strips text outside HTML tags)
        for campaign in campaigns:
            for sequence in campaign.get("sequences", []):
                for step in sequence.get("steps", []):
                    for variant in step.get("variants", []):
                        if "body" in variant:
                            body = variant["body"]
                            # Skip if already HTML
                            if "<p>" in body:
                                continue
                            paragraphs = body.split("\n\n")
                            html_parts = []
                            for p in paragraphs:
                                p = p.replace("\n", "<br>")
                                if p.strip():
                                    html_parts.append(f"<p>{p}</p>")
                            variant["body"] = "".join(html_parts)

        logger.info(f"Generated {len(campaigns)} campaigns")
        return campaigns

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.error(f"Response was: {result_text[:1000]}")
        raise
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise


def create_campaign_in_instantly(campaign_data: dict) -> dict:
    """
    Create a single campaign in Instantly via API.
    Returns the created campaign data or error.
    """
    api_key = os.getenv("INSTANTLY_API_KEY")
    if not api_key:
        return {"error": "INSTANTLY_API_KEY not configured in .env"}

    url = f"{INSTANTLY_API_BASE}/campaigns"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Set default campaign settings
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

    payload = {
        "name": campaign_data["campaign_name"],
        "sequences": campaign_data["sequences"],
        "campaign_schedule": {
            "start_date": start_date,
            "end_date": end_date,
            "schedules": [
                {
                    "name": "Weekday Schedule",
                    "days": {"1": True, "2": True, "3": True, "4": True, "5": True},
                    "timing": {"from": "09:00", "to": "17:00"},
                    "timezone": "America/Chicago"
                }
            ]
        },
        "email_gap": 10,
        "daily_limit": 50,
        "stop_on_reply": True,
        "stop_on_auto_reply": True,
        "link_tracking": True,
        "open_tracking": True,
        "text_only": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 429:
            # Rate limited - wait and retry once
            logger.warning("Rate limited, waiting 30 seconds...")
            time.sleep(30)
            response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code not in [200, 201]:
            logger.error(f"Instantly API error: {response.status_code} - {response.text}")
            return {"error": f"API error {response.status_code}", "details": response.text}

        result = response.json()
        logger.info(f"Created campaign: {campaign_data['campaign_name']} (ID: {result.get('id', 'unknown')})")
        return result

    except requests.exceptions.Timeout:
        return {"error": "Request timeout"}
    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        return {"error": str(e)}


def generate_offers_if_missing(client_name: str, client_description: str) -> list[str]:
    """Generate 3 offers if none provided."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Generate 3 distinct cold email offers for this business:

Business: {client_name}
Description: {client_description}

Each offer should be:
1. Low barrier to entry (free audit, demo, quick call)
2. High perceived value
3. Different from the others (variety of angles)

Output format (one offer per line, no numbering):
Free workflow audit to find automation opportunities
Live demo of our AI system
Revenue share partnership pilot

Generate 3 offers now:"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        offers = [line.strip() for line in text.split("\n") if line.strip()]
        return offers[:3]

    except Exception as e:
        logger.error(f"Failed to generate offers: {e}")
        # Return generic fallback offers
        return [
            "Free strategy call to discuss your goals",
            "Custom demo of our solution",
            "Pilot program with performance guarantee"
        ]


def main():
    parser = argparse.ArgumentParser(description="Create Instantly email campaigns")
    parser.add_argument("--client_name", required=True, help="Client/company name")
    parser.add_argument("--client_description", required=True, help="Description of the client and their offering")
    parser.add_argument("--offers", help="Pipe-separated offers (e.g., 'Offer 1|Offer 2|Offer 3')")
    parser.add_argument("--target_audience", default="Business owners and decision makers", help="Target audience description")
    parser.add_argument("--social_proof", default="", help="Credentials and social proof to include")
    parser.add_argument("--dry_run", action="store_true", help="Generate campaigns without creating in Instantly")

    args = parser.parse_args()

    # Check for API key early (always needed — we fetch source campaigns from Instantly)
    api_key = os.getenv("INSTANTLY_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        print(json.dumps({
            "status": "error",
            "error": "INSTANTLY_API_KEY not configured in .env",
            "help": "Add your Instantly API v2 key to .env file. Get it from https://app.instantly.ai/app/settings/integrations"
        }, indent=2))
        sys.exit(1)

    # Parse or generate offers
    if args.offers:
        offers = [o.strip() for o in args.offers.split("|")]
    else:
        logger.info("No offers provided, generating...")
        offers = generate_offers_if_missing(args.client_name, args.client_description)

    # Ensure we have exactly 3 offers
    while len(offers) < 3:
        offers.append(f"Custom solution discussion {len(offers) + 1}")
    offers = offers[:3]

    logger.info(f"Using offers: {offers}")

    # Step 1: Fetch all campaigns from Instantly
    logger.info("Fetching existing campaigns from Instantly...")
    all_campaigns = fetch_all_campaigns()

    # Step 2: Pick the 3 closest analogues
    logger.info("Selecting closest analogue campaigns...")
    selected_ids = pick_closest_campaigns(all_campaigns, args.client_description, offers)

    # Step 3: Fetch full sequences from those campaigns
    logger.info("Fetching source campaign sequences...")
    source_campaigns = fetch_campaign_sequences(selected_ids)
    source_text = format_source_campaigns(source_campaigns)

    # Step 4: Rewrite for new brand
    logger.info("Rewriting campaigns for new brand...")
    campaigns = generate_campaigns_with_claude(
        client_name=args.client_name,
        client_description=args.client_description,
        offers=offers,
        target_audience=args.target_audience,
        social_proof=args.social_proof,
        source_campaigns_text=source_text,
    )

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "campaigns_generated": len(campaigns),
            "campaigns": campaigns
        }, indent=2))
        return

    # Create campaigns in Instantly
    results = []
    campaign_ids = []
    campaign_names = []
    errors = []

    for campaign in campaigns:
        result = create_campaign_in_instantly(campaign)
        results.append(result)

        if "error" in result:
            errors.append(result)
        else:
            campaign_ids.append(result.get("id", "unknown"))
            campaign_names.append(campaign["campaign_name"])

        # Small delay between API calls
        time.sleep(2)

    # Output results
    output = {
        "status": "success" if not errors else "partial_success" if campaign_ids else "failed",
        "campaigns_created": len(campaign_ids),
        "campaign_ids": campaign_ids,
        "campaign_names": campaign_names
    }

    if errors:
        output["errors"] = errors

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
