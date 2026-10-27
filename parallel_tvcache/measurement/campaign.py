"""Explicit run selection and characterization table/CDF exports.

Do not glob all of jobs/ and treat it as a clean research dataset. Pass a
manifest that names included attempts and exclusion reasons.
"""
from __future__ import annotations

import collections
import csv
import json
from pathlib import Path
from typing import Any

from parallel_tvcache.measurement.trace import _cdf, read_pi_session


REQUIRED_MANIFEST_FIELDS = (
    "benchmark",
    "purpose",
    "model",
    "cache_mode",
    "attempts",
)


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_MANIFEST_FIELDS if k not in data]
    if missing:
        raise ValueError(f"Manifest missing fields: {missing}")
    if not isinstance(data["attempts"], list):
        raise ValueError("manifest.attempts must be a list")
    return data


def select_attempt_roots(manifest: dict[str, Any], workspace: Path) -> list[dict[str, Any]]:
    selected = []
    for attempt in manifest["attempts"]:
        include = bool(attempt.get("include", True))
        rel = attempt.get("path")
        if not rel:
            raise ValueError(f"Attempt missing path: {attempt}")
        root = Path(rel) if Path(rel).is_absolute() else (workspace / rel).resolve()
        selected.append({
            "id": attempt.get("id", root.name),
            "path": root,
            "include": include,
            "reason": attempt.get("reason", ""),
            "task": attempt.get("task", ""),
            "variant": attempt.get("variant", "official"),
        })
    return selected


def analyze_selected(attempts: list[dict[str, Any]], benchmark: str | None = None) -> dict[str, Any]:
    included = [a for a in attempts if a["include"]]
    excluded = [
        {"id": a["id"], "path": str(a["path"]), "reason": a["reason"]}
        for a in attempts if not a["include"]
    ]
    groups: collections.Counter[int] = collections.Counter()
    by_tool: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    n_turns = n_calls = n_multi = n_sessions = 0
    merged_calls: list[dict[str, Any]] = []
    for attempt in included:
        files = [attempt["path"]] if attempt["path"].is_file() else sorted(attempt["path"].rglob("*.jsonl"))
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
                n_multi += int(count > 1)
                groups[count] += 1
                per_tool = collections.Counter(c["tool_name"] for c in calls)
                for name, frequency in per_tool.items():
                    by_tool[name][frequency] += 1
                for call in calls:
                    merged_calls.append({
                        "session": str(path),
                        "attempt_id": attempt["id"],
                        "turn_id": turn["turn_id"],
                        **call,
                    })
    tool_characterization = {}
    for name, frequencies in sorted(by_tool.items()):
        counts = frequencies.copy()
        absent = n_turns - sum(frequencies.values())
        if absent:
            counts[0] = absent
        tool_characterization[name] = {
            "turns": n_turns,
            "turns_with_tool": sum(frequencies.values()),
            "parallel_turn_fraction": sum(v for k, v in counts.items() if k > 1) / n_turns if n_turns else 0.0,
            "calls_per_turn_cdf": _cdf(counts),
        }
    result: dict[str, Any] = {
        "sessions": n_sessions,
        "turns": n_turns,
        "tool_calls": n_calls,
        "parallel_turn_fraction": n_multi / n_turns if n_turns else 0.0,
        "calls_per_turn_cdf": _cdf(groups),
        "tool_characterization": tool_characterization,
        "denominator": "All assistant messages, including zero-call turns. Per-tool rows count only calls of that type over the same turns.",
        "tool_frequency_per_turn": {k: dict(sorted(v.items())) for k, v in sorted(by_tool.items())},
        "calls": merged_calls,
        "note": "Parallel-turn fraction means >1 model-emitted tool call; not measured concurrent execution.",
        "excluded_attempts": excluded,
        "included_attempts": [
            {"id": a["id"], "path": str(a["path"]), "task": a["task"], "variant": a["variant"]}
            for a in included
        ],
    }
    if benchmark:
        result["benchmark"] = benchmark
    return result


