#!/usr/bin/env python3
"""
Extract structured data from a PDF invoice.

Usage:
    python3 extract_invoice.py <path_to_invoice.pdf>

Returns JSON to stdout with vendor, amount, date, line items, tax.
Uses pdfplumber for text extraction, falls back to pytesseract OCR for scanned PDFs.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def error_exit(message: str):
    """Print a JSON error and exit."""
    print(json.dumps({"success": False, "error": message}, indent=2))
    sys.exit(1)


def extract_text_pdfplumber(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_ocr(pdf_path: str) -> str:
    """Fallback: extract text from scanned PDF using OCR."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        error_exit(
            "OCR fallback requires pytesseract and pdf2image. "
            "Install with: pip install pytesseract pdf2image"
        )

    images = convert_from_path(pdf_path)
    text_parts = []
    for img in images:
        text_parts.append(pytesseract.image_to_string(img))
    return "\n".join(text_parts)


def extract_tables(pdf_path: str) -> list[list[list[str]]]:
    """Extract tables from PDF pages using pdfplumber."""
    import pdfplumber

    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)
    return all_tables


def parse_amount(text: str) -> float | None:
    """Parse a monetary amount from text, handling $, commas, etc."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text.strip())
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def detect_currency(text: str) -> str:
    """Detect currency from symbols or ISO codes in text."""
    currency_map = {
        "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY",
        "CAD": "CAD", "AUD": "AUD", "CHF": "CHF",
    }
    # Check for ISO codes first
    for code in ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF"]:
        if code in text:
            return code
    # Then symbols
    for symbol, code in currency_map.items():
        if symbol in text:
            return code
    return "USD"


def parse_date(text: str) -> str | None:
    """Try multiple date formats and return ISO 8601."""
    formats = [
        "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y", "%m-%d-%Y", "%d-%m-%Y",
        "%m/%d/%y", "%d/%m/%y", "%b. %d, %Y",
    ]
    text = text.strip().rstrip(".")
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def find_date(text: str, label_pattern: str) -> str | None:
    """Find a date near a label in the text."""
    pattern = rf"{label_pattern}\s*[:\-]?\s*(\S+[\s\S]{{0,20}})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip().split("\n")[0].strip()
        # Try parsing progressively shorter substrings
        for length in range(len(candidate), 5, -1):
            result = parse_date(candidate[:length])
            if result:
                return result
    return None


def find_amount(text: str, label_pattern: str) -> float | None:
    """Find a monetary amount near a label in the text."""
    pattern = rf"{label_pattern}\s*[:\-]?\s*\$?([\d,]+\.?\d*)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return parse_amount(match.group(1))
    return None


def extract_vendor(text: str) -> str:
    """Extract vendor name — typically the first prominent line of the invoice."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    # Skip lines that look like headers/labels
    skip_patterns = re.compile(
        r"^(invoice|bill|statement|receipt|date|due|to|from|page|#|no\.|number)",
        re.IGNORECASE,
    )
    for line in lines[:5]:
        if not skip_patterns.match(line) and len(line) > 2:
            return line
    return lines[0] if lines else "Unknown"


def extract_vendor_address(text: str, vendor: str) -> str | None:
    """Try to extract address lines following the vendor name."""
    idx = text.find(vendor)
    if idx == -1:
        return None
    after = text[idx + len(vendor):idx + len(vendor) + 200]
    lines = [l.strip() for l in after.split("\n") if l.strip()]
    address_lines = []
    for line in lines[:3]:
        # Stop at labels
        if re.match(r"^(invoice|bill|date|due|to|from|item|desc|qty)", line, re.IGNORECASE):
            break
        # Looks like an address line (has numbers or commas or state abbreviations)
        if re.search(r"\d|,|[A-Z]{2}\s+\d{5}", line):
            address_lines.append(line)
    return ", ".join(address_lines) if address_lines else None


