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

            def model_dump_json(self, indent=None):
                return json.dumps(self.__dict__, indent=indent, default=str)

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

    if "dateutil.parser" not in sys.modules:
        dateutil = types.ModuleType("dateutil")
        parser = types.ModuleType("dateutil.parser")
        parser.parse = lambda value, dayfirst=False: types.SimpleNamespace(date=lambda: types.SimpleNamespace(isoformat=lambda: "2026-01-10"))
        dateutil.parser = parser
        sys.modules["dateutil"] = dateutil
        sys.modules["dateutil.parser"] = parser

    if "openpyxl" not in sys.modules:
        openpyxl = types.ModuleType("openpyxl")
        openpyxl.load_workbook = lambda *args, **kwargs: object()
        sys.modules["openpyxl"] = openpyxl

    if "pypdf" not in sys.modules:
        pypdf = types.ModuleType("pypdf")

        class PdfReader:
            def __init__(self, path):
                self.pages = []

        pypdf.PdfReader = PdfReader
        sys.modules["pypdf"] = pypdf


_install_dependency_stubs()

from invoices.extraction import extract_invoice


class ExtractionOCRTests(unittest.TestCase):
    def test_image_ocr_enabled_extracts_multilingual_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ACME_invoice.jpg"
            path.write_bytes(b"jpeg")
            ocr_text = "Faktura cislo INV-77 Datum 10.01.2026 Celkem 123,45 CZK"
            with patch("invoices.extraction._ocr_image", return_value=ocr_text) as ocr_mock:
                result = extract_invoice(path, enable_ocr=True, ocr_languages="eng+deu+spa+ces")

            ocr_mock.assert_called_once_with(path, "eng+deu+spa+ces")
            self.assertEqual(result.invoice_number, "INV-77")
            self.assertEqual(result.currency, "CZK")
            self.assertEqual(result.total_amount, 123.45)

    def test_image_ocr_disabled_skips_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ACME_invoice.jpg"
            path.write_bytes(b"jpeg")
            with patch("invoices.extraction._ocr_image") as ocr_mock:
                result = extract_invoice(path, enable_ocr=False)

            ocr_mock.assert_not_called()
            self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
