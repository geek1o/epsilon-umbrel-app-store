"""Validated UI settings translated to JellyPlex-Watched 8.5.3 variables."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit, quote

KINDS = ('plex', 'jellyfin', 'emby')
DIRECTIONS = tuple(f'{source}_to_{target}' for source in KINDS for target in KINDS)
FILTERS = ('whitelist_users', 'blacklist_users', 'whitelist_library', 'blacklist_library',
           'whitelist_library_type', 'blacklist_library_type')
DEFAULTS = {
    'enabled': False, 'dryrun': True, 'interval': 3600, 'request_timeout': 300,
    'max_threads': 1, 'generate_guids': True, 'generate_locations': True,
    'ssl_bypass': False, 'debug_level': 'INFO', 'servers': [],
    'directions': {key: True for key in DIRECTIONS},
    'user_mapping': {}, 'library_mapping': {}, **{key: [] for key in FILTERS},
}


def defaults():
    return copy.deepcopy(DEFAULTS)


def read_config(path: Path):
    if not path.exists():
        return defaults()
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Файл настроек повреждён. Восстановите его из резервной копии.')
    return validate({**defaults(), **value}, {})


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def text(value, label, limit=500):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label}: недопустимое значение.')
    return value.strip()


def validate_url(value):
    value = text(value, 'Адрес сервера', 1000).rstrip('/')
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError('Адрес сервера: проверьте имя узла и порт.') from None
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
        parsed.username is not None or parsed.password is not None or parsed.query or
        parsed.fragment or ',' in value or '\\' in value or any(c.isspace() for c in value)):
        raise ValueError('Укажите HTTP(S)-адрес без логина, пароля, параметров и запятых.')
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Порт сервера должен быть от 1 до 65535.')
    return value


def boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f'{label}: ожидается переключатель.')
    return value


def integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label}: укажите целое число от {low} до {high}.')
    return value


def mapping(value, label):
    if not isinstance(value, dict) or len(value) > 100:
        raise ValueError(f'{label}: нужен JSON-объект из пар имён.')
    output = {}
    for key, target in value.items():
        key = text(key, label, 200)
        target = text(target, label, 200)
        if not key or not target:
            raise ValueError(f'{label}: имена не могут быть пустыми.')
        if key.casefold() == target.casefold():
            raise ValueError(f'{label}: одинаковые имена сопоставлять не нужно.')
        output[key] = target
    names = [x.casefold() for pair in output.items() for x in pair]
    if len(names) != len(set(names)):
        raise ValueError(f'{label}: каждое имя должно участвовать только в одной паре.')
    return output


def validate_server(payload, existing):
    if not isinstance(payload, dict):
        raise ValueError('Проверьте настройки сервера.')
    server_id = text(payload.get('id', ''), 'ID сервера', 64) or uuid.uuid4().hex
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', server_id):
        raise ValueError('Некорректный ID сервера.')
    kind = payload.get('kind')
    if kind not in KINDS:
        raise ValueError('Выберите Plex, Jellyfin или Emby.')
    old = next((s for s in existing.get('servers', []) if s['id'] == server_id and s['kind'] == kind), {})
    token = text(payload.get('token', ''), 'Токен', 2000) or old.get('token', '')
    if not token or ',' in token or any(c.isspace() for c in token):
        raise ValueError('Укажите токен сервера. Запятые и пробелы в токене недопустимы.')
    return {'id': server_id, 'kind': kind,
            'name': text(payload.get('name', ''), 'Название', 100) or kind.capitalize(),
            'url': validate_url(payload.get('url', '')), 'token': token}


def ready(config):
    servers = config['servers']
    if len(servers) < 2:
        return False
    return any(config['directions'][f'{a["kind"]}_to_{b["kind"]}']
               for a in servers for b in servers if a['id'] != b['id'])


def validate(payload, existing):
    if not isinstance(payload, dict):
        raise ValueError('Ожидается объект настроек.')
    output = defaults()
    for key in ('enabled', 'dryrun', 'generate_guids', 'generate_locations', 'ssl_bypass'):
        output[key] = boolean(payload.get(key, existing.get(key, DEFAULTS[key])), key)
    for key, label, low, high in (('interval', 'Интервал', 60, 604800),
                                 ('request_timeout', 'Тайм-аут', 5, 1800),
                                 ('max_threads', 'Число потоков', 1, 16)):
        output[key] = integer(payload.get(key, existing.get(key, DEFAULTS[key])), label, low, high)
    output['debug_level'] = payload.get('debug_level', existing.get('debug_level', 'INFO'))
    if output['debug_level'] not in ('INFO', 'DEBUG', 'TRACE'):
        raise ValueError('Выберите уровень журнала INFO, DEBUG или TRACE.')
    if not output['generate_guids'] and not output['generate_locations']:
        raise ValueError('Включите сопоставление по ID провайдеров или по именам файлов.')
    servers = payload.get('servers', existing.get('servers', []))
    if not isinstance(servers, list) or len(servers) > 20:
        raise ValueError('Можно добавить до 20 серверов.')
    output['servers'] = [validate_server(s, existing) for s in servers]
    ids = [s['id'] for s in output['servers']]
    urls = [(s['kind'], s['url'].casefold()) for s in output['servers']]
    if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
        raise ValueError('Один сервер нельзя добавить дважды.')
    directions = payload.get('directions', existing.get('directions', DEFAULTS['directions']))
    if not isinstance(directions, dict):
        raise ValueError('Проверьте направления синхронизации.')
    output['directions'] = {key: boolean(directions.get(key, True), key) for key in DIRECTIONS}
    for key in ('user_mapping', 'library_mapping'):
        output[key] = mapping(payload.get(key, existing.get(key, {})), key)
    for key in FILTERS:
        values = payload.get(key, existing.get(key, []))
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError(f'{key}: ожидается список имён.')
        output[key] = []
        for value in values:
            value = text(value, key, 200)
            if not value or ',' in value:
                raise ValueError(f'{key}: пустые имена и запятые недопустимы.')
            if value not in output[key]:
                output[key].append(value)
    if output['enabled'] and not ready(output):
        raise ValueError('Для расписания добавьте минимум два сервера и включите направление между ними.')
    return output


def public_config(config):
    value = copy.deepcopy(config)
    for server in value['servers']:
        server['token_set'] = bool(server['token'])
        server['token'] = ''
    return value


def environment(config, runtime_dir: Path):
    """The v8.5.3 YAML settings on upstream main do not apply to this release."""
    values = {
        'ENV_FILE': '/dev/null', 'RUN_ONLY_ONCE': 'True',
        'LOG_FILE': str(runtime_dir / 'upstream.log'),
        'MARK_FILE': str(runtime_dir / 'marked.log'),
        'DEBUG_LEVEL': config['debug_level'], 'SLEEP_DURATION': str(config['interval']),
        'REQUEST_TIMEOUT': str(config['request_timeout']), 'MAX_THREADS': str(config['max_threads']),
    }
    for key in ('dryrun', 'generate_guids', 'generate_locations', 'ssl_bypass'):
        values[key.upper()] = str(config[key])
    for kind in KINDS:
        servers = [s for s in config['servers'] if s['kind'] == kind]
        values[kind.upper() + '_BASEURL'] = ','.join(s['url'] for s in servers)
        values[kind.upper() + '_TOKEN'] = ','.join(s['token'] for s in servers)
    # Never inherit the image's alternative Plex account authentication.
    for key in ('PLEX_USERNAME', 'PLEX_PASSWORD', 'PLEX_SERVERNAME'):
        values[key] = ''
    for key in DIRECTIONS:
        values['SYNC_FROM_' + key.upper()] = str(config['directions'][key])
    for key in ('user_mapping', 'library_mapping'):
        values[key.upper()] = json.dumps(config[key], ensure_ascii=False)
    for key in FILTERS:
        values[key.upper()] = ','.join(config[key])
    return values


def redact(value: str, config):
    for server in config.get('servers', []):
        token = server.get('token', '')
        if token:
            for secret in sorted({token, quote(token, safe='')}, key=len, reverse=True):
                value = value.replace(secret, '[скрыто]')
    return re.sub(r'(?i)((?:x-plex-token|x-emby-token|api_key|token)[=:]\s*)[^\s&\'\"<>]+',
                  r'\1[скрыто]', value)
