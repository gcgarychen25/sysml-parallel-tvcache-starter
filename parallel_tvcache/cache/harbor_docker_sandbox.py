"""Docker-backed Sandbox for paper tvclient (Harbor trial container).

The live env_id is a Docker container id (Harbor ``main``). Cold handles from
``fork()`` are ``docker commit`` image ids. Restoring a handle copies the
workspace into the live Harbor container so the verifier still grades the
Harbor trial FS.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from typing import Optional

from tvclient.sandbox import Sandbox
from tvclient.tool_call import ToolCall

from parallel_tvcache.cache.context import live_container_var
from parallel_tvcache.cache.pi_tool_call import PiToolCall


async def _run(*args: str, check: bool = True) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    out, err = out_b.decode(), err_b.decode()
    if check and proc.returncode != 0:
        raise RuntimeError(f"cmd failed ({proc.returncode}): {' '.join(args)}\n{err}")
    return proc.returncode, out, err


class HarborDockerSandbox(Sandbox):
    """Sandbox = Harbor agent container (+ commit/restore for TVCache)."""

    WORKDIR = os.environ.get("SYSML_TVCACHE_WORKDIR", "/app")

    def __init__(
        self,
        task_name: str,
        env_id: Optional[str] = None,
        *,
        live_container: Optional[str] = None,
    ):
        super().__init__(task_name=task_name, env_id=env_id)
        # Stable Harbor container for this rollout (tools + grading target).
        self.live_container = (
            live_container
            or live_container_var.get()
            or os.environ.get("SYSML_TVCACHE_CONTAINER", "")
        )
        self._commit_images: list[str] = []

    async def start(self) -> None:
        if not self.live_container:
            raise RuntimeError(
                "HarborDockerSandbox needs live_container or SYSML_TVCACHE_CONTAINER"
            )
        if self.env_id is None:
            # Fresh: Harbor already booted the trial container.
            self.env_id = self.live_container
            return
        # Restore cold commit image into the live Harbor container workspace.
        await self._restore_image_into_live(self.env_id)
        self.env_id = self.live_container

    async def fork(self) -> "HarborDockerSandbox":
        if not self.live_container:
            raise RuntimeError("cannot fork without live_container")
        tag = f"sysml-tvcache-{uuid.uuid4().hex[:12]}"
        await _run("docker", "commit", self.live_container, tag)
        self._commit_images.append(tag)
        child = HarborDockerSandbox(
            task_name=self.task_name,
            env_id=tag,
            live_container=self.live_container,
        )
        return child

    async def execute(self, tool_call: ToolCall) -> str:
        if not isinstance(tool_call, PiToolCall):
            # Allow TestToolCall / others via serialize path — treat as bash.
            name = "bash"
            arguments: dict = {"command": getattr(tool_call, "command", str(tool_call))}
        else:
            name = tool_call.name
            arguments = tool_call.arguments
        try:
            cmd = self._tool_to_shell(name, arguments)
        except ValueError as exc:
            return f"Failed to execute: {exc}"
        code, out, err = await _run(
            "docker",
            "exec",
            "-w",
            self.WORKDIR,
            self.live_container,
            "bash",
            "-lc",
            cmd,
            check=False,
        )
        if code != 0:
            text = (out + err).strip() or f"exit {code}"
            return f"Failed to execute: {text}"
        return out if out else (err or "")

    async def stop(self) -> None:
        # Do not remove the Harbor trial container (Harbor owns lifecycle).
        # Drop commit images we created if SYSML_TVCACHE_CLEAN_COMMITS=1.
        if os.environ.get("SYSML_TVCACHE_CLEAN_COMMITS", "").strip() in ("1", "true", "yes"):
            for img in self._commit_images:
                await _run("docker", "rmi", "-f", img, check=False)
            self._commit_images.clear()

    async def _restore_image_into_live(self, image: str) -> None:
        tmp = f"sysml-tvcache-restore-{uuid.uuid4().hex[:10]}"
        try:
            await _run("docker", "create", "--name", tmp, image)
            # Copy workdir tree into live container.
            code, _, err = await _run(
                "docker",
                "cp",
                f"{tmp}:{self.WORKDIR}/.",
                f"{self.live_container}:{self.WORKDIR}/",
                check=False,
            )
            if code != 0:
                raise RuntimeError(f"docker cp restore failed: {err}")
        finally:
            await _run("docker", "rm", "-f", tmp, check=False)

    @staticmethod
    def _tool_to_shell(name: str, arguments: dict) -> str:
        if name == "bash":
            command = arguments.get("command")
            if not command:
                raise ValueError("bash requires command")
            return str(command)
        if name == "read":
            path = arguments.get("path") or arguments.get("file_path")
            if not path:
                raise ValueError("read requires path")
            return f"cat -- {shlex.quote(str(path))}"
        if name == "write":
            path = arguments.get("path") or arguments.get("file_path")
            content = arguments.get("content") or arguments.get("contents") or ""
            if not path:
                raise ValueError("write requires path")
            # Prefer printf with %s via env-less heredoc in bash.
            return (
                f"mkdir -p \"$(dirname {shlex.quote(str(path))})\" && "
                f"cat > {shlex.quote(str(path))} <<'SYSML_TVCACHE_EOF'\n"
                f"{content}"
                f"\nSYSML_TVCACHE_EOF"
            )
        if name == "edit":
            # Best-effort: if old/new provided, sed; else fail clearly.
            path = arguments.get("path") or arguments.get("file_path")
            old = arguments.get("oldText") or arguments.get("old_str")
            new = arguments.get("newText") or arguments.get("new_str")
            if not path or old is None or new is None:
                raise ValueError("edit requires path + oldText/newText")
            # Python one-liner for safe replace once.
            payload = json.dumps({"path": path, "old": old, "new": new})
            return (
                "python3 - <<'PY'\n"
                "import json, pathlib\n"
                f"d=json.loads({payload!r})\n"
                "p=pathlib.Path(d['path']); t=p.read_text()\n"
                "if d['old'] not in t: raise SystemExit('oldText not found')\n"
                "p.write_text(t.replace(d['old'], d['new'], 1))\n"
                "PY"
            )
        raise ValueError(f"unsupported tool for TVCache sandbox: {name}")
