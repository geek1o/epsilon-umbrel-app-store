import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("anime365_sidecar_ui", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(app)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.config_path = self.root / "config" / ".env"
        self.library_path = self.root / "library"
        self.library_path.mkdir()
        self.patches = (
            mock.patch.object(app, "CONFIG_PATH", self.config_path),
            mock.patch.object(app, "LIBRARY_PATH", self.library_path),
        )
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tempdir.cleanup()

    def valid_payload(self):
        return {
            "anime365_base_url": "https://smotret-anime.app",
            "anime365_login": "user@example.com",
            "anime365_password": "secret-password",
            "emby_base_url": "http://epsilon-emby_server_1:8096/emby",
            "emby_api_key": "secret-key",
            "emby_library_id": "3",
            "emby_user_id": "abc123",
        }

    def test_write_is_atomic_restricted_and_redacts_secrets(self):
        existing = {"CUSTOM_UPSTREAM_OPTION": "keep-me"}
        config = app.validate_config(self.valid_payload(), existing)
        app.write_env_file(config, existing)

        mode = stat.S_IMODE(self.config_path.stat().st_mode)
        self.assertEqual(mode, 0o600)
        values = app.read_env_file()
        self.assertEqual(values["SIDECAR_LIBRARY_DIRECTORY"], "/library")
        self.assertEqual(values["CUSTOM_UPSTREAM_OPTION"], "keep-me")

        public = app.public_config()
        self.assertEqual(public["config"]["anime365_password"], "")
        self.assertEqual(public["config"]["emby_api_key"], "")
        self.assertTrue(public["secret_set"]["anime365_password"])
        self.assertTrue(public["secret_set"]["emby_api_key"])

    def test_blank_secret_preserves_saved_value(self):
        first = app.validate_config(self.valid_payload(), {})
        existing = {
            spec[1]: first[spec[0]]
            for spec in app.FIELD_SPECS
        }
        changed = self.valid_payload()
        changed["anime365_password"] = ""
        changed["emby_api_key"] = ""
        result = app.validate_config(changed, existing)
        self.assertEqual(result["anime365_password"], "secret-password")
        self.assertEqual(result["emby_api_key"], "secret-key")

    def test_validation_rejects_invalid_duration_and_url(self):
        payload = self.valid_payload()
        payload["scan_idle_interval"] = "five minutes"
        with self.assertRaisesRegex(ValueError, "неверный интервал"):
            app.validate_config(payload, {})

        payload = self.valid_payload()
        payload["emby_base_url"] = "epsilon-emby:8096"
        with self.assertRaisesRegex(ValueError, "полный адрес"):
            app.validate_config(payload, {})

    def test_manifest_statistics(self):
        manifest = {
            "shows": {
                "one": {
                    "episodes": {
                        "1": {"translations": {"10": {}, "11": {}}},
                        "2": {"translations": {"12": {}}},
                    }
                },
                "two": {"episodes": {}},
            }
        }
        (self.library_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        status = app.library_status()
        self.assertEqual(status["shows"], 2)
        self.assertEqual(status["episodes"], 2)
        self.assertEqual(status["translations"], 3)


if __name__ == "__main__":
    unittest.main()
