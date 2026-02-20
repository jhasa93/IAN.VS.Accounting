from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


def build_services(credentials_path: str):
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    gmail = build("gmail", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return gmail, drive


def fetch_new_messages(gmail: Any, label: str, processed_ids: set[str]) -> list[dict[str, Any]]:
    response = gmail.users().messages().list(userId="me", labelIds=[label], q="is:unread").execute()
    out: list[dict[str, Any]] = []
    for m in response.get("messages", []):
        if m["id"] in processed_ids:
            continue
        detail = gmail.users().messages().get(userId="me", id=m["id"], format="full").execute()
        out.append(detail)
    return out


def ensure_gmail_label(gmail: Any, label_name: str) -> str:
    labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label.get("name") == label_name:
            return label["id"]
    created = gmail.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    return created["id"]


def mark_message_processed(gmail: Any, message_id: str, processed_label_id: str) -> None:
    gmail.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": [processed_label_id],
            "removeLabelIds": ["UNREAD"],
        },
    ).execute()


def decode_b64url(data: str) -> bytes:
    missing = 4 - (len(data) % 4)
    if missing and missing != 4:
        data += "=" * missing
    return base64.urlsafe_b64decode(data)


def ensure_folder(drive: Any, parent_id: str, name: str) -> str:
    q = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    found = drive.files().list(q=q, fields="files(id,name)").execute().get("files", [])
    if found:
        return found[0]["id"]
    folder_meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    return drive.files().create(body=folder_meta, fields="id").execute()["id"]


def upload_invoice_file(drive: Any, folder_id: str, file_path: Path, target_name: str) -> tuple[str, bool]:
    q = f"'{folder_id}' in parents and name='{target_name}' and trashed=false"
    found = drive.files().list(q=q, fields="files(id,name)").execute().get("files", [])
    if found:
        return found[0]["id"], False
    media = MediaFileUpload(str(file_path), resumable=False)
    created = drive.files().create(body={"name": target_name, "parents": [folder_id]}, media_body=media, fields="id").execute()
    return created["id"], True


def derive_folder_path(invoice_date: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(invoice_date)
    return str(dt.year), f"{dt.month:02d}"
