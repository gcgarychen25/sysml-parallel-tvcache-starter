from parallel_tvcache.cache.pi_tool_call import PiToolCall


def test_read_is_stateless():
    c = PiToolCall("read", {"path": "/app/x"})
    assert c.will_mutate_state() is False


def test_bash_mutates():
    c = PiToolCall("bash", {"command": "echo hi"})
    assert c.will_mutate_state() is True


def test_serialize_stable():
    a = PiToolCall("bash", {"command": "echo", "x": 1})
    b = PiToolCall("bash", {"x": 1, "command": "echo"})
    assert a.serialize() == b.serialize()
