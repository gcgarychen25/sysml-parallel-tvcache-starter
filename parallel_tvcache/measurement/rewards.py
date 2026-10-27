"""Summarize Harbor job artifacts without assuming that trial completion = pass."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def report(root: Path) -> dict[str, Any]:
    candidates = sorted(root.rglob("reward.json")) if root.exists() else []
    rewards = []
    for file in candidates:
        try:
            data = json.loads(file.read_text())
        except (OSError, ValueError):
            continue
        rewards.append({"path": str(file), "data": data})
    return {"reward_files": len(rewards), "rewards": rewards,
            "note": "Inspect the actual reward schema and grader logs; missing files or reward=0 do not imply infrastructure incompatibility."}
