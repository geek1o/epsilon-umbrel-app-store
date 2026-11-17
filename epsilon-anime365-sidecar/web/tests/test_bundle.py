import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

WEB_DIRECTORY = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = WEB_DIRECTORY.parent
SPEC = importlib.util.spec_from_file_location("build_bundle", WEB_DIRECTORY / "build_bundle.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class BundleTests(unittest.TestCase):
    def test_committed_bundle_matches_sources_and_version(self):
        self.assertEqual(builder.BUNDLE_PATH.read_text(encoding="utf-8"), builder.build_bundle())
        # The bundle must survive envsubst without expanding JavaScript literals.
        self.assertNotIn("$", builder.build_bundle())

    def test_umbrel_whitelist_update_runs_new_ui_without_touching_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "installed"
            installed.mkdir()
            stale_web = installed / "web"
            stale_web.mkdir()
            (stale_web / "app.py").write_text('raise RuntimeError("old installed web was executed")\n')
            config = installed / "data" / "config" / ".env"
            config.parent.mkdir(parents=True)
            original_config = b'SIDECAR_ANIME365_LOGIN="existing-user"\nSIDECAR_EMBY_API_KEY="saved-secret"\n'
            config.write_bytes(original_config)

            # Reproduce Umbrel's update allowlist: root templates are refreshed; web/ is not.
            for pattern in ("docker-compose.yml", "*.template", "exports.sh", "torrc", "hooks", "umbrel-app.yml"):
                for source in PACKAGE_DIRECTORY.glob(pattern):
                    if source.is_file():
                        shutil.copyfile(source, installed / source.name)
            self.assertIn("old installed web", (stale_web / "app.py").read_text())
            for template in installed.glob("*.template"):
                rendered = template.with_suffix("")
                if shutil.which("envsubst"):
                    result = subprocess.run(["envsubst"], input=template.read_bytes(), check=True, capture_output=True)
                    rendered.write_bytes(result.stdout)
                else:
                    # Without dollar signs, rendering is the identity operation.
                    self.assertNotIn(b"$", template.read_bytes())
                    shutil.copyfile(template, rendered)

            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            library = root / "empty-library"
            library.mkdir()
            env = {**os.environ, "PORT": str(port), "CONFIG_PATH": str(config), "LIBRARY_PATH": str(library)}
            with tempfile.TemporaryFile() as logs:
                process = subprocess.Popen([sys.executable, str(installed / "ui.py")], env=env, stdout=logs, stderr=logs)
                try:
                    base = f"http://127.0.0.1:{port}"
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            with urllib.request.urlopen(base + "/health", timeout=1) as response:
                                health = json.load(response)
                            break
                        except (OSError, urllib.error.URLError):
                            if process.poll() is not None or time.monotonic() > deadline:
                                logs.seek(0)
                                self.fail("Generated UI failed to start: " + logs.read().decode())
                            time.sleep(0.05)
                    self.assertEqual(health["status"], "ok")
                    self.assertNotEqual(health["ui_version"], "development")
                    with urllib.request.urlopen(base + "/api/config") as response:
                        public = json.load(response)
                    self.assertEqual(public["ui_version"], health["ui_version"])
                    self.assertEqual(public["config"]["emby_api_key"], "")
                    self.assertTrue(public["secret_set"]["emby_api_key"])
                    self.assertIn("watched_episodes_cleanup_policy", public["config"])
                    with urllib.request.urlopen(base + "/") as response:
                        html = response.read().decode()
                    self.assertIn(f'/app.js?v={health["ui_version"]}', html)
                    self.assertNotIn("__UI_VERSION__", html)
                    self.assertIn('name="jellyfin_base_url"', html)
                    self.assertIn('name="watched_episodes_cleanup_after"', html)
                    for filename in ("app.css", "app.js"):
                        with urllib.request.urlopen(base + "/" + filename) as response:
                            self.assertEqual(response.read(), (WEB_DIRECTORY / "static" / filename).read_bytes())
                    self.assertEqual(config.read_bytes(), original_config)
                finally:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
