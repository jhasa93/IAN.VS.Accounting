from __future__ import annotations

import csv
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
    for field in ["vendor_name", "invoice_date", "currency"]:
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
