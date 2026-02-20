from __future__ import annotations

from typing import Any

from .models import LedgerRecord

HEADERS = [
    "Invoice Issued Date",
    "Due Date",
    "Vendor Name",
    "Vendor ICO/VAT",
    "Language",
    "Amount",
    "Currency",
    "Tax Amount",
    "Category",
    "Source",
    "Drive File Link",
    "Gmail Message ID",
]


def ensure_sheet_headers(sheets: Any, spreadsheet_id: str) -> None:
    """Ensure the spreadsheet has the proper header row."""
    try:
        result = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="A1:L1"
        ).execute()
        existing = result.get("values", [[]])
        if existing and existing[0]:
            return  # Headers already exist
    except Exception:
        pass  # Sheet might be empty
    
    # Write headers
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1:L1",
        valueInputOption="RAW",
        body={"values": [HEADERS]}
    ).execute()


def append_or_update_record(sheets: Any, spreadsheet_id: str, record: LedgerRecord) -> None:
    """Append or update a record in the Google Sheet."""
    # Ensure headers exist
    ensure_sheet_headers(sheets, spreadsheet_id)
    
    # Get all data to find if record exists (using Gmail Message ID as key)
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="L:L"  # Gmail Message ID column
    ).execute()
    
    values = result.get("values", [])
    row_to_update = None
    
    # Find existing record (skip header row)
    for idx, row in enumerate(values[1:], start=2):
        if row and row[0] == record.gmail_message_id:
            row_to_update = idx
            break
    
    # Prepare record values
    record_values = [
        record.invoice_date,
        record.due_date,
        record.vendor_name,
        record.vendor_vat,
        record.language,
        record.total_amount,
        record.currency,
        record.tax_amount,
        record.category,
        record.source_type,
        record.drive_file_link,
        record.gmail_message_id,
    ]
    
    if row_to_update:
        # Update existing row
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"A{row_to_update}:L{row_to_update}",
            valueInputOption="RAW",
            body={"values": [record_values]}
        ).execute()
    else:
        # Append new row
        sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="A:L",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [record_values]}
        ).execute()


def reconcile(sheets: Any, spreadsheet_id: str) -> tuple[int, int]:
    """Check for duplicate Gmail Message IDs in the sheet."""
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="L:L"  # Gmail Message ID column
    ).execute()
    
    values = result.get("values", [])
    if len(values) <= 1:
        return 0, 0  # Only headers or empty
    
    seen = set()
    dup = 0
    
    for row in values[1:]:  # Skip header
        if not row or not row[0]:
            continue
        message_id = row[0]
        if message_id in seen:
            dup += 1
        seen.add(message_id)
    
    return len(values) - 1, dup
