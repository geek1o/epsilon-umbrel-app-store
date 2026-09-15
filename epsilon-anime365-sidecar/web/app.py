#!/usr/bin/env python3
"""Configuration and status UI for the unmodified anime365-sidecar container."""

from __future__ import annotations

import json
import os
import re
import shutil
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
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/config/.env"))
LIBRARY_PATH = Path(os.environ.get("LIBRARY_PATH", "/library"))
PORT = int(os.environ.get("PORT", "8080"))
STARTED_AT = time.time()

FIELD_SPECS = (
    ("anime365_base_url", "SIDECAR_ANIME365_BASE_URL", "https://smotret-anime.app", True, False),
    ("anime365_login", "SIDECAR_ANIME365_LOGIN", "", True, False),
    ("anime365_password", "SIDECAR_ANIME365_PASSWORD", "", True, True),
    (
        "anime_list_database_url",
        "SIDECAR_ANIME_LIST_DATABASE_URL",
        "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json",
        True,
        False,
    ),
    ("anime_list_refresh_idle_interval", "SIDECAR_ANIME_LIST_REFRESH_IDLE_INTERVAL", "24h", True, False),
    ("emby_base_url", "SIDECAR_EMBY_BASE_URL", os.environ.get("DEFAULT_EMBY_BASE_URL", ""), True, False),
    ("emby_public_base_url", "SIDECAR_EMBY_PUBLIC_BASE_URL", os.environ.get("DEFAULT_EMBY_PUBLIC_BASE_URL", ""), False, False),
    ("emby_api_key", "SIDECAR_EMBY_API_KEY", "", True, True),
    ("emby_library_id", "SIDECAR_EMBY_LIBRARY_ID", "", True, False),
    ("emby_user_id", "SIDECAR_EMBY_USER_ID", "", True, False),
    ("translations", "SIDECAR_TRANSLATIONS", "ru_subtitles,ru_dub", True, False),
    ("preferred_translation_authors", "SIDECAR_PREFERRED_TRANSLATION_AUTHORS", "", False, False),
    ("blacklisted_translation_authors", "SIDECAR_BLACKLISTED_TRANSLATION_AUTHORS", "", False, False),
    ("scan_sources", "SIDECAR_SCAN_SOURCES", "list_watching", True, False),
    ("episodes_to_download_ahead", "SIDECAR_EPISODES_TO_DOWNLOAD_AHEAD", "50", True, False),
    ("delete_removed_translations", "SIDECAR_DELETE_REMOVED_TRANSLATIONS", "false", False, False),
    ("download_timeout_image", "SIDECAR_DOWNLOAD_TIMEOUT_IMAGE", "1m", True, False),
    ("download_timeout_video", "SIDECAR_DOWNLOAD_TIMEOUT_VIDEO", "1h", True, False),
    ("scan_idle_interval", "SIDECAR_SCAN_IDLE_INTERVAL", "5m", True, False),
    ("metadata_refresh_idle_interval", "SIDECAR_METADATA_REFRESH_IDLE_INTERVAL", "1h", True, False),
    ("fresh_items_metadata_refresh_idle_interval", "SIDECAR_FRESH_ITEMS_METADATA_REFRESH_IDLE_INTERVAL", "1m", True, False),
    ("shikimori_base_url", "SIDECAR_SHIKIMORI_BASE_URL", "https://shikimori.io", True, False),
    ("telegram_bot_api_credentials", "SIDECAR_TELEGRAM_BOT_API_CREDENTIALS", "", False, True),
    ("log_level", "SIDECAR_LOG_LEVEL", "INFO", True, False),
    ("http_proxy", "HTTP_PROXY", "", False, True),
    ("https_proxy", "HTTPS_PROXY", "", False, True),
    ("no_proxy", "NO_PROXY", "epsilon-emby_server_1,localhost,127.0.0.1", False, False),
)

KEY_TO_SPEC = {spec[0]: spec for spec in FIELD_SPECS}
ENV_TO_SPEC = {spec[1]: spec for spec in FIELD_SPECS}
SECRET_KEYS = {spec[0] for spec in FIELD_SPECS if spec[4]}
REQUIRED_KEYS = {spec[0] for spec in FIELD_SPECS if spec[3]}
DURATION_KEYS = {
    "anime_list_refresh_idle_interval",
    "download_timeout_image",
    "download_timeout_video",
    "scan_idle_interval",
    "metadata_refresh_idle_interval",
    "fresh_items_metadata_refresh_idle_interval",
}
URL_KEYS = {
    "anime365_base_url",
    "anime_list_database_url",
    "emby_base_url",
    "emby_public_base_url",
    "shikimori_base_url",
    "http_proxy",
    "https_proxy",
}
LIST_KEYS = {
    "translations",
    "preferred_translation_authors",
    "blacklisted_translation_authors",
    "scan_sources",
}
FIXED_ENV = {
    "SIDECAR_LIBRARY_DIRECTORY": "/library",
    "SIDECAR_TEMPORARY_DIRECTORY": "/tmp/anime365-sidecar",
}
GO_DURATION_RE = re.compile(r"^(?:\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h))+$")

