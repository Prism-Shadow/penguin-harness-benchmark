"""Loopback-only wire fixture; SDK transport and retry logic remain real."""

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit


@contextmanager
def wire_fixture():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def do_DELETE(self):
            self.respond()

        def respond(self):
            path = urlsplit(self.path).path
            if path == '/_probe/requests':
                self.send_json(200, requests)
                return
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            requests.append({'method': self.command, 'path': path,
                             'query': urlsplit(self.path).query,
                             'body': body.decode('utf-8')})
            attempts = sum(entry['path'] == path for entry in requests)
            if '/retry/' in path:
                mode = path.split('/retry/', 1)[1].split('/')[0]
                status = 400 if mode == 'nonretryable' else 500
                if mode == 'recover' and attempts > 2:
                    self.send_json(200, {'id': 'recovered', 'object': 'customer'})
                else:
                    self.send_json(status, {'error': {'type': 'api_error',
                                                      'message': 'controlled failure'}})
            else:
                self.send_json(200, {'id': 'echoed', 'object': 'customer'})

        def send_json(self, status, payload):
            body = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
