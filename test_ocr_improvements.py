from pathlib import Path
from invoices.extraction import extract_invoice
import json

# Load the queue to see what files need review
queue_path = Path("data/queue.json")
with open(queue_path) as f:
    queue = json.load(f)

print(f"Testing OCR on {len(queue)} queued items:\n")
print("=" * 80)

for item in queue:
    if item['status'] == 'Needs Review':
        staged_path = Path(item['staged_path'])
        if staged_path.exists():
            print(f"\n📄 File: {staged_path.name}")
            print(f"   Original status: {item['review_notes']}")
            print(f"   Confidence: {item['extraction_confidence']}")
            print("\n🔍 Re-extracting with improved OCR...\n")
            
            # Re-extract with OCR enabled
            result = extract_invoice(staged_path, enable_ocr=True, ocr_languages="eng+deu+spa+ces")
            
            print(f"   Vendor Name: {result.vendor_name}")
            print(f"   Vendor VAT: {result.vendor_vat}")
            print(f"   Invoice Number: {result.invoice_number}")
            print(f"   Invoice Date: {result.invoice_date}")
            print(f"   Currency: {result.currency}")
            print(f"   Total Amount: {result.total_amount}")
            print(f"   Tax Amount: {result.tax_amount}")
            print(f"   Language: {result.language}")
            print(f"   ✅ Valid: {result.valid}")
            print(f"   Confidence: {result.confidence}")
            if result.validation_errors:
                print(f"   ⚠️  Validation Errors: {', '.join(result.validation_errors)}")
            print("\n" + "=" * 80)
        else:
            print(f"\n⚠️  File not found: {staged_path}")
