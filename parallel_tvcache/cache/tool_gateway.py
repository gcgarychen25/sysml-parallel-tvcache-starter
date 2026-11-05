"""Host-side TVCache tool gateway (Unix socket).

Pi extensions RPC here; each (task_id, rollout_id) owns one TvcacheToolExecutor
sharing the Mac-side tvcache-rust server across concurrent Harbor rollouts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tvclient.executor import TvcacheToolExecutor

from parallel_tvcache.cache.context import live_container_var, rollout_id_var, task_id_var
from parallel_tvcache.cache.harbor_docker_sandbox import HarborDockerSandbox
from parallel_tvcache.cache.metrics import log_metric
from parallel_tvcache.cache.pi_tool_call import PiToolCall

LOG = logging.getLogger("sysml.tvcache.gateway")


async def _resolve_container_id(ref: str) -> str:
    """Map hostname / short id to a full Docker container id when possible."""
    if not ref:
        return ref
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "inspect",
        "-f",
        "{{.Id}}",
        ref,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, _ = await proc.communicate()
    if proc.returncode == 0:
        cid = out_b.decode().strip()
        if cid:
            return cid
    return ref


@dataclass
class RolloutSession:
    task_id: str
    rollout_id: str
    container_id: str
    executor: TvcacheToolExecutor
    history: list[PiToolCall] = field(default_factory=list)
    closed: bool = False


class ToolGateway:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7878,
        sock_path: str | None = None,
    ):
        self.host = host
        self.port = port
        self.sock_path = Path(
            sock_path
            or os.environ.get("SYSML_TVCACHE_SOCK", "results/tvcache/tvcache.sock")
        )
        self._sessions: dict[tuple[str, str], RolloutSession] = {}
        self._lock = asyncio.Lock()

    async def get_session(
        self, task_id: str, rollout_id: str, container_id: str
    ) -> RolloutSession:
        key = (task_id, rollout_id)
        async with self._lock:
            sess = self._sessions.get(key)
            if sess and not sess.closed:
                if container_id and sess.container_id != container_id:
                    sess.container_id = container_id
                return sess
            token = live_container_var.set(container_id)
            try:
                ex = TvcacheToolExecutor(
                    HarborDockerSandbox,
                    PiToolCall,
                    task_id,
                    host=self.host,
                    port=self.port,
                )
                await ex.client.connect()
                ex.set_rollout_id(rollout_id)
            finally:
                live_container_var.reset(token)
            sess = RolloutSession(
                task_id=task_id,
                rollout_id=rollout_id,
                container_id=container_id,
                executor=ex,
            )
            self._sessions[key] = sess
            return sess

    async def handle_tool(self, req: dict[str, Any]) -> dict[str, Any]:
        task_id = str(req.get("task_id") or "unknown-task")
        rollout_id = str(req.get("rollout_id") or "unknown-rollout")
        container_id = await _resolve_container_id(str(req.get("container_id") or ""))
        name = str(req["name"])
        arguments = dict(req.get("arguments") or {})
        call = PiToolCall(name=name, arguments=arguments)

        sess = await self.get_session(task_id, rollout_id, container_id)
        token_c = live_container_var.set(sess.container_id)
        token_t = task_id_var.set(task_id)
        token_r = rollout_id_var.set(rollout_id)
        t0 = time.perf_counter()
        try:
            sess.history.append(call)
            # Hit ⇒ lookup_or_execute returns without sandbox execute.
            before_exec = sess.executor.total_executions
            result = await sess.executor.lookup_or_execute(list(sess.history))
            elapsed = time.perf_counter() - t0
            source = "hit" if sess.executor.total_executions == before_exec else "miss"
            log_metric(
                {
                    "event": "tool",
                    "task_id": task_id,
                    "rollout_id": rollout_id,
                    "tool": name,
                    "source": source,
                    "elapsed_s": elapsed,
                    "mutates": call.will_mutate_state(),
                }
            )
            return {
                "ok": True,
                "output": result,
                "source": source,
                "elapsed_s": elapsed,
            }
        except Exception as exc:  # noqa: BLE001 — surface to Pi
            LOG.exception("tool gateway failure")
            log_metric(
                {
                    "event": "tool_error",
                    "task_id": task_id,
                    "rollout_id": rollout_id,
                    "tool": name,
                    "error": str(exc),
                }
            )
            return {"ok": False, "error": str(exc), "output": f"Failed to execute: {exc}"}
        finally:
            live_container_var.reset(token_c)
            task_id_var.reset(token_t)
            rollout_id_var.reset(token_r)

    async def close_rollout(self, task_id: str, rollout_id: str) -> None:
        key = (task_id, rollout_id)
        async with self._lock:
            sess = self._sessions.pop(key, None)
        if sess and not sess.closed:
            sess.closed = True
            await sess.executor.close()

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for sess in sessions:
            if not sess.closed:
                sess.closed = True
                await sess.executor.close()


async def _handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, gateway: ToolGateway
) -> None:
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            req = json.loads(line.decode())
            op = req.get("op", "tool")
            if op == "tool":
                resp = await gateway.handle_tool(req)
            elif op == "close":
                await gateway.close_rollout(
                    str(req.get("task_id") or ""),
                    str(req.get("rollout_id") or ""),
                )
                resp = {"ok": True}
            elif op == "ping":
                resp = {"ok": True, "pong": True}
            else:
                resp = {"ok": False, "error": f"unknown op {op}"}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def serve_forever(gateway: ToolGateway) -> None:
    gateway.sock_path.parent.mkdir(parents=True, exist_ok=True)
    if gateway.sock_path.exists():
        gateway.sock_path.unlink()
    server = await asyncio.start_unix_server(
        lambda r, w: _handle_client(r, w, gateway),
        path=str(gateway.sock_path),
    )
    LOG.info("tool gateway listening on %s", gateway.sock_path)
    stop = asyncio.Event()

    def _stop(*_args: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass
    async with server:
        await stop.wait()
    await gateway.close_all()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="SysML TVCache tool gateway")
    p.add_argument("--host", default=os.environ.get("SYSML_TVCACHE_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("SYSML_TVCACHE_PORT", "7878")))
    p.add_argument(
        "--sock",
        default=os.environ.get("SYSML_TVCACHE_SOCK", "results/tvcache/tvcache.sock"),
    )
    args = p.parse_args()
    gateway = ToolGateway(host=args.host, port=args.port, sock_path=args.sock)
    asyncio.run(serve_forever(gateway))


if __name__ == "__main__":
    main()