def extract_invoice_number(text: str) -> str | None:
    """Find invoice number. Handles cases where pdfplumber splits the number across lines."""
    # First try: number on the same line
    patterns = [
        r"invoice\s*#?\s*[:\-]?\s*(\d+)",
        r"inv\s*[#.\-]?\s*(\d+)",
        r"invoice\s+number\s*[:\-]?\s*(\d+)",
        r"#\s*(\d+)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            digits = match.group(1)
            # Check if the number continues on the next line (pdfplumber line-split)
            after = text[match.end():]
            continuation = re.match(r"\s*\n(\d+)", after)
            if continuation:
                digits += continuation.group(1)
            return digits
    return None


def parse_line_items_from_tables(tables: list[list[list[str]]]) -> list[dict]:
    """Parse line items from extracted tables."""
    items = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [str(c).lower().strip() if c else "" for c in table[0]]

        # Find relevant columns
        desc_col = next((i for i, h in enumerate(header) if "desc" in h or "item" in h or "product" in h or "service" in h), None)
        qty_col = next((i for i, h in enumerate(header) if "qty" in h or "quantity" in h or "qnty" in h), None)
        price_col = next((i for i, h in enumerate(header) if "price" in h or "rate" in h or "unit" in h), None)
        amount_col = next((i for i, h in enumerate(header) if "amount" in h or "total" in h or "ext" in h or "line" in h), None)

        if desc_col is None and amount_col is None:
            continue

        for row in table[1:]:
            if not row or all(not c for c in row):
                continue
            item = {}
            if desc_col is not None and desc_col < len(row) and row[desc_col]:
                desc = str(row[desc_col]).strip()
                # Skip summary rows
                if re.match(r"^(sub\s*total|total|tax|shipping|discount|balance|credit|amount\s+due|grand\s+total)", desc, re.IGNORECASE):
                    continue
                item["description"] = desc
            if qty_col is not None and qty_col < len(row):
                qty = parse_amount(str(row[qty_col]))
                if qty is not None:
                    item["quantity"] = qty
            if price_col is not None and price_col < len(row):
                price = parse_amount(str(row[price_col]))
                if price is not None:
                    item["unit_price"] = price
            if amount_col is not None and amount_col < len(row):
                amt = parse_amount(str(row[amount_col]))
                if amt is not None:
                    item["amount"] = amt

            # Only keep items that have a description (skip bare amount rows)
            if item.get("description"):
                items.append(item)

    return items


def parse_line_items_from_text(text: str) -> list[dict]:
    """Fallback: parse line items from raw text using patterns."""
    items = []
    # Look for lines with a description followed by an amount
    pattern = r"^(.+?)\s+\$?([\d,]+\.\d{2})\s*$"
    for line in text.split("\n"):
        line = line.strip()
        match = re.match(pattern, line)
        if match:
            desc = match.group(1).strip()
            amount = parse_amount(match.group(2))
            if amount is not None and not re.match(
                r"^(sub\s*total|total|tax|shipping|discount|balance|due|paid|credit|amount\s+due|grand\s+total)",
                desc, re.IGNORECASE,
            ):
                items.append({"description": desc, "amount": amount})
    return items


def extract_invoice_data(pdf_path: str) -> dict:
    """Main extraction pipeline."""
    path = Path(pdf_path)
    if not path.exists():
        error_exit(f"File not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        error_exit(f"Not a PDF file: {pdf_path}")

    # Extract text
    text = extract_text_pdfplumber(pdf_path)
    ocr_used = False
    if len(text.strip()) < 50:
        text = extract_text_ocr(pdf_path)
        ocr_used = True

    if not text.strip():
        error_exit("Could not extract any text from the PDF (even with OCR).")

    # Extract tables for line items
    tables = [] if ocr_used else extract_tables(pdf_path)

    # Build result
    result = {"success": True}

    # Vendor
    result["vendor"] = extract_vendor(text)
    vendor_address = extract_vendor_address(text, result["vendor"])
    if vendor_address:
        result["vendor_address"] = vendor_address

    # Invoice number
    inv_num = extract_invoice_number(text)
    if inv_num:
        result["invoice_number"] = inv_num

    # Dates
    invoice_date = find_date(text, r"(?:invoice\s+)?date")
    if invoice_date:
        result["date"] = invoice_date
    due_date = find_date(text, r"due\s*date|payment\s+due|due")
    if due_date:
        result["due_date"] = due_date

    # Line items — prefer table extraction, fall back to text parsing
    line_items = parse_line_items_from_tables(tables)
    if not line_items:
        line_items = parse_line_items_from_text(text)

    # Deduplicate identical line items (multi-section PDFs repeat tables)
    seen = set()
    unique_items = []
    for item in line_items:
        key = (item.get("description", ""), item.get("amount"), item.get("quantity"), item.get("unit_price"))
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    line_items = unique_items
    result["line_items"] = line_items

    # Totals
    subtotal = find_amount(text, r"subtotal|sub\s*-?\s*total")
    tax = find_amount(text, r"(?:sales\s+)?tax|vat|gst|hst")
    total = find_amount(text, r"(?:grand\s+)?total|amount\s+due|balance\s+due|total\s+due")

    # If no subtotal but we have line items, sum them
    if subtotal is None and line_items:
        amounts = [i["amount"] for i in line_items if "amount" in i]
        if amounts:
            subtotal = round(sum(amounts), 2)

    if subtotal is not None:
        result["subtotal"] = subtotal
    if tax is not None:
        result["tax"] = tax
        # Derive tax rate if we have subtotal
        if subtotal and subtotal > 0:
            result["tax_rate"] = round(tax / subtotal, 4)
    else:
        result["tax"] = 0.0

    if total is not None:
        result["total"] = total
    elif subtotal is not None:
        result["total"] = round(subtotal + (tax or 0), 2)

    # Currency
    result["currency"] = detect_currency(text)

    # Notes (payment terms, PO numbers, etc.)
    notes_patterns = [
        r"(?:payment\s+)?terms?\s*[:\-]\s*(.+)",
        r"notes?\s*[:\-]\s*(.+)",
        r"(net\s+\d+)",
    ]
    notes = []
    for pat in notes_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            notes.append(match.group(1).strip())
    if notes:
        result["notes"] = "; ".join(notes)

    if ocr_used:
        result["_warning"] = "Text extracted via OCR — verify accuracy."

    return result


def main():
    if len(sys.argv) < 2:
        error_exit("Usage: python3 extract_invoice.py <path_to_invoice.pdf>")

    pdf_path = sys.argv[1]
    result = extract_invoice_data(pdf_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
