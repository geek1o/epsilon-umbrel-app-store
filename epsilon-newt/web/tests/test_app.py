import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("epsilon_newt_ui", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(app)


class NewtConfigTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.config_path = root / "config.json"
        self.health_path = root / "health"
        self.patches = (
            mock.patch.object(app, "CONFIG_PATH", self.config_path),
            mock.patch.object(app, "HEALTH_PATH", self.health_path),
        )
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tempdir.cleanup()

    def payload(self):
        return {"endpoint": "https://pangolin.example.com", "id": "site-id", "secret": "site-secret"}

    def test_write_restricts_permissions_and_redacts_secret(self):
        config = app.validate_payload(self.payload(), {"futureOption": "kept"})
        app.write_config(config, {"futureOption": "kept"})
        self.assertEqual(stat.S_IMODE(self.config_path.stat().st_mode), 0o600)
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["futureOption"], "kept")
        self.assertEqual(saved["secret"], "site-secret")
        public = app.public_config()
        self.assertEqual(public["config"]["secret"], "")
        self.assertTrue(public["secret_set"])

    def test_blank_secret_preserves_saved_secret(self):
        payload = self.payload()
        payload["secret"] = ""
        config = app.validate_payload(payload, {"secret": "already-saved"})
        self.assertEqual(config["secret"], "already-saved")

    def test_validation_rejects_bad_endpoint_and_duration(self):
        payload = self.payload()
        payload["endpoint"] = "pangolin.example.com"
        with self.assertRaisesRegex(ValueError, "полный адрес"):
            app.validate_payload(payload, {})
        payload = self.payload()
        payload["pingInterval"] = "soon"
        with self.assertRaisesRegex(ValueError, "неверный интервал"):
            app.validate_payload(payload, {})

    def test_connected_state_uses_upstream_health_file(self):
        app.write_config(app.validate_payload(self.payload(), {}), {})
        self.health_path.write_text("ok", encoding="utf-8")
        with app.LOCK:
            app.restart_required = False
        state = app.state_payload()
        self.assertEqual(state["state"], "connected")
        self.assertTrue(state["connected"])


if __name__ == "__main__":
    unittest.main()
