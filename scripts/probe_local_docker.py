#!/usr/bin/env python3
"""Actual Docker network enforcement test. Requires Harbor's Python env."""
import asyncio
import http.server
import json
from pathlib import Path
import threading
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parallel_tvcache.evaluation.docker_disconnect import detach_networks, restore_networks, docker_json


async def command(*args):
    p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await p.communicate()
    return p.returncode,out.decode(),err.decode()


async def main():
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'sysml-network-probe')
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    name='sysml-netprobe-'+uuid.uuid4().hex[:10]
    evidence={}
    try:
        rc,out,err=await command('docker','run','--detach','--name',name,'python:3.12-slim','sleep','600')
        assert rc==0,err
        resolved=await command('docker','exec',name,'python','-c',"import socket; print(socket.gethostbyname('host.docker.internal'))")
        assert resolved[0]==0,resolved
        address=resolved[1].strip()
        evidence['controlled_host_ip']=address
        code="import urllib.request; print(urllib.request.urlopen('http://%s:%s', timeout=3).read().decode())" % (address,server.server_port)
        before=await command('docker','exec',name,'python','-c',code)
        evidence['before_http']=before
        assert before[0]==0 and 'sysml-network-probe' in before[1],before
        saved=await detach_networks(name)
        evidence['original_networks']=saved
        evidence['isolated_inspect']=(await docker_json('inspect',name))[0]['NetworkSettings']
        isolated=await command('docker','exec',name,'python','-c',code)
        evidence['isolated_http']=isolated
        interfaces=await command('docker','exec',name,'python','-c',"import json,socket; from pathlib import Path; print(json.dumps({n:int(Path('/sys/class/net',n,'flags').read_text(),16) for _,n in socket.if_nameindex()})); print(Path('/proc/net/route').read_text())")
        evidence['isolated_interfaces']=interfaces
        assert isolated[0]!=0, 'Controlled host endpoint remained reachable'
        lines=interfaces[1].splitlines()
        flags=json.loads(lines[0])
        assert all(not (f & 1) for n,f in flags.items() if n!='lo'),flags
        assert not [line for line in lines[2:] if line.strip()],interfaces
        await restore_networks(name,saved)
        restored=await command('docker','exec',name,'python','-c',code)
        evidence['restored_http']=restored
        assert restored[0]==0 and 'sysml-network-probe' in restored[1],restored
        evidence['passed']=True
    finally:
        await command('docker','rm','--force',name)
        server.shutdown();server.server_close()
        Path('results/local-docker-network-probe.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('PASS: controlled host HTTP reachable -> disconnected/no-up-egress-interface/no-IPv4-route/unreachable -> restored')


if __name__=='__main__': asyncio.run(main())