def table_rows(result: dict[str, Any], benchmark: str) -> list[dict[str, Any]]:
    rows = [{
        "benchmark": benchmark,
        "tool_type": "All tools",
        "turns": result["turns"],
        "turns_with_gt1_tool_call_pct": 100.0 * result["parallel_turn_fraction"],
        "tool_calls": result["tool_calls"],
        "sessions": result["sessions"],
    }]
    for name, stats in result.get("tool_characterization", {}).items():
        freq = result.get("tool_frequency_per_turn", {}).get(name, {})
        rows.append({
            "benchmark": benchmark,
            "tool_type": name,
            "turns": stats["turns"],
            "turns_with_gt1_tool_call_pct": 100.0 * stats["parallel_turn_fraction"],
            "tool_calls": sum(int(k) * int(v) for k, v in freq.items()),
            "sessions": result["sessions"],
        })
    return rows


def write_table_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["benchmark", "tool_type", "turns_with_gt1_tool_call_pct", "turns", "tool_calls", "sessions"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fields})


def _svg_cdf(points: list[dict[str, Any]], title: str, width: int = 640, height: int = 360) -> str:
    if not points:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<text x="24" y="40" font-family="Helvetica,Arial,sans-serif">{title}: no turns</text></svg>\n'
        )
    pad_l, pad_r, pad_t, pad_b = 56, 24, 40, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    xs = [p["calls_per_turn"] for p in points]
    max_x = max(xs) if max(xs) > 0 else 1

    def sx(x: float) -> float:
        return pad_l + (x / max_x) * plot_w

    def sy(y: float) -> float:
        return pad_t + (1.0 - y) * plot_h

    d = [f"M {sx(points[0]['calls_per_turn']):.1f} {sy(0):.1f}"]
    prev_y = 0.0
    for p in points:
        x = p["calls_per_turn"]
        y = p["cdf"]
        d.append(f"L {sx(x):.1f} {sy(prev_y):.1f}")
        d.append(f"L {sx(x):.1f} {sy(y):.1f}")
        prev_y = y
    d.append(f"L {sx(max_x):.1f} {sy(prev_y):.1f}")
    path_d = " ".join(d)
    ticks_x = "".join(
        f'<line x1="{sx(x):.1f}" y1="{pad_t + plot_h}" x2="{sx(x):.1f}" y2="{pad_t + plot_h + 6}" stroke="#333"/>'
        f'<text x="{sx(x):.1f}" y="{height - 16}" text-anchor="middle" font-size="12">{x}</text>'
        for x in sorted(set(xs))
    )
    ticks_y = "".join(
        f'<line x1="{pad_l - 6}" y1="{sy(y):.1f}" x2="{pad_l}" y2="{sy(y):.1f}" stroke="#333"/>'
        f'<text x="{pad_l - 10}" y="{sy(y) + 4:.1f}" text-anchor="end" font-size="12">{y:.1f}</text>'
        for y in (0.0, 0.5, 1.0)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="#fff"/>
  <text x="{width / 2:.0f}" y="24" text-anchor="middle" font-size="14" font-family="Helvetica,Arial,sans-serif">{title}</text>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#333"/>
  <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#333"/>
  <path d="{path_d}" fill="none" stroke="#1f4e79" stroke-width="2"/>
  {ticks_x}
  {ticks_y}
  <text x="{width / 2:.0f}" y="{height - 4}" text-anchor="middle" font-size="12">calls per turn</text>
  <text x="16" y="{height / 2:.0f}" text-anchor="middle" font-size="12" transform="rotate(-90 16,{height / 2:.0f})">CDF</text>
</svg>
'''


def write_cdf_exports(result: dict[str, Any], out_dir: Path, benchmark: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    overall_json = out_dir / "cdf-all-tools.json"
    overall_json.write_text(json.dumps(result["calls_per_turn_cdf"], indent=2) + "\n", encoding="utf-8")
    written.append(overall_json)
    overall_svg = out_dir / "cdf-all-tools.svg"
    overall_svg.write_text(_svg_cdf(result["calls_per_turn_cdf"], f"{benchmark} / All tools"), encoding="utf-8")
    written.append(overall_svg)
    for name, stats in result.get("tool_characterization", {}).items():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        jpath = out_dir / f"cdf-tool-{safe}.json"
        spath = out_dir / f"cdf-tool-{safe}.svg"
        jpath.write_text(json.dumps(stats["calls_per_turn_cdf"], indent=2) + "\n", encoding="utf-8")
        spath.write_text(_svg_cdf(stats["calls_per_turn_cdf"], f"{benchmark} / {name}"), encoding="utf-8")
        written.extend([jpath, spath])
    return written
