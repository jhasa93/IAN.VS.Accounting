from invoices.google_services import build_services
from invoices.config import load_config
import json
from pathlib import Path
import shutil

# Load config and build services
config = load_config()
gmail, drive, sheets = build_services(config.credentials_path)

# Get the INVOICE_PROCESSED label ID
labels_result = gmail.users().labels().list(userId='me').execute()
label_id = None
for label in labels_result.get('labels', []):
    if label['name'] == 'INVOICE_PROCESSED':
        label_id = label['id']
        break

if label_id:
    print(f"Found label ID: {label_id}")
    
    # Get all processed message IDs from state
    state_path = Path("data/state.json")
    if state_path.exists():
        with open(state_path) as f:
            state = json.load(f)
        message_ids = state.get('processed_message_ids', [])
        
        print(f"Removing label from {len(message_ids)} messages...")
        for msg_id in message_ids:
            try:
                gmail.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={'removeLabelIds': [label_id]}
                ).execute()
                print(f"  ✓ Removed label from {msg_id}")
            except Exception as e:
                print(f"  ✗ Error with {msg_id}: {e}")
else:
    print("INVOICE_PROCESSED label not found")

# Clear state
print("\nClearing state.json...")
state_path = Path("data/state.json")
state_path.write_text('{"processed_message_ids": []}')
print("✓ Cleared state.json")

# Clear queue
print("\nClearing queue.json...")
queue_path = Path("data/queue.json")
queue_path.write_text('[]')
print("✓ Cleared queue.json")

# Clear staging folder
print("\nClearing staging folder...")
staging_path = Path("data/staging")
if staging_path.exists():
    for item in staging_path.iterdir():
        if item.is_file():
            item.unlink()
            print(f"  ✓ Deleted {item.name}")
    print("✓ Cleared staging folder")
else:
    print("  Staging folder doesn't exist")

print("\n" + "=" * 80)
print("✅ Everything cleared! Ready to reprocess from scratch.")
print("=" * 80)
print("\nRun: invoices fetch-email")
