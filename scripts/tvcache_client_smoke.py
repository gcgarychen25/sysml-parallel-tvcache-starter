#!/usr/bin/env python3
"""Smoke: connect to tvcache-rust, insert + find round-trip (no Docker)."""

from __future__ import annotations

import asyncio
import os
import sys

# Prefer vendored tvclient when not installed editable.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_ROOT, "vendor", "tvclient"))
sys.path.insert(0, _ROOT)

from tvclient.client import TVCacheClient  # noqa: E402


async def main() -> int:
    host = os.environ.get("SYSML_TVCACHE_HOST", "127.0.0.1")
    port = int(os.environ.get("SYSML_TVCACHE_PORT", "7878"))
    task = "smoke-task"
    path = ['{"name":"bash","arguments":{"command":"echo hi"}}']
    async with TVCacheClient(host, port) as client:
        await client.insert(task, path, value="hi\n", sandbox_id=None, runtime=1)
        async with await client.find(task, path) as found:
            if found.value != "hi\n":
                print(f"FAIL expected hi\\n got {found.value!r}", file=sys.stderr)
                return 1
    print(f"OK tvcache smoke insert/find on {host}:{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
