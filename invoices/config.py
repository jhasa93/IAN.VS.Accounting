from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    credentials_path: str = ""
    gmail_label: str = "INBOX"
    gmail_processed_label: str = "INVOICE_PROCESSED"
    drive_root_folder_id: str = ""
    spreadsheet_id: str = ""
    staging_dir: str = "./data/staging"
    queue_path: str = "./data/queue.json"
    state_path: str = "./data/state.json"
    log_path: str = "./data/invoices.log"
    backup_dir: str = "./data/backups"
    enable_ocr: bool = True
    ocr_languages: str = "eng+deu+spa+ces"
    enable_ai_enhancement: bool = False
    ai_provider: str = "openai"  # "anthropic" or "openai"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"  # or "gpt-4o" for higher accuracy, "claude-3-5-sonnet-20241022" for Anthropic
    ai_confidence_threshold: float = 0.8


DEFAULT_CONFIG_PATH = Path("./invoices.config.json")


def write_default_config(path: Path = DEFAULT_CONFIG_PATH) -> Path:
    path.write_text(AppConfig().model_dump_json(indent=2), encoding="utf-8")
    return path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(**raw)
