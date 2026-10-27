#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parallel_tvcache.measurement.trace import analyze
p = argparse.ArgumentParser()
p.add_argument("path", type=Path, help="One Pi session .jsonl or directory of Harbor jobs")
p.add_argument("--output", type=Path)
p.add_argument("--benchmark", help="Label for one benchmark only; do not combine benchmark directories")
a = p.parse_args()
r = analyze(a.path)
if a.benchmark:
    r["benchmark"] = a.benchmark
out = json.dumps(r, indent=2, ensure_ascii=False)
if a.output:
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(out + "\n")
print(json.dumps({k: v for k, v in r.items() if k != "calls"}, indent=2))
