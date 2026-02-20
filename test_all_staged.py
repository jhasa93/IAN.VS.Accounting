from pathlib import Path
from invoices.extraction import extract_invoice

# Check all staged files
staging = Path("data/staging")
if staging.exists():
    files = list(staging.glob("*"))
    print(f"Found {len(files)} files in staging\n")
    
    for f in files:
        print(f"=" * 80)
        print(f"File: {f.name}")
        print(f"=" * 80)
        result = extract_invoice(f, enable_ocr=True)
        
        print(f"Vendor Name: {result.vendor_name}")
        print(f"Vendor VAT: {result.vendor_vat}")
        print(f"Invoice Date: {result.invoice_date}")
        print(f"Currency: {result.currency}")
        print(f"Total Amount: {result.total_amount}")
        print(f"Tax Amount: {result.tax_amount}")
        print(f"Language: {result.language}")
        print(f"Valid: {result.valid}")
        print(f"Confidence: {result.confidence}")
        print(f"Validation Errors: {result.validation_errors}")
        print()
else:
    print("Staging directory doesn't exist")
