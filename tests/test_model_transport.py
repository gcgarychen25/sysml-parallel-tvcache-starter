"""Real local sockets and streaming; no LLM, containers, or paid calls."""
import pytest
import http.client
import http.server
import json
import threading
import tempfile
from pathlib import Path

from parallel_tvcache.inference.model_transport import UnixModelServer, LoopbackRelay


@pytest.mark.parametrize('upstream_key', [None, 'host-key-sentinel'])
def test_relay_streams_model_only_and_retains_no_credentials(tmp_path, upstream_key):
    observed = []

    class Backend(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            observed.append((self.path, self.headers.get('Authorization')))
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            self.wfile.write(b'data: {"ok":true}\n\ndata: [DONE]\n\n')

    with tempfile.TemporaryDirectory(dir='/tmp', prefix='tvc-') as short_dir, http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend) as backend:
        with UnixModelServer(Path(short_dir) / 'model.sock', backend.server_port, 'tiny', tmp_path / 'records', upstream_key=upstream_key) as unix:
            with LoopbackRelay(Path(short_dir) / 'model.sock', 0) as relay:
                servers = [backend, unix, relay]
                threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
                for t in threads:
                    t.start()
                try:
                    client = http.client.HTTPConnection(*relay.server_address, timeout=5)
                    client.request('POST', '/v1/chat/completions', json.dumps({'model': 'tiny', 'messages': []}),
                                   {'Authorization': 'Bearer sentinel-never-forward'})
                    response = client.getresponse()
                    assert response.status == 200
                    assert response.read() == b'data: {"ok":true}\n\ndata: [DONE]\n\n'
                    client.close()
                    for path in ['http://example.invalid/v1/chat/completions', '/etc/passwd', '/v1/models?target=http://example.invalid']:
                        client = http.client.HTTPConnection(*relay.server_address, timeout=5)
                        client.request('GET', path)
                        response = client.getresponse()
                        assert response.status == 403
                        response.read()
                        client.close()
                    assert observed == [('/v1/chat/completions', 'Bearer '+upstream_key if upstream_key else None)]
                finally:
                    for s in reversed(servers):
                        s.shutdown()
                    for t in threads:
                        t.join(timeout=5)
    records = list((tmp_path / 'records').glob('*'))
    assert any(p.name.endswith('.response.bin') for p in records)
    assert all(b'sentinel-never-forward' not in p.read_bytes() and b'host-key-sentinel' not in p.read_bytes() for p in records)
