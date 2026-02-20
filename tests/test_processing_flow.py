import base64
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _install_dependency_stubs() -> None:
    if "pydantic" not in sys.modules:
        pydantic = types.ModuleType("pydantic")

        class BaseModel:
            def __init__(self, **kwargs):
                annotations = {}
                for cls in reversed(type(self).mro()):
                    annotations.update(getattr(cls, "__annotations__", {}))
                for key in annotations:
                    if key in kwargs:
                        setattr(self, key, kwargs[key])
                    elif hasattr(type(self), key):
                        default = getattr(type(self), key)
                        setattr(self, key, default() if callable(default) and getattr(default, "_is_factory", False) else default)
                    else:
                        setattr(self, key, None)

            def model_dump(self, mode=None):
                out = {}
                for k, v in self.__dict__.items():
                    if mode == "json" and hasattr(v, "isoformat"):
                        out[k] = v.isoformat()
                    else:
                        out[k] = v
                return out

            def model_dump_json(self, indent=None):
                return json.dumps(self.model_dump(mode="json"), indent=indent, default=str)

        def Field(default=None, default_factory=None):
            if default_factory is not None:
                def _factory_wrapper():
                    return default_factory()

                _factory_wrapper._is_factory = True
                return _factory_wrapper
            return default

        pydantic.BaseModel = BaseModel
        pydantic.Field = Field
        sys.modules["pydantic"] = pydantic

    if "google.oauth2.service_account" not in sys.modules:
        google = types.ModuleType("google")
        auth = types.ModuleType("google.auth")
        transport = types.ModuleType("google.auth.transport")
        requests_transport = types.ModuleType("google.auth.transport.requests")
        oauth2 = types.ModuleType("google.oauth2")
        credentials_mod = types.ModuleType("google.oauth2.credentials")
        service_account = types.ModuleType("google.oauth2.service_account")

        class Credentials:
            @staticmethod
            def from_service_account_file(path, scopes=None):
                return object()

            @staticmethod
            def from_authorized_user_file(path, scopes=None):
                return object()

        service_account.Credentials = Credentials
        credentials_mod.Credentials = Credentials
        requests_transport.Request = object
        transport.requests = requests_transport
        auth.transport = transport
        google.auth = auth
        oauth2.service_account = service_account
        google.oauth2 = oauth2
        sys.modules["google"] = google
        sys.modules["google.auth"] = auth
        sys.modules["google.auth.transport"] = transport
        sys.modules["google.auth.transport.requests"] = requests_transport
        sys.modules["google.oauth2"] = oauth2
        sys.modules["google.oauth2.credentials"] = credentials_mod
        sys.modules["google.oauth2.service_account"] = service_account

    if "google_auth_oauthlib.flow" not in sys.modules:
        google_auth_oauthlib = types.ModuleType("google_auth_oauthlib")
        flow_mod = types.ModuleType("google_auth_oauthlib.flow")

        class InstalledAppFlow:
            @staticmethod
            def from_client_secrets_file(path, scopes):
                class _Flow:
                    def run_local_server(self, port=0):
                        return object()

                return _Flow()

        flow_mod.InstalledAppFlow = InstalledAppFlow
        google_auth_oauthlib.flow = flow_mod
        sys.modules["google_auth_oauthlib"] = google_auth_oauthlib
        sys.modules["google_auth_oauthlib.flow"] = flow_mod

    if "googleapiclient.discovery" not in sys.modules:
        googleapiclient = types.ModuleType("googleapiclient")
        discovery = types.ModuleType("googleapiclient.discovery")
        http = types.ModuleType("googleapiclient.http")

        def build(name, version, credentials=None):
            return object()

        class MediaFileUpload:
            def __init__(self, path, resumable=False):
                self.path = path

        discovery.build = build
        http.MediaFileUpload = MediaFileUpload
        googleapiclient.discovery = discovery
        googleapiclient.http = http
        sys.modules["googleapiclient"] = googleapiclient
        sys.modules["googleapiclient.discovery"] = discovery
        sys.modules["googleapiclient.http"] = http

    if "dateutil.parser" not in sys.modules:
        dateutil = types.ModuleType("dateutil")
        parser = types.ModuleType("dateutil.parser")

        def parse(value):
            return value

        parser.parse = parse
        dateutil.parser = parser
        sys.modules["dateutil"] = dateutil
        sys.modules["dateutil.parser"] = parser

    if "openpyxl" not in sys.modules:
        openpyxl = types.ModuleType("openpyxl")

        class Workbook:
            def __init__(self):
                self.active = types.SimpleNamespace(title="Invoices", append=lambda *_: None)

            def save(self, path):
                Path(path).write_text("stub workbook", encoding="utf-8")

        def load_workbook(path, data_only=False):
            class _Sheet:
                max_row = 1

                def cell(self, row, column, value=None):
                    return types.SimpleNamespace(value=None)

                def append(self, values):
                    pass

            return {"Invoices": _Sheet()}

        openpyxl.Workbook = Workbook
        openpyxl.load_workbook = load_workbook
        sys.modules["openpyxl"] = openpyxl

    if "requests" not in sys.modules:
        requests = types.ModuleType("requests")

        class _Resp:
            def __init__(self, content=b""):
                self.content = content

            def raise_for_status(self):
                return None

        def get(url, timeout=30):
            return _Resp()

        requests.get = get
        sys.modules["requests"] = requests

    if "pypdf" not in sys.modules:
        pypdf = types.ModuleType("pypdf")

        class PdfReader:
            def __init__(self, path):
                self.pages = []

        pypdf.PdfReader = PdfReader
        sys.modules["pypdf"] = pypdf


_install_dependency_stubs()

from invoices.config import AppConfig
from invoices.processing import process_new_email


