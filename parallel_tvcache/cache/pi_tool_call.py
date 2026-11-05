"""Pi-shaped ToolCall for paper tvclient (Exp B sequential TVCache)."""

from __future__ import annotations

import json
import os
from typing import Any

from tvclient.tool_call import ToolCall

# Conservative mutate heuristic (override with SYSML_TVCACHE_READONLY_TOOLS).
_DEFAULT_READONLY = frozenset({"read", "grep", "find", "ls", "search"})


def _readonly_tools() -> frozenset[str]:
    raw = os.environ.get("SYSML_TVCACHE_READONLY_TOOLS", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return _DEFAULT_READONLY


class PiToolCall(ToolCall):
    """One Pi tool invocation: cache key = {name, arguments}."""

    def __init__(self, name: str, arguments: dict[str, Any] | None = None):
        self.name = str(name)
        self.arguments = dict(arguments or {})

    def to_dict(self) -> dict:
        return {"name": self.name, "arguments": self.arguments}

    def will_mutate_state(self) -> bool:
        return self.name not in _readonly_tools()

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "PiToolCall":
        return cls(name=str(payload["name"]), arguments=dict(payload.get("arguments") or {}))

    def __repr__(self) -> str:
        return f"PiToolCall({self.name}, {json.dumps(self.arguments, sort_keys=True)[:120]})"
