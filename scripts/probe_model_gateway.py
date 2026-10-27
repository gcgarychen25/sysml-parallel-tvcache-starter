#!/usr/bin/env python3
"""Synthetic transport test in real Docker; no LLM or benchmark trajectory."""
import asyncio
import http.server
import json
from pathlib import Path
import threading
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parallel_tvcache.evaluation.docker_disconnect import detach_networks, restore_networks


async def command(*args):
    p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await p.communicate()
    return p.returncode,out.decode(),err.decode()


async def main():
    requests=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            assert self.headers.get('Authorization')=='Bearer docker-probe-sentinel'
            requests.append(self.path)
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(b'{"synthetic_transport_probe":true}')
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    suffix=uuid.uuid4().hex[:8]
    gateway='sysml-gateway-probe-'+suffix
    task='sysml-task-probe-'+suffix
    volume='sysml-model-probe-'+suffix
    evidence={'synthetic':True}
    records=Path('results/docker-gateway-probe-records').resolve();records.mkdir(parents=True,exist_ok=True)
    try:
        for args in [
            ('docker','volume','create',volume),
            ('docker','run','--detach','--name',gateway,'--mount',f'type=volume,src={volume},dst=/bridge',
             '--mount',f'type=bind,src={records},dst=/records','--env','SYSML_UPSTREAM_MODEL_API_KEY=docker-probe-sentinel',
             'sysml-model-gateway:smoke','--backend-port',str(server.server_port)),
            ('docker','run','--detach','--name',task,'--mount',f'type=volume,src={volume},dst=/run/sysml-model,readonly',
             'python:3.12-slim','sleep','600'),
            ('docker','cp','parallel_tvcache/inference/model_transport.py',task+':/tmp/model_transport.py'),
            ('docker','exec','--detach','--user','1000',task,'python','/tmp/model_transport.py','sandbox',
             '--socket','/run/sysml-model/model.sock'),
        ]:
            rc,out,err=await command(*args);assert rc==0,(args,err)
        code="import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18081/v1/models', timeout=5).read().decode())"
        for _ in range(30):
            initial=await command('docker','exec','--user','1000',task,'python','-c',code)
            if initial[0]==0: break
            await asyncio.sleep(.1)
        evidence['before']=initial
        assert initial[0]==0,initial
        saved=await detach_networks(task)
        isolated=await command('docker','exec','--user','1000',task,'python','-c',code)
        evidence['isolated']=isolated
        assert isolated[0]==0 and json.loads(isolated[1])['synthetic_transport_probe'],isolated
        await restore_networks(task,saved)
        evidence['model_routes_seen']=requests
        assert requests==['/v1/models','/v1/models'],requests
        evidence['passed']=True
    finally:
        for name in (task,gateway): await command('docker','rm','--force',name)
        await command('docker','volume','rm',volume)
        server.shutdown();server.server_close()
        Path('results/docker-model-gateway-probe.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('PASS: unprivileged disconnected Docker task reaches only the model bridge through a Linux-volume Unix socket')


if __name__=='__main__': asyncio.run(main())