class FakeExtraction:
    vendor_name = "ACME"
    invoice_number = "INV-1"
    invoice_date = "2026-01-10"
    due_date = ""
    currency = "USD"
    subtotal = None
    tax_amount = None
    total_amount = 100.0
    category = None
    vendor_vat = ""
    language = "en"
    confidence = 0.95
    valid = True
    validation_errors = []


class ProcessingFlowTests(unittest.TestCase):
    def _run_flow_for_attachment(self, filename: str, mime_type: str, file_bytes: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            ledger_path = root / "master_ledger.xlsx"
            queue_path = root / "queue.json"
            state_path = root / "state.json"
            log_path = root / "invoices.log"

            cfg = AppConfig(
                credentials_path=str(root / "creds.json"),
                gmail_label="INBOX",
                gmail_processed_label="INVOICE_PROCESSED",
                drive_root_folder_id="drive-root",
                spreadsheet_id=str(ledger_path),
                staging_dir=str(staging),
                queue_path=str(queue_path),
                state_path=str(state_path),
                log_path=str(log_path),
                backup_dir=str(root / "backups"),
            )

            attachment_data = base64.urlsafe_b64encode(file_bytes).decode()
            mock_message = {
                "id": "msg-1",
                "internalDate": "1700000000000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "vendor@example.com"},
                        {"name": "Subject", "value": f"Invoice {filename}"},
                    ],
                    "parts": [
                        {
                            "filename": filename,
                            "mimeType": mime_type,
                            "body": {"data": attachment_data},
                        }
                    ],
                },
            }

            processed_marks = []

            def fake_append_or_update_record(_sheets, spreadsheet_id, record):
                Path(spreadsheet_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")

            with patch("invoices.processing.build_services", return_value=(object(), object(), object())), \
                patch("invoices.processing.fetch_new_messages", return_value=[mock_message]), \
                patch("invoices.processing.ensure_gmail_label", return_value="lbl-processed"), \
                patch("invoices.processing.ensure_folder", side_effect=["year-folder", "month-folder"]), \
                patch("invoices.processing.upload_invoice_file", return_value=("drive-file-1", True)), \
                patch("invoices.processing.extract_invoice", return_value=FakeExtraction()), \
                patch("invoices.processing.append_or_update_record", side_effect=fake_append_or_update_record), \
                patch("invoices.processing.mark_message_processed", side_effect=lambda *args: processed_marks.append(args)):
                result = process_new_email(cfg)

            staged_files = list(staging.iterdir())
            self.assertEqual(result["messages_processed"], 1)
            self.assertEqual(result["items_queued"], 1)
            self.assertEqual(result["items_filed"], 1)
            self.assertEqual(len(staged_files), 1)
            self.assertTrue(staged_files[0].name.endswith(Path(filename).suffix))
            self.assertTrue(ledger_path.exists(), "expected master ledger file in mocked local folder")
            self.assertTrue(queue_path.exists(), "expected queue file in mocked local folder")
            self.assertEqual(len(processed_marks), 1, "expected Gmail message to be tagged as processed")

    def test_fetch_processes_mock_csv_email(self):
        self._run_flow_for_attachment(
            filename="invoice.csv",
            mime_type="text/csv",
            file_bytes=b"vendor,invoice_number,invoice_date,currency,total_amount\nACME,INV-1,2026-01-10,USD,100.00\n",
        )

    def test_fetch_processes_mock_pdf_email(self):
        self._run_flow_for_attachment(
            filename="invoice.pdf",
            mime_type="application/pdf",
            file_bytes=b"%PDF-1.4 fake invoice pdf bytes",
        )

    def test_fetch_processes_mock_image_email(self):
        self._run_flow_for_attachment(
            filename="invoice.jpg",
            mime_type="image/jpeg",
            file_bytes=b"\xff\xd8\xff\xe0 fake jpeg bytes",
        )

    def test_fetch_downloads_link_from_html_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            cfg = AppConfig(
                credentials_path=str(root / "creds.json"),
                gmail_label="INBOX",
                gmail_processed_label="INVOICE_PROCESSED",
                drive_root_folder_id="drive-root",
                spreadsheet_id=str(root / "master_ledger.xlsx"),
                staging_dir=str(staging),
                queue_path=str(root / "queue.json"),
                state_path=str(root / "state.json"),
                log_path=str(root / "invoices.log"),
                backup_dir=str(root / "backups"),
            )

            html = '<a href="https://www.zasilkovna.cz/api/invoice.pdf?token=test">invoice</a>'
            html_data = base64.urlsafe_b64encode(html.encode()).decode()
            mock_message = {
                "id": "msg-html-link",
                "internalDate": "1700000000000",
                "payload": {
                    "headers": [{"name": "From", "value": "vendor@example.com"}],
                    "parts": [{"filename": "", "mimeType": "text/html", "body": {"data": html_data}}],
                },
            }

            with patch("invoices.processing.build_services", return_value=(object(), object(), object())), \
                patch("invoices.processing.fetch_new_messages", return_value=[mock_message]), \
                patch("invoices.processing.ensure_gmail_label", return_value="lbl-processed"), \
                patch("invoices.processing.download_link", return_value=staging / "invoice.pdf") as dl_mock, \
                patch("invoices.processing.extract_invoice", return_value=FakeExtraction()), \
                patch("invoices.processing.ensure_folder", side_effect=["year-folder", "month-folder"]), \
                patch("invoices.processing.upload_invoice_file", return_value=("drive-file-1", True)), \
                patch("invoices.processing.append_or_update_record"), \
                patch("invoices.processing.mark_message_processed"):
                result = process_new_email(cfg)

            self.assertEqual(result["items_queued"], 1)
            dl_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
