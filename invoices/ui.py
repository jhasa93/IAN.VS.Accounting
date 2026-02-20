from __future__ import annotations

import json
import shutil
import threading
import traceback
from datetime import datetime
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config, write_default_config
from .google_services import build_services, ensure_gmail_label
from .ledger import reconcile
from .processing import process_new_email
from .storage import QueueStore


def execute_action(action: str, config_path: Path = DEFAULT_CONFIG_PATH) -> str:
    if action == "init":
        path = write_default_config(config_path)
        return f"Wrote config scaffold: {path}"

    cfg = load_config(config_path)

    if action == "doctor":
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
        return "\n".join(f"{name}: {'OK' if ok else 'FAIL'}" for name, ok in checks)

    if action == "fetch-email":
        result = process_new_email(cfg)
        return json.dumps(result, indent=2)

    if action == "reconcile-ledger":
        rows, dup = reconcile(Path(cfg.workbook_path))
        return f"rows={rows} duplicates={dup}"

    if action == "queue-list":
        q = QueueStore(Path(cfg.queue_path))
        items = q.list()
        if not items:
            return "queue is empty"
        return "\n".join(
            f"{item.internal_id} | {item.status} | {item.original_file_name} | {item.review_notes}" for item in items
        )

    if action == "backup":
        dest = Path(cfg.backup_dir) / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest.mkdir(parents=True, exist_ok=True)
        for p in [cfg.workbook_path, cfg.queue_path, cfg.state_path, cfg.log_path]:
            src = Path(p)
            if src.exists():
                shutil.copy2(src, dest / src.name)
        return f"backup created at {dest}"

    raise ValueError(f"Unknown action: {action}")


def run_ui(config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except Exception as exc:
        raise RuntimeError("Tkinter is not available in this Python environment.") from exc

    root = tk.Tk()
    root.title("Invoices Assistant")
    root.geometry("860x560")

    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    header = tk.Label(frame, text="Invoices Local Operator UI", font=("Arial", 14, "bold"))
    header.pack(anchor="w")

    subtitle = tk.Label(
        frame,
        text=f"Config: {config_path}",
        fg="#555555",
    )
    subtitle.pack(anchor="w", pady=(0, 8))

    output = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=22)
    output.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

    def append_output(text: str) -> None:
        output.insert(tk.END, text + "\n")
        output.see(tk.END)

    def run_action(action: str, label: str) -> None:
        append_output(f"\n== {label} ==")

        def worker() -> None:
            try:
                result = execute_action(action=action, config_path=config_path)
            except Exception:
                result = traceback.format_exc()

            root.after(0, lambda: append_output(result))

        threading.Thread(target=worker, daemon=True).start()

    buttons = [
        ("Initialize Config", "init"),
        ("Run Health Check", "doctor"),
        ("Fetch New Invoices", "fetch-email"),
        ("List Review Queue", "queue-list"),
        ("Reconcile Ledger", "reconcile-ledger"),
        ("Backup Files", "backup"),
    ]

    buttons_frame = tk.Frame(frame)
    buttons_frame.pack(fill=tk.X)

    for index, (label, action) in enumerate(buttons):
        button = tk.Button(
            buttons_frame,
            text=label,
            command=lambda a=action, l=label: run_action(a, l),
            padx=8,
            pady=6,
        )
        button.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)

    for col in range(3):
        buttons_frame.grid_columnconfigure(col, weight=1)

    append_output("Ready. Use the buttons above to run invoice tasks.")
    root.mainloop()
