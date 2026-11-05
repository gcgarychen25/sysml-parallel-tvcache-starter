#!/usr/bin/env python3
"""Summarize Exp B TVCache JSONL metrics → stdout + optional JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from parallel_tvcache.cache.metrics import summarize_metrics  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "path",
        nargs="?",
        default=None,
        help="tvcache-metrics.jsonl (default: SYSML_TVCACHE_METRICS or results/characterization/$PREFIX/...)",
    )
    p.add_argument("-o", "--output", help="Write summary JSON here")
    args = p.parse_args()
    path = Path(args.path) if args.path else None
    summary = summarize_metrics(path)
    text = json.dumps(summary, indent=2)
    print(text)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
