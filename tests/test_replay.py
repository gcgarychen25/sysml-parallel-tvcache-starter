"""Trace-replay simulator: synthetic rollouts with known answers."""

import json

from parallel_tvcache.replay.simulate import POLICIES, readonly_bash, simulate
from parallel_tvcache.replay.traces import Call, Rollout, Turn, load_session, parse_args


def call(cid, tool, start, dur=1.0, out="o", err=False, live=None, **args):
    return Call(cid, tool, args, start, dur, err, out, live)


def rollout(name, *turns, task="t"):
    return Rollout(task, name, name, [Turn(i, list(cs)) for i, cs in enumerate(turns)])


def run(policy, *rollouts):
    return simulate(list(rollouts), POLICIES[policy])


def test_later_rollout_hits_after_owner_finished():
    r1 = rollout("r1", [call("a", "bash", 0, command="make")])
    r2 = rollout("r2", [call("b", "bash", 5, command="make")])
    res = run("sequential", r1, r2)
    assert (res.hits, res.waits) == (1, 0)
    assert res.turns_full_hit == 1
    

def test_concurrent_duplicate_waits_only_with_in_flight_sharing():
    r1 = rollout("r1", [call("a", "bash", 0, dur=10, command="make")])
    r2 = rollout("r2", [call("b", "bash", 4, dur=10, command="make")])
    assert run("sequential", r1, r2).waits == 0          # both execute
    res = run("design_a", r1, r2)
    assert res.waits == 1
    # r2 waits 6 s (the owner's remaining time) instead of 10 s
    assert abs(res.cached_wait_s - 16.0) < 1e-6 and res.baseline_wait_s == 20.0


def test_partial_hit_still_waits_on_slowest_miss():
    r1 = rollout("r1", [call("a", "read", 0, dur=1, path="A")])
    r2 = rollout("r2", [call("b", "read", 5, dur=1, path="A"),
                        call("c", "read", 5, dur=3, path="C")])
    res = run("design_a", r1, r2)
    assert res.turns_any_hit == 1 and res.turns_full_hit == 0
    assert abs(res.cached_wait_s - (1 + 3)) < 1e-6        # r2's turn still costs 3 s

def test_divergent_history_misses():
    r1 = rollout("r1", [call("a", "bash", 0, command="echo 1 > f")], [call("b", "read", 2, path="f")])
    r2 = rollout("r2", [call("c", "bash", 5, command="echo 2 > f")], [call("d", "read", 7, path="f")])
    assert run("design_c", r1, r2).hits == 0

def test_order_free_turns_match_reordered_mutations():
    r1 = rollout("r1", [call("a", "edit", 0, path="x"), call("b", "edit", 0, path="y")],
                 [call("c", "bash", 2, command="pytest")])
    r2 = rollout("r2", [call("d", "edit", 5, path="y"), call("e", "edit", 5, path="x")],
                 [call("f", "bash", 7, command="pytest")])
    assert run("design_a", r1, r2).hits == 0             # "pytest" keyed on x,y vs y,x
    assert run("c3_order_free", r1, r2).hits == 3        # both edits + pytest

def test_normalized_keys_ignore_whitespace_and_timeout():
    r1 = rollout("r1", [call("a", "bash", 0, command="go  build ./...", timeout=60)])
    r2 = rollout("r2", [call("b", "bash", 5, command="go build ./...", timeout=120)])
    assert run("design_a", r1, r2).hits == 0
    assert run("c1_normalize", r1, r2).hits == 1


def test_readonly_bash_allowlist_is_conservative():
    yes = ["ls -la", "cd /app && git status", "cat a.py | head -20", "grep -rn foo src"]
    no = ["echo x > f", "sed -i s/a/b/ f", "pip install .", "find . -delete", "cat a | sh",
          "git checkout main", "ls; rm -rf x", "echo $(rm f)"]
    for cmd in yes:
        assert readonly_bash(call("x", "bash", 0, command=cmd)), cmd
    for cmd in no:
        assert not readonly_bash(call("x", "bash", 0, command=cmd)), cmd


def test_readonly_bash_does_not_break_the_chain():
    r1 = rollout("r1", [call("a", "bash", 0, command="ls")], [call("b", "bash", 2, command="make")])
    r2 = rollout("r2", [call("c", "bash", 5, command="make")])
    assert run("design_a", r1, r2).hits == 0             # "ls" counted as a state change
    assert run("c2_readonly_bash", r1, r2).hits == 1


def test_errors_are_not_cached_and_stale_hits_are_counted():
    r1 = rollout("r1", [call("a", "bash", 0, err=True, command="x")])
    r2 = rollout("r2", [call("b", "bash", 5, command="x")])
    assert run("sequential", r1, r2).hits == 0
    r3 = rollout("r3", [call("c", "bash", 0, out="v1", command="date")])
    r4 = rollout("r4", [call("d", "bash", 5, out="v2", command="date")])
    assert run("sequential", r3, r4).stale_hits == 1


def test_tasks_never_share_entries():
    r1 = rollout("r1", [call("a", "bash", 0, command="make")], task="t1")
    r2 = rollout("r2", [call("b", "bash", 5, command="make")], task="t2")
    assert run("design_c", r1, r2).hits == 0


def test_parse_args_handles_json_and_python_repr():
    assert parse_args('{"command": "ls"}') == {"command": "ls"}
    assert parse_args("{'command': 'ls', 'timeout': 60}") == {"command": "ls", "timeout": 60}
    assert parse_args({"path": "a"}) == {"path": "a"}


def test_load_session_pairs_calls_with_results(tmp_path):
    d = tmp_path / "jobs/w-task1/task1__abc/agent/pi/sessions"
    d.mkdir(parents=True)
    recs = [
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "id": "c1", "name": "read", "arguments": '{"path": "a"}'},
            {"type": "toolCall", "id": "c2", "name": "bash", "arguments": "{'command': 'ls'}"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolCallId": "c2", "durationMs": 500,
                                        "timestamp": 1_000_000_000_500, "content": [{"text": "x"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolCallId": "c1", "durationMs": 200,
                                        "timestamp": 1_000_000_000_200, "content": [{"text": "y"}]}},
    ]
    f = d / "s.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in recs))
    r = load_session(f)
    assert (r.task, r.attempt) == ("task1", "abc")
    assert [c.call_id for c in r.turns[0].calls] == ["c1", "c2"]   # emission order kept
    assert r.turns[0].calls[1].duration == 0.5
    assert abs(r.turns[0].calls[0].start - 1_000_000_000.0) < 1e-6

def test_team_formula_credits_each_reuse_a_typical_miss():
    # misses 1 s and 3 s (typical = 2 s); one hit costs ~1 ms
    r1 = rollout("r1", [call("a", "bash", 0, dur=1, command="x")], [call("b", "bash", 2, dur=3, command="y")])
    r2 = rollout("r2", [call("c", "bash", 10, dur=1, command="x")])
    res = run("sequential", r1, r2)
    actual, cf = 1 + 3 + 0.001, 1 + 3 + 2
    assert res.team_saved_pct() == round(100 * (1 - actual / cf), 1)


def test_agreement_with_live_decisions():
    r1 = rollout("r1", [call("a", "bash", 0, command="make", live="miss")])
    r2 = rollout("r2", [call("b", "bash", 5, command="make", live="hit")])
    agr = run("sequential", r1, r2).agreement()
    assert agr["agree_%"] == 100.0 and agr["both_reuse"] == 1