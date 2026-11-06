"""LoopbackPi + TVCache tool gateway extension (Exp B sequential).

Tools RPC to the Mac-side gateway over TCP
(``host.docker.internal:SYSML_TVCACHE_GATEWAY_PORT``, default 17878).
Requires ``SYSML_CACHE_MODE=sequential`` and running ``tvcache-rust`` + tool gateway.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from parallel_tvcache.evaluation.loopback_pi import LoopbackPi

_EXTENSION_SRC = Path(__file__).with_name("tvcache_tools_extension.ts")
_REMOTE_EXTENSION = "/tmp/harbor-pi-agent/tvcache-tools.ts"


class TvcacheLoopbackPi(LoopbackPi):
    """Harbor Pi with model loopback + TVCache-routed tools."""

    async def install(self, environment):
        await super().install(environment)
        await environment.exec(command="mkdir -p /tmp/harbor-pi-agent")
        await environment.upload_file(_EXTENSION_SRC, _REMOTE_EXTENSION)

    def build_cli_flags(self) -> str:
        base = super().build_cli_flags() or ""
        flag = f"--extension {_REMOTE_EXTENSION}"
        if flag in base:
            return base
        return f"{base} {flag}".strip()

    async def run(self, instruction, environment, context):
        task_id = (
            os.environ.get("SYSML_TVCACHE_TASK_ID")
            or os.environ.get("SYSML_CURRENT_TASK")
            or "harbor-task"
        )
        rollout = os.environ.get("SYSML_TVCACHE_ROLLOUT_ID") or ""
        gw_host = os.environ.get("SYSML_TVCACHE_GATEWAY_HOST", "host.docker.internal")
        gw_port = os.environ.get("SYSML_TVCACHE_GATEWAY_PORT", "17878")
        cmd = (
            "mkdir -p /tmp/harbor-pi-agent && "
            f"printf '%s' {shlex.quote(task_id)} > /tmp/harbor-pi-agent/tvcache-task-id && "
            f"printf '%s' {shlex.quote(gw_host)} > /tmp/harbor-pi-agent/tvcache-gw-host && "
            f"printf '%s' {shlex.quote(gw_port)} > /tmp/harbor-pi-agent/tvcache-gw-port"
        )
        if rollout:
            cmd += (
                f" && printf '%s' {shlex.quote(rollout)} "
                f"> /tmp/harbor-pi-agent/tvcache-rollout-id"
            )
        await environment.exec(command=cmd)
        await super().run(instruction, environment, context)
