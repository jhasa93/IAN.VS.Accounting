# Invoices CLI

Local-first invoice processing system that automatically extracts data from Gmail invoice emails, uploads files to Google Drive, and maintains an Excel ledger in Google Sheets.

## Features

- 📧 **Gmail Integration**: Fetches invoices from Gmail attachments and email links
- 🤖 **AI-Powered Extraction**: Uses GPT-4o-mini vision to extract invoice details automatically
- 🔍 **OCR Support**: Processes scanned PDFs and images with Tesseract OCR
- 📁 **Google Drive Filing**: Automatically organizes invoices by date (`Invoices/YYYY/MM`)
- 📊 **Google Sheets Ledger**: Maintains detailed records with vendor info, amounts, dates, etc.
- 🖥️ **CLI & GUI**: Command-line interface or simple desktop UI
- 🔄 **Idempotent Processing**: Safe to re-run without duplicates

## Prerequisites

- **Python 3.10+**
- **Google Cloud Project** with Gmail and Drive APIs enabled
- **Poppler** (for PDF to image conversion)
- **Tesseract OCR** (optional, for scanned documents)
- **OpenAI API key** (optional, for AI enhancement)

## Installation

### 1. Clone Repository

```powershell
git clone <repository-url>
cd IAN.VS.Accounting
```

### 2. Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

**Basic installation:**
```powershell
pip install -e .
```

**With AI enhancement (recommended):**
```powershell
pip install -e ".[ai]"
```

### 4. Install Poppler (Required for AI Enhancement)

Poppler converts PDF pages to images for AI vision analysis.

**Download and install:**
```powershell
$url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip"
$output = "$env:TEMP\poppler.zip"
$dest = "C:\poppler"
Invoke-WebRequest -Uri $url -OutFile $output
Expand-Archive -Path $output -DestinationPath $dest -Force
Remove-Item $output
```

**Add to PATH permanently:**
```powershell
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\poppler\poppler-24.08.0\Library\bin", "User")
```

**Verify installation:**
```powershell
# Restart PowerShell, then:
pdftoppm -v
```

### 5. Install Tesseract OCR (Optional)

Only needed if you have scanned invoices.
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Install with language packs: English, German, Spanish, Czech
- Add to PATH: `C:\Program Files\Tesseract-OCR`

## Configuration

### 1. Google Cloud Setup

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable **Gmail API** and **Google Drive API**
4. Create **OAuth 2.0 credentials** (Desktop app)
5. Download credentials as `client_secret.json` to project root

### 2. Find Your Gmail Label ID

```powershell
.\.venv\Scripts\Activate.ps1
python -c "from invoices.google_services import build_services; gmail, _, _ = build_services('client_secret.json'); labels = gmail.users().labels().list(userId='me').execute(); print('\n'.join([f'{l[\"name\"]}: {l[\"id\"]}' for l in labels['labels']]))"
```

Look for your invoice label (e.g., `INBOX`, `Label_123`, etc.)

### 3. Find Your Google Drive Folder ID

1. Open Google Drive in browser
2. Navigate to your Invoices folder (or create one)
3. Copy the folder ID from the URL: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID`

### 4. Find Your Google Sheets Spreadsheet ID

1. Create a new Google Sheet for your ledger
2. Copy the ID from the URL: `https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit`

### 5. Initialize Configuration

```powershell
invoices init
```

This creates `invoices.config.json`. Edit it with your values:

```json
{
  "credentials_path": "client_secret.json",
  "gmail_label": "INBOX",
  "gmail_processed_label": "INVOICE_PROCESSED",
  "drive_root_folder_id": "YOUR_DRIVE_FOLDER_ID",
  "spreadsheet_id": "YOUR_SPREADSHEET_ID",
  "staging_dir": "./data/staging",
  "queue_path": "./data/queue.json",
  "state_path": "./data/state.json",
  "log_path": "./data/invoices.log",
  "backup_dir": "./data/backups",
  "enable_ocr": true,
  "ocr_languages": "eng+deu+spa+ces",
  "enable_ai_enhancement": true,
  "ai_provider": "openai",
  "ai_api_key": "YOUR_OPENAI_API_KEY",
  "ai_model": "gpt-4o-mini",
  "ai_confidence_threshold": 0.8
}
```

### 6. Get OpenAI API Key (for AI Enhancement)

1. Sign up at https://platform.openai.com/
2. Add payment method (minimum $5)
3. Create API key at https://platform.openai.com/api-keys
4. Copy key starting with `sk-proj-...`
5. Add to `invoices.config.json`

### 7. Validate Setup

```powershell
invoices doctor
```

This checks:
- ✅ Credentials file exists
- ✅ Gmail API access
- ✅ Drive API access
- ✅ Spreadsheet access

## Usage

### Process New Invoices

```powershell
invoices fetch-email
```

This will:
1. Fetch unread emails from Gmail with your label
2. Download attachments and linked documents
3. Extract invoice data using OCR and AI
4. Upload files to Google Drive
5. Write records to Google Sheets
6. Mark emails as processed

### Review Queue

```powershell
# List all items
invoices queue list

