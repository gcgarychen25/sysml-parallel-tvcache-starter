"""Optional model-only transport; no cache and no tool execution.

Host: fixed loopback vLLM HTTP endpoint -> Unix HTTP socket.
Sandbox: loopback TCP -> that mounted Unix socket. Never forwards a target
chosen by the request. The standard run_one.sh does not load this module.
"""
import argparse
import http.client
import http.server
import json
import os
from pathlib import Path
import selectors
import socket
import socketserver
import time
import uuid

MAX_REQUEST_BYTES = 2 * 1024 * 1024
ALLOWED_ROUTES = {('GET', '/v1/models'), ('POST', '/v1/chat/completions')}


class ModelHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # Request headers can contain credentials; never log them.

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        if (self.command, self.path) not in ALLOWED_ROUTES:
            self.send_error(403, 'Only model API routes are available')
            return
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Chunked requests are unsupported')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= MAX_REQUEST_BYTES:
                raise ValueError('Request size outside limit')
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('Incomplete body')
            if self.command == 'POST':
                data = json.loads(body)
                if not isinstance(data, dict) or data.get('model') != self.server.model:
                    raise ValueError('Unexpected model')
        except (ValueError, TypeError):
            self.send_error(400, 'Invalid model request')
            return
        rid = uuid.uuid4().hex
        root = self.server.records
        root.mkdir(parents=True, exist_ok=True)
        (root / (rid + '.request.json')).write_bytes(body)
        connection = http.client.HTTPConnection(self.server.backend_host, self.server.backend_port, timeout=180)
        started = time.time_ns()
        status = None
        try:
            # Copy no Authorization, Host, or target URL from the sandbox.
            headers = {'Content-Type': 'application/json'}
            if self.server.upstream_key:
                headers['Authorization'] = 'Bearer ' + self.server.upstream_key
            connection.request(self.command, self.path, body=body, headers=headers)
            upstream = connection.getresponse()
            status = upstream.status
            self.send_response(status)
            for name in ('Content-Type', 'Content-Length'):
                if value := upstream.getheader(name):
                    self.send_header(name, value)
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            with (root / (rid + '.response.bin')).open('wb') as output:
                while chunk := upstream.read1(65536):
                    output.write(chunk)
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except (OSError, http.client.HTTPException):
            # Close a partially streamed response rather than inventing a result.
            self.close_connection = True
        finally:
            connection.close()
            (root / (rid + '.meta.json')).write_text(json.dumps({
                'request_id': rid, 'method': self.command, 'path': self.path,
                'start_unix_ns': started, 'end_unix_ns': time.time_ns(), 'status': status,
            }) + '\n')


class UnixModelServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, path, backend_port, model, records, backend_host='127.0.0.1', upstream_key=None):
        self.upstream_key = upstream_key
        self.backend_host = backend_host
        self.backend_port = backend_port
        self.model = model
        self.records = Path(records)
        super().__init__(str(path), ModelHandler)
        # Socket is mounted individually into the task. Its host parent must
        # remain private (0700); mapped unprivileged task users need socket access.
        os.chmod(path, 0o666)


class RelayHandler(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
            upstream.connect(self.server.unix_path)
            with selectors.DefaultSelector() as selector:
                selector.register(self.request, selectors.EVENT_READ, upstream)
                selector.register(upstream, selectors.EVENT_READ, self.request)
                while selector.get_map():
                    for key, _ in selector.select(timeout=180):
                        data = key.fileobj.recv(65536)
                        if data:
                            key.data.sendall(data)
                        else:
                            selector.unregister(key.fileobj)
                            try:
                                key.data.shutdown(socket.SHUT_WR)
                            except OSError:
                                pass


class LoopbackRelay(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, unix_path, port=18081):
        self.unix_path = str(unix_path)
        super().__init__(('127.0.0.1', port), RelayHandler)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['host', 'sandbox'])
    p.add_argument('--socket', required=True)
    p.add_argument('--port', type=int, default=18081)
    p.add_argument('--backend-port', type=int, default=18080)
    p.add_argument('--backend-host', default='127.0.0.1')
    p.add_argument('--model', default=os.environ.get('SYSML_MODEL_ID', 'Qwen/Qwen3-0.6B'))
    p.add_argument('--records', default='model-records')
    a = p.parse_args()
    if a.mode == 'host':
        server = UnixModelServer(a.socket, a.backend_port, a.model, a.records, a.backend_host, os.environ.get('SYSML_UPSTREAM_MODEL_API_KEY'))
    else:
        server = LoopbackRelay(a.socket, a.port)
    with server:
        server.serve_forever()


if __name__ == '__main__':
    main()
