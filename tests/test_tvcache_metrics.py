import json
from pathlib import Path

from parallel_tvcache.cache.metrics import log_metric, summarize_metrics


def test_log_and_summarize(tmp_path: Path, monkeypatch):
    path = tmp_path / "m.jsonl"
    monkeypatch.setenv("SYSML_TVCACHE_METRICS", str(path))
    log_metric({"event": "tool", "source": "hit", "tool": "bash"})
    log_metric({"event": "tool", "source": "miss", "tool": "bash"})
    log_metric({"event": "tool", "source": "hit", "tool": "read"})
    s = summarize_metrics(path)
    assert s["calls"] == 3
    assert s["hits"] == 2
    assert s["misses"] == 1
    assert abs(s["per_call_hit_rate"] - 2 / 3) < 1e-9
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    assert rows[0]["source"] == "hit"
