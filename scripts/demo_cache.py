#!/usr/bin/env python3
"""Standalone deterministic demo: not a DeepSWE score or Rust TVCache test."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parallel_tvcache import ParallelCache, ToolCall

async def main():
    cache = ParallelCache()
    count = {}
    async def execute(call):
        k = call.arguments["path"]
        count[k] = count.get(k, 0) + 1
        await asyncio.sleep(0.03 if k == "a.py" else 0.01)
        return "contents:" + k
    def call(cid, path):
        return ToolCall(cid, "read", {"path": path})
    batches = [
        [call("1", "a.py")],
        [call("2", "a.py"), call("3", "b.py")],
        [call("4", "a.py"), call("5", "b.py")],
    ]
    for i, batch in enumerate(batches):
        outcome = await cache.run_batch("demo-task", "initial-snapshot", batch, execute)
        print(json.dumps({"batch": i, "call_hit_rate": outcome.call_hit_rate,
                          "wait_seconds": round(outcome.wait_seconds, 3),
                          "results": [vars(x) for x in outcome.results]}, indent=2))
    print("Actual sandbox call counts:", count)

if __name__ == "__main__":
    asyncio.run(main())
