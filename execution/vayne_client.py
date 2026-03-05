#!/usr/bin/env python3
"""
Vayne API Client - LinkedIn Sales Navigator scraping via Vayne.

This module provides a client for the Vayne API to automate LinkedIn lead scraping.
Handles order creation, status polling, and CSV download.

Environment Variables:
    VAYNE_API_KEY: Your Vayne API token (get from Dashboard > API Settings)

Usage:
    from vayne_client import get_client

    client = get_client()

    # Check credits
    credits = client.get_credits()
    print(f"Available: {credits['data']['available']}")

    # Create a scraping order
    result = client.create_order(
        name="SaaS CEOs",
        url="https://www.linkedin.com/sales/search/people?query=...",
        limit=100,
    )

    # Wait for completion and get CSV
    order = client.wait_for_order(result["data"]["id"])
    csv_path = client.download_export(order["data"]["id"], ".tmp/leads.csv")
"""

import os
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.vayne.io/api"


def get_headers() -> dict:
    """Get authorization headers for Vayne API."""
    api_key = os.getenv("VAYNE_API_KEY")
    if not api_key:
        raise ValueError("VAYNE_API_KEY not set in .env")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


class VayneClient:
    """Vayne API client for LinkedIn Sales Navigator scraping."""

    def __init__(self):
        self.headers = get_headers()

    def get_credits(self) -> dict:
        """
        Get current credits and limits.

        Returns:
            dict with success status and credit info
        """
        url = f"{BASE_URL}/credits"
        response = requests.get(url, headers=self.headers)
        return self._handle_response(response)

    def check_linkedin_auth(self) -> dict:
        """
        Check if LinkedIn session is authenticated.

        Returns:
            dict with authentication status
        """
        url = f"{BASE_URL}/linkedin_authentication"
        response = requests.get(url, headers=self.headers)
        return self._handle_response(response)

    def check_url(self, url: str) -> dict:
        """
        Validate a Sales Navigator URL and get prospect count.

        Args:
            url: LinkedIn Sales Navigator search URL

        Returns:
            dict with total prospects and type
        """
        api_url = f"{BASE_URL}/url_checks"
        payload = {"url": url}
        response = requests.post(api_url, json=payload, headers=self.headers, timeout=35)
        return self._handle_response(response)

    def create_order(
        self,
        name: str,
        url: str,
        limit: Optional[int] = None,
        email_enrichment: bool = False,
        export_format: str = "simple",
    ) -> dict:
        """
        Create a new scraping order.

        Args:
            name: Unique name for this order
            url: LinkedIn Sales Navigator search URL
            limit: Max profiles to scrape (None = all)
            email_enrichment: Use Vayne's email enrichment (costs extra credits)
            export_format: "simple" or "advanced"

        Returns:
            dict with order details including ID
        """
        api_url = f"{BASE_URL}/orders"
        payload = {
            "name": name,
            "url": url,
            "limit": limit,
            "email_enrichment": email_enrichment,
            "saved_search": False,
            "secondary_webhook": "",
            "export_format": export_format,
        }
        response = requests.post(api_url, json=payload, headers=self.headers)
        return self._handle_response(response)

    def get_order(self, order_id: int) -> dict:
        """
        Get order status and details.

        Args:
            order_id: The order ID

        Returns:
            dict with order details including scraping_status and export URLs
        """
        url = f"{BASE_URL}/orders/{order_id}"
        response = requests.get(url, headers=self.headers)
        return self._handle_response(response)

    def generate_export(self, order_id: int, export_format: str = "simple") -> dict:
        """
        Generate an export for a completed order.

        Args:
            order_id: The order ID
            export_format: "simple" or "advanced"

        Returns:
            dict with export status
        """
        url = f"{BASE_URL}/orders/{order_id}/export"
        payload = {"format": export_format}
        response = requests.post(url, json=payload, headers=self.headers)
        return self._handle_response(response)

    def wait_for_order(
        self,
        order_id: int,
        poll_interval: int = 10,
        timeout: int = 3600,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """
        Poll until order is complete.

        Args:
            order_id: The order ID
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait
            on_progress: Optional callback(order_data) for progress updates

        Returns:
            dict with completed order details
        """
        start_time = time.time()

        while True:
            result = self.get_order(order_id)

            if not result["success"]:
                return result

            order = result["data"]["order"]
            status = order.get("scraping_status")

            if on_progress:
                on_progress(order)

            if status == "finished":
                return result

            if status in ["failed", "cancelled"]:
                return {
                    "success": False,
                    "error": f"Order {status}",
                    "data": result["data"],
                }

            if time.time() - start_time > timeout:
                return {
                    "success": False,
                    "error": f"Timeout after {timeout}s",
                    "data": result["data"],
                }

            time.sleep(poll_interval)

    def download_export(
        self,
        order_id: int,
        output_path: str,
        export_format: str = "simple",
        wait_for_export: bool = True,
    ) -> dict:
        """
        Download the CSV export for a completed order.

        Args:
            order_id: The order ID
            output_path: Where to save the CSV
            export_format: "simple" or "advanced"
            wait_for_export: If True, wait for export generation

        Returns:
            dict with success status and file path
        """
        # Get order to check export status
        result = self.get_order(order_id)
        if not result["success"]:
            return result

        order = result["data"]["order"]
        exports = order.get("exports", {})
        export_info = exports.get(export_format, {})

        # Check if export is ready
        if export_info.get("status") != "completed":
            if not wait_for_export:
                return {
                    "success": False,
                    "error": f"Export not ready: {export_info.get('status')}",
                }

            # Trigger export generation
            self.generate_export(order_id, export_format)

            # Wait for export
            for _ in range(60):  # Max 5 minutes
                time.sleep(5)
                result = self.get_order(order_id)
                if result["success"]:
                    exports = result["data"]["order"].get("exports", {})
                    export_info = exports.get(export_format, {})
                    if export_info.get("status") == "completed":
                        break

        file_url = export_info.get("file_url")
        if not file_url:
            return {
                "success": False,
                "error": "No export URL available",
            }

        # Download the file
        try:
            response = requests.get(file_url, timeout=120)
            response.raise_for_status()

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(response.content)

            return {
                "success": True,
                "data": {
                    "file_path": output_path,
                    "size_bytes": len(response.content),
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Download failed: {str(e)}",
            }

    def _handle_response(self, response: requests.Response) -> dict:
        """Handle API response and normalize format."""
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code in [200, 201, 202]:
            return {
                "success": True,
                "data": data,
                "status_code": response.status_code,
            }
        else:
            return {
                "success": False,
                "error": data.get("details", data.get("error", f"HTTP {response.status_code}")),
                "status_code": response.status_code,
                "data": data,
            }


def get_client() -> VayneClient:
    """Get a configured Vayne client instance."""
    return VayneClient()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Vayne API")
    parser.add_argument("--credits", action="store_true", help="Check credits")
    parser.add_argument("--auth", action="store_true", help="Check LinkedIn auth")
    parser.add_argument("--check-url", help="Validate a Sales Navigator URL")
    args = parser.parse_args()

    try:
        client = get_client()

        if args.credits:
            result = client.get_credits()
            if result["success"]:
                print(f"Credits: {result['data']}")
            else:
                print(f"Error: {result['error']}")

        if args.auth:
            result = client.check_linkedin_auth()
            if result["success"]:
                print(f"LinkedIn Auth: {result['data']}")
            else:
                print(f"Error: {result['error']}")

        if args.check_url:
            print(f"Checking URL...")
            result = client.check_url(args.check_url)
            if result["success"]:
                print(f"  Total prospects: {result['data'].get('total')}")
                print(f"  Type: {result['data'].get('type')}")
            else:
                print(f"  Error: {result['error']}")

    except ValueError as e:
        print(f"Setup error: {e}")
