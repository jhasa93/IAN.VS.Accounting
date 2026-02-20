from pathlib import Path
from invoices.extraction import extract_invoice

# Check if any staged files exist
staging = Path("data/staging")
if staging.exists():
    files = list(staging.glob("*"))
    if files:
        for f in files[:1]:  # Just check first file
            print(f"Testing extraction on: {f.name}\n")
            result = extract_invoice(f, enable_ocr=True)
            
            print("Extraction Results:")
            print(f"  Vendor Name: {result.vendor_name}")
            print(f"  Vendor VAT: {result.vendor_vat}")
            print(f"  Invoice Date: {result.invoice_date}")
            print(f"  Currency: {result.currency}")
            print(f"  Total Amount: {result.total_amount}")
            print(f"  Tax Amount: {result.tax_amount}")
            print(f"  Language: {result.language}")
            print(f"  Valid: {result.valid}")
            print(f"  Confidence: {result.confidence}")
            print(f"  Validation Errors: {result.validation_errors}")
    else:
        print("No files in staging directory")
else:
    print("Staging directory doesn't exist")
