"""Local authenticated read-only summary service; cloud entrypoint uses AWS IAM."""
import hmac
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from fitness.dashboard import render


def create_handler(output, token):
    if len(token)<24: raise ValueError('API token must contain at least 24 characters')
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token):
                self.send_response(401); self.end_headers(); return
            if self.path not in ('/','/summary','/health'):
                self.send_response(404); self.end_headers(); return
            try:
                pointer=json.loads((Path(output)/'latest.json').read_text())
                summary=json.loads((Path(pointer['run_dir'])/'summary.json').read_text())
            except (FileNotFoundError,KeyError,json.JSONDecodeError):
                self.send_response(503); self.end_headers(); return
            data=render(summary).encode() if self.path=='/' else json.dumps(summary if self.path=='/summary' else {'status':'ready','as_of':summary['as_of']}).encode()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8' if self.path=='/' else 'application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def log_message(self,*args): pass
    return Handler

if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',8085),create_handler(os.environ['FITNESS_PUBLISHED'],os.environ['FITNESS_API_TOKEN'])).serve_forever()
