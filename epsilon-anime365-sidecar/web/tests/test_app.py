import importlib.util
import json
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

    def jellyfin_payload(self):
        return {
            **{key: value for key, value in self.valid_payload().items() if not key.startswith("emby_")},
            "media_server": "jellyfin",
            "jellyfin_base_url": "http://jellyfin:8096/jellyfin",
            "jellyfin_api_key": "jellyfin-secret",
            "jellyfin_library_id": "12345678-1234-5678-9012-123456789abc",
            "jellyfin_user_id": "12345678123456789012123456789abc",
        }

    def test_jellyfin_config_omits_all_emby_variables_and_redacts_key(self):
        # Inactive provider defaults must not leak into the .env: upstream rejects them.
        existing = {"SIDECAR_EMBY_BASE_URL": "http://emby:8096", "SIDECAR_EMBY_API_KEY": "old-secret"}
        config = app.validate_config(self.jellyfin_payload(), existing)
        app.write_env_file(config, existing)
        values = app.read_env_file()
        self.assertFalse(any(key.startswith("SIDECAR_EMBY_") for key in values))
        self.assertEqual(values["SIDECAR_MEDIA_SERVER"], "jellyfin")
        self.assertEqual(values["SIDECAR_JELLYFIN_API_KEY"], "jellyfin-secret")
        public = app.public_config()
        self.assertEqual(public["config"]["jellyfin_api_key"], "")
        self.assertTrue(public["secret_set"]["jellyfin_api_key"])
        self.assertEqual(app.required_status(values), (True, []))
        # Empty browser password fields preserve the key on later saves.
        saved = app.validate_config({"jellyfin_api_key": "", "log_level": "DEBUG"}, values)
        self.assertEqual(saved["jellyfin_api_key"], "jellyfin-secret")

    def test_emby_remains_default_for_existing_config(self):
        existing = {app.KEY_TO_SPEC[key][1]: value for key, value in self.valid_payload().items()}
        config = app.validate_config({"log_level": "WARN"}, existing)
        app.write_env_file(config, existing)
        values = app.read_env_file()
        self.assertEqual(values["SIDECAR_MEDIA_SERVER"], "emby")
        self.assertFalse(any(key.startswith("SIDECAR_JELLYFIN_") for key in values))
        self.assertEqual(values["SIDECAR_EMBY_API_KEY"], "secret-key")
        self.assertEqual(values["SIDECAR_WATCHED_EPISODES_CLEANUP_POLICY"], "do_not_delete")
        self.assertEqual(values["SIDECAR_WATCHED_EPISODES_CLEANUP_AFTER"], "336h")

    def test_provider_validation_and_required_fields(self):
        for change in (
            {"media_server": "plex"},
            {"jellyfin_api_key": ""},
            {"jellyfin_library_id": "not-a-uuid"},
            {"jellyfin_user_id": "0" * 32},
            {"jellyfin_base_url": "jellyfin:8096"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                app.validate_config({**self.jellyfin_payload(), **change}, {})

    def test_cannot_switch_an_existing_library(self):
        for filename, payload in (("manifest.json", self.jellyfin_payload()),
                                  ("manifest-jellyfin.json", self.valid_payload())):
            manifest = self.library_path / filename
            manifest.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Переключение существующей библиотеки"):
                app.validate_config(payload, {})
            self.assertEqual(manifest.read_text(), "{}")
            manifest.unlink()

    def test_cleanup_modes_round_trip_and_invalid_values_are_rejected(self):
        for policy in ("do_not_delete", "delete_watched_episodes", "delete_completed_and_dropped_shows"):
            config = app.validate_config({**self.valid_payload(),
                                         "watched_episodes_cleanup_policy": policy,
                                         "watched_episodes_cleanup_after": "0s",
                                         "delete_removed_translations": True}, {})
            app.write_env_file(config, {})
            values = app.read_env_file()
            self.assertEqual(values["SIDECAR_WATCHED_EPISODES_CLEANUP_POLICY"], policy)
            self.assertEqual(values["SIDECAR_WATCHED_EPISODES_CLEANUP_AFTER"], "0s")
            self.assertEqual(values["SIDECAR_DELETE_REMOVED_TRANSLATIONS"], "true")
        with self.assertRaisesRegex(ValueError, "политику удаления"):
            app.validate_config({**self.valid_payload(), "watched_episodes_cleanup_policy": "delete_all"}, {})

    def test_cleanup_duration_accepts_go_syntax_and_rejects_negative_and_overflow(self):
        for duration in ("0s", "0", "336h", "1h30m", ".5h", "1.m", "1µs", "1μs", "+2h"):
            with self.subTest(duration=duration):
                app.validate_config({**self.valid_payload(), "watched_episodes_cleanup_after": duration}, {})
        for duration in ("-1h", "14d", "1h garbage", "999999999h"):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                app.validate_config({**self.valid_payload(), "watched_episodes_cleanup_after": duration}, {})

    def test_optional_secrets_can_be_explicitly_cleared(self):
        config = app.validate_config({**self.valid_payload(),
                                      "http_proxy": "http://user:password@proxy:3128",
                                      "telegram_bot_api_credentials": "telegram://token@api.telegram.org/?recipient=123"}, {})
        app.write_env_file(config, {})
        existing = app.read_env_file()
        result = app.validate_config({"_clear_secrets": ["http_proxy", "telegram_bot_api_credentials"]}, existing)
        app.write_env_file(result, existing)
        self.assertEqual(app.read_env_file()["HTTP_PROXY"], "")
        self.assertEqual(app.read_env_file()["SIDECAR_TELEGRAM_BOT_API_CREDENTIALS"], "")
        self.assertEqual(app.read_env_file()["SIDECAR_ANIME365_PASSWORD"], "secret-password")
        self.assertFalse(app.public_config()["secret_set"]["http_proxy"])
        with self.assertRaisesRegex(ValueError, "обязательные поля"):
            app.validate_config({"_clear_secrets": ["anime365_password"]}, existing)

    def test_jellyfin_statistics_uses_its_own_manifest(self):
        (self.library_path / "manifest-jellyfin.json").write_text(json.dumps({
            "media_server": "jellyfin", "shows": {"1": {"episodes": {"1": {"translations": {"1": {}}}}}}
        }))
        status = app.library_status(provider="jellyfin")
        self.assertEqual((status["shows"], status["episodes"], status["translations"]), (1, 1, 1))
        self.assertEqual(status["manifest_name"], "manifest-jellyfin.json")
        self.assertEqual(app.library_status(provider="emby")["shows"], 0)

    def test_jellyfin_api_check_uses_unsaved_url_and_saved_secret(self):
        app.write_env_file(app.validate_config(self.jellyfin_payload(), {}), {})
        with mock.patch.object(app, "request_url", return_value=(200, b'{"Version":"10.11"}')) as request:
            result = app.test_connection("jellyfin", {"jellyfin_base_url": "http://new-server/jellyfin/", "jellyfin_api_key": ""})
        request.assert_called_once_with("http://new-server/jellyfin/System/Info", {"X-Emby-Token": "jellyfin-secret"})
        self.assertIn("Jellyfin: 10.11", result["message"])


if __name__ == "__main__":
    unittest.main()
