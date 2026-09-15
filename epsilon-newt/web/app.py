#!/usr/bin/env python3
"""Small configuration and tunnel-status panel for the official Newt image."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/config/config.json"))
HEALTH_PATH = Path(os.environ.get("HEALTH_PATH", "/status/health"))
PORT = int(os.environ.get("PORT", "8080"))
STARTED_AT = time.time()
LOCK = threading.Lock()
restart_required = False

DEFAULTS: dict[str, Any] = {
    "endpoint": "https://app.pangolin.net",
    "id": "",
    "secret": "",
    "name": "",
    "dns": "9.9.9.9",
    "logLevel": "INFO",
    "pingInterval": "15s",
    "pingTimeout": "7s",
    "udpProxyIdleTimeout": "90s",
    "disableClients": False,
    "disableSsh": False,
    "enforceHcCert": False,
}
SECRET_FIELDS = {"secret"}
BOOL_FIELDS = {"disableClients", "disableSsh", "enforceHcCert"}
DURATION_FIELDS = {"pingInterval", "pingTimeout", "udpProxyIdleTimeout"}


def iso_time(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def read_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_PATH
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def public_config() -> dict[str, Any]:
    saved = read_config()
    config = {**DEFAULTS, **saved}
    secret_set = bool(str(saved.get("secret", "")).strip())
    config["secret"] = ""
    return {"config": config, "secret_set": secret_set}


def validate_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter the full Pangolin URL, including http:// or https://")
    if parsed.query or parsed.fragment:
        raise ValueError("The Pangolin URL must not contain a query string or fragment")
    return value.rstrip("/")


def validate_duration(name: str, value: str) -> str:
    import re

    if not re.fullmatch(r"(?:\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h))+", value):
        raise ValueError(f"{name}: invalid duration; use a value such as 15s or 1m30s")
    return value


def validate_payload(payload: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    config = {**DEFAULTS, **existing}
    for key in DEFAULTS:
        if key not in payload:
            continue
        value = payload[key]
        if key in BOOL_FIELDS:
            config[key] = bool(value)
            continue
        value = str(value or "").strip()
        if key in SECRET_FIELDS and not value:
            continue
        config[key] = value

    config["endpoint"] = validate_url(str(config["endpoint"]))
    for key in ("id", "secret"):
        if not str(config.get(key, "")).strip():
            raise ValueError(f"Required field is missing: {key}")
    if str(config["logLevel"]).upper() not in {"DEBUG", "INFO", "WARN", "ERROR"}:
        raise ValueError("Log level must be DEBUG, INFO, WARN, or ERROR")
    config["logLevel"] = str(config["logLevel"]).upper()
    for key in DURATION_FIELDS:
        config[key] = validate_duration(key, str(config[key]))
    return config


def write_config(config: dict[str, Any], existing: dict[str, Any], path: Path | None = None) -> None:
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**existing, **config}
    fd, temporary_name = tempfile.mkstemp(prefix="config.", suffix=".json", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def state_payload() -> dict[str, Any]:
    config = read_config()
    configured = all(str(config.get(key, "")).strip() for key in ("endpoint", "id", "secret"))
    connected = HEALTH_PATH.is_file() and HEALTH_PATH.read_text(encoding="utf-8").strip() == "ok"
    with LOCK:
        needs_restart = restart_required
    if not configured:
        state = "configuration_required"
    elif needs_restart:
        state = "restart_required"
    elif connected:
        state = "connected"
    else:
        state = "connecting"
    return {
        "state": state,
        "configured": configured,
        "connected": connected,
        "restart_required": needs_restart,
        "config_updated_at": iso_time(CONFIG_PATH.stat().st_mtime) if CONFIG_PATH.is_file() else None,
        "tunnel_updated_at": iso_time(HEALTH_PATH.stat().st_mtime) if connected else None,
        "ui_uptime_seconds": int(time.time() - STARTED_AT),
    }


def test_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = validate_url(str(payload.get("endpoint", DEFAULTS["endpoint"])))
    request = urllib.request.Request(endpoint, headers={"User-Agent": "Epsilon-Newt-UI/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            code = response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    if code >= 500:
        raise ValueError(f"Pangolin returned HTTP {code}")
    return {"ok": True, "message": f"Pangolin is reachable (HTTP {code}). Newt will verify the ID and secret after restart."}


class Handler(BaseHTTPRequestHandler):
    server_version = "EpsilonNewtUI/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, filename: str, content_type: str) -> None:
        path = STATIC_DIR / filename
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 32768:
            raise ValueError("Invalid request size")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        return payload

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            self.send_static("index.html", "text/html; charset=utf-8")
        elif path == "/app.css":
            self.send_static("app.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self.send_static("app.js", "application/javascript; charset=utf-8")
        elif path == "/api/config":
            self.send_json(public_config())
        elif path == "/api/state":
            self.send_json(state_payload())
        elif path == "/health":
            self.send_json({"status": "ok"})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/config":
                existing = read_config()
                config = validate_payload(payload, existing)
                write_config(config, existing)
                global restart_required
                with LOCK:
                    restart_required = True
                self.send_json({"ok": True, "message": "Settings saved. Restart Newt from Umbrel to apply them.", "restart_required": True})
                return
            if path == "/api/test":
                self.send_json(test_endpoint(payload))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, urllib.error.URLError) as exc:
            self.send_json({"ok": False, "error": f"Connection or write error: {exc}"}, HTTPStatus.BAD_GATEWAY)
        except Exception:
            self.send_json({"ok": False, "error": "Internal panel error. Check the UI container logs."}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Newt UI listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
