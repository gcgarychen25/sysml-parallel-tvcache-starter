from pathlib import Path
import json
from parallel_tvcache.measurement.trace import analyze, read_pi_session

ROOT = Path(__file__).resolve().parents[1]

def test_session_trace_parses_model_emitted_batches():
    path = ROOT / "fixtures" / "pi_session.jsonl"
    turns = read_pi_session(path)
    assert [len(t["calls"]) for t in turns] == [2, 1, 0]
    result = analyze(path)
    assert result["turns"] == 3
    assert result["tool_calls"] == 3
    assert result["parallel_turn_fraction"] == 1 / 3
    assert result["calls_per_turn_cdf"][-1]["cdf"] == 1.0
    assert [c["call_id"] for c in result["calls"]] == ["call-001", "call-002", "call-003"]


def test_per_tool_characterization_includes_absent_and_zero_call_turns(tmp_path):
    path = tmp_path / 'mixed.jsonl'
    messages = [
        [('read', '1'), ('read', '2'), ('bash', '3')],
        [('bash', '4')],
        [],
    ]
    path.write_text('\n'.join(json.dumps({
        'type': 'message', 'message': {'role': 'assistant', 'content': [
            {'type': 'toolCall', 'name': name, 'id': cid, 'arguments': {}}
            for name, cid in calls
        ]}
    }) for calls in messages))
    result = analyze(path)
    read = result['tool_characterization']['read']
    assert read['turns'] == 3
    assert read['turns_with_tool'] == 1
    assert read['parallel_turn_fraction'] == 1 / 3
    assert read['calls_per_turn_cdf'] == [
        {'calls_per_turn': 0, 'turns': 2, 'cdf': 2 / 3},
        {'calls_per_turn': 2, 'turns': 1, 'cdf': 1.0},
    ]
    # A mixed-tool turn is not a multi-bash turn.
    bash = result['tool_characterization']['bash']
    assert bash['turns_with_tool'] == 2
    assert bash['parallel_turn_fraction'] == 0
    assert bash['calls_per_turn_cdf'][-1]['cdf'] == 1.0


def test_empty_trace_has_no_cdf_or_tool_rows(tmp_path):
    result = analyze(tmp_path)
    assert result['turns'] == 0
    assert result['calls_per_turn_cdf'] == []
    assert result['tool_characterization'] == {}
