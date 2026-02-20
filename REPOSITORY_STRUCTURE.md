# Repository Structure

## 📁 Core Application Files

### `invoices/` - Main Application Package
Contains all the invoice processing logic.

**Key modules:**
- `cli.py` - Command-line interface
- `extraction.py` - Invoice data extraction (OCR, AI, regex)
- `processing.py` - Main workflow orchestration
- `google_services.py` - Gmail/Drive/Sheets API integration
- `ledger.py` - Spreadsheet management
- `models.py` - Data structures
- `config.py` - Configuration handling
- `storage.py` - Local data storage
- `ui.py` - Desktop GUI

### `tests/` - Unit Tests
Automated tests for the application. You don't need to modify these.

### `pyproject.toml` - Python Package Configuration
Defines dependencies and package metadata. **Don't edit unless adding new features.**

## 📄 Documentation Files

### User-Facing
- **`README.md`** - Complete documentation (START HERE)
- **`QUICKSTART.md`** - 5-minute setup guide
- **`INSTALLATION_CHECKLIST.md`** - Step-by-step checklist

### Developer-Facing
- `AGENTS.md` - AI agent instructions for maintaining this codebase
- `INVOICE_PROCESSING_EPIC_PLAN.md` - Original project specifications
- `plan.md` - Development roadmap

## 🛠️ Utility Scripts

### End-User Utilities
- **`check_drive.py`** - View your Drive folder structure
- **`check_sheet.py`** - View your spreadsheet contents
- **`reset_everything.py`** - ⚠️ Clear all state and reprocess everything
- **`reset_for_reprocessing.py`** - Reset specific messages

## ⚙️ Configuration Files

### You MUST Create These
- **`client_secret.json`** - Google OAuth credentials (download from Google Cloud Console)
- **`invoices.config.json`** - Your application configuration (copy from template)

### Templates
- `invoices.config.json.template` - Configuration template with placeholders

### Auto-Generated (Don't Edit)
- `token.json` - OAuth access token (created on first run)

## 📦 Data Directory

### `data/` - Local Application Data
Created automatically on first run:
- `staging/` - Temporarily downloaded invoices
- `queue.json` - Processing queue
- `state.json` - Processed message IDs
- `invoices.log` - Application logs
- `backups/` - Created by `invoices backup` command

## 🚫 Files to Ignore

These are handled by `.gitignore` and you don't need to worry about them:
- `.venv/` - Python virtual environment
- `__pycache__/` - Python bytecode
- `.egg-info/` - Package metadata
- `*.pyc` - Compiled Python files

## 📝 Files You'll Interact With

**Setup (one-time):**
1. `client_secret.json` - Download from Google Cloud
2. `invoices.config.json` - Configure your settings

**Daily use:**
- Just run `invoices` commands!
- Optionally use utility scripts to inspect data

**Optional:**
- `check_drive.py` - When you want to see what's in Drive
- `check_sheet.py` - When you want to see ledger contents
- `reset_everything.py` - When you want to start over

## 🎯 Quick Reference

```powershell
# Regular use
invoices fetch-email          # Process new invoices
invoices queue list            # View queue
invoices ui                    # Launch GUI

# Inspection
python check_drive.py          # View Drive
python check_sheet.py          # View Sheets

# Maintenance
invoices backup                # Create backup
invoices doctor                # Validate setup

# Nuclear option
python reset_everything.py     # Start completely fresh
```
