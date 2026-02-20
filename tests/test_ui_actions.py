import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
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


_install_dependency_stubs()

from invoices.ui import execute_action


class UIActionTests(unittest.TestCase):
    def test_execute_action_fetch_email_formats_result_json(self):
        cfg = SimpleNamespace()
        with patch("invoices.ui.load_config", return_value=cfg), patch(
            "invoices.ui.process_new_email", return_value={"messages_processed": 2, "items_filed": 3}
        ):
            output = execute_action("fetch-email", Path("/tmp/config.json"))

        self.assertEqual(json.loads(output), {"messages_processed": 2, "items_filed": 3})

    def test_execute_action_queue_list_empty_message(self):
        cfg = SimpleNamespace(queue_path="/tmp/queue.json")
        fake_store = SimpleNamespace(list=lambda: [])

        with patch("invoices.ui.load_config", return_value=cfg), patch("invoices.ui.QueueStore", return_value=fake_store):
            output = execute_action("queue-list", Path("/tmp/config.json"))

        self.assertEqual(output, "queue is empty")

    def test_execute_action_backup_creates_timestamp_folder_and_copies_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook = root / "master.xlsx"
            queue = root / "queue.json"
            state = root / "state.json"
            log = root / "invoices.log"
            for path in (workbook, queue, state, log):
                path.write_text("data", encoding="utf-8")

            cfg = SimpleNamespace(
                backup_dir=str(root / "backups"),
                workbook_path=str(workbook),
                queue_path=str(queue),
                state_path=str(state),
                log_path=str(log),
            )

            with patch("invoices.ui.load_config", return_value=cfg):
                output = execute_action("backup", Path("/tmp/config.json"))

            self.assertIn("backup created at", output)
            backup_dirs = list((root / "backups").iterdir())
            self.assertEqual(len(backup_dirs), 1)
            copied = {p.name for p in backup_dirs[0].iterdir()}
            self.assertEqual(copied, {"master.xlsx", "queue.json", "state.json", "invoices.log"})

    def test_execute_action_unknown_action_raises(self):
        cfg = SimpleNamespace()
        with patch("invoices.ui.load_config", return_value=cfg):
            with self.assertRaises(ValueError):
                execute_action("not-real", Path("/tmp/config.json"))


if __name__ == "__main__":
    unittest.main()
