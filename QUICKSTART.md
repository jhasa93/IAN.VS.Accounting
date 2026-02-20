# Quick Start Guide

## 5-Minute Setup

### 1. Install Python & Dependencies

```powershell
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install with AI support
pip install -e ".[ai]"
```

### 2. Install Poppler (for PDF processing)

```powershell
# Download and extract
$url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\poppler.zip"
Expand-Archive -Path "$env:TEMP\poppler.zip" -DestinationPath "C:\poppler" -Force

# Add to PATH (restart PowerShell after)
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\poppler\poppler-24.08.0\Library\bin", "User")
```

### 3. Setup Google Cloud

1. Go to https://console.cloud.google.com/
2. Create project → Enable **Gmail API** and **Google Drive API**
3. Create **OAuth 2.0 credentials** (Desktop app)
4. Download as `client_secret.json` to project folder

### 4. Get OpenAI API Key

1. Go to https://platform.openai.com/
2. Add payment method (min $5)
3. Create API key at https://platform.openai.com/api-keys

### 5. Configure

```powershell
# Initialize config
invoices init

# Find Gmail label
python -c "from invoices.google_services import build_services; gmail, _, _ = build_services('client_secret.json'); labels = gmail.users().labels().list(userId='me').execute(); print('\n'.join([f'{l[\"name\"]}: {l[\"id\"]}' for l in labels['labels']]))"

# Edit invoices.config.json with:
# - gmail_label (from above)
# - drive_root_folder_id (from Drive URL)
# - spreadsheet_id (from Sheets URL)
# - ai_api_key (from OpenAI)
```

### 6. Validate & Run

```powershell
# Check setup
invoices doctor

# Process invoices!
invoices fetch-email
```

## Need Help?

See full [README.md](README.md) for detailed instructions and troubleshooting.
