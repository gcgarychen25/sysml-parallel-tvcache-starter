#!/usr/bin/env python3
"""Copy a DeepSWE task before altering setup; never mutate upstream source."""
import argparse
import shutil
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("task_id")
p.add_argument("--source", type=Path, default=Path("vendor/deep-swe/tasks"))
p.add_argument("--destination", type=Path, default=Path("results/tasks"))
a = p.parse_args()
src = a.source / a.task_id
dst = a.destination / a.task_id
if not (src / "task.toml").is_file():
    raise SystemExit(f"Missing task.toml: {src}")
if dst.exists():
    raise SystemExit(f"Will not overwrite: {dst}")
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(src, dst)
print(f"Copied task to {dst}\nInspect environment/Dockerfile and instruction.md manually.\n"
      "The handout requires moving setup commands from Dockerfile into the agent prompt; "
      "do not remove verifier dependencies or accidentally expose tests/solution to the agent.")
