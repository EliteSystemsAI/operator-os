#!/usr/bin/env python3
"""
Scrape LinkedIn - Full automated pipeline from Sales Navigator URL to Google Sheets.

This script orchestrates the entire lead generation workflow:
1. Create Vayne scraping order from Sales Navigator URL
2. Wait for scraping to complete
3. Download CSV export
4. Enrich with emails via AnyMailFinder
5. Export to Google Sheets

Usage:
    # Full pipeline
    python scrape_linkedin.py \
        --url "https://www.linkedin.com/sales/search/people?query=..." \
        --name "SaaS CEOs Dec 2024" \
        --limit 100

    # Just check URL (no credits used)
    python scrape_linkedin.py \
        --url "https://www.linkedin.com/sales/search/people?query=..." \
        --check-only

    # Skip enrichment (just scrape)
    python scrape_linkedin.py \
        --url "..." \
        --name "Test" \
        --skip-enrichment

    # Skip Google Sheets export
    python scrape_linkedin.py \
        --url "..." \
        --name "Test" \
        --skip-sheets
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vayne_client import get_client as get_vayne_client
from enrich_leads import enrich_leads
from export_leads_to_sheets import export_to_sheets


def run_pipeline(
    url: str,
    name: str,
    limit: int = None,
    skip_enrichment: bool = False,
    skip_sheets: bool = False,
    output_dir: str = ".tmp",
) -> dict:
    """
    Run the full LinkedIn lead generation pipeline.

    Args:
        url: LinkedIn Sales Navigator search URL
        name: Name for the order and output files
        limit: Max leads to scrape (None = all)
        skip_enrichment: If True, skip email enrichment
        skip_sheets: If True, skip Google Sheets export
        output_dir: Directory for intermediate files

    Returns:
        dict with pipeline results
    """
    os.makedirs(output_dir, exist_ok=True)

    # Generate filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in name).strip()
    safe_name = safe_name.replace(" ", "_")

    raw_csv = os.path.join(output_dir, f"{safe_name}_{timestamp}_raw.csv")
    enriched_csv = os.path.join(output_dir, f"{safe_name}_{timestamp}_enriched.csv")

    results = {
        "name": name,
        "url": url,
        "limit": limit,
        "steps": {},
    }

    # Step 1: Create Vayne order
    print("=" * 60)
    print("STEP 1: Creating Vayne scraping order")
    print("=" * 60)

    vayne = get_vayne_client()

    # First check the URL
    print(f"Validating URL...")
    check_result = vayne.check_url(url)
    if not check_result["success"]:
        print(f"  Error: {check_result['error']}")
        results["steps"]["url_check"] = {"success": False, "error": check_result["error"]}
        return results

    total_prospects = check_result["data"].get("total", 0)
    print(f"  Found {total_prospects} prospects")
    results["steps"]["url_check"] = {"success": True, "total_prospects": total_prospects}

    if limit:
        print(f"  Limiting to {limit} leads")

    # Create order
    print(f"\nCreating order: {name}")
    order_result = vayne.create_order(
        name=name,
        url=url,
        limit=limit,
        email_enrichment=False,  # We'll use AnyMailFinder instead
        export_format="simple",
    )

    if not order_result["success"]:
        print(f"  Error: {order_result['error']}")
        results["steps"]["create_order"] = {"success": False, "error": order_result["error"]}
        return results

    order_id = order_result["data"]["order"]["id"]
    print(f"  Order created: ID {order_id}")
    results["steps"]["create_order"] = {"success": True, "order_id": order_id}

    # Step 2: Wait for scraping
    print("\n" + "=" * 60)
    print("STEP 2: Waiting for scraping to complete")
    print("=" * 60)

    def progress_callback(order):
        scraped = order.get("scraped", 0)
        total = order.get("total", 0)
        status = order.get("scraping_status", "unknown")
        print(f"  Progress: {scraped}/{total} ({status})")

    wait_result = vayne.wait_for_order(
        order_id,
        poll_interval=15,
        timeout=7200,  # 2 hours max
        on_progress=progress_callback,
    )

    if not wait_result["success"]:
        print(f"  Error: {wait_result['error']}")
        results["steps"]["scraping"] = {"success": False, "error": wait_result["error"]}
        return results

    order_data = wait_result["data"]["order"]
    scraped_count = order_data.get("scraped", 0)
    print(f"\n  Scraping complete: {scraped_count} leads")
    results["steps"]["scraping"] = {"success": True, "scraped": scraped_count}

    # Step 3: Download CSV
    print("\n" + "=" * 60)
    print("STEP 3: Downloading CSV export")
    print("=" * 60)

    download_result = vayne.download_export(order_id, raw_csv)

    if not download_result["success"]:
        print(f"  Error: {download_result['error']}")
        results["steps"]["download"] = {"success": False, "error": download_result["error"]}
        return results

    print(f"  Downloaded: {raw_csv}")
    print(f"  Size: {download_result['data']['size_bytes']} bytes")
    results["steps"]["download"] = {
        "success": True,
        "file": raw_csv,
        "size": download_result["data"]["size_bytes"],
    }

    # Step 4: Enrich with emails
    if skip_enrichment:
        print("\n" + "=" * 60)
        print("STEP 4: Skipping email enrichment (--skip-enrichment)")
        print("=" * 60)
        results["steps"]["enrichment"] = {"success": True, "skipped": True}
        final_csv = raw_csv
    else:
        print("\n" + "=" * 60)
        print("STEP 4: Enriching with AnyMailFinder")
        print("=" * 60)

        try:
            enrich_result = enrich_leads(
                input_file=raw_csv,
                output_file=enriched_csv,
                dry_run=False,
            )
            print(f"\n  Enrichment complete:")
            print(f"    Processed: {enrich_result.get('enriched', 0)}")
            print(f"    Emails found: {enrich_result.get('emails_found', 0)}")
            print(f"    Success rate: {enrich_result.get('success_rate', 0):.1f}%")

            results["steps"]["enrichment"] = {
                "success": True,
                "file": enriched_csv,
                "emails_found": enrich_result.get("emails_found", 0),
                "success_rate": enrich_result.get("success_rate", 0),
            }
            final_csv = enriched_csv
        except Exception as e:
            print(f"  Error: {str(e)}")
            results["steps"]["enrichment"] = {"success": False, "error": str(e)}
            final_csv = raw_csv

    # Step 5: Export to Google Sheets
    if skip_sheets:
        print("\n" + "=" * 60)
        print("STEP 5: Skipping Google Sheets export (--skip-sheets)")
        print("=" * 60)
        results["steps"]["sheets"] = {"success": True, "skipped": True}
    else:
        print("\n" + "=" * 60)
        print("STEP 5: Exporting to Google Sheets")
        print("=" * 60)

        sheet_title = f"LinkedIn Leads - {name}"
        try:
            sheets_result = export_to_sheets(
                input_file=final_csv,
                create_title=sheet_title,
                sheet_name="Leads",
                valid_only=not skip_enrichment,  # Only filter if we enriched
            )

            if sheets_result["success"]:
                print(f"\n  Spreadsheet created!")
                print(f"    URL: {sheets_result['url']}")
                print(f"    Rows: {sheets_result['exported_rows']}")
                results["steps"]["sheets"] = {
                    "success": True,
                    "url": sheets_result["url"],
                    "rows": sheets_result["exported_rows"],
                }
            else:
                print(f"  Error: {sheets_result.get('error')}")
                results["steps"]["sheets"] = {"success": False, "error": sheets_result.get("error")}
        except Exception as e:
            print(f"  Error: {str(e)}")
            results["steps"]["sheets"] = {"success": False, "error": str(e)}

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    if results["steps"].get("sheets", {}).get("url"):
        print(f"\nGoogle Sheet: {results['steps']['sheets']['url']}")

    print(f"\nLocal files:")
    print(f"  Raw: {raw_csv}")
    if not skip_enrichment:
        print(f"  Enriched: {enriched_csv}")

    results["success"] = all(
        step.get("success", False)
        for step in results["steps"].values()
    )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Full LinkedIn lead generation pipeline"
    )
    parser.add_argument(
        "--url", "-u",
        required=True,
        help="LinkedIn Sales Navigator search URL",
    )
    parser.add_argument(
        "--name", "-n",
        help="Name for the order (default: auto-generated)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Max leads to scrape (default: all)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Just validate URL and show prospect count (no credits used)",
    )
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Skip email enrichment step",
    )
    parser.add_argument(
        "--skip-sheets",
        action="store_true",
        help="Skip Google Sheets export",
    )
    parser.add_argument(
        "--output-dir",
        default=".tmp",
        help="Directory for intermediate files (default: .tmp)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    # Generate name if not provided
    if not args.name:
        args.name = f"LinkedIn_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # Check-only mode
        if args.check_only:
            print("Checking URL (no credits used)...")
            vayne = get_vayne_client()
            result = vayne.check_url(args.url)

            if result["success"]:
                print(f"  Valid URL!")
                print(f"  Total prospects: {result['data'].get('total')}")
                print(f"  Type: {result['data'].get('type')}")
                sys.exit(0)
            else:
                print(f"  Error: {result['error']}")
                sys.exit(1)

        # Full pipeline
        result = run_pipeline(
            url=args.url,
            name=args.name,
            limit=args.limit,
            skip_enrichment=args.skip_enrichment,
            skip_sheets=args.skip_sheets,
            output_dir=args.output_dir,
        )

        if args.json:
            print(json.dumps(result, indent=2))

        sys.exit(0 if result.get("success") else 1)

    except ValueError as e:
        print(f"Setup error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
