"""Mini-SWE via the same Unix-socket model loopback as LoopbackPi.

Harbor's stock mini-swe-agent points OPENAI_BASE_URL at 127.0.0.1:18081 but does
not start the sandbox relay. Without this wrapper, every completion hits
Connection refused. Also forces chat-completions + reasoning_effort for Qwen
(Harbor 0.24 treats any openai/* + reasoning_effort as litellm_response /
/v1/responses, which our gateway allowlist does not expose).
"""
from __future__ import annotations

import os
import shlex
import uuid
from pathlib import Path

from harbor.agents.installed.mini_swe_agent import (
    MiniSweAgent,
    _DEFAULT_LITELLM_TIMEOUT_SEC,
)
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


class LoopbackMiniSwe(MiniSweAgent):
    async def install(self, environment: BaseEnvironment) -> None:
        await super().install(environment)
        await environment.upload_file(
            Path(__file__).resolve().parents[1] / "inference" / "model_transport.py",
            "/tmp/sysml-model-transport.py",
        )
        await self.exec_as_agent(
            environment,
            command=(
                "nohup python3 /tmp/sysml-model-transport.py sandbox "
                "--socket /run/sysml-model/model.sock --port 18081 "
                "</dev/null >/tmp/sysml-model-transport.log 2>&1 &"
            ),
        )

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        mode = environment.network_policy.network_mode.value
        allow_egress = _env_truthy("SYSML_ALLOW_AGENT_EGRESS") or mode in (
            "public",
            "allowlist",
        )
        if mode != "no-network" and not allow_egress:
            raise RuntimeError(
                "LoopbackMiniSwe requires no-network agent policy "
                "(or SYSML_ALLOW_AGENT_EGRESS=1 / public|allowlist for setup variants)"
            )
        expected_model = os.environ.get("SYSML_MODEL_ID", "Qwen/Qwen3-0.6B")
        probe = f"""python3 - <<'PYPROBE'
import json, time, urllib.request
expected = {expected_model!r}
for attempt in range(30):
    try:
        models = json.load(urllib.request.urlopen('http://127.0.0.1:18081/v1/models', timeout=15))
        break
    except OSError:
        if attempt == 29:
            raise
        time.sleep(0.1)
assert any(m['id'] == expected for m in models['data']), (expected, models)
print('MODEL_LOOPBACK_OK; MINI_SWE')
PYPROBE"""
        result = await self.exec_as_agent(environment, command=probe)
        (self.logs_dir / "model-network-probe.txt").write_text(result.stdout or "")
        await self._run_chat_completions(instruction, environment, context)

    async def _run_chat_completions(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        """Same as MiniSweAgent.run, but never switches to litellm_response."""
        augmented_instruction = instruction
        if self.mcp_servers:
            mcp_info = (
                "\n\nMCP Servers:\nThe following MCP servers are available for this task.\n"
            )
            for s in self.mcp_servers:
                if s.transport == "stdio":
                    args_str = " ".join(s.args)
                    mcp_info += (
                        f"- {s.name}: stdio transport, command: {s.command} {args_str}\n"
                    )
                else:
                    mcp_info += f"- {s.name}: {s.transport} transport, url: {s.url}\n"
            augmented_instruction = instruction + mcp_info

        escaped_instruction = shlex.quote(augmented_instruction)
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        access = self.model_connection
        env = {
            **access.env,
            "MSWEA_CONFIGURED": "true",
            "MSWEA_COST_TRACKING": "ignore_errors",
        }
        if access.api_key is None:
            raise ValueError(
                f"No API key found for model {self.model_name!r}. "
                "Please set MSWEA_API_KEY or the provider's API key variable."
            )

        cli_flags = self.build_cli_flags()
        extra_flags = (cli_flags + " ") if cli_flags else ""
        config_flags = f"-c model.model_kwargs.timeout={_DEFAULT_LITELLM_TIMEOUT_SEC} "

        if self._config_yaml:
            config_path = "/tmp/mswea-config/custom.yaml"
            heredoc_marker = f"MSWEA_CONFIG_EOF_{uuid.uuid4().hex[:8]}"
            write_config_cmd = (
                f"mkdir -p /tmp/mswea-config\n"
                f"cat > '{config_path}' << '{heredoc_marker}'\n"
                f"{self._config_yaml}\n"
                f"{heredoc_marker}\n"
            )
            await self.exec_as_agent(environment, command=write_config_cmd, env=env)
            config_flags += f"-c {config_path} "
        if self._litellm_model_registry_json:
            registry_path = "/tmp/mswea-config/registry.json"
            heredoc_marker = f"MSWEA_REGISTRY_EOF_{uuid.uuid4().hex[:8]}"
            write_registry_cmd = (
                f"mkdir -p /tmp/mswea-config\n"
                f"cat > '{registry_path}' << '{heredoc_marker}'\n"
                f"{self._litellm_model_registry_json}\n"
                f"{heredoc_marker}\n"
            )
            await self.exec_as_agent(environment, command=write_registry_cmd, env=env)
            config_flags += f"-c model.litellm_model_registry={registry_path} "

        if self.session_id:
            header_names = (
                self._session_id_headers
                if self._session_id_headers is not None
                else ["X-Session-ID"]
            )
            for header_name in header_names:
                session_header_config = (
                    f"model.model_kwargs.extra_headers.{header_name}={self.session_id}"
                )
                config_flags += f"-c {shlex.quote(session_header_config)} "

        # Chat completions + reasoning_effort for Qwen/vLLM (not /v1/responses).
        if self.options.reasoning_effort:
            eff = shlex.quote(self.options.reasoning_effort)
            config_flags += f"-c model.model_kwargs.reasoning_effort={eff} "
        if self.options.max_tokens is not None:
            config_flags += f"-c model.model_kwargs.max_tokens={self.options.max_tokens} "

        config_flags = "-c mini " + config_flags
        await self.exec_as_agent(
            environment,
            command=(
                'if [ -f "$HOME/.local/bin/env" ]; then . "$HOME/.local/bin/env"; '
                'else export PATH="$HOME/.local/bin:$PATH"; fi; '
                f"mini-swe-agent --yolo --model={self.model_name} --task={escaped_instruction} "
                f"--output={self._mini_swe_agent_trajectory_path} {extra_flags}"
                f"{config_flags}"
                f"--exit-immediately 2>&1 </dev/null | tee /logs/agent/mini-swe-agent.txt"
            ),
            env=env,
        )
