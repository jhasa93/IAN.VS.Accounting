from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import typer

from .config import DEFAULT_CONFIG_PATH, load_config, write_default_config
from .google_services import build_services, ensure_gmail_label
from .ledger import reconcile
from .processing import process_new_email
from .storage import QueueStore

app = typer.Typer(help="Invoice processing CLI")
queue_app = typer.Typer(help="Queue operations")
app.add_typer(queue_app, name="queue")


@app.command("init")
def init(config_path: Path = DEFAULT_CONFIG_PATH):
    path = write_default_config(config_path)
    typer.echo(f"Wrote config scaffold: {path}")


@app.command("doctor")
def doctor(config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    checks = []
    cred_exists = Path(cfg.credentials_path).exists()
    checks.append(("credentials_file", cred_exists))
    try:
        gmail, drive = build_services(cfg.credentials_path)
        gmail.users().labels().list(userId="me").execute()
        ensure_gmail_label(gmail, cfg.gmail_processed_label)
        drive.files().get(fileId=cfg.drive_root_folder_id, fields="id,name").execute()
        checks.append(("gmail_access", True))
        checks.append(("processed_label", True))
        checks.append(("drive_access", True))
    except Exception:
        checks.append(("gmail_access", False))
        checks.append(("processed_label", False))
        checks.append(("drive_access", False))
    for name, ok in checks:
        typer.echo(f"{name}: {'OK' if ok else 'FAIL'}")


@app.command("fetch-email")
def fetch_email(config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    result = process_new_email(cfg)
    typer.echo(json.dumps(result, indent=2))


@app.command("reconcile-ledger")
def reconcile_ledger(config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    rows, dup = reconcile(Path(cfg.workbook_path))
    typer.echo(f"rows={rows} duplicates={dup}")


@queue_app.command("list")
def queue_list(config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    q = QueueStore(Path(cfg.queue_path))
    for item in q.list():
        typer.echo(f"{item.internal_id} | {item.status} | {item.original_file_name} | {item.review_notes}")


@queue_app.command("show")
def queue_show(internal_id: str, config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    q = QueueStore(Path(cfg.queue_path))
    item = q.get(internal_id)
    if not item:
        raise typer.Exit("not found")
    typer.echo(item.model_dump_json(indent=2))


@queue_app.command("fix")
def queue_fix(internal_id: str, field: str, value: str, config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    q = QueueStore(Path(cfg.queue_path))
    item = q.get(internal_id)
    if not item:
        raise typer.Exit("not found")
    if not hasattr(item, field):
        raise typer.Exit(f"unknown field {field}")
    setattr(item, field, value)
    item.review_notes = f"manual_edit:{field}"
    item.updated_at = datetime.utcnow()
    q.update(item)
    typer.echo("updated")


@queue_app.command("approve")
def queue_approve(internal_id: str, config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    q = QueueStore(Path(cfg.queue_path))
    item = q.get(internal_id)
    if not item:
        raise typer.Exit("not found")
    item.status = "Extracted"
    item.review_notes = f"approved:{datetime.utcnow().isoformat()}"
    q.update(item)
    typer.echo("approved")


@app.command("backup")
def backup(config_path: Path = DEFAULT_CONFIG_PATH):
    cfg = load_config(config_path)
    dest = Path(cfg.backup_dir) / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for p in [cfg.workbook_path, cfg.queue_path, cfg.state_path, cfg.log_path]:
        src = Path(p)
        if src.exists():
            shutil.copy2(src, dest / src.name)
    typer.echo(f"backup created at {dest}")


if __name__ == "__main__":
    app()
