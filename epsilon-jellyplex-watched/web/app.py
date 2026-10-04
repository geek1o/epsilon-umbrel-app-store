#!/usr/bin/env python3
"""Umbrel-authenticated configuration panel for official JellyPlex-Watched."""
from __future__ import annotations

import json
import os
import ssl
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from config import defaults, public_config, read_config, ready, validate, validate_server, write_json
from worker import Worker

APP_DIR = Path(__file__).resolve().parent
DATA = Path(os.environ.get('JPW_DATA_DIR', '/data'))
CONFIG_PATH = DATA / 'config/config.json'
PORT = int(os.environ.get('PORT', '8080'))
UPSTREAM = Path(os.environ.get('JPW_UPSTREAM_DIR', '/app'))
LOCK = threading.RLock()
WORKER = None
STATIC = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/app.css': ('app.css', 'text/css; charset=utf-8'),
          '/logo.svg': ('logo.svg', 'image/svg+xml')}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def test_connection(payload, config):
    server = validate_server(payload, config)
    kind, base, token = server['kind'], server['url'], server['token']
    headers = {'Accept': 'application/json', 'User-Agent': 'Epsilon-JellyPlex-UI/1.0'}
    if kind == 'plex':
        endpoint = base + '/library/sections'
        headers['X-Plex-Token'] = token
    else:
        endpoint = base + '/System/Info'
        headers['X-Emby-Token'] = token
    context = ssl.create_default_context()
    if kind == 'plex' and config['ssl_bypass']:
        context.check_hostname = False
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context),
                                        urllib.request.ProxyHandler({}))
    request = urllib.request.Request(endpoint, headers=headers)
    try:
        with opener.open(request, timeout=10) as response:
            body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise ValueError('Ответ сервера слишком большой.')
        try:
            result = json.loads(body)
            name = result.get('ServerName') if kind != 'plex' else None
            if kind == 'plex':
                if not isinstance(result.get('MediaContainer'), dict):
                    raise ValueError
            elif not result.get('Id') or not result.get('Version'):
                raise ValueError
        except (ValueError, AttributeError):
            if kind != 'plex':
                raise ValueError('Ответ не похож на API Jellyfin/Emby. Проверьте адрес сервера.') from None
            try:
                root = ET.fromstring(body)
                if root.tag != 'MediaContainer':
                    raise ValueError
            except (ET.ParseError, ValueError):
                raise ValueError('Ответ не похож на API Plex. Проверьте адрес сервера.') from None
            name = None
        return {'ok': True, 'message': f'{kind.capitalize()}: подключение и токен проверены.',
                'server_name': name}
    except urllib.error.HTTPError as exc:
        exc.close()
        if exc.code in (401, 403):
            raise ValueError('Сервер отклонил токен. Проверьте токен и права доступа.') from None
        if 300 <= exc.code < 400:
            raise ValueError('Сервер перенаправляет запрос. Укажите конечный адрес API.') from None
        raise ValueError(f'Сервер вернул HTTP {exc.code}. Проверьте адрес API.') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError('Сервер недоступен. Проверьте адрес, порт, сеть и сертификат HTTPS.') from None


def state():
    config = read_config(CONFIG_PATH)
    snapshot = WORKER.snapshot() if WORKER else {}
    return {'config': public_config(config), 'ready': ready(config), 'status': snapshot,
            'version': '8.5.3-ui.1'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'EpsilonJellyPlexUI/1.0'

    def log_message(self, format, *args):
        # Never log request bodies, credentials, or query strings.
        pass

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == '/health':
                healthy = WORKER is not None and WORKER.thread is not None and WORKER.thread.is_alive()
                self.send(200 if healthy else 503, {'ok': healthy})
            elif path == '/api/state':
                with LOCK:
                    self.send(200, state())
            elif path == '/api/logs':
                log = DATA / 'logs/sync.log'
                if log.exists():
                    with log.open('rb') as stream:
                        stream.seek(max(0, log.stat().st_size - 64 * 1024))
                        value = stream.read().decode('utf-8', errors='replace')
                    value = '\n'.join(value.splitlines()[-300:])
                else:
                    value = 'Запусков пока не было.'
                self.send(200, {'text': value})
            elif path in STATIC:
                filename, mime = STATIC[path]
                self.send(200, (APP_DIR / 'static' / filename).read_bytes(), mime)
            else:
                self.send(404, {'error': 'Страница не найдена.'})
        except (OSError, ValueError, KeyError):
            self.send(500, {'error': 'Не удалось прочитать настройки или журнал. Проверьте данные приложения.'})

    def do_POST(self):
        # A custom header and JSON (without CORS) block browser cross-origin writes.
        if self.headers.get('X-JPW-Request') != '1' or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send(403, {'error': 'Запрос отклонён. Откройте панель через Umbrel.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 64 * 1024:
                raise ValueError('Запрос пустой или слишком большой.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Ожидается объект настроек.')
            path = urlsplit(self.path).path
            if path == '/api/config':
                with LOCK:
                    existing = read_config(CONFIG_PATH)
                    config = validate(payload, existing)
                    write_json(CONFIG_PATH, config)
                    WORKER.changed()
                    self.send(200, state())
            elif path == '/api/test':
                with LOCK:
                    existing = read_config(CONFIG_PATH)
                self.send(200, test_connection(payload, existing))
            elif path == '/api/run':
                with LOCK:
                    if not ready(read_config(CONFIG_PATH)):
                        raise ValueError('Добавьте минимум два сервера и включите направление между ними.')
                    WORKER.run_now()
                self.send(202, {'ok': True, 'message': 'Запуск принят.'})
            else:
                self.send(404, {'error': 'Действие не найдено.'})
        except ValueError as exc:
            # All validation errors are static; never echo credentials or upstream errors.
            message = 'Не удалось разобрать JSON.' if isinstance(exc, json.JSONDecodeError) else str(exc)
            self.send(400, {'error': message})
        except (OSError, KeyError):
            self.send(500, {'error': 'Не удалось сохранить настройки. Проверьте данные приложения.'})


def main():
    import signal
    global WORKER
    os.umask(0o077)
    for path in (DATA / 'config', DATA / 'logs'):
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
    if not CONFIG_PATH.exists():
        write_json(CONFIG_PATH, defaults())
    WORKER = Worker(DATA, UPSTREAM)
    WORKER.start()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    server.daemon_threads = True
    def stop(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        WORKER.close()
        server.server_close()


if __name__ == '__main__':
    main()
