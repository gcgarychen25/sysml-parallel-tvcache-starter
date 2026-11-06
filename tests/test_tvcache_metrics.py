import json
from pathlib import Path

from parallel_tvcache.cache.metrics import (
    log_metric,
    summarize_metrics,
    summarize_turn_hits,
)


def test_log_and_summarize(tmp_path: Path, monkeypatch):
    path = tmp_path / "m.jsonl"
    monkeypatch.setenv("SYSML_TVCACHE_METRICS", str(path))
    log_metric({"event": "tool", "source": "hit", "tool": "bash", "elapsed_s": 0.01})
    log_metric({"event": "tool", "source": "miss", "tool": "bash", "elapsed_s": 0.40})
    log_metric({"event": "tool", "source": "hit", "tool": "read", "elapsed_s": 0.02})
    s = summarize_metrics(path)
    assert s["calls"] == 3
    assert s["hits"] == 2
    assert s["misses"] == 1
    assert abs(s["per_call_hit_rate"] - 2 / 3) < 1e-9
    assert s["tool_wait_saved_rate"] is not None
    assert s["tool_wait_saved_rate"] > 0
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    assert rows[0]["source"] == "hit"


def test_summarize_turn_hits_from_session(tmp_path: Path):
    job = tmp_path / "job-task"
    sess_dir = job / "trial__abc" / "agent" / "pi" / "sessions"
    sess_dir.mkdir(parents=True)
    # one miss turn + one hit turn
    lines = [
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "toolCall", "name": "bash"}],
            },
        },
        {
            "type": "message",
            "message": {
                "role": "toolResult",
                "details": {"tvcache": {"source": "miss", "elapsed_s": 0.3}},
            },
        },
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "toolCall", "name": "read"}],
            },
        },
        {
            "type": "message",
            "message": {
                "role": "toolResult",
                "details": {"tvcache": {"source": "hit", "elapsed_s": 0.01}},
            },
        },
    ]
    (sess_dir / "s.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8"
    )
    t = summarize_turn_hits([job])
    assert t["tool_turns"] == 2
    assert t["tool_turns_with_hit"] == 1
    assert abs(t["per_turn_hit_rate"] - 0.5) < 1e-9