# Show details of specific item
invoices queue show <internal_id>

# Manually approve item for filing
invoices queue approve <internal_id>
```

### Launch Desktop UI

```powershell
invoices ui
```

Provides buttons for:
- Fetch & Process Emails
- View Queue
- Create Backup

### Other Commands

```powershell
# Verify ledger integrity
invoices reconcile-ledger

# Create backup of data
invoices backup
```

## How AI Enhancement Works

When enabled, the system uses GPT-4o-mini vision to extract missing invoice fields:

1. **Initial Extraction**: Regex patterns and OCR extract what they can
2. **AI Trigger**: If confidence < 0.8 OR required fields missing, AI is called
3. **Vision Analysis**: PDF converted to image and sent to GPT-4o-mini
4. **Field Extraction**: AI extracts:
   - Vendor name and VAT/Tax ID
   - Invoice number
   - Invoice date and due date
   - Currency and amounts (total, subtotal, tax)
   - Document language
5. **Merge Results**: AI fills gaps in initial extraction
6. **High Confidence**: Result marked as 0.9 confidence

**Required Fields for Auto-Filing:**
- `vendor_name`
- `vendor_vat` (IČO, DIČ, Tax ID)
- `invoice_date`
- `currency`
- `total_amount`

**Cost**: ~$0.001-0.002 per invoice with gpt-4o-mini

## Troubleshooting

### "Unable to get page count. Is poppler installed?"

Poppler is not in PATH. Install it and restart your terminal.

### "You exceeded your current quota"

Add credits to your OpenAI account at https://platform.openai.com/settings/organization/billing

### "Permission denied" on Gmail/Drive

Re-authenticate:
```powershell
Remove-Item token.json
invoices doctor
```

### OCR not working

Install Tesseract OCR and add to PATH, or disable in config:
```json
"enable_ocr": false
```

### Items stuck in "Needs Review"

Check extraction details:
```powershell
invoices queue show <internal_id>
```

Missing required fields? Enable AI enhancement or manually approve:
```powershell
invoices queue approve <internal_id>
```

## Utility Scripts

- **check_drive.py**: View your Drive folder structure
- **check_sheet.py**: View spreadsheet contents  
- **reset_everything.py**: Clear all state and start fresh (removes labels, clears queue)
- **reset_for_reprocessing.py**: Reset specific messages for reprocessing

## Architecture

```
invoices/
├── cli.py              # Typer commands
├── config.py           # Configuration model
├── extraction.py       # Invoice parsing (regex, OCR, AI)
├── google_services.py  # Gmail/Drive/Sheets API wrappers
├── ledger.py           # Spreadsheet operations
├── models.py           # Pydantic data models
├── processing.py       # Main orchestration
├── storage.py          # Local JSON stores
└── ui.py              # Desktop UI
```

## Testing

```powershell
# Run all tests
python -m unittest discover tests

# Run specific test
python -m unittest tests.test_processing_flow
python -m unittest tests.test_extraction_ocr
```

## Security

- ⚠️ **Never commit** `client_secret.json`, `token.json`, or `invoices.config.json`
- API keys and credentials are in `.gitignore`
- Secrets are never logged
- Local-first design: all data stored locally and in your Google account

## License

[Add your license here]
