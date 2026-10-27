#!/usr/bin/env python3
"""Nonzero exit code when no parseable numeric Harbor verifier reward exists."""
import argparse
import json
from numbers import Real
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("job_dir", type=Path, help="Harbor jobs directory")
a = p.parse_args()
paths = list(a.job_dir.rglob("reward.json"))
found = 0
for path in sorted(paths):
    try:
        data = json.loads(path.read_text())
        # DeepSWE's actual reward.json normally exposes a numeric 'reward'.
        reward = data.get("reward") if isinstance(data, dict) else None
        if isinstance(reward, Real) and not isinstance(reward, bool):
            print(f"VERIFIER_REWARD={reward} PATH={path}")
            found += 1
        else:
            print(f"SCHEMA_REQUIRES_INSPECTION {path}: {str(data)[:300]}")
    except Exception as exc:
        print(f"ERROR {path}: {exc}")
if not found:
    raise SystemExit("No numeric verifier reward found. Not a proven end-to-end grading run.")
