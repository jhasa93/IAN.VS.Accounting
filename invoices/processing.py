from __future__ import annotations

import json
import logging
import mimetypes
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from .config import AppConfig
from .extraction import extract_invoice
from .google_services import (
    build_services,
    decode_b64url,
    derive_folder_path,
    ensure_folder,
    ensure_gmail_label,
    fetch_new_messages,
    mark_message_processed,
    upload_invoice_file,
)
from .ledger import append_or_update_record
from .models import LedgerRecord, QueueItem
from .storage import QueueStore, StateStore

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".tiff"}


def build_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("invoices")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_path)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
    return logger


def extract_links(text: str) -> list[str]:
    return re.findall(r"https?://[^\s<>'\"]+", text)


def download_link(url: str, staging_dir: Path) -> Path | None:
    parsed = urlparse(url)
    name = Path(parsed.path).name or f"download-{uuid.uuid4().hex[:8]}"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    out = staging_dir / name
    out.write_bytes(resp.content)
    return out


def _payload_parts(payload: dict) -> list[dict]:
    parts = payload.get("parts", [])
    if not parts:
        return [payload]
    flat = []
    for p in parts:
        flat.extend(_payload_parts(p))
    return flat


def process_new_email(config: AppConfig) -> dict[str, int]:
    logger = build_logger(Path(config.log_path))
    staging = Path(config.staging_dir)
    staging.mkdir(parents=True, exist_ok=True)
    queue = QueueStore(Path(config.queue_path))
    state = StateStore(Path(config.state_path))
    gmail, drive = build_services(config.credentials_path)
    processed_label_id = ensure_gmail_label(gmail, config.gmail_processed_label)

    processed, queued, filed = 0, 0, 0
    messages = fetch_new_messages(gmail, config.gmail_label, state.processed_ids())
    for msg in messages:
        processed += 1
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        sender = headers.get("From", "unknown")
        subject = headers.get("Subject", "")
        received = datetime.utcfromtimestamp(int(msg["internalDate"]) / 1000)

        staged_files: list[tuple[Path, str]] = []
        for part in _payload_parts(msg["payload"]):
            filename = part.get("filename")
            if not filename:
                continue
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                logger.warning("Unsupported attachment: %s", filename)
                continue
            data = part.get("body", {}).get("data")
            if not data:
                continue
            out = staging / f"{uuid.uuid4().hex}_{filename}"
            out.write_bytes(decode_b64url(data))
            staged_files.append((out, "Attachment"))

        body_text = ""
        for part in _payload_parts(msg["payload"]):
            if part.get("mimeType", "").startswith("text/plain") and part.get("body", {}).get("data"):
                body_text += decode_b64url(part["body"]["data"]).decode("utf-8", errors="ignore")
        for link in extract_links(body_text):
            try:
                dl = download_link(link, staging)
                if dl:
                    staged_files.append((dl, "Link"))
            except Exception as exc:
                logger.warning("Link download failed %s: %s", link, exc)

        message_had_files = len(staged_files) > 0
        message_had_review = False
        message_had_filed = False

        for staged_path, source_type in staged_files:
            result = extract_invoice(staged_path)
            item = QueueItem(
                internal_id=uuid.uuid4().hex,
                source_type=source_type,  # type: ignore[arg-type]
                source_email_message_id=msg["id"],
                sender_email=sender,
                subject=subject,
                received_at=received,
                original_file_name=staged_path.name,
                staged_path=str(staged_path),
                extraction_confidence=result.confidence,
                status="Extracted" if result.valid and result.confidence >= 0.8 else "Needs Review",
                review_notes=";".join(result.validation_errors),
                error_type=None if result.valid else "missing_required_fields",
            )
            queue.add(item)
            queued += 1
            if item.status == "Needs Review":
                message_had_review = True
                continue
            year, month = derive_folder_path(result.invoice_date or datetime.utcnow().date().isoformat())
            year_id = ensure_folder(drive, config.drive_root_folder_id, year)
            month_id = ensure_folder(drive, year_id, month)
            invoice_num = result.invoice_number or "UNKNOWN"
            vendor = (result.vendor_name or "VENDOR").replace(" ", "_")
            dated = result.invoice_date or datetime.utcnow().date().isoformat()
            target_name = f"{dated}_{vendor}_{invoice_num}{staged_path.suffix.lower()}"
            drive_id, _ = upload_invoice_file(drive, month_id, staged_path, target_name)
            record = LedgerRecord(
                internal_id=item.internal_id,
                source_type=item.source_type,
                source_email_message_id=item.source_email_message_id,
                sender_email=item.sender_email,
                original_file_name=item.original_file_name,
                stored_file_name=target_name,
                drive_file_id=drive_id,
                drive_folder_path=f"Invoices/{year}/{month}",
                vendor_name=result.vendor_name or "",
                invoice_number=result.invoice_number or "",
                invoice_date=result.invoice_date or "",
                due_date=result.due_date or "",
                currency=result.currency or "",
                subtotal=result.subtotal,
                tax_amount=result.tax_amount,
                total_amount=result.total_amount or 0.0,
                category=result.category,
                extraction_confidence=result.confidence,
                status="Filed",
                review_notes=item.review_notes,
                created_at=item.created_at.isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
            append_or_update_record(Path(config.workbook_path), record)
            item.status = "Filed"
            queue.update(item)
            filed += 1
            message_had_filed = True

        if message_had_files and message_had_filed and not message_had_review:
            mark_message_processed(gmail, msg["id"], processed_label_id)
        state.mark_processed(msg["id"])

    return {"messages_processed": processed, "items_queued": queued, "items_filed": filed}
