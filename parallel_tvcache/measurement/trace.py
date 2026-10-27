"""Analyze Pi session JSONL files, including those saved by Harbor's Pi adapter.

Observes model-emitted calls per assistant message (turn). It does NOT claim
actual execution overlap, which needs tool-start/tool-end timestamps.
"""
from __future__ import annotations
import collections
import json
from pathlib import Path
from typing import Any


def _entries(path: Path):
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def read_pi_session(path: Path) -> list[dict[str, Any]]:
    turns = []
    for event in _entries(path):
        message = event.get("message") if event.get("type") == "message" else None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        calls = []
        for part in message.get("content", []):
            if isinstance(part, dict) and part.get("type") in ("toolCall", "tool_call"):
                calls.append({
                    "call_id": str(part.get("id", "")),
                    "tool_name": str(part.get("name", "")),
                    "arguments": part.get("arguments", {}),
                })
        # Include turns with zero calls for a correctly defined denominator.
        turns.append({"turn_id": len(turns), "calls": calls})
    return turns


def _cdf(groups: collections.Counter[int]) -> list[dict[str, Any]]:
    total = sum(groups.values())
    running = 0
    rows = []
    for k, count in sorted(groups.items()):
        running += count
        rows.append({"calls_per_turn": k, "turns": count, "cdf": running / total})
    return rows


def analyze(root: Path) -> dict[str, Any]:
    files = [root] if root.is_file() else sorted(root.rglob("*.jsonl"))
    # Pi sessions can have other .jsonl files; filter to events with assistant messages.
    groups: collections.Counter[int] = collections.Counter()
    by_tool: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    n_turns = n_calls = n_multi = n_sessions = 0
    calls_data = []
    for path in files:
        turns = read_pi_session(path)
        if not turns:
            continue
        n_sessions += 1
        for turn in turns:
            calls = turn["calls"]
            count = len(calls)
            n_turns += 1
            n_calls += count
            n_multi += count > 1
            groups[count] += 1
            per_tool = collections.Counter(c["tool_name"] for c in calls)
            for name, frequency in per_tool.items():
                by_tool[name][frequency] += 1
            for call in calls:
                calls_data.append({"session": str(path), "turn_id": turn["turn_id"], **call})
    tool_characterization = {}
    for name, frequencies in sorted(by_tool.items()):
        # Count calls of this type over ALL assistant turns, including turns
        # with none of this type. Keep the legacy positive-only histogram below.
        counts = frequencies.copy()
        absent = n_turns - sum(frequencies.values())
        if absent:
            counts[0] = absent
        tool_characterization[name] = {
            "turns": n_turns,
            "turns_with_tool": sum(frequencies.values()),
            "parallel_turn_fraction": sum(v for k, v in counts.items() if k > 1) / n_turns,
            "calls_per_turn_cdf": _cdf(counts),
        }
    return {
        "sessions": n_sessions,
        "turns": n_turns,
        "tool_calls": n_calls,
        "parallel_turn_fraction": n_multi / n_turns if n_turns else 0.0,
        "calls_per_turn_cdf": _cdf(groups),
        "tool_characterization": tool_characterization,
        "denominator": "All assistant messages, including zero-call turns. Per-tool rows count only calls of that type over the same turns.",
        "tool_frequency_per_turn": {k: dict(sorted(v.items())) for k, v in sorted(by_tool.items())},
        "calls": calls_data,
        "note": "Parallel-turn fraction means >1 model-emitted tool call; not measured concurrent execution.",
    }
