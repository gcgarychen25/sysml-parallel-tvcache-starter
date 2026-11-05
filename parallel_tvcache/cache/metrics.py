"""Append-only JSONL metrics for Exp B sequential TVCache."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def metrics_path() -> Path:
    raw = os.environ.get("SYSML_TVCACHE_METRICS", "").strip()
    if raw:
        return Path(raw)
    prefix = os.environ.get("SYSML_JOB_PREFIX", "tvcache")
    return Path("results") / "characterization" / prefix / "tvcache-metrics.jsonl"


def log_metric(event: dict[str, Any]) -> None:
    path = metrics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), **event}
    line = json.dumps(row, sort_keys=True) + "\n"
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def summarize_metrics(path: Path | None = None) -> dict[str, Any]:
    p = path or metrics_path()
    if not p.exists():
        return {"path": str(p), "calls": 0, "hits": 0, "misses": 0, "per_call_hit_rate": None}
    hits = misses = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        src = row.get("source")
        if src == "hit":
            hits += 1
        elif src in ("miss", "inflight", "bypass"):
            misses += 1
    total = hits + misses
    return {
        "path": str(p),
        "calls": total,
        "hits": hits,
        "misses": misses,
        "per_call_hit_rate": (hits / total) if total else None,
    }
