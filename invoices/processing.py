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
    """Extract HTTP/HTTPS links from text, stripping trailing punctuation."""
    links = re.findall(r"https?://[^\s<>'\"]+", text)
    # Strip common trailing punctuation that shouldn't be part of URLs
    return [link.rstrip(')]},.;:!?') for link in links]


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
    gmail, drive, sheets = build_services(config.credentials_path)
    processed_label_id = ensure_gmail_label(gmail, config.gmail_processed_label)

    processed, queued, filed = 0, 0, 0
    messages = fetch_new_messages(gmail, config.gmail_label, processed_label_id, state.processed_ids())
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
            
            # Try inline data first
            data = part.get("body", {}).get("data")
            
            # If no inline data, fetch using attachmentId
            if not data:
                attachment_id = part.get("body", {}).get("attachmentId")
                if attachment_id:
                    try:
                        attachment = gmail.users().messages().attachments().get(
                            userId="me",
                            messageId=msg["id"],
                            id=attachment_id
                        ).execute()
                        data = attachment.get("data")
                    except Exception as exc:
                        logger.warning("Failed to fetch attachment %s: %s", filename, exc)
                        continue
            
            if not data:
                logger.warning("No data for attachment: %s", filename)
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

        # Prefer PDF over CSV when both are available for the same invoice
        # Group by base name and prefer .pdf extension
        file_preference = {}
        for staged_path, source_type in staged_files:
            base_name = staged_path.stem.split('_')[-1] if '_' in staged_path.stem else staged_path.stem
            ext = staged_path.suffix.lower()
            
            if base_name not in file_preference:
                file_preference[base_name] = (staged_path, source_type)
            else:
                # If we have a PDF, prefer it over CSV/Excel
                current_ext = file_preference[base_name][0].suffix.lower()
                if ext == '.pdf' and current_ext in ['.csv', '.xlsx', '.xls']:
                    file_preference[base_name] = (staged_path, source_type)
        
        staged_files = list(file_preference.values())

        message_had_files = len(staged_files) > 0
        message_had_review = False
        message_had_filed = False

        for staged_path, source_type in staged_files:
            result = extract_invoice(
                staged_path,
                enable_ocr=config.enable_ocr,
                ocr_languages=config.ocr_languages,
            )
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
            
            # Build filename: {date}-{vendorName}-{amount}-{currency}.pdf
            vendor = (result.vendor_name or "VENDOR").replace(" ", "_").replace("/", "-")
            dated = result.invoice_date or datetime.utcnow().date().isoformat()
            amount = result.total_amount or 0.0
            currency = result.currency or "XXX"
            target_name = f"{dated}-{vendor}-{amount:.2f}-{currency}{staged_path.suffix.lower()}"
            
            drive_id, _ = upload_invoice_file(drive, month_id, staged_path, target_name)
            drive_link = f"https://drive.google.com/file/d/{drive_id}/view"
            
            record = LedgerRecord(
                invoice_date=result.invoice_date or "",
                due_date=result.due_date or "",
                vendor_name=result.vendor_name or "",
                vendor_vat=result.vendor_vat or "",
                language=result.language or "en",
                total_amount=result.total_amount or 0.0,
                currency=result.currency or "",
                tax_amount=result.tax_amount,
                category=result.category,
                source_type=item.source_type,
                drive_file_link=drive_link,
                gmail_message_id=msg["id"],
            )
            append_or_update_record(sheets, config.spreadsheet_id, record)
            item.status = "Filed"
            queue.update(item)
            filed += 1
            message_had_filed = True

        if message_had_files and message_had_filed and not message_had_review:
            mark_message_processed(gmail, msg["id"], processed_label_id)
        state.mark_processed(msg["id"])

    return {"messages_processed": processed, "items_queued": queued, "items_filed": filed}
