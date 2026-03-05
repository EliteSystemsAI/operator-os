#!/usr/bin/env python3
"""
Google Sheets API Client - Read and write to Google Sheets.

This module provides a reusable client for Google Sheets operations.
Supports both OAuth2 (desktop app) and service account authentication.

Files:
    credentials.json: OAuth2 client credentials (desktop app) or service account key
    token.json: Cached OAuth2 tokens (auto-generated on first run)

Setup (OAuth2 - recommended for personal use):
    1. Create a Google Cloud project
    2. Enable Google Sheets API
    3. Create OAuth2 credentials (Desktop app type)
    4. Download as credentials.json
    5. First run will open browser for authentication

Usage:
    from google_sheets_client import get_client

    client = get_client()

    # Read data
    data = client.read_sheet("SPREADSHEET_ID", "Sheet1!A1:D100")

    # Write data
    client.write_sheet("SPREADSHEET_ID", "Sheet1!A1", [["Name", "Email"], ["John", "john@example.com"]])

    # Append rows
    client.append_rows("SPREADSHEET_ID", "Sheet1", [["New", "Row"]])
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    raise ImportError(
        "Google API libraries not installed. Run:\n"
        "pip install google-auth google-auth-oauthlib google-api-python-client"
    )

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Default paths
DEFAULT_CREDENTIALS_PATH = "credentials_leftclick.json"
DEFAULT_TOKEN_PATH = "token_leftclick.json"


def get_credentials():
    """
    Load credentials, supporting both OAuth2 and service account.

    OAuth2 flow:
        1. Check for cached token in token.json
        2. If expired, refresh using refresh token
        3. If no token, run interactive OAuth flow (opens browser)

    Service account:
        - Detected by presence of 'type': 'service_account' in credentials.json
    """
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS_PATH)
    token_path = os.path.join(os.path.dirname(creds_path) or ".", DEFAULT_TOKEN_PATH)

    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Credentials file not found at {creds_path}. "
            "Download from Google Cloud Console."
        )

    # Check if it's a service account
    with open(creds_path, "r") as f:
        creds_data = json.load(f)

    if creds_data.get("type") == "service_account":
        # Service account auth
        return ServiceAccountCredentials.from_service_account_file(creds_path, scopes=SCOPES)

    # OAuth2 flow for desktop app
    creds = None

    # Check for existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            creds.refresh(Request())
        else:
            # Run OAuth flow (opens browser)
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())
        print(f"Saved credentials to {token_path}")

    return creds


class GoogleSheetsClient:
    """Google Sheets API client for read/write operations."""

    def __init__(self):
        self.creds = get_credentials()
        self.service = build("sheets", "v4", credentials=self.creds)
        self.sheets = self.service.spreadsheets()

    def read_sheet(
        self,
        spreadsheet_id: str,
        range_name: str,
        value_render_option: str = "FORMATTED_VALUE",
    ) -> dict:
        """
        Read values from a spreadsheet range.

        Args:
            spreadsheet_id: The spreadsheet ID (from URL)
            range_name: A1 notation range (e.g., "Sheet1!A1:D100")
            value_render_option: How to render values (FORMATTED_VALUE, UNFORMATTED_VALUE, FORMULA)

        Returns:
            dict with keys:
                - success: bool
                - data: {values: [[...], [...]], range: str, major_dimension: str}
                - error: error message if failed
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueRenderOption=value_render_option,
            ).execute()

            return {
                "success": True,
                "data": {
                    "values": result.get("values", []),
                    "range": result.get("range"),
                    "major_dimension": result.get("majorDimension"),
                },
            }
        except HttpError as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": e.resp.status,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def write_sheet(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """
        Write values to a spreadsheet range (overwrites existing data).

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: A1 notation range (e.g., "Sheet1!A1")
            values: 2D list of values to write
            value_input_option: How to interpret input (USER_ENTERED, RAW)

        Returns:
            dict with success status and update details
        """
        try:
            body = {"values": values}
            result = self.sheets.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
            ).execute()

            return {
                "success": True,
                "data": {
                    "updated_range": result.get("updatedRange"),
                    "updated_rows": result.get("updatedRows"),
                    "updated_columns": result.get("updatedColumns"),
                    "updated_cells": result.get("updatedCells"),
                },
            }
        except HttpError as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": e.resp.status,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def append_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        values: list[list],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """
        Append rows to the end of a sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: Name of the sheet (e.g., "Sheet1")
            values: 2D list of rows to append
            value_input_option: How to interpret input (USER_ENTERED, RAW)

        Returns:
            dict with success status and update details
        """
        try:
            body = {"values": values}
            result = self.sheets.values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:A",
                valueInputOption=value_input_option,
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()

            updates = result.get("updates", {})
            return {
                "success": True,
                "data": {
                    "updated_range": updates.get("updatedRange"),
                    "updated_rows": updates.get("updatedRows"),
                    "updated_columns": updates.get("updatedColumns"),
                    "updated_cells": updates.get("updatedCells"),
                },
            }
        except HttpError as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": e.resp.status,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def clear_sheet(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> dict:
        """
        Clear values from a range (keeps formatting).

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: A1 notation range to clear

        Returns:
            dict with success status
        """
        try:
            self.sheets.values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name,
            ).execute()

            return {"success": True, "data": {"cleared_range": range_name}}
        except HttpError as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": e.resp.status,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def create_spreadsheet(
        self,
        title: str,
        sheet_names: Optional[list[str]] = None,
    ) -> dict:
        """
        Create a new spreadsheet.

        Args:
            title: Spreadsheet title
            sheet_names: Optional list of sheet names to create

        Returns:
            dict with spreadsheet ID and URL
        """
        try:
            sheets_data = []
            if sheet_names:
                sheets_data = [{"properties": {"title": name}} for name in sheet_names]
            else:
                sheets_data = [{"properties": {"title": "Sheet1"}}]

            spreadsheet = {
                "properties": {"title": title},
                "sheets": sheets_data,
            }

            result = self.sheets.create(body=spreadsheet).execute()

            spreadsheet_id = result.get("spreadsheetId")
            return {
                "success": True,
                "data": {
                    "spreadsheet_id": spreadsheet_id,
                    "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                    "title": result.get("properties", {}).get("title"),
                },
            }
        except HttpError as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": e.resp.status,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_spreadsheet_url(self, spreadsheet_id: str) -> str:
        """Get the URL for a spreadsheet."""
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


def get_client() -> GoogleSheetsClient:
    """Get a configured Google Sheets client instance."""
    return GoogleSheetsClient()


if __name__ == "__main__":
    # Quick test - list first sheet of a spreadsheet
    import argparse

    parser = argparse.ArgumentParser(description="Test Google Sheets connection")
    parser.add_argument("--spreadsheet-id", help="Spreadsheet ID to test read")
    parser.add_argument("--create", help="Create a new spreadsheet with this title")
    args = parser.parse_args()

    try:
        client = get_client()
        print("Google Sheets client initialized successfully!")

        if args.create:
            print(f"Creating spreadsheet: {args.create}")
            result = client.create_spreadsheet(args.create)
            if result["success"]:
                print(f"  Created: {result['data']['url']}")
            else:
                print(f"  Error: {result['error']}")

        if args.spreadsheet_id:
            print(f"Reading from spreadsheet: {args.spreadsheet_id}")
            result = client.read_sheet(args.spreadsheet_id, "Sheet1!A1:E5")
            if result["success"]:
                values = result["data"]["values"]
                print(f"  Found {len(values)} rows")
                for row in values[:3]:
                    print(f"    {row}")
            else:
                print(f"  Error: {result['error']}")

    except FileNotFoundError as e:
        print(f"Setup error: {e}")
    except Exception as e:
        print(f"Error: {e}")
