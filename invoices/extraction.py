from __future__ import annotations

import base64
import csv
import json
import re
from pathlib import Path

from dateutil.parser import parse as parse_date
from openpyxl import load_workbook
from pypdf import PdfReader

from .models import ExtractionResult

CURRENCY_RE = re.compile(r"\b(USD|EUR|GBP|AUD|CAD|INR|CZK)\b", re.I)
DATE_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./]\s*\d{1,2}[./]\s*\d{4})\b")
INVOICE_RE = re.compile(
    r"(?:invoice|faktura|factura|rechnung)\s*(?:#|number|no|num(?:ero)?|cislo|č(?:\.|\s*)?íslo)?\s*[:\-]?\s*((?=[A-Z0-9\-/]*\d)[A-Z0-9\-/]+)",
    re.I,
)
TOTAL_RE = re.compile(r"(?:total|celkem|gesamt)\s*[:\-]?\s*([0-9]+(?:[.,][0-9]{1,2})?)", re.I)
VAT_RE = re.compile(
    r"(?:VAT|IČO|ICO|DIČ|DIC|IČ|IC|Tax ID|Registration No)\s*[:\-]?\s*([A-Z]{0,2}\s*[0-9\s]{6,15})",
    re.I,
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff"}
VENDOR_LINE_RE = re.compile(
    r"(?:supplier|vendor|dodavatel|dodavatel[ée]?|from|vystavil|issuer)\s*[:\-]?\s*([^\n\r]{2,80})",
    re.I,
)
# Czech company name pattern (s.r.o., a.s., spol. s r.o., etc.) at start of document
COMPANY_NAME_RE = re.compile(
    r"^([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][^\n]{3,60}(?:s\.r\.o\.|a\.s\.|spol\.\s*s\s*r\.o\.|v\.o\.s\.))",
    re.I | re.MULTILINE,
)


def _validate(result: ExtractionResult) -> ExtractionResult:
    errs = []
    for field in ["vendor_name", "vendor_vat", "invoice_date", "currency"]:
        if not getattr(result, field):
            errs.append(f"missing_{field}")
    if result.total_amount is None:
        errs.append("missing_total_amount")
    if result.invoice_date:
        try:
            parse_date(result.invoice_date)
        except Exception:
            errs.append("invalid_invoice_date")
    result.validation_errors = errs
    result.valid = len(errs) == 0
    if result.valid and result.confidence < 0.8:
        result.confidence = 0.8
    return result


def _detect_language(text: str) -> str:
    """Simple language detection based on common words."""
    text_lower = text.lower()
    
    # Czech indicators
    czech_words = ['faktura', 'celkem', 'dph', 'kč', 'částka', 'dodavatel', 'odběratel', 'ičo', 'dič']
    czech_score = sum(1 for word in czech_words if word in text_lower)
    
    # German indicators
    german_words = ['rechnung', 'gesamt', 'mwst', 'betrag', 'lieferant', 'kunde', 'steuernummer']
    german_score = sum(1 for word in german_words if word in text_lower)
    
    # Spanish indicators
    spanish_words = ['factura', 'total', 'iva', 'importe', 'proveedor', 'cliente', 'nif', 'cif']
    spanish_score = sum(1 for word in spanish_words if word in text_lower)
    
    # English indicators
    english_words = ['invoice', 'total', 'vat', 'amount', 'supplier', 'customer', 'tax id']
    english_score = sum(1 for word in english_words if word in text_lower)
    
    scores = {
        'cs': czech_score,
        'de': german_score,
        'es': spanish_score,
        'en': english_score,
    }
    
    max_lang = max(scores, key=scores.get)
    return max_lang if scores[max_lang] > 0 else 'en'


def _normalize_date(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    try:
        parsed = parse_date(raw_value, dayfirst=True)
        return parsed.date().isoformat()
    except Exception:
        return raw_value


def _extract_vendor_name(text: str, path: Path) -> str | None:
    # Try Czech company name pattern first
    company_match = COMPANY_NAME_RE.search(text)
    if company_match:
        vendor = company_match.group(1).strip(" ,.-")
        if vendor and not vendor.lower().startswith(('variabilní', 'konstantní', 'specifický')):
            return vendor
    
    # Try generic vendor line pattern
    match = VENDOR_LINE_RE.search(text)
    if match:
        vendor = re.split(r"\s{2,}", match.group(1).strip())[0].strip(" ,.-")
        if vendor and not vendor.lower().startswith(('variabilní', 'konstantní', 'specifický')):
            return vendor

    # Fallback to filename-derived value (without UUID prefixes from staging)
    stem = path.stem
    stem = re.sub(r"^[0-9a-f]{8,32}_", "", stem, flags=re.I)
    if "_" in stem:
        guess = stem.split("_")[0].strip(" -")
        return guess or None
    return None


def _ocr_image(path: Path, ocr_languages: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception:
        return ""
    return pytesseract.image_to_string(Image.open(path), lang=ocr_languages)


def _ocr_pdf(path: Path, ocr_languages: str) -> str:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        return ""

    pages = convert_from_path(str(path))
    return "\n".join(pytesseract.image_to_string(page, lang=ocr_languages) for page in pages)


def _extract_text(path: Path, enable_ocr: bool = True, ocr_languages: str = "eng+deu+spa+ces") -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        if text.strip() or not enable_ocr:
            return text
        return _ocr_pdf(path, ocr_languages)
    if suffix in IMAGE_SUFFIXES:
        if not enable_ocr:
            return ""
        return _ocr_image(path, ocr_languages)
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_invoice(path: Path, enable_ocr: bool = True, ocr_languages: str = "eng+deu+spa+ces") -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            rows = list(csv.DictReader(f))
        row = rows[0] if rows else {}
        res = ExtractionResult(
            vendor_name=row.get("vendor") or row.get("Vendor"),
            invoice_number=row.get("invoice_number") or row.get("InvoiceNumber"),
            invoice_date=_normalize_date(row.get("invoice_date") or row.get("InvoiceDate")),
            currency=row.get("currency") or row.get("Currency"),
            total_amount=float(row["total_amount"]) if row.get("total_amount") else None,
            confidence=0.95 if row else 0.2,
        )
        return _validate(res)
    if suffix in {".xlsx", ".xls"}:
        wb = load_workbook(path, data_only=True)
        ws = wb.active
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        values = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
        m = dict(zip(headers, values))
        res = ExtractionResult(
            vendor_name=m.get("vendor") or m.get("Vendor"),
            invoice_number=m.get("invoice_number") or m.get("InvoiceNumber"),
            invoice_date=_normalize_date(str(m.get("invoice_date") or m.get("InvoiceDate") or "")),
            currency=m.get("currency") or m.get("Currency"),
            total_amount=float(m["total_amount"]) if m.get("total_amount") is not None else None,
            confidence=0.9,
        )
        return _validate(res)

    text = _extract_text(path, enable_ocr=enable_ocr, ocr_languages=ocr_languages)
    currency = (CURRENCY_RE.search(text).group(1).upper() if CURRENCY_RE.search(text) else None)
    inv_no = INVOICE_RE.search(text).group(1) if INVOICE_RE.search(text) else None
    date_match = DATE_RE.search(text)
    date = _normalize_date(date_match.group(0) if date_match else None)
    total_match = TOTAL_RE.search(text)
    total = float(total_match.group(1).replace(",", ".")) if total_match else None
    vendor = _extract_vendor_name(text, path)
    vat_match = VAT_RE.search(text)
    vat = vat_match.group(1).strip() if vat_match else ""
    language = _detect_language(text)
    res = ExtractionResult(
        vendor_name=vendor,
        vendor_vat=vat,
        invoice_number=inv_no,
        invoice_date=date,
        currency=currency,
        total_amount=total,
        language=language,
        confidence=0.55,
    )
    return _validate(res)


def _encode_image_base64(path: Path) -> str:
    """Encode image file to base64."""
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _convert_pdf_to_image_base64(path: Path) -> str:
    """Convert first page of PDF to base64 image."""
    try:
        from pdf2image import convert_from_path
        from io import BytesIO
        import os
        
        # Try to find poppler in common locations
        poppler_path = None
        possible_paths = [
            r"C:\poppler\poppler-24.08.0\Library\bin",
            r"C:\Program Files\poppler\Library\bin",
            r"C:\poppler\Library\bin",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                poppler_path = p
                break
        
        pages = convert_from_path(str(path), first_page=1, last_page=1, poppler_path=poppler_path)
        if not pages:
            return ""
        
        # Convert PIL image to JPEG bytes
        buffer = BytesIO()
        pages[0].save(buffer, format="JPEG", quality=95)
        image_bytes = buffer.getvalue()
        return base64.standard_b64encode(image_bytes).decode("utf-8")
    except Exception:
        return ""


def _enhance_with_anthropic(path: Path, api_key: str, model: str, existing_result: ExtractionResult) -> ExtractionResult:
    """Use Anthropic Claude vision to extract missing or low-confidence fields."""
    try:
        import anthropic
    except ImportError:
        return existing_result
    
    # Prepare image
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        image_data = _encode_image_base64(path)
        media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    elif suffix == ".pdf":
        image_data = _convert_pdf_to_image_base64(path)
        if not image_data:
            return existing_result
        media_type = "image/jpeg"
    else:
        # Can't process non-image formats with vision
        return existing_result
    
    # Build prompt focusing on missing fields
    missing_fields = []
    if not existing_result.vendor_name:
        missing_fields.append("vendor_name")
    if not existing_result.invoice_number:
        missing_fields.append("invoice_number")
    if not existing_result.invoice_date:
        missing_fields.append("invoice_date")
    if not existing_result.currency:
        missing_fields.append("currency")
    if existing_result.total_amount is None:
        missing_fields.append("total_amount")
    if not existing_result.vendor_vat:
        missing_fields.append("vendor_vat")
    if not existing_result.due_date:
        missing_fields.append("due_date")
    
    prompt = f"""You are an expert invoice data extraction assistant. Analyze this invoice image and extract the following information in JSON format.

Focus on these fields (especially the missing ones: {', '.join(missing_fields) if missing_fields else 'all'}):
- vendor_name: Company name (supplier/issuer)
- vendor_vat: VAT/Tax ID number (IČO, DIČ, Tax ID, etc.)
- invoice_number: Invoice/Faktura number
- invoice_date: Invoice date in YYYY-MM-DD format
- due_date: Due date in YYYY-MM-DD format
- currency: Currency code (USD, EUR, CZK, etc.)
- subtotal: Subtotal amount before tax (numeric)
- tax_amount: Tax/VAT amount (numeric)
- total_amount: Total amount (numeric)
- language: Document language (en, cs, de, es)

Current extraction results (may be incomplete or low confidence):
{json.dumps(existing_result.model_dump(exclude={"validation_errors", "valid", "confidence"}), indent=2)}

Return ONLY a JSON object with the extracted fields. Use null for fields you cannot find. For numeric fields, use numbers not strings.
Be precise with dates (use YYYY-MM-DD format). Extract the complete vendor name including legal form (s.r.o., a.s., GmbH, Ltd, etc.)."""
    
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt}
                ],
            }]
        )
        
        # Parse response
        text_content = response.content[0].text if response.content else ""
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text_content, re.DOTALL)
        if json_match:
            text_content = json_match.group(1)
        
        ai_data = json.loads(text_content)
        
        # Merge AI results with existing, preferring AI for missing/empty fields
        merged = ExtractionResult(
            vendor_name=ai_data.get("vendor_name") or existing_result.vendor_name,
            vendor_vat=ai_data.get("vendor_vat") or existing_result.vendor_vat,
            invoice_number=ai_data.get("invoice_number") or existing_result.invoice_number,
            invoice_date=_normalize_date(ai_data.get("invoice_date")) or existing_result.invoice_date,
            due_date=_normalize_date(ai_data.get("due_date")) or existing_result.due_date,
            currency=(ai_data.get("currency") or existing_result.currency or "").upper() if ai_data.get("currency") or existing_result.currency else None,
            subtotal=ai_data.get("subtotal") or existing_result.subtotal,
            tax_amount=ai_data.get("tax_amount") or existing_result.tax_amount,
            total_amount=ai_data.get("total_amount") or existing_result.total_amount,
            category=ai_data.get("category") or existing_result.category,
            language=ai_data.get("language") or existing_result.language,
            confidence=0.9,  # High confidence for AI-enhanced results
        )
        return _validate(merged)
    
    except Exception as exc:
        # Log error but return existing result
        print(f"AI enhancement failed: {exc}")
        return existing_result


