# Invoices CLI

Implements the local-first invoice processing epic from `INVOICE_PROCESSING_EPIC_PLAN.md`.

## Commands
- `invoices init` – create config scaffold.
- `invoices doctor` – validate credentials, Gmail access, and Drive access.
- Successful processed emails are tagged in Gmail with `INVOICE_PROCESSED` (configurable).
- `invoices fetch-email` – manually fetch unread Gmail invoice emails and process queue.
- `invoices reconcile-ledger` – verify ledger integrity.
- `invoices queue list|show|fix|approve` – review queue workflow.
- `invoices backup` – backup ledger/queue/state/log files.

## Setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -e .`
3. `invoices init`
4. Edit `invoices.config.json` with:
   - `credentials_path`
   - `gmail_label` (label ID)
   - `drive_root_folder_id`
   - `workbook_path`
5. Run `invoices doctor`.
6. Run `invoices fetch-email`.

## Processing Notes
- Supported files: PDF, CSV, XLSX/XLS, PNG/JPG/JPEG/TIFF.
- Links in email bodies are downloaded when file extension is supported.
- Records with missing required fields are marked `Needs Review` and remain in local queue.
- Finalized records are uploaded to Drive under `Invoices/YYYY/MM` and written to Excel workbook.

## Security and reliability
- Secrets are loaded from config and never logged.
- Processed message IDs are tracked for idempotent manual runs.
- Backups can be created with `invoices backup`.


## Testing
- Run unit tests with mocked Gmail/Drive and local temp storage (CSV, PDF, and image attachments): `python -m unittest -v tests/test_processing_flow.py`.
