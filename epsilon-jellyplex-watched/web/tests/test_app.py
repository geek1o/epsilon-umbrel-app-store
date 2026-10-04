"""Regression checks for config, secrets, API boundaries, and job lifecycle."""
import copy
import importlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

WEB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB))
config = importlib.import_module('config')
app = importlib.import_module('app')
from worker import Worker


def settings():
    value = config.defaults()
    value['servers'] = [
        {'id': 'one', 'kind': 'plex', 'name': 'Plex', 'url': 'http://plex:32400', 'token': 'secret-plex'},
        {'id': 'two', 'kind': 'emby', 'name': 'Emby', 'url': 'http://emby:8096/emby', 'token': 'secret-emby'},
    ]
    return value


def wait_for(predicate, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('Condition not reached before timeout')


class ConfigTests(unittest.TestCase):
    def test_first_run_safe_and_defaults_independent(self):
        a = config.defaults(); b = config.defaults()
        self.assertFalse(a['enabled']); self.assertTrue(a['dryrun'])
        a['directions']['plex_to_emby'] = False
        self.assertTrue(b['directions']['plex_to_emby'])
        self.assertFalse(config.ready(a))

    def test_secret_redaction_preservation_replacement_and_removal(self):
        saved = settings(); public = config.public_config(saved)
        self.assertNotIn('secret-', json.dumps(public))
        self.assertTrue(public['servers'][0]['token_set'])
        self.assertEqual(config.validate(public, saved)['servers'][0]['token'], 'secret-plex')
        public['servers'][0]['token'] = 'replacement'
        self.assertEqual(config.validate(public, saved)['servers'][0]['token'], 'replacement')
        public['servers'] = public['servers'][1:]
        self.assertNotIn('secret-plex', json.dumps(config.validate(public, saved)))

    def test_secret_not_retained_when_type_changes(self):
        public = config.public_config(settings()); public['servers'][0]['kind'] = 'jellyfin'
        with self.assertRaises(ValueError): config.validate(public, settings())

    def test_reject_invalid_settings(self):
        for key, value in [('enabled', 'false'), ('interval', 0), ('max_threads', True),
                           ('request_timeout', 1801), ('debug_level', 'BOGUS')]:
            payload = settings(); payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): config.validate(payload, {})
        for url in ['file:///etc/passwd', 'http://user:password@host', 'http://host/?token=x',
                    'http://host:99999', 'http://host,another', 'http://host/#x', 'http://host\n']:
            with self.subTest(url=url), self.assertRaises(ValueError): config.validate_url(url)

    def test_duplicate_servers_and_no_matching_methods_rejected(self):
        payload = settings(); payload['servers'][1] = copy.deepcopy(payload['servers'][0])
        with self.assertRaises(ValueError): config.validate(payload, {})
        payload = settings(); payload['generate_guids'] = payload['generate_locations'] = False
        with self.assertRaises(ValueError): config.validate(payload, {})

    def test_schedule_requires_active_direction_and_two_servers(self):
        payload = settings(); payload['enabled'] = True
        payload['servers'] = payload['servers'][:1]
        with self.assertRaises(ValueError): config.validate(payload, {})
        payload = settings(); payload['enabled'] = True
        payload['directions'] = dict.fromkeys(config.DIRECTIONS, False)
        with self.assertRaises(ValueError): config.validate(payload, {})
        payload['directions']['plex_to_emby'] = True
        self.assertTrue(config.ready(config.validate(payload, {})))

    def test_mapping_ambiguity_and_filters(self):
        for mapping in [{'a':'b', 'c':'b'}, {'a':'b', 'b':'c'}, {'Alice':'alice'}, {'a':0}]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError): config.mapping(mapping, 'users')
        payload = settings(); payload['whitelist_users'] = ['alice', 'bob', 'alice']
        self.assertEqual(config.validate(payload, {})['whitelist_users'], ['alice', 'bob'])
        payload['whitelist_users'] = ['alice,bob']
        with self.assertRaises(ValueError): config.validate(payload, {})

    def test_environment_server_order_and_all_directions(self):
        payload = settings(); payload['servers'].append({'id':'three', 'kind':'plex', 'name':'Other', 'url':'http://other:32400','token':'other-token'})
        payload['directions']['emby_to_plex'] = False
        payload['user_mapping'] = {'alice':'Алиса'}
        payload['whitelist_users'] = ['alice','bob']
        env = config.environment(payload, Path('/tmp/runtime'))
        self.assertEqual(env['PLEX_BASEURL'], 'http://plex:32400,http://other:32400')
        self.assertEqual(env['PLEX_TOKEN'], 'secret-plex,other-token')
        self.assertEqual(env['JELLYFIN_BASEURL'], '')
        self.assertEqual(env['RUN_ONLY_ONCE'], 'True'); self.assertEqual(env['ENV_FILE'], '/dev/null')
        self.assertEqual(env['SYNC_FROM_EMBY_TO_PLEX'], 'False')
        self.assertEqual(env['WHITELIST_USERS'], 'alice,bob')
        self.assertEqual(json.loads(env['USER_MAPPING']), {'alice':'Алиса'})
        self.assertEqual(env['PLEX_USERNAME'], '')
        self.assertEqual(len([k for k in env if k.startswith('SYNC_FROM_')]), 9)

    def test_atomic_write_permissions_and_corrupt_file_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config/config.json'
            config.write_json(path, settings())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(config.read_config(path), settings())
            path.write_text('{bad JSON')
            with self.assertRaises(ValueError): config.read_config(path)
            self.assertEqual(path.read_text(), '{bad JSON')
            path.write_text(json.dumps({'servers': 'invalid'}))
            with self.assertRaises(ValueError): config.read_config(path)

    def test_log_redaction(self):
        value = config.redact('secret-plex X-Plex-Token=secret-plex&next=1 api_key=unknown', settings())
        self.assertNotIn('secret-plex', value); self.assertNotIn('unknown', value)
        self.assertIn('next=1', value)


class MediaAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        token = self.headers.get('X-Emby-Token') or self.headers.get('X-Plex-Token')
        if token != 'valid-token':
            self.send_response(401); self.end_headers(); return
        if self.path.startswith('/redirect'):
            self.send_response(302); self.send_header('Location', '/System/Info'); self.end_headers(); return
        if self.path.startswith('/html'):
            body = b'<html>login</html>'
        elif self.path.endswith('/library/sections'):
            body = b'<MediaContainer size="0" />'
        else:
            body = json.dumps({'Id': 'server', 'ServerName': 'Test', 'Version': '4.10'}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = ThreadingHTTPServer(('127.0.0.1', 0), MediaAPI)
        cls.mock_thread = threading.Thread(target=cls.mock.serve_forever, daemon=True); cls.mock_thread.start()
        cls.mock_url = f'http://127.0.0.1:{cls.mock.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.mock.shutdown(); cls.mock.server_close(); cls.mock_thread.join()

    def test_authenticated_checks_and_redirect_rejection(self):
        for kind in config.KINDS:
            server = {'id': 'test', 'name': 'Test', 'kind': kind, 'url': self.mock_url, 'token': 'valid-token'}
            self.assertTrue(app.test_connection(server, config.defaults())['ok'])
            server['token'] = 'bad-secret'
            with self.assertRaises(ValueError) as exc: app.test_connection(server, config.defaults())
            self.assertNotIn('bad-secret', str(exc.exception))
            server['token'] = 'valid-token'; server['url'] = self.mock_url + '/redirect'
            with self.assertRaises(ValueError): app.test_connection(server, config.defaults())
            server['url'] = self.mock_url + '/html'
            with self.assertRaises(ValueError): app.test_connection(server, config.defaults())

    def test_check_with_saved_token(self):
        value = config.defaults(); value['servers'] = [{'id':'test','name':'Test','kind':'emby','url':self.mock_url,'token':'valid-token'}]
        public = config.public_config(value)['servers'][0]
        self.assertTrue(app.test_connection(public, value)['ok'])

    def test_http_write_boundary_and_no_secret_response(self):
        class FakeWorker:
            thread = None
            def snapshot(self): return {'running':False}
            def changed(self): pass
            def run_now(self): pass
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory); path = data / 'config/config.json'; config.write_json(path, settings())
            with patch.object(app, 'DATA', data), patch.object(app, 'CONFIG_PATH', path), patch.object(app, 'WORKER', FakeWorker()):
                server = ThreadingHTTPServer(('127.0.0.1',0), app.Handler)
                thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    body = urllib.request.urlopen(base + '/api/state').read().decode()
                    self.assertNotIn('secret-plex', body)
                    payload = json.dumps(config.public_config(settings())).encode()
                    request = urllib.request.Request(base+'/api/config',data=payload,headers={'Content-Type':'application/json'})
                    with self.assertRaises(urllib.error.HTTPError) as exc: urllib.request.urlopen(request)
                    self.assertEqual(exc.exception.code,403)
                    request.add_header('X-JPW-Request','1')
                    body = urllib.request.urlopen(request).read().decode()
                    self.assertNotIn('secret-plex',body)
                    self.assertEqual(config.read_config(path)['servers'][0]['token'],'secret-plex')
                finally:
                    server.shutdown(); server.server_close(); thread.join()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.root = Path(self.directory.name)
        self.data = self.root/'data'; self.upstream = self.root/'upstream'; self.upstream.mkdir()
        self.runtime_patch = patch.dict(os.environ, {'JPW_RUNTIME_DIR':str(self.root/'runtime')}); self.runtime_patch.start()
        config.write_json(self.data/'config/config.json',settings())
        self.worker = Worker(self.data,self.upstream)
    def tearDown(self):
        self.worker.close(); self.runtime_patch.stop(); self.directory.cleanup()

    def test_paused_manual_run_and_redacted_persisted_output(self):
        self.upstream.joinpath('main.py').write_text('import os\nprint(os.environ["PLEX_TOKEN"])\nprint("DRY="+os.environ["DRYRUN"])\n')
        self.worker.start(); time.sleep(.08)
        self.assertIsNone(self.worker.snapshot()['last_finished_at'])
        self.worker.run_now(); wait_for(lambda:self.worker.snapshot()['last_finished_at'])
        self.assertEqual(self.worker.snapshot()['last_result'],'success')
        log=self.worker.log_path.read_text(); self.assertNotIn('secret-plex',log); self.assertIn('DRY=True',log)
        self.assertIsNone(self.worker.snapshot()['next_at'])

    def test_manual_request_captures_saved_settings(self):
        self.upstream.joinpath('main.py').write_text('import os\nprint("DRY="+os.environ["DRYRUN"])\n')
        self.worker.run_now()
        value=settings();value['dryrun']=False;config.write_json(self.worker.config_path,value)
        self.worker.start();wait_for(lambda:self.worker.snapshot()['last_finished_at'])
        self.assertTrue(self.worker.snapshot()['last_dryrun'])

    def test_upstream_zero_exit_with_error_record_is_failure(self):
        self.upstream.joinpath('main.py').write_text('print("2026 | ERROR    | failed")\n')
        self.worker.start(); self.worker.run_now(); wait_for(lambda:self.worker.snapshot()['last_finished_at'])
        self.assertEqual(self.worker.snapshot()['last_result'],'error')

    def test_no_overlapping_runs_and_apply_changes_next_run(self):
        self.upstream.joinpath('main.py').write_text('import os,time\nprint("DRY="+os.environ["DRYRUN"],flush=True)\ntime.sleep(.3)\n')
        self.worker.start(); self.worker.run_now(); wait_for(lambda:self.worker.snapshot()['running'])
        with self.assertRaises(ValueError): self.worker.run_now()
        value=settings(); value['dryrun']=False; config.write_json(self.worker.config_path,value); self.worker.changed()
        wait_for(lambda:self.worker.snapshot()['last_finished_at'])
        self.assertTrue(self.worker.snapshot()['last_dryrun'])
        previous=self.worker.snapshot()['last_finished_at']; self.worker.run_now()
        wait_for(lambda:self.worker.snapshot()['last_finished_at']!=previous)
        self.assertFalse(self.worker.snapshot()['last_dryrun'])

    def test_scheduler_pause_and_shutdown_child(self):
        self.upstream.joinpath('main.py').write_text('import time\nprint("started",flush=True)\ntime.sleep(30)\n')
        value=settings();value['enabled']=True;config.write_json(self.worker.config_path,value)
        self.worker.start();wait_for(lambda:self.worker.snapshot()['running'])
        value['enabled']=False;config.write_json(self.worker.config_path,value);self.worker.changed()
        self.worker.close()
        self.assertFalse(self.worker.thread.is_alive());self.assertIsNone(self.worker.process)
        self.assertEqual(self.worker.snapshot()['last_result'],'interrupted')


if __name__ == '__main__': unittest.main()