def _enhance_with_openai(path: Path, api_key: str, model: str, existing_result: ExtractionResult) -> ExtractionResult:
    """Use OpenAI GPT-4 Vision to extract missing or low-confidence fields."""
    try:
        import openai
    except ImportError:
        return existing_result
    
    # Prepare image
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        image_data = _encode_image_base64(path)
    elif suffix == ".pdf":
        image_data = _convert_pdf_to_image_base64(path)
        if not image_data:
            return existing_result
    else:
        return existing_result
    
    # Build prompt
    missing_fields = []
    if not existing_result.vendor_name:
        missing_fields.append("vendor_name")
    if not existing_result.invoice_number:
        missing_fields.append("invoice_number")
    if not existing_result.invoice_date:
        missing_fields.append("invoice_date")
    if not existing_result.currency:
        missing_fields.append("currency")
    if existing_result.total_amount is None:
        missing_fields.append("total_amount")
    if not existing_result.vendor_vat:
        missing_fields.append("vendor_vat")
    if not existing_result.due_date:
        missing_fields.append("due_date")
    
    prompt = f"""You are an expert invoice data extraction assistant. Analyze this invoice image and extract the following information in JSON format.

Focus on these fields (especially the missing ones: {', '.join(missing_fields) if missing_fields else 'all'}):
- vendor_name: Company name (supplier/issuer)
- vendor_vat: VAT/Tax ID number (IČO, DIČ, Tax ID, etc.)
- invoice_number: Invoice/Faktura number
- invoice_date: Invoice date in YYYY-MM-DD format
- due_date: Due date in YYYY-MM-DD format
- currency: Currency code (USD, EUR, CZK, etc.)
- subtotal: Subtotal amount before tax (numeric)
- tax_amount: Tax/VAT amount (numeric)
- total_amount: Total amount (numeric)
- language: Document language (en, cs, de, es)

Current extraction results (may be incomplete or low confidence):
{json.dumps(existing_result.model_dump(exclude={"validation_errors", "valid", "confidence"}), indent=2)}

Return ONLY a JSON object with the extracted fields. Use null for fields you cannot find. For numeric fields, use numbers not strings.
Be precise with dates (use YYYY-MM-DD format). Extract the complete vendor name including legal form (s.r.o., a.s., GmbH, Ltd, etc.)."""
    
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                        },
                    },
                    {"type": "text", "text": prompt}
                ],
            }],
            max_tokens=1024,
        )
        
        # Parse response
        text_content = response.choices[0].message.content or ""
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text_content, re.DOTALL)
        if json_match:
            text_content = json_match.group(1)
        
        ai_data = json.loads(text_content)
        
        # Merge AI results with existing, preferring AI for missing/empty fields
        merged = ExtractionResult(
            vendor_name=ai_data.get("vendor_name") or existing_result.vendor_name,
            vendor_vat=ai_data.get("vendor_vat") or existing_result.vendor_vat,
            invoice_number=ai_data.get("invoice_number") or existing_result.invoice_number,
            invoice_date=_normalize_date(ai_data.get("invoice_date")) or existing_result.invoice_date,
            due_date=_normalize_date(ai_data.get("due_date")) or existing_result.due_date,
            currency=(ai_data.get("currency") or existing_result.currency or "").upper() if ai_data.get("currency") or existing_result.currency else None,
            subtotal=ai_data.get("subtotal") or existing_result.subtotal,
            tax_amount=ai_data.get("tax_amount") or existing_result.tax_amount,
            total_amount=ai_data.get("total_amount") or existing_result.total_amount,
            category=ai_data.get("category") or existing_result.category,
            language=ai_data.get("language") or existing_result.language,
            confidence=0.9,  # High confidence for AI-enhanced results
        )
        return _validate(merged)
    
    except Exception as exc:
        # Log error but return existing result
        print(f"AI enhancement failed: {exc}")
        return existing_result


