from pathlib import Path
from invoices.extraction import _extract_text

# Check the problematic invoice.pdf
invoice_pdf = Path("data/staging/invoice.pdf")
if invoice_pdf.exists():
    print("Extracting text from invoice.pdf...\n")
    text = _extract_text(invoice_pdf, enable_ocr=True)
    print("=" * 80)
    print("EXTRACTED TEXT:")
    print("=" * 80)
    print(text)
    print("\n" + "=" * 80)
else:
    print("invoice.pdf not found")
