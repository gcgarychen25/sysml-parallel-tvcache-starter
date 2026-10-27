from pathlib import Path
from parallel_tvcache.measurement.rewards import report

def test_reward_report_reads_nested_paths(tmp_path: Path):
    p = tmp_path / "jobs" / "trial" / "verifier"
    p.mkdir(parents=True)
    (p / "reward.json").write_text('{"reward": 0}')
    r = report(tmp_path)
    assert r["reward_files"] == 1
    assert r["rewards"][0]["data"]["reward"] == 0
