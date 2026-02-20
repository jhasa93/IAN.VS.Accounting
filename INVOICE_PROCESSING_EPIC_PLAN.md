# Epic Plan: Local Invoice Processing System for Small Business Owner

## 1) Epic Overview
Build a **local-first invoice processing system** that runs on the owner’s PC (inside VS Code), checks a configured Gmail mailbox when manually triggered, ingests invoice files or download links, extracts accounting details, files documents into Google Drive by year/month, and updates a master Excel ledger.

### Confirmed constraints from business owner
- A Gmail account already exists for receiving invoices.
- The same Google account already has access to the Google Drive target folder.
- Google API access is already set up (credentials to be provided during implementation).
- Mailbox checks can be **manual trigger only** in MVP.

### Epic Goals
- Reduce manual invoice sorting and data entry.
- Standardize Drive organization: `Invoices/YYYY/MM`.
- Keep one reliable Excel workbook with accounting-ready invoice records.
- Support mixed input formats: PDF, CSV, Excel, images, and email links to invoice downloads.

### Non-Goals (MVP)
- Fully automatic always-on background daemon.
- Full ERP capabilities.
- Complex tax filing automation by jurisdiction.

---

## 2) Core User Flow (MVP)
1. Owner runs a command in VS Code: `invoices fetch-email`.
2. System checks mailbox for unread/new invoice emails.
3. System collects invoice sources:
   - Email attachments (`.pdf`, `.csv`, `.xlsx/.xls`, images).
   - Supported invoice download links found in the email body.
4. System stages documents locally and extracts invoice data.
5. System determines invoice issue date and destination Drive folder (`YYYY/MM`).
6. System uploads/moves file to Google Drive destination.
7. System appends/updates the main Excel ledger row.
8. If extraction confidence is low or data is invalid, item goes to review queue.

---

## 3) Feature Breakdown (Epic → Features)

## Feature A — Local Setup, Credentials, and Validation
**Outcome:** Owner can run the system locally with explicit setup checks.

### Scope
- `.env` + config file for mailbox and Drive settings.
- Google API credentials path and permission checks.
- Local staging, logs, and output paths.

### Deliverables
- `invoices init` (create config scaffold).
- `invoices doctor` (validate credentials, mailbox access, Drive access).
- Setup guide for VS Code users.

### Acceptance criteria
- One command verifies Gmail + Drive connectivity.
- Clear error output for missing/invalid credentials.

---

## Feature B — Gmail Ingestion (Manual Trigger)
**Outcome:** User can manually pull new invoice emails and queue files for processing.

### Scope
- Manual command: `invoices fetch-email`.
- Read only new/unprocessed emails from configured mailbox/label.
- Parse attachments and normalize allowed file types:
  - PDF (`.pdf`)
  - Spreadsheets (`.csv`, `.xlsx`, `.xls`)
  - Images (`.png`, `.jpg`, `.jpeg`, `.tiff`)
- Parse email body for invoice links (HTTP/HTTPS) and download allowed file types.
- Store source metadata: message ID, sender, subject, received timestamp.

### Deliverables
- Gmail fetch module (using existing Google API setup).
- Link downloader with extension/content-type validation.
- Quarantine handling for unsupported files and failed downloads.

### Acceptance criteria
- Manual command ingests only new/unprocessed emails.
- Attachments and valid links both enter the processing queue.
- Unsupported files/links are logged and visible for review.

---

## Feature C — Google Drive Placement & Naming
**Outcome:** Processed invoices are stored in the correct Drive folder structure.

### Scope
- Resolve invoice issue date → destination path `Invoices/YYYY/MM`.
- Create missing year/month folders automatically.
- Deterministic naming convention, e.g. `YYYY-MM-DD_VENDOR_INVNUMBER.ext`.
- Duplicate-safe upload behavior.

### Deliverables
- Drive folder resolver service.
- File upload/move service with idempotency checks.

### Acceptance criteria
- Every finalized invoice lands in the correct `YYYY/MM` folder.
- Duplicate handling is deterministic and recorded.

---

## Feature D — Invoice Parsing & Extraction (AI/OCR)
**Outcome:** Extract accounting-relevant fields from mixed invoice formats.

### Scope
- Parser pipeline for PDF/image OCR and table/text extraction from CSV/Excel.
- Required fields:
  - Vendor
  - Invoice number
  - Invoice date
  - Currency
  - Total amount
