#!/usr/bin/env python3
"""Export Table-1 CSV and CDF plots from an explicit campaign manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parallel_tvcache.measurement.campaign import (
    analyze_selected,
    load_manifest,
    select_attempt_roots,
    table_rows,
    write_cdf_exports,
    write_table_csv,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", type=Path, help="JSON manifest listing included/excluded attempts")
    p.add_argument("--workspace", type=Path, default=ROOT, help="Root for relative attempt paths")
    p.add_argument("--output-dir", type=Path, required=True, help="Directory for table/CDF/summary outputs")
    args = p.parse_args()

    manifest = load_manifest(args.manifest)
    attempts = select_attempt_roots(manifest, args.workspace)
    result = analyze_selected(attempts, benchmark=manifest["benchmark"])
    result["manifest"] = {
        "path": str(args.manifest),
        "purpose": manifest["purpose"],
        "model": manifest["model"],
        "cache_mode": manifest["cache_mode"],
        "notes": manifest.get("notes", ""),
    }
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "characterization-summary.json"
    summary_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = table_rows(result, manifest["benchmark"])
    table_path = out / "table1-workload.csv"
    write_table_csv(rows, table_path)
    cdf_paths = write_cdf_exports(result, out / "cdf", manifest["benchmark"])
    print(json.dumps({
        "summary": str(summary_path),
        "table": str(table_path),
        "cdf_files": [str(p) for p in cdf_paths],
        "turns": result["turns"],
        "tool_calls": result["tool_calls"],
        "parallel_turn_fraction": result["parallel_turn_fraction"],
        "included": len(result["included_attempts"]),
        "excluded": len(result["excluded_attempts"]),
    }, indent=2))


if __name__ == "__main__":
    main()
