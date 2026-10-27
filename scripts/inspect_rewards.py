#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parallel_tvcache.measurement.rewards import report
p = argparse.ArgumentParser()
p.add_argument("job_dir", type=Path)
a = p.parse_args()
print(json.dumps(report(a.job_dir), indent=2))
