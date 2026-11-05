"""Per-request Harbor container binding for HarborDockerSandbox."""

from __future__ import annotations

import contextvars

live_container_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sysml_tvcache_live_container", default=""
)
task_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sysml_tvcache_task_id", default=""
)
rollout_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sysml_tvcache_rollout_id", default=""
)