state_lock = threading.Lock()
restart_required = False


def utc_iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dotenv_value(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith('"'):
        try:
            return str(json.loads(raw))
        except json.JSONDecodeError:
            return raw.strip('"')
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return raw


def read_env_file(path: Path | None = None) -> dict[str, str]:
    path = path or CONFIG_PATH
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            values[key] = parse_dotenv_value(raw)
    return values


def config_from_env(values: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, env_name, default, _, _ in FIELD_SPECS:
        result[key] = values.get(env_name, default)
    return result


def normalize_list(value: Any) -> str:
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    return ",".join(part.strip() for part in items if str(part).strip())


def validate_url(key: str, value: str) -> None:
    if not value:
        return
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{key}: укажите полный адрес с http:// или https://")


def validate_config(payload: dict[str, Any], existing: dict[str, str]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Ожидался JSON-объект с настройками")

    result = config_from_env(existing)
    for key, value in payload.items():
        if key not in KEY_TO_SPEC:
            continue
        if value is None:
            value = ""
        if isinstance(value, bool):
            value = "true" if value else "false"
        value = str(value).strip()
        if key in SECRET_KEYS and not value:
            continue
        result[key] = normalize_list(value) if key in LIST_KEYS else value

    missing = [key for key in sorted(REQUIRED_KEYS) if not result.get(key, "").strip()]
    if missing:
        raise ValueError("Не заполнены обязательные поля: " + ", ".join(missing))

    for key in URL_KEYS:
        validate_url(key, result.get(key, ""))

    for key in DURATION_KEYS:
        value = result.get(key, "")
        if not GO_DURATION_RE.fullmatch(value):
            raise ValueError(f"{key}: неверный интервал, пример: 30s, 5m или 1h30m")

    try:
        episodes = int(result["episodes_to_download_ahead"])
    except ValueError as exc:
        raise ValueError("episodes_to_download_ahead: требуется целое число") from exc
    if episodes < 0 or episodes > 10000:
        raise ValueError("episodes_to_download_ahead: допустимо значение от 0 до 10000")
    result["episodes_to_download_ahead"] = str(episodes)

    log_level = result["log_level"].upper()
    if log_level not in {"DEBUG", "INFO", "WARN", "ERROR"}:
        raise ValueError("log_level: выберите DEBUG, INFO, WARN или ERROR")
    result["log_level"] = log_level

    delete_removed = result.get("delete_removed_translations", "false").lower()
    if delete_removed not in {"true", "false"}:
        raise ValueError("delete_removed_translations: требуется true или false")
    result["delete_removed_translations"] = delete_removed

    telegram = result.get("telegram_bot_api_credentials", "")
    if telegram and urllib.parse.urlsplit(telegram).scheme != "telegram":
        raise ValueError("telegram_bot_api_credentials: адрес должен начинаться с telegram://")

    return result


def write_env_file(config: dict[str, str], existing: dict[str, str], path: Path | None = None) -> None:
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    known_env_names = set(ENV_TO_SPEC) | set(FIXED_ENV)
    lines = [
        "# Managed by the Anime365 Sidecar web configuration panel.",
        "# Manual edits are allowed, but saving in the panel will rewrite known values.",
    ]
    for key, env_name, _, _, _ in FIELD_SPECS:
        value = config.get(key, "")
        lines.append(f"{env_name}={json.dumps(value, ensure_ascii=False)}")
    for env_name, value in FIXED_ENV.items():
        lines.append(f"{env_name}={json.dumps(value)}")
    unknown = {key: value for key, value in existing.items() if key not in known_env_names}
    if unknown:
        lines.append("# Variables not managed by the panel.")
        for key in sorted(unknown):
            lines.append(f"{key}={json.dumps(unknown[key], ensure_ascii=False)}")

    fd, temporary_name = tempfile.mkstemp(prefix=".env.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def public_config() -> dict[str, Any]:
    values = read_env_file()
    config = config_from_env(values)
    secret_set = {key: bool(values.get(KEY_TO_SPEC[key][1], "")) for key in SECRET_KEYS}
    for key in SECRET_KEYS:
        config[key] = ""
    return {
        "config": config,
        "secret_set": secret_set,
        "library_directory": "/library",
        "emby_library_directory": "/downloads/anime365",
    }


def required_status(values: dict[str, str]) -> tuple[bool, list[str]]:
    config = config_from_env(values)
    missing = [key for key in sorted(REQUIRED_KEYS) if not config.get(key, "").strip()]
    return not missing, missing


def library_status(path: Path | None = None) -> dict[str, Any]:
    path = path or LIBRARY_PATH
    manifest_path = path / "manifest.json"
    result: dict[str, Any] = {
        "available": path.is_dir(),
        "manifest_found": manifest_path.is_file(),
        "manifest_updated_at": None,
        "shows": 0,
        "episodes": 0,
        "translations": 0,
        "disk_total": None,
        "disk_free": None,
    }
    if path.is_dir():
        try:
            usage = shutil.disk_usage(path)
            result["disk_total"] = usage.total
            result["disk_free"] = usage.free
        except OSError:
            pass
    if not manifest_path.is_file():
        return result
    try:
        result["manifest_updated_at"] = utc_iso(manifest_path.stat().st_mtime)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        shows = payload.get("shows", {}) if isinstance(payload, dict) else {}
        if not isinstance(shows, dict):
            return result
        result["shows"] = len(shows)
        for show in shows.values():
            episodes = show.get("episodes", {}) if isinstance(show, dict) else {}
            if not isinstance(episodes, dict):
                continue
            result["episodes"] += len(episodes)
            for episode in episodes.values():
                translations = episode.get("translations", {}) if isinstance(episode, dict) else {}
                if isinstance(translations, dict):
                    result["translations"] += len(translations)
    except (OSError, ValueError, TypeError):
        result["manifest_error"] = True
    return result


def status_payload() -> dict[str, Any]:
    values = read_env_file()
    configured, missing = required_status(values)
    with state_lock:
        needs_restart = restart_required
    if not configured:
        state = "configuration_required"
    elif needs_restart:
        state = "restart_required"
    elif (LIBRARY_PATH / "manifest.json").is_file():
        state = "library_detected"
    else:
        state = "configured"
    return {
        "state": state,
        "configured": configured,
        "missing": missing,
        "restart_required": needs_restart,
        "config_updated_at": utc_iso(CONFIG_PATH.stat().st_mtime) if CONFIG_PATH.is_file() else None,
        "ui_uptime_seconds": int(time.time() - STARTED_AT),
        "library": library_status(),
        "note": "Статус процесса sidecar смотрите в Umbrel; upstream не предоставляет health API.",
    }


def merge_test_config(payload: dict[str, Any]) -> dict[str, str]:
    existing = read_env_file()
    config = config_from_env(existing)
    for key, value in payload.items():
        if key not in KEY_TO_SPEC or value is None:
            continue
        value = str(value).strip()
        if key in SECRET_KEYS and not value:
            continue
        config[key] = value
    return config


def request_url(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "Epsilon-Anime365-Sidecar/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, response.read(4096)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4096)


def test_connection(service: str, payload: dict[str, Any]) -> dict[str, Any]:
    config = merge_test_config(payload)
    if service == "anime365":
        validate_url("anime365_base_url", config.get("anime365_base_url", ""))
        code, _ = request_url(config["anime365_base_url"])
        if code >= 500:
            raise ValueError(f"Anime365 отвечает с ошибкой HTTP {code}")
        return {"ok": True, "message": f"Сайт Anime365 доступен (HTTP {code}). Логин проверит sidecar после перезапуска."}

    if service == "emby":
        validate_url("emby_base_url", config.get("emby_base_url", ""))
        base = config["emby_base_url"].rstrip("/")
        api_key = config.get("emby_api_key", "")
        if not api_key:
            raise ValueError("Сначала укажите API key Emby")
        code, body = request_url(base + "/System/Info", {"X-Emby-Token": api_key})
        if code != 200:
            raise ValueError(f"Emby отклонил запрос (HTTP {code}); проверьте адрес и API key")
        try:
            info = json.loads(body)
            version = info.get("Version", "неизвестна")
        except (ValueError, TypeError):
            version = "неизвестна"
        return {"ok": True, "message": f"Соединение и API key работают. Версия Emby: {version}."}

    raise ValueError("Неизвестный тип проверки")


class Handler(BaseHTTPRequestHandler):
    server_version = "Anime365SidecarUI/1.0"

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
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Требуется Content-Type: application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Некорректный Content-Length") from exc
        if length < 1 or length > 65536:
            raise ValueError("Некорректный размер запроса")
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("Некорректный JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Ожидался JSON-объект")
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_static("index.html", "text/html; charset=utf-8")
        elif parsed.path == "/app.css":
            self.send_static("app.css", "text/css; charset=utf-8")
        elif parsed.path == "/app.js":
            self.send_static("app.js", "application/javascript; charset=utf-8")
        elif parsed.path == "/api/config":
            self.send_json(public_config())
        elif parsed.path == "/api/status":
            self.send_json(status_payload())
        elif parsed.path == "/health":
            self.send_json({"status": "ok"})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/config":
                existing = read_env_file()
                config = validate_config(payload, existing)
                write_env_file(config, existing)
                global restart_required
                with state_lock:
                    restart_required = True
                self.send_json(
                    {
                        "ok": True,
                        "message": "Настройки сохранены. Перезапустите Anime365 Sidecar в Umbrel, чтобы применить их.",
                        "restart_required": True,
                    }
                )
                return
            if parsed.path == "/api/test/anime365":
                self.send_json(test_connection("anime365", payload))
                return
            if parsed.path == "/api/test/emby":
                self.send_json(test_connection("emby", payload))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, urllib.error.URLError) as exc:
            self.send_json({"ok": False, "error": f"Ошибка соединения или записи: {exc}"}, HTTPStatus.BAD_GATEWAY)
        except Exception:
            self.send_json({"ok": False, "error": "Внутренняя ошибка панели. Проверьте журнал контейнера UI."}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Anime365 Sidecar UI listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
