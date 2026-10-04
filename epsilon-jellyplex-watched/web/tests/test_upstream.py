"""Optional real 8.5.3 integration; set JPW_TEST_UPSTREAM to its source directory."""
import copy
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from worker import Worker

UPSTREAM = Path(os.environ.get('JPW_TEST_UPSTREAM', '/nonexistent'))


class FakeMediaServer:
    def __init__(self, watched, name):
        self.watched = watched
        self.position = 0
        self.name = name
        self.posts = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def send(self, value):
                body = json.dumps(value).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_GET(self):
                if (self.headers.get('X-Emby-Token') != 'test-token' and
                    'Token="test-token"' not in self.headers.get('Authorization','')):
                    self.send_response(401);self.end_headers();return
                url = urlsplit(self.path); query = parse_qs(url.query)
                if url.path.startswith('/System/Info'):
                    self.send({'Id':owner.name,'ServerName':owner.name,'Version':'10.11.0' if owner.name=='Source' else '4.10.0'})
                elif url.path == '/Users': self.send([{'Id':'u','Name':'alice'}])
                elif url.path.endswith('/Views'):
                    self.send({'Items':[{'Id':'lib','Name':'Movies','CollectionType':'movies'}]})
                elif url.path == '/Users/u/Items':
                    movie={'Id':'film','Name':'Demo Film','Type':'Movie','Path':'/movies/demo.mkv',
                           'ProviderIds':{'Imdb':'tt0000001'},
                           'UserData':{'Played':owner.watched,'PlaybackPositionTicks':owner.position,
                                       'LastPlayedDate':'2026-05-01T12:00:00Z'}}
                    filters=query.get('Filters',[])
                    show = (not filters or ('IsPlayed' in filters and owner.watched) or
                            ('IsResumable' in filters and owner.position>0 and not owner.watched))
                    self.send({'Items':[movie] if show else []})
                else:
                    self.send_response(404);self.end_headers()
            def do_POST(self):
                length=int(self.headers.get('Content-Length',0));body=json.loads(self.rfile.read(length))
                owner.posts.append((self.path,body));owner.watched=body['Played'];owner.position=body['PlaybackPositionTicks']
                self.send_response(204);self.end_headers()
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()


@unittest.skipUnless((UPSTREAM/'main.py').exists(), 'Set JPW_TEST_UPSTREAM for real upstream integration')
class UpstreamTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
        self.source=FakeMediaServer(True,'Source');self.target=FakeMediaServer(False,'Target')
        self.runtime_patch=patch.dict(os.environ,{'JPW_RUNTIME_DIR':str(self.root/'runtime')});self.runtime_patch.start()
        self.worker=Worker(self.root/'data',UPSTREAM)
        self.config=config.defaults()
        self.config['directions']=dict.fromkeys(config.DIRECTIONS,False)
        self.config['directions']['jellyfin_to_emby']=True
        self.config['servers']=[{'id':'source','kind':'jellyfin','name':'Source','url':self.source.url,'token':'test-token'},
                                {'id':'target','kind':'emby','name':'Target','url':self.target.url,'token':'test-token'}]
    def tearDown(self):
        self.worker.close();self.source.close();self.target.close();self.runtime_patch.stop();self.directory.cleanup()
    def run_sync(self, dryrun):
        self.config['dryrun']=dryrun
        self.worker.run_process(copy.deepcopy(self.config))
        self.assertEqual(self.worker.snapshot()['last_result'],'success',self.worker.log_path.read_text())
    def test_real_dryrun_then_watched_write(self):
        self.run_sync(True);self.assertEqual(self.target.posts,[])
        self.assertIn('[DRYRUN]',self.worker.log_path.read_text());self.assertFalse(self.target.watched)
        self.run_sync(False);self.assertTrue(self.target.watched);self.assertEqual(len(self.target.posts),1)
        self.assertEqual(self.source.posts,[])
        self.assertEqual(self.target.posts[0][1]['PlaybackPositionTicks'],0)
    def test_disabled_direction_prevents_write(self):
        self.config['directions']['jellyfin_to_emby']=False
        self.config['directions']['emby_to_jellyfin']=True
        self.run_sync(False);self.assertEqual(self.target.posts,[]);self.assertFalse(self.target.watched)
    def test_real_partial_progress_write(self):
        self.source.watched=False;self.source.position=1200000000
        self.run_sync(True);self.assertEqual(self.target.posts,[])
        self.run_sync(False);self.assertFalse(self.target.watched)
        self.assertEqual(self.target.position,1200000000)
        self.assertEqual(len(self.target.posts),1)
    def test_same_type_sync(self):
        self.config['servers'][0]['kind']='emby'
        self.config['directions']=dict.fromkeys(config.DIRECTIONS,False)
        self.config['directions']['emby_to_emby']=True
        self.run_sync(False);self.assertTrue(self.target.watched)


if __name__=='__main__':unittest.main()
