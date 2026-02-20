from invoices.google_services import build_services
from invoices.config import load_config

# Load config and build services
config = load_config()
gmail, drive, sheets = build_services(config.credentials_path)

# Message IDs to unlabel
message_ids = [
    "19c724e4821abc0f",
    "19c74ce0e00dbe6d",
    "19c7594707d4cc34",
    "19c7599eddbc6fb5",
    "19c79cd49d1d19b1"
]

# Get the INVOICE_PROCESSED label ID
labels_result = gmail.users().labels().list(userId='me').execute()
label_id = None
for label in labels_result.get('labels', []):
    if label['name'] == 'INVOICE_PROCESSED':
        label_id = label['id']
        break

if not label_id:
    print("INVOICE_PROCESSED label not found")
else:
    print(f"Found label ID: {label_id}")
    for msg_id in message_ids:
        try:
            gmail.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': [label_id]}
            ).execute()
            print(f"Removed label from message {msg_id}")
        except Exception as e:
            print(f"Error removing label from {msg_id}: {e}")

print("\nClearing state and queue files...")
import json
from pathlib import Path

# Clear state
state_path = Path("data/state.json")
state_path.write_text('{"processed_message_ids": []}')
print("Cleared state.json")

# Clear queue
queue_path = Path("data/queue.json")
queue_path.write_text('[]')
print("Cleared queue.json")

print("\nDone! You can now run: invoices fetch-email")
