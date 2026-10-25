import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
from urllib.request import build_opener, ProxyHandler, Request
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lobby', ROOT / 'server.py')
lobby = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lobby)

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No production storage/network; ephemeral HTTP server plus in-memory fixture.
        cls.original_load, cls.original_save = lobby.load, lobby.save
        cls.items = []
        lobby.load = lambda: cls.items
        def save(items): cls.items = items
        lobby.save = save
        cls.server = lobby.ThreadingHTTPServer(('127.0.0.1', 0), lobby.AppHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_address[1])
        cls.client = build_opener(ProxyHandler({}))
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        lobby.load, lobby.save = cls.original_load, cls.original_save
    def request(self, path, payload=None):
        req = Request(self.url + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Content-Type':'application/json'})
        try:
            with self.client.open(req, timeout=5) as r: return r.status, r.read()
        except HTTPError as e:
            with e: return e.code, e.read()
    def test_static_assets(self):
        for path in ['/', '/app.js', '/manifest.webmanifest', '/service-worker.js', '/icons/icon-192.png']:
            with self.subTest(path=path): self.assertEqual(self.request(path)[0], 200)
    def test_anytime_roundtrip(self):
        data = {'people':[{'name':'Player Alpha','status':'yes','time':'any'}]}
        self.assertEqual(self.request('/api/people', data)[0], 200)
        self.assertEqual(json.loads(self.request('/api/people')[1]), data)
    def test_invalid_roster(self):
        self.assertEqual(self.request('/api/people', {'people':[{'name':'','status':'yes','time':'any'}]})[0], 400)
    def test_notification_disabled(self):
        topic = lobby.TOPIC; lobby.TOPIC = ''
        try: self.assertEqual(self.request('/api/note', {'message':'Local synthetic check'})[0], 502)
        finally: lobby.TOPIC = topic
    def test_bad_note(self):
        self.assertEqual(self.request('/api/note', {'message':''})[0], 400)
    def test_unknown_path(self):
        self.assertEqual(self.request('/server.py')[0], 404)
        self.assertEqual(self.request('/../server.py')[0], 404)
    def test_synthetic_fixture(self):
        roster=json.loads((ROOT/'docs/demo-roster.json').read_text())
        self.assertTrue(all(x['name'].startswith('Player ') for x in roster))

if __name__ == '__main__': unittest.main()