def enhance_extraction_with_ai(
    path: Path,
    existing_result: ExtractionResult,
    provider: str,
    api_key: str,
    model: str,
    confidence_threshold: float = 0.8,
) -> ExtractionResult:
    """
    Enhance extraction results using AI vision models when confidence is low or fields are missing.
    
    Args:
        path: Path to invoice file
        existing_result: Initial extraction result from regex/OCR
        provider: "anthropic" or "openai"
        api_key: API key for the provider
        model: Model name (e.g., "claude-3-5-sonnet-20241022" or "gpt-4o")
        confidence_threshold: Only enhance if existing confidence is below this
    
    Returns:
        Enhanced ExtractionResult with better confidence and more complete fields
    """
    # Skip if no API key provided
    if not api_key:
        return existing_result
    
    # Check if any important fields are missing (even if result is "valid")
    has_missing_fields = (
        not existing_result.vendor_vat
        or not existing_result.invoice_number
        or not existing_result.due_date
        or existing_result.tax_amount is None
        or existing_result.subtotal is None
    )
    
    # Skip AI enhancement only if result is good AND has most fields filled
    if existing_result.valid and existing_result.confidence >= confidence_threshold and not has_missing_fields:
        return existing_result
    
    if provider.lower() == "anthropic":
        return _enhance_with_anthropic(path, api_key, model, existing_result)
    elif provider.lower() == "openai":
        return _enhance_with_openai(path, api_key, model, existing_result)
    else:
        return existing_result
