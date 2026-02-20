from invoices.google_services import build_services
from invoices.config import load_config

config = load_config()
gmail, drive, sheets = build_services(config.credentials_path)

# List files in the root invoices folder
results = drive.files().list(
    q=f"'{config.drive_root_folder_id}' in parents and trashed=false",
    fields="files(id, name, mimeType)"
).execute()

files = results.get('files', [])
print(f"Found {len(files)} files in root Invoices folder:")
for f in files:
    print(f"  {f['name']} ({f['mimeType']})")
    
    # Check if it's a folder
    if f['mimeType'] == 'application/vnd.google-apps.folder':
        # List contents
        subresults = drive.files().list(
            q=f"'{f['id']}' in parents and trashed=false",
            fields="files(id, name, mimeType)"
        ).execute()
        subfiles = subresults.get('files', [])
        print(f"    Contains {len(subfiles)} items:")
        for sf in subfiles:
            print(f"      {sf['name']} ({sf['mimeType']})")
            
            # Check if it's a folder (month folder)
            if sf['mimeType'] == 'application/vnd.google-apps.folder':
                monthresults = drive.files().list(
                    q=f"'{sf['id']}' in parents and trashed=false",
                    fields="files(id, name, mimeType)"
                ).execute()
                monthfiles = monthresults.get('files', [])
                print(f"        Contains {len(monthfiles)} items:")
                for mf in monthfiles:
                    print(f"          {mf['name']}")
