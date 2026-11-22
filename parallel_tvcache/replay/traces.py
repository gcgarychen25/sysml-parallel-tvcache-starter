"""Parse Harbor Pi session files into rollouts -> turns -> tool calls.

A Pi session (``jobs/<prefix>-<task>/<task>__<trial>/agent/pi/sessions/*.jsonl``)
is one rollout. Each assistant message is one turn; its ``toolCall`` content
blocks are the calls the model emitted in that turn. The matching
``toolResult`` messages carry the duration, error flag and output.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Call:
    call_id: str
    tool: str
    args: dict[str, Any]
    start: float          # seconds (epoch); result time minus duration
    duration: float       # seconds
    is_error: bool
    output_hash: str      # sha256 of the result text, for stale-hit checks
    live_source: str | None = None   # hit / inflight / miss / bypass, if the run used TVCache


@dataclass
class Turn:
    index: int
    calls: list[Call]


@dataclass
class Rollout:
    task: str
    attempt: str
    path: str
    turns: list[Turn] = field(default_factory=list)

    @property
    def calls(self) -> list[Call]:
        return [c for t in self.turns for c in t.calls]


def parse_args(raw: Any) -> dict[str, Any]:
    """Arguments arrive as a dict, a JSON string, or a Python-repr string."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    for loader in (json.loads, ast.literal_eval):
        try:
            value = loader(raw)
            if isinstance(value, dict):
                return value
        except (ValueError, SyntaxError, TypeError):
            continue
    return {"_raw": raw}


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _ts(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return value / 1000.0 if value > 1e11 else float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def task_and_attempt(path: Path) -> tuple[str, str]:
    """``.../<task>__<trial>/agent/pi/sessions/x.jsonl`` -> (task, trial)."""
    for part in reversed(path.parts):
        if "__" in part:
            task, _, trial = part.partition("__")
            return task, trial
    return path.parent.name, path.stem


def load_session(path: str | Path) -> Rollout:
    path = Path(path)
    task, attempt = task_and_attempt(path)
    rollout = Rollout(task=task, attempt=attempt, path=str(path))
    pending: dict[str, dict[str, Any]] = {}
    order: list[tuple[int, str]] = []          # (turn index, call id) in emission order
    turn_index = -1

    for line in path.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "message":
            continue
        msg = rec.get("message") or {}
        role = msg.get("role")
        if role == "assistant":
            turn_index += 1
            rollout.turns.append(Turn(turn_index, []))
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "toolCall":
                    cid = block.get("id") or f"t{turn_index}-{len(order)}"
                    pending[cid] = {"tool": block.get("name", "?"),
                                    "args": parse_args(block.get("arguments"))}
                    order.append((turn_index, cid))
        elif role == "toolResult":
            cid = msg.get("toolCallId")
            if cid not in pending:
                continue
            dur = float(msg.get("durationMs") or 0) / 1000.0
            end = _ts(msg.get("timestamp")) or _ts(rec.get("timestamp")) or 0.0

            live = ((msg.get("details") or {}).get("tvcache") or {}).get("source")

            pending[cid].update(
                duration=dur, start=end - dur, is_error=bool(msg.get("isError")),
                output_hash=hashlib.sha256(_text(msg.get("content")).encode()).hexdigest(),
                live_source=live)

    for t_idx, cid in order:
        p = pending[cid]
        if "duration" not in p:          # no result recorded (aborted turn)
            continue
        rollout.turns[t_idx].calls.append(Call(
            call_id=cid, tool=p["tool"], args=p["args"], start=p["start"],
            duration=p["duration"], is_error=p["is_error"], output_hash=p["output_hash"],
            live_source=p.get("live_source")))
    return rollout


def load_rollouts(root: str | Path, prefix: str | None = None) -> list[Rollout]:
    """All Pi sessions under ``root`` (a jobs/ dir), optionally one job prefix."""
    root = Path(root)
    paths = sorted(root.glob("**/agent/pi/sessions/*.jsonl"))
    if prefix:
        paths = [p for p in paths if any(part.startswith(prefix) for part in p.parts)]
    return [r for r in (load_session(p) for p in paths) if r.calls]