# plan.md

## Objective
Operate and evolve the `invoices` CLI so it remains reliable for manual, local-first invoice processing with Google Gmail + Drive and a local Excel ledger.

## Current System Snapshot
- **Delivery status**: MVP flows are implemented (init/doctor/fetch/reconcile/queue/backup).
- **Core stack**: Python 3.10+, Typer CLI, Pydantic models, OpenPyXL ledger writes, Google API client, requests, pypdf, optional OCR (`pytesseract`, optional `pdf2image`).
- **Primary risk areas**:
  1. External API integration assumptions (service-account-only auth model).
  2. Extraction heuristics for noisy PDFs/images.
  3. Local file mutation reliability (JSON/workbook consistency).

## Operational Priorities for Codex Agents
1. **Keep ingestion deterministic and idempotent**
   - Never reprocess already finalized Gmail messages unless explicitly designed.
   - Ensure label/read-state logic stays coherent with local state tracking.
2. **Protect accounting data quality**
   - Keep strict required-field validation before auto-filing.
   - Route uncertain records to queue review rather than silent auto-posting.
3. **Preserve operability for non-technical users**
   - Keep command UX simple and error messages actionable.
   - Document every visible behavior change in README.
4. **Preserve testability without cloud dependencies**
   - Use mocks/stubs for Gmail/Drive/OCR in unit tests.

## Default Execution Plan for New Work
Follow this sequence unless task-specific constraints require otherwise:

1. **Read context quickly**
   - Review `README.md`, `AGENTS.md`, and relevant module(s).
2. **Scope and impact analysis**
   - Identify which pipeline stage is impacted (ingest, extract, queue, file, ledger, backup).
3. **Implement minimal patch**
   - Favor isolated changes in one module when possible.
4. **Add/update tests**
   - Extend existing unittest coverage close to the changed behavior.
5. **Run verification**
   - Execute relevant tests; include command output status in final report.
6. **Update docs**
   - Keep README and plan/agent docs aligned when behavior changes.

## Test Matrix
- Fast baseline:
  - `python -m unittest -v tests/test_processing_flow.py`
  - `python -m unittest -v tests/test_extraction_ocr.py`
- Optional manual CLI smoke checks:
  - `invoices init`
  - `invoices doctor`
  - `invoices fetch-email`
  - `invoices queue list`
  - `invoices reconcile-ledger`
  - `invoices backup`

## Definition of “Optimal Codex Operation” for This Repo
A Codex task is considered optimally executed when:
- Changes are small, reversible, and aligned with the existing architecture.
- Idempotency and ledger correctness are preserved.
- Tests covering touched behavior pass locally.
- User-facing docs remain accurate.
- Final response clearly states summary + test commands + results.

## Near-Term Improvement Backlog (Agent-facing)
1. Add tests for link-download failures and mixed-message outcomes (some filed + some review).
2. Add tests for duplicate Drive filenames/idempotent upload behavior.
3. Improve extraction confidence scoring granularity by source type.
4. Add a validation command for config schema + path writability checks.
5. Add regression tests for queue fix/approve lifecycle updates.