- Optional fields:
  - Subtotal
  - Tax amount
  - Due date
  - Category hint
- Confidence scoring + validation rules.
- Optional Codex-assisted parsing for difficult documents when available.

### Deliverables
- Unified extraction contract (JSON result schema).
- Validator for date/amount consistency.
- Review queue for low-confidence items.

### Acceptance criteria
- Required fields extracted for common invoice formats above agreed confidence threshold.
- Low-confidence or invalid records are blocked from auto-finalization.

---

## Feature E — Master Excel Ledger Management
**Outcome:** Excel workbook remains accounting source of truth.

### Scope
- Create/maintain master workbook.
- Append new invoice rows and update corrected rows.
- Track status lifecycle: `Received`, `Extracted`, `Needs Review`, `Filed`, `Posted`, `Paid`.

### Suggested workbook columns
- Internal ID
- Source Type (Attachment/Link)
- Source Email Message ID
- Sender Email
- Original File Name
- Stored File Name
- Drive File ID
- Drive Folder Path
- Vendor Name
- Invoice Number
- Invoice Date
- Due Date
- Currency
- Subtotal
- Tax Amount
- Total Amount
- Category
- Extraction Confidence
- Status
- Review Notes
- Created At / Updated At

### Deliverables
- Excel writer with file-lock detection and retries.
- `invoices reconcile-ledger` integrity check command.

### Acceptance criteria
- Successful processing always writes/updates exactly one ledger record.
- Workbook remains compatible with Microsoft Excel.

---

## Feature F — Review & Exception Workflow in VS Code
**Outcome:** Owner can resolve failures quickly.

### Scope
- CLI review commands:
  - `invoices queue list`
  - `invoices queue show <id>`
  - `invoices queue fix <id>`
  - `invoices queue approve <id>`
- Exception types:
  - Missing required fields
  - Download/link failure
  - Unsupported file type
  - Duplicate detection alerts

### Deliverables
- Local queue store + audit trail.
- Reprocess command after edits.

### Acceptance criteria
- User can fix and reprocess blocked invoices without data loss.
- All manual edits are timestamped.

---

## Feature G — Reliability, Security, and Backup
**Outcome:** Safe, supportable local operations.

### Scope
- Structured logging for each processing step.
- Local secret hygiene (`.env` and credential file handling).
- Backup job for ledger + queue state.
- Retry/dead-letter policy for transient failures.

### Deliverables
- Logging standard.
- Backup/restore runbook.

### Acceptance criteria
- Recover from crash/network interruption without duplicating finalized records.
- Secrets never written to logs.

---

## 4) Delivery Phases

### Phase 1 (MVP — requested now)
- Feature A: setup + doctor command.
- Feature B: **manual Gmail fetch** with attachment + link ingestion.
- Feature C: Drive folder placement by `YYYY/MM`.
- Feature D: baseline extraction for PDF/image/CSV/Excel.
- Feature E: Excel ledger write/update.
- Feature F: basic exception queue CLI.

### Phase 2
- Optional scheduled mailbox polling (still local).
- Better duplicate detection and classification.
- Enhanced extraction and validation coverage.

### Phase 3
- Optional WhatsApp ingestion integration.
- Reporting exports and operational dashboards.

---

## 5) Technical Inputs Needed From Owner
To start implementation, owner should provide:
1. Google API credential details (type + JSON file path).
2. Gmail mailbox details (target inbox or label to monitor).
3. Google Drive root folder ID/path for invoice storage.
4. Preferred Excel workbook path/name.
5. Naming convention preferences (if different from default).

---

## 6) Definition of Done (Epic)
- Manual mailbox trigger pulls new emails and processes supported attachments/links.
- Invoices are stored in Drive by year and month.
- Master Excel ledger is updated with extracted accounting fields.
- Exceptions are queued and resolvable from VS Code commands.
- Setup + run instructions allow owner to operate the system locally.

---

## 7) Backlog Seed (First Tickets)
1. Create config schema and `invoices doctor` command.
2. Implement Gmail message fetch by label + processed-state tracking.
3. Build attachment parser and allowed-file validator.
4. Build secure link extractor/downloader from email bodies.
5. Implement Drive folder resolver (`YYYY/MM`) and uploader.
6. Define extraction schema for PDF/image/CSV/Excel and add validators.
7. Implement Excel ledger writer + reconcile command.
8. Add review queue CLI and retry/reprocess flow.
