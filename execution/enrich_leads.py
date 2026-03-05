#!/usr/bin/env python3
"""
Enrich Leads - Process Vayne CSV export and add email addresses via AnyMailFinder.

This script takes a CSV exported from Vayne (LinkedIn Sales Navigator scraper),
enriches each lead with email addresses, and outputs an enriched CSV.

Usage:
    python enrich_leads.py --input leads.csv --output enriched_leads.csv

    # Dry run (no API calls, just validate CSV)
    python enrich_leads.py --input leads.csv --dry-run

    # Limit number of leads to process
    python enrich_leads.py --input leads.csv --limit 10

Expected Vayne CSV columns:
    - firstName, lastName (or fullName)
    - companyName (or company)
    - companyDomain (or domain, website)
    - title, linkedinUrl, location, etc.

Output adds columns:
    - email, email_status, enrichment_error
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anymailfinder_client import get_client


def extract_domain_from_url(url: str) -> Optional[str]:
    """Extract domain from a URL or website field."""
    if not url:
        return None

    url = url.strip().lower()

    # Remove protocol
    for prefix in ["https://", "http://", "www."]:
        if url.startswith(prefix):
            url = url[len(prefix):]

    # Remove path
    url = url.split("/")[0]

    # Remove port
    url = url.split(":")[0]

    return url if url else None


def normalize_lead(row: dict) -> dict:
    """
    Normalize a Vayne CSV row to standard field names.

    Handles various column name formats from Vayne exports.
    """
    # Name fields (handle various formats including Vayne's "first name" with space)
    first_name = (
        row.get("firstName")
        or row.get("first_name")
        or row.get("first name")  # Vayne format
        or row.get("First Name")
        or ""
    ).strip()

    last_name = (
        row.get("lastName")
        or row.get("last_name")
        or row.get("last name")  # Vayne format
        or row.get("Last Name")
        or ""
    ).strip()

    full_name = (
        row.get("fullName")
        or row.get("full_name")
        or row.get("Full Name")
        or row.get("name")
        or row.get("Name")
        or ""
    ).strip()

    # If we have full_name but not first/last, try to split
    if full_name and not (first_name and last_name):
        parts = full_name.split(" ", 1)
        if len(parts) >= 1:
            first_name = first_name or parts[0]
        if len(parts) >= 2:
            last_name = last_name or parts[1]

    # If we have first/last but not full, combine
    if first_name and last_name and not full_name:
        full_name = f"{first_name} {last_name}"

    # Company fields
    company = (
        row.get("companyName")
        or row.get("company_name")
        or row.get("Company Name")
        or row.get("company")
        or row.get("Company")
        or ""
    ).strip()

    # Domain - try multiple fields
    domain = (
        row.get("companyDomain")
        or row.get("company_domain")
        or row.get("domain")
        or row.get("Domain")
        or ""
    ).strip()

    # Try to extract from website if no domain
    if not domain:
        website = (
            row.get("corporate website")  # Vayne format
            or row.get("website")
            or row.get("Website")
            or row.get("companyWebsite")
            or row.get("company_website")
            or ""
        )
        domain = extract_domain_from_url(website) or ""

    # Other useful fields
    title = (
        row.get("job title")  # Vayne format
        or row.get("title")
        or row.get("Title")
        or row.get("jobTitle")
        or row.get("job_title")
        or ""
    ).strip()

    # Existing email (Vayne sometimes provides emails)
    existing_email = (
        row.get("email")
        or row.get("Email")
        or ""
    ).strip()

    linkedin_url = (
        row.get("linkedin url")  # Vayne format
        or row.get("linkedinUrl")
        or row.get("linkedin_url")
        or row.get("LinkedIn URL")
        or row.get("profileUrl")
        or row.get("profile_url")
        or ""
    ).strip()

    location = (
        row.get("location")
        or row.get("Location")
        or ""
    ).strip()

    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "company": company,
        "domain": domain,
        "title": title,
        "linkedin_url": linkedin_url,
        "location": location,
        "existing_email": existing_email,  # Preserve emails from Vayne
        # Preserve original row for any extra fields
        "_original": row,
    }


def enrich_leads(
    input_file: str,
    output_file: str,
    limit: Optional[int] = None,
    dry_run: bool = False,
    delay: float = 0.5,
) -> dict:
    """
    Read leads from CSV, enrich with emails, write to output CSV.

    Args:
        input_file: Path to Vayne CSV export
        output_file: Path for enriched output CSV
        limit: Max number of leads to process (None = all)
        dry_run: If True, validate but don't call API
        delay: Seconds between API calls

    Returns:
        dict with processing stats
    """
    # Read input CSV
    with open(input_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_leads = list(reader)

    print(f"Read {len(raw_leads)} leads from {input_file}")

    # Normalize all leads
    leads = [normalize_lead(row) for row in raw_leads]

    # Apply limit
    if limit:
        leads = leads[:limit]
        print(f"Processing {len(leads)} leads (limit applied)")

    # Validate leads
    valid_leads = []
    skipped = []
    for i, lead in enumerate(leads):
        if not lead["full_name"] and not (lead["first_name"] and lead["last_name"]):
            skipped.append((i, "Missing name"))
            continue
        if not lead["domain"] and not lead["company"]:
            skipped.append((i, "Missing domain/company"))
            continue
        valid_leads.append(lead)

    print(f"Valid leads: {len(valid_leads)}, Skipped: {len(skipped)}")

    if skipped and len(skipped) <= 10:
        for idx, reason in skipped:
            print(f"  Skipped row {idx}: {reason}")

    if dry_run:
        print("\nDry run - no API calls made")
        return {
            "total": len(leads),
            "valid": len(valid_leads),
            "skipped": len(skipped),
            "dry_run": True,
        }

    # Enrich with AnyMailFinder
    client = get_client()
    enriched = []

    print(f"\nEnriching {len(valid_leads)} leads...")

    # Separate leads with existing emails from those needing enrichment
    pre_enriched = []
    needs_enrichment = []

    for lead in valid_leads:
        existing_email = lead.get("existing_email", "")
        if existing_email:
            lead["email"] = existing_email
            lead["email_status"] = "pre-enriched"
            lead["enrichment_error"] = ""
            pre_enriched.append(lead)
        else:
            needs_enrichment.append(lead)

    print(f"  Pre-enriched (from Vayne): {len(pre_enriched)}")
    print(f"  Need API enrichment: {len(needs_enrichment)}")

    # Add pre-enriched leads to results
    enriched.extend(pre_enriched)
    client.valid_count += len(pre_enriched)

    # Use bulk API for remaining leads
    if needs_enrichment:
        print(f"\nRunning bulk enrichment via AnyMailFinder...")
        bulk_result = client.bulk_enrich(
            leads=needs_enrichment,
            file_name=f"enrich_{len(needs_enrichment)}_leads",
            poll_interval=3,
            timeout=600,
        )

        if bulk_result["success"]:
            # Match results back to leads by domain + name
            results_map = {}
            for r in bulk_result["data"]:
                key = (
                    r.get("domain", "").lower().strip(),
                    r.get("first_name", "").lower().strip(),
                    r.get("last_name", "").lower().strip(),
                )
                results_map[key] = r

            matched = 0
            for lead in needs_enrichment:
                key = (
                    lead.get("domain", "").lower().strip(),
                    lead.get("first_name", "").lower().strip(),
                    lead.get("last_name", "").lower().strip(),
                )
                result = results_map.get(key, {})
                if result:
                    matched += 1
                # Handle both field naming conventions
                lead["email"] = result.get("email") or result.get("valid_email_only") or ""
                raw_status = result.get("email_status") or result.get("amf_status") or "not_found"
                # Normalize "ok" to "valid" for consistency
                lead["email_status"] = "valid" if raw_status == "ok" else raw_status
                lead["enrichment_error"] = ""
                enriched.append(lead)

            print(f"  Matched {matched}/{len(needs_enrichment)} results to leads")
        else:
            print(f"  Bulk enrichment failed: {bulk_result.get('error')}")
            # Mark all as failed
            for lead in needs_enrichment:
                lead["email"] = ""
                lead["email_status"] = "error"
                lead["enrichment_error"] = bulk_result.get("error", "Bulk API failed")
                enriched.append(lead)

    # Write output CSV
    output_columns = [
        "full_name",
        "first_name",
        "last_name",
        "email",
        "email_status",
        "title",
        "company",
        "domain",
        "linkedin_url",
        "location",
        "enrichment_error",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)

    stats = client.get_stats()
    print(f"\nEnrichment complete!")
    print(f"  Total processed: {stats['total_requests']}")
    print(f"  Valid emails found: {stats['valid_emails']}")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")
    print(f"\nOutput written to: {output_file}")

    return {
        "total": len(leads),
        "valid": len(valid_leads),
        "skipped": len(skipped),
        "enriched": len(enriched),
        "emails_found": stats["valid_emails"],
        "success_rate": stats["success_rate"],
        "output_file": output_file,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Enrich Vayne LinkedIn leads with email addresses"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input CSV file (Vayne export)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSV file (default: input_enriched.csv)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Max number of leads to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CSV without making API calls",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between API calls in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    # Default output filename
    if not args.output:
        base = os.path.splitext(args.input)[0]
        args.output = f"{base}_enriched.csv"

    # Validate input exists
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    try:
        result = enrich_leads(
            input_file=args.input,
            output_file=args.output,
            limit=args.limit,
            dry_run=args.dry_run,
            delay=args.delay,
        )

        if args.json:
            print(json.dumps(result, indent=2))

        sys.exit(0 if result.get("emails_found", 0) > 0 or args.dry_run else 1)

    except FileNotFoundError as e:
        print(f"File error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Setup error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
