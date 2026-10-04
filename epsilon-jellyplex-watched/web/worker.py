"""Run the unmodified upstream entry point, one job at a time."""
from __future__ import annotations

import copy
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from config import environment, read_config, ready, redact, write_json

ERROR_LINE = re.compile(r'\|\s*(?:ERROR|CRITICAL)\s*\|')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


class Worker:
    def __init__(self, data: Path, upstream: Path):
        self.data, self.upstream = data, upstream
        self.config_path = data / 'config/config.json'
        self.status_path = data / 'config/status.json'
        self.log_path = data / 'logs/sync.log'
        self.runtime = Path(os.environ.get('JPW_RUNTIME_DIR', '/tmp/jellyplex-watched'))
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.pending = None
        self.process = None
        self.thread = None
        try:
            import json
            previous = json.loads(self.status_path.read_text())
        except (OSError, ValueError):
            previous = {}
        if not isinstance(previous, dict):
            previous = {}
        self.state = {
            'running': False, 'running_dryrun': None, 'started_at': None,
            'last_finished_at': previous.get('last_finished_at'),
            'last_result': previous.get('last_result'),
            'last_dryrun': previous.get('last_dryrun'), 'next_at': None,
            'config_error': False,
        }

    def start(self):
        self.thread = threading.Thread(target=self.loop, name='jellyplex-scheduler', daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def update(self, **values):
        with self.lock:
            self.state.update(values)
            write_json(self.status_path, self.state)

    def changed(self):
        with self.lock:
            if not self.state['running']:
                self.state['next_at'] = None
        self.wake.set()

    def run_now(self):
        with self.lock:
            if self.state['running'] or self.pending:
                raise ValueError('Синхронизация уже запущена. Дождитесь завершения.')
            config = read_config(self.config_path)
            if not ready(config):
                raise ValueError('Добавьте минимум два сервера и включите направление между ними.')
            # Capture the saved settings at the manual request, avoiding a stale
            # scheduler read when Save and Run arrive close together.
            self.pending = config
        self.wake.set()

    def append_log(self, line):
        # A bounded, already-redacted history, plus one bounded previous file.
        if self.log_path.exists() and self.log_path.stat().st_size > 512 * 1024:
            os.replace(self.log_path, self.log_path.with_suffix('.previous.log'))
        with self.log_path.open('a', encoding='utf-8') as stream:
            os.chmod(self.log_path, 0o600)
            stream.write(line.rstrip('\n') + '\n')

    def run_process(self, config):
        self.update(running=True, running_dryrun=config['dryrun'], started_at=time.time(), next_at=None)
        failed = False
        self.append_log('\n── ' + time.strftime('%Y-%m-%d %H:%M:%S %Z') +
                        (' · проверка без изменений' if config['dryrun'] else ' · синхронизация') + ' ──')
        child_env = {**os.environ, **environment(config, self.runtime),
                     'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'NO_COLOR': '1'}
        try:
            with self.lock:
                if self.stopping.is_set():
                    return
                self.process = subprocess.Popen(
                    [sys.executable, '-u', str(self.upstream / 'main.py')],
                    cwd=self.upstream, env=child_env, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                    errors='replace', start_new_session=True,
                )
                process = self.process
            # Upstream catches exceptions and can exit with code 0 on failure.
            # Its ERROR/CRITICAL records must also make the run fail.
            with process.stdout:
                for line in process.stdout:
                    clean = ANSI.sub('', line)
                    failed = failed or bool(ERROR_LINE.search(clean))
                    self.append_log(redact(clean, config))
            failed = bool(process.wait()) or failed
        except Exception:
            failed = True
            self.append_log('Не удалось выполнить синхронизацию. Проверьте журнал контейнера и настройки серверов.')
        finally:
            if self.process and self.process.poll() is None:
                self.terminate()
            with self.lock:
                self.process = None
            result = 'interrupted' if self.stopping.is_set() else ('error' if failed else 'success')
            self.update(running=False, running_dryrun=None, last_finished_at=time.time(),
                        last_result=result, last_dryrun=config['dryrun'])
            # Raw upstream files are transient; only redacted output is persisted.
            for name in ('upstream.log', 'marked.log'):
                (self.runtime / name).unlink(missing_ok=True)

    def loop(self):
        while not self.stopping.is_set():
            try:
                config = read_config(self.config_path)
                self.update_if_needed(config_error=False)
                with self.lock:
                    manual = self.pending
                    self.pending = None
                    if not config['enabled']:
                        self.state['next_at'] = None
                    elif self.state['next_at'] is None:
                        self.state['next_at'] = time.time()
                    due = config['enabled'] and self.state['next_at'] <= time.time()
                if manual is not None:
                    config = manual
                if ready(config) and (manual is not None or due):
                    self.run_process(config)
                    latest = read_config(self.config_path)
                    self.update(next_at=time.time() + latest['interval'] if latest['enabled'] else None)
            except (OSError, ValueError, KeyError):
                self.update_if_needed(config_error=True)
            self.wake.wait(1)
            self.wake.clear()

    def update_if_needed(self, **values):
        with self.lock:
            if any(self.state.get(k) != v for k, v in values.items()):
                self.update(**values)

    def terminate(self):
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass

    def close(self):
        self.stopping.set()
        self.wake.set()
        self.terminate()
        if self.thread:
            self.thread.join(timeout=15)
