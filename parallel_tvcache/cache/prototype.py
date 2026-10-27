"""A *conservative prototype*, not a replacement for stateful Rust TVCache.

Only read-only tool results with an explicitly provided, stable sandbox state ID
can be cached. A batch containing *any* mutating call bypasses caching entirely.
This deliberately avoids the false assumption that identical command strings
mean identical sandbox state. The production integration must use the assigned
Rust TVCache tool-call graph and real sandbox snapshot semantics.

Async executor callback: async def execute(call: ToolCall) -> str
The call ID is always rebound to the current request, even on a cache hit.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    mutates_state: bool = False


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    output: str
    source: str  # hit, miss, inflight, bypass
    elapsed_seconds: float


@dataclass(frozen=True)
class BatchResult:
    results: list[ToolResult]
    wait_seconds: float
    @property
    def call_hit_rate(self) -> float:
        return sum(r.source in ("hit", "inflight") for r in self.results) / len(self.results) if self.results else 0.0
    @property
    def full_hit(self) -> bool:
        return bool(self.results) and all(r.source == "hit" for r in self.results)


Execute = Callable[[ToolCall], Awaitable[str]]


class ParallelCache:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._inflight: dict[str, asyncio.Future[str]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(task_id: str, state_id: str, call: ToolCall) -> str:
        raw = json.dumps(
            {"task": task_id, "state": state_id, "tool": call.name, "args": call.arguments},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def run_batch(
        self,
        task_id: str,
        state_id: str | None,
        calls: list[ToolCall],
        execute: Execute,
    ) -> BatchResult:
        """Preserve input order and IDs. Execute misses concurrently.

        All calls in a cacheable batch are treated as reading the SAME immutable
        snapshot. If the harness cannot guarantee this, do not supply state_id.
        """
        ids = [c.call_id for c in calls]
        if len(ids) != len(set(ids)):
            raise ValueError("call_id must be unique within a turn")
        start = time.perf_counter()
        bypass = not state_id or any(c.mutates_state for c in calls)
        async def one(call: ToolCall) -> ToolResult:
            t = time.perf_counter()
            if bypass:
                value = await execute(call)
                return ToolResult(call.call_id, call.name, value, "bypass", time.perf_counter() - t)
            key = self._key(task_id, state_id, call)
            async with self._lock:
                cached = self._values.get(key)
                if cached is not None:
                    return ToolResult(call.call_id, call.name, cached, "hit", time.perf_counter() - t)
                fut = self._inflight.get(key)
                leader = fut is None
                if leader:
                    fut = asyncio.get_running_loop().create_future()
                    self._inflight[key] = fut
            assert fut is not None
            if not leader:
                return ToolResult(call.call_id, call.name, await fut, "inflight", time.perf_counter() - t)
            try:
                value = await execute(call)
                # A failed tool operation should raise. A returned error string
                # is treated as data; adapters must classify tool errors.
                async with self._lock:
                    self._values[key] = value
                    fut.set_result(value)
                    del self._inflight[key]
                return ToolResult(call.call_id, call.name, value, "miss", time.perf_counter() - t)
            except BaseException as exc:
                async with self._lock:
                    if self._inflight.get(key) is fut:
                        del self._inflight[key]
                    fut.set_exception(exc)
                    # Suppress 'Future exception was never retrieved' when
                    # no concurrent waiter existed.
                    fut.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
                raise
        results = await asyncio.gather(*(one(c) for c in calls))
        return BatchResult(list(results), time.perf_counter() - start)

    def clear(self) -> None:
        if self._inflight:
            raise RuntimeError("cannot clear cache during in-flight execution")
        self._values.clear()

    @property
    def size(self) -> int:
        return len(self._values)
