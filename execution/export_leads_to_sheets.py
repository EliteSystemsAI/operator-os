#!/usr/bin/env python3
"""
Export Leads to Google Sheets - Push enriched leads to a Google Spreadsheet.

This script takes an enriched CSV (from enrich_leads.py) and exports it
to a Google Sheet for easy access and sharing.

Usage:
    # Export to existing spreadsheet
    python export_leads_to_sheets.py --input enriched_leads.csv --spreadsheet-id SHEET_ID

    # Create new spreadsheet
    python export_leads_to_sheets.py --input enriched_leads.csv --create "LinkedIn Leads - Dec 2024"

    # Append to existing data (vs overwrite)
    python export_leads_to_sheets.py --input enriched_leads.csv --spreadsheet-id SHEET_ID --append

    # Only export leads with valid emails
    python export_leads_to_sheets.py --input enriched_leads.csv --create "Leads" --valid-only
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

from google_sheets_client import get_client


def read_csv(file_path: str) -> tuple[list[str], list[list[str]]]:
    """Read CSV file and return headers + rows."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    return headers, rows


def filter_valid_emails(headers: list[str], rows: list[list[str]]) -> list[list[str]]:
    """Filter to only rows with valid email status."""
    try:
        status_idx = headers.index("email_status")
        email_idx = headers.index("email")
    except ValueError:
        # If columns don't exist, return all rows
        return rows

    return [
        row for row in rows
        if len(row) > max(status_idx, email_idx)
        and row[status_idx] in ("valid", "ok", "pre-enriched")  # ok = AnyMailFinder bulk API
        and row[email_idx]
    ]


def export_to_sheets(
    input_file: str,
    spreadsheet_id: Optional[str] = None,
    create_title: Optional[str] = None,
    sheet_name: str = "Leads",
    append: bool = False,
    valid_only: bool = False,
) -> dict:
    """
    Export CSV to Google Sheets.

    Args:
        input_file: Path to enriched CSV
        spreadsheet_id: Existing spreadsheet ID to write to
        create_title: Title for new spreadsheet (creates if provided)
        sheet_name: Name of the sheet/tab
        append: If True, append rows; if False, overwrite
        valid_only: If True, only export rows with valid emails

    Returns:
        dict with export details including spreadsheet URL
    """
    # Read CSV
    headers, rows = read_csv(input_file)
    total_rows = len(rows)
    print(f"Read {total_rows} leads from {input_file}")

    # Filter if requested
    if valid_only:
        rows = filter_valid_emails(headers, rows)
        print(f"Filtered to {len(rows)} leads with valid emails")

    if not rows:
        return {
            "success": False,
            "error": "No leads to export after filtering",
            "total_rows": total_rows,
            "exported_rows": 0,
        }

    # Initialize client
    client = get_client()

    # Create new spreadsheet if requested
    if create_title:
        print(f"Creating spreadsheet: {create_title}")
        result = client.create_spreadsheet(create_title, [sheet_name])
        if not result["success"]:
            return {
                "success": False,
                "error": f"Failed to create spreadsheet: {result.get('error')}",
            }
        spreadsheet_id = result["data"]["spreadsheet_id"]
        print(f"Created: {result['data']['url']}")

    if not spreadsheet_id:
        return {
            "success": False,
            "error": "Either --spreadsheet-id or --create is required",
        }

    # Prepare data with headers
    data = [headers] + rows

    # Write to sheet
    if append:
        print(f"Appending {len(rows)} rows to {sheet_name}...")
        result = client.append_rows(spreadsheet_id, sheet_name, rows)
    else:
        print(f"Writing {len(rows)} rows to {sheet_name}...")
        result = client.write_sheet(spreadsheet_id, f"{sheet_name}!A1", data)

    if not result["success"]:
        return {
            "success": False,
            "error": f"Failed to write data: {result.get('error')}",
            "spreadsheet_id": spreadsheet_id,
        }

    url = client.get_spreadsheet_url(spreadsheet_id)
    print(f"\nExport complete!")
    print(f"  Spreadsheet: {url}")
    print(f"  Rows exported: {len(rows)}")

    return {
        "success": True,
        "spreadsheet_id": spreadsheet_id,
        "url": url,
        "sheet_name": sheet_name,
        "total_rows": total_rows,
        "exported_rows": len(rows),
        "mode": "append" if append else "overwrite",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export enriched leads to Google Sheets"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input CSV file (enriched leads)",
    )
    parser.add_argument(
        "--spreadsheet-id", "-s",
        help="Existing Google Spreadsheet ID to write to",
    )
    parser.add_argument(
        "--create", "-c",
        help="Create a new spreadsheet with this title",
    )
    parser.add_argument(
        "--sheet-name",
        default="Leads",
        help="Name of the sheet/tab (default: Leads)",
    )
    parser.add_argument(
        "--append", "-a",
        action="store_true",
        help="Append to existing data instead of overwriting",
    )
    parser.add_argument(
        "--valid-only", "-v",
        action="store_true",
        help="Only export leads with valid email addresses",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    # Validate input exists
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Validate we have either spreadsheet_id or create
    if not args.spreadsheet_id and not args.create:
        print("Error: Either --spreadsheet-id or --create is required", file=sys.stderr)
        sys.exit(1)

    try:
        result = export_to_sheets(
            input_file=args.input,
            spreadsheet_id=args.spreadsheet_id,
            create_title=args.create,
            sheet_name=args.sheet_name,
            append=args.append,
            valid_only=args.valid_only,
        )

        if args.json:
            print(json.dumps(result, indent=2))

        if result["success"]:
            sys.exit(0)
        else:
            print(f"Error: {result.get('error')}", file=sys.stderr)
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"File error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
