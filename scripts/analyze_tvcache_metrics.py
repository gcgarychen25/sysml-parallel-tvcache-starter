#!/usr/bin/env python3
"""Summarize Exp B TVCache JSONL (+ optional Pi sessions) → Table 2 fields.

Outputs per-call hit rate, per-turn hit rate (from jobs/*/agent/pi/sessions),
and tool-wait saved (from elapsed_s vs typical-miss counterfactual).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from parallel_tvcache.cache.metrics import (  # noqa: E402
    discover_job_dirs,
    metrics_path,
    summarize_metrics,
)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Exp B TVCache metrics → call/turn hit rate + tool-wait saved"
    )
    p.add_argument(
        "path",
        nargs="?",
        default=None,
        help="tvcache-metrics.jsonl (default: SYSML_TVCACHE_METRICS or results/characterization/$PREFIX/...)",
    )
    p.add_argument(
        "--jobs-dir",
        type=Path,
        default=None,
        help="Harbor jobs root (default: ./jobs). Used to derive per-turn hit rate.",
    )
    p.add_argument(
        "--no-sessions",
        action="store_true",
        help="Skip Pi session scan (call hit + tool-wait only).",
    )
    p.add_argument("-o", "--output", help="Write summary JSON here")
    args = p.parse_args()
    path = Path(args.path) if args.path else metrics_path()
    job_dirs = None
    if not args.no_sessions:
        jobs_root = args.jobs_dir or (_ROOT / "jobs")
        job_dirs = discover_job_dirs(path, jobs_root)
    summary = summarize_metrics(path, job_dirs=job_dirs)
    # Stable handout-oriented aliases
    summary["table2"] = {
        "per_call_hit_rate_pct": (
            None
            if summary.get("per_call_hit_rate") is None
            else round(100.0 * summary["per_call_hit_rate"], 2)
        ),
        "per_turn_hit_rate_pct": (
            None
            if summary.get("per_turn_hit_rate") is None
            else round(100.0 * summary["per_turn_hit_rate"], 2)
        ),
        "tool_wait_saved_pct": (
            None
            if summary.get("tool_wait_saved_rate") is None
            else round(100.0 * summary["tool_wait_saved_rate"], 2)
        ),
    }
    if job_dirs is not None:
        summary["job_dirs"] = [str(d) for d in job_dirs]
    text = json.dumps(summary, indent=2)
    print(text)
    out = Path(args.output) if args.output else path.with_name("tvcache-summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
