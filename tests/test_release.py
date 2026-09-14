import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from fitness.api import create_handler
from fitness.exports import ingest_export
from fitness.pipeline import ROOT,connect


class ReleaseTests(unittest.TestCase):
    def test_export_replay_empty_completion_and_failed_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); envelope=root/'export.json'; heartbeat=root/'heartbeat.json'; database=root/'source.db'
            rows=[json.loads(x) for x in (ROOT/'fixtures/baseline.jsonl').read_text().splitlines()]
            data={'completed_at':'2026-09-08T12:00:00Z','sources':['watch','phone'],'records':rows}
            envelope.write_text(json.dumps(data))
            for _ in range(2): ingest_export(database,envelope,heartbeat,'2026-09-09T00:00:00Z')
            source=connect(str(database))
            self.assertEqual(source.execute('select count(*) from revisions').fetchone()[0],3);source.close()
            before=heartbeat.read_bytes()
            data['records'][0]['revision']=0;envelope.write_text(json.dumps(data))
            with self.assertRaises(ValueError): ingest_export(database,envelope,heartbeat,'2026-09-09T00:00:00Z')
            self.assertEqual(before,heartbeat.read_bytes())
            data.update(records=[],sources=['manual']);envelope.write_text(json.dumps(data))
            ingest_export(database,envelope,heartbeat,'2026-09-09T00:00:00Z')
            self.assertEqual(json.loads(heartbeat.read_text()),{'manual':'2026-09-08T12:00:00Z'})

    def test_http_auth_fail_closed_and_published_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);token='test-only-not-a-real-secret-123456'
            server=ThreadingHTTPServer(('127.0.0.1',0),create_handler(root,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def fetch(path,auth=None):
                return urlopen(Request('http://127.0.0.1:'+str(server.server_port)+path,headers={} if auth is None else {'Authorization':auth}),timeout=5)
            try:
                for auth in (None,'Bearer wrong'):
                    with self.assertRaises(HTTPError) as error: fetch('/summary',auth)
                    self.assertEqual(error.exception.code,401)
                with self.assertRaises(HTTPError) as error: fetch('/summary','Bearer '+token)
                self.assertEqual(error.exception.code,503)
                (root/'latest.json').write_text(json.dumps({'run_dir':str(root)}))
                summary={'as_of':'2026-09-15T00:00:00Z','weeks':[],'days':[],'freshness':{},'synthetic_only':True}
                (root/'summary.json').write_text(json.dumps(summary))
                with fetch('/summary','Bearer '+token) as response:
                    self.assertEqual(json.load(response),summary)
                    self.assertEqual(response.headers['Cache-Control'],'no-store')
                with fetch('/','Bearer '+token) as response: self.assertIn(b'Synthetic demonstration',response.read())
                with self.assertRaises(HTTPError) as error: fetch('/private','Bearer '+token)
                self.assertEqual(error.exception.code,404)
            finally: server.shutdown();server.server_close();thread.join()
