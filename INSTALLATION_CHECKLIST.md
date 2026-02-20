# Installation Checklist

Use this checklist to ensure everything is set up correctly.

## ✅ Prerequisites

- [ ] Python 3.10 or higher installed
- [ ] PowerShell 5.1 or higher
- [ ] Google Cloud account
- [ ] OpenAI account with API access

## ✅ Installation Steps

- [ ] Clone repository
- [ ] Create virtual environment (`.venv`)
- [ ] Install dependencies: `pip install -e ".[ai]"`
- [ ] Install Poppler (PDF processor)
- [ ] Add Poppler to PATH
- [ ] Verify Poppler: `pdftoppm -v`
- [ ] (Optional) Install Tesseract OCR

## ✅ Google Cloud Setup

- [ ] Create Google Cloud project
- [ ] Enable Gmail API
- [ ] Enable Google Drive API
- [ ] Create OAuth 2.0 credentials (Desktop app)
- [ ] Download `client_secret.json`
- [ ] Place in project root folder

## ✅ Google Services Setup

- [ ] Create Google Drive "Invoices" folder
- [ ] Note the folder ID from URL
- [ ] Create Google Sheet for ledger
- [ ] Note the spreadsheet ID from URL
- [ ] Find Gmail label ID for invoices

## ✅ Configuration

- [ ] Run `invoices init`
- [ ] Copy `invoices.config.json.template` to `invoices.config.json`
- [ ] Set `gmail_label`
- [ ] Set `drive_root_folder_id`
- [ ] Set `spreadsheet_id`
- [ ] Get OpenAI API key
- [ ] Set `ai_api_key`
- [ ] Review and adjust other settings

## ✅ Validation

- [ ] Run `invoices doctor`
- [ ] All checks pass ✓

## ✅ First Run

- [ ] Run `invoices fetch-email`
- [ ] Check queue: `invoices queue list`
- [ ] Verify Drive: `python check_drive.py`
- [ ] Verify Sheets: `python check_sheet.py`

## ✅ All Done!

Your invoice processing system is ready! 🎉

For ongoing use:
- Run `invoices fetch-email` regularly (or set up scheduled task)
- Review items with `invoices queue list`
- Use `invoices ui` for GUI instead of CLI
- Create backups with `invoices backup`

## Need Help?

- See [README.md](README.md) for detailed documentation
- See [QUICKSTART.md](QUICKSTART.md) for quick reference
- Check Troubleshooting section in README
