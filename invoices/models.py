from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Status = Literal["Received", "Extracted", "Needs Review", "Filed", "Posted", "Paid"]


class QueueItem(BaseModel):
    internal_id: str
    source_type: Literal["Attachment", "Link"]
    source_email_message_id: str
    sender_email: str
    subject: str
    received_at: datetime
    original_file_name: str
    staged_path: str
    extraction_confidence: float = 0.0
    status: Status = "Received"
    review_notes: str = ""
    error_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractionResult(BaseModel):
    vendor_name: Optional[str] = None
    vendor_vat: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    category: Optional[str] = None
    language: Optional[str] = None
    confidence: float = 0.0
    valid: bool = False
    validation_errors: list[str] = Field(default_factory=list)


class LedgerRecord(BaseModel):
    invoice_date: str
    due_date: str
    vendor_name: str
    vendor_vat: str
    language: str
    total_amount: float
    currency: str
    tax_amount: Optional[float]
    category: Optional[str]
    source_type: str
    drive_file_link: str
    gmail_message_id: str
