"""Utility script to view Google Sheets ledger contents.

Displays all rows from your configured spreadsheet
showing invoice records and their extracted data.

Usage:
    python check_sheet.py
"""
from invoices.google_services import build_services
from invoices.config import load_config

config = load_config()
gmail, drive, sheets = build_services(config.credentials_path)

# Read the spreadsheet
spreadsheet_id = config.spreadsheet_id
result = sheets.spreadsheets().values().get(
    spreadsheetId=spreadsheet_id,
    range='A:L'
).execute()

values = result.get('values', [])
print(f"Spreadsheet has {len(values)} rows:")
for i, row in enumerate(values):
    print(f"Row {i+1}: {row}")
