# AGENTS.md

## Mission
This repository implements a **local-first invoice processing CLI** named `invoices`. The app ingests Gmail invoice emails, extracts invoice fields from attachments/links, files invoices to Google Drive by `YYYY/MM`, and writes records to a local Excel ledger.

Your primary objective as an agent is to keep this workflow stable, idempotent, and easy to operate from VS Code.

## Project Map
- `invoices/cli.py` — Typer entrypoint (`init`, `doctor`, `fetch-email`, `reconcile-ledger`, `queue`, `backup`).
- `invoices/processing.py` — main orchestration for Gmail fetch → extract → queue/review → Drive upload → ledger update.
- `invoices/extraction.py` — extraction heuristics for CSV/XLSX/PDF/images, with optional OCR.
- `invoices/google_services.py` — Gmail/Drive API wrappers and helper methods.
- `invoices/ledger.py` — Excel workbook creation, append/update logic, and reconciliation.
- `invoices/storage.py` — local JSON state and queue stores.
- `invoices/models.py` — Pydantic models for queue items, extraction results, and ledger records.
- `tests/` — unit tests using mocks and dependency stubs.

## Key Runtime Contracts
1. **Idempotency**
   - Messages are tracked in state (`processed_message_ids`) and only unread messages are fetched.
   - After successful filing with no review items in the same message, Gmail message is labeled processed and marked read.
2. **Status flow**
   - Queue item starts in extracted state and becomes either `Needs Review` (missing required fields / low confidence) or `Filed`.
3. **Required extracted fields for auto-filing**
   - `vendor_name`, `invoice_number`, `invoice_date`, `currency`, `total_amount`.
4. **Drive layout**
   - Destination path must remain `Invoices/YYYY/MM` based on invoice date.
5. **Ledger integrity**
   - `internal_id` is the unique record key used by append-or-update logic.

## Agent Working Rules
- Prefer minimal, targeted changes. Avoid broad refactors unless requested.
- Keep CLI behavior and command names backward compatible.
- Never log secrets or credential contents.
- Preserve local-first behavior (no background daemon assumptions unless explicitly requested).
- Maintain clear error pathways for missing credentials, unsupported files, and extraction failures.

## Setup and Validation Commands
Use these commands when validating changes:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest -v tests/test_processing_flow.py
python -m unittest -v tests/test_extraction_ocr.py
```

For manual smoke checks:

```bash
invoices init
invoices doctor
invoices fetch-email
invoices queue list
invoices reconcile-ledger
invoices backup
```

## Change Guidance by Area
### CLI (`invoices/cli.py`)
- Keep output human-readable and stable for operators.
- If adding a command, document it in `README.md`.

### Processing (`invoices/processing.py`)
- Preserve order of operations: fetch → stage → extract → queue → file → ledger → mark processed.
- Guard network calls and partial failures so a single bad link/file does not kill the whole batch.

### Extraction (`invoices/extraction.py`)
- Keep parser deterministic and testable.
- OCR is optional and must gracefully degrade if optional packages are missing.
- When adding fields, update model + validation + tests consistently.

### Storage/Ledger
- JSON and workbook writes must remain robust for local usage.
- Retain compatibility with existing queue/state file shape.

## Testing Expectations
- For behavior changes, update/add focused unit tests in `tests/`.
- Prefer mock-based tests (current suite avoids external API calls and heavy dependencies).
- Run relevant test files before finishing.

## Documentation Expectations
When changing behavior, keep these in sync:
- `README.md` (user-facing command/workflow changes)
- `INVOICE_PROCESSING_EPIC_PLAN.md` (if scope/phase assumptions change)
- `plan.md` (agent execution plan and priorities)
