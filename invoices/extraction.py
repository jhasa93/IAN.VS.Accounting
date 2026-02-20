from __future__ import annotations

import csv
import re
from pathlib import Path

from dateutil.parser import parse as parse_date
from openpyxl import load_workbook
from pypdf import PdfReader

from .models import ExtractionResult

CURRENCY_RE = re.compile(r"\b(USD|EUR|GBP|AUD|CAD|INR)\b", re.I)
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
INVOICE_RE = re.compile(r"invoice\s*(?:#|number)?\s*[:\-]?\s*([A-Z0-9\-]+)", re.I)
TOTAL_RE = re.compile(r"\btotal\b\s*[:\-]?\s*([0-9]+(?:\.[0-9]{1,2})?)", re.I)


def _validate(result: ExtractionResult) -> ExtractionResult:
    errs = []
    for field in ["vendor_name", "invoice_number", "invoice_date", "currency"]:
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


def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_invoice(path: Path) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            rows = list(csv.DictReader(f))
        row = rows[0] if rows else {}
        res = ExtractionResult(
            vendor_name=row.get("vendor") or row.get("Vendor"),
            invoice_number=row.get("invoice_number") or row.get("InvoiceNumber"),
            invoice_date=row.get("invoice_date") or row.get("InvoiceDate"),
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
            invoice_date=str(m.get("invoice_date") or m.get("InvoiceDate") or ""),
            currency=m.get("currency") or m.get("Currency"),
            total_amount=float(m["total_amount"]) if m.get("total_amount") is not None else None,
            confidence=0.9,
        )
        return _validate(res)

    text = _extract_text(path)
    currency = (CURRENCY_RE.search(text).group(1).upper() if CURRENCY_RE.search(text) else None)
    inv_no = INVOICE_RE.search(text).group(1) if INVOICE_RE.search(text) else None
    date = DATE_RE.search(text).group(0) if DATE_RE.search(text) else None
    total = float(TOTAL_RE.search(text).group(1)) if TOTAL_RE.search(text) else None
    vendor = path.stem.split("_")[0] if "_" in path.stem else None
    res = ExtractionResult(
        vendor_name=vendor,
        invoice_number=inv_no,
        invoice_date=date,
        currency=currency,
        total_amount=total,
        confidence=0.55,
    )
    return _validate(res)
