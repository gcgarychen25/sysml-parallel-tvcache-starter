import asyncio
import pytest
from parallel_tvcache import ParallelCache, ToolCall


def c(cid, name="read", args=None, mutates=False):
    return ToolCall(cid, name, args if args is not None else {"path": "a.py"}, mutates)


def test_partial_hits_order_and_call_id_remap():
    async def check():
        engine = ParallelCache()
        executed = []
        async def execute(call):
            executed.append(call.arguments["path"])
            await asyncio.sleep(0.01)
            return "value:" + call.arguments["path"]
        await engine.run_batch("task", "commit1", [c("original", args={"path": "a.py"})], execute)
        result = await engine.run_batch("task", "commit1", [
            c("new-b", args={"path": "b.py"}),
            c("new-a", args={"path": "a.py"}),
        ], execute)
        assert [x.call_id for x in result.results] == ["new-b", "new-a"]
        assert [x.source for x in result.results] == ["miss", "hit"]
        assert executed == ["a.py", "b.py"]
        assert result.call_hit_rate == 0.5
        assert not result.full_hit
    asyncio.run(check())


def test_inflight_deduplicates_within_and_across_batches():
    async def check():
        engine = ParallelCache()
        executions = 0
        async def execute(call):
            nonlocal executions
            executions += 1
            await asyncio.sleep(0.04)
            return "same result"
        r1, r2 = await asyncio.gather(
            engine.run_batch("t", "s", [c("A"), c("B")], execute),
            engine.run_batch("t", "s", [c("C")], execute),
        )
        assert executions == 1
        assert [x.output for x in r1.results] == ["same result"] * 2
        assert [x.call_id for x in r1.results + r2.results] == ["A", "B", "C"]
        assert sorted([x.source for x in r1.results + r2.results]) == ["inflight", "inflight", "miss"]
    asyncio.run(check())


def test_state_change_invalidates_read_only_key():
    async def check():
        engine = ParallelCache()
        runs = 0
        async def execute(call):
            nonlocal runs
            runs += 1
            return f"run-{runs}"
        a = await engine.run_batch("task", "before-edit", [c("1")], execute)
        b = await engine.run_batch("task", "after-edit", [c("2")], execute)
        assert a.results[0].output != b.results[0].output
        assert runs == 2
    asyncio.run(check())


def test_mutating_batch_bypasses_entire_batch_and_unknown_state_bypasses():
    async def check():
        engine = ParallelCache()
        runs = 0
        async def execute(call):
            nonlocal runs
            runs += 1
            return "output"
        calls = [c("r"), c("w", name="write", mutates=True)]
        a = await engine.run_batch("task", "before", calls, execute)
        b = await engine.run_batch("task", "before", calls, execute)
        d = await engine.run_batch("task", None, [c("z")], execute)
        assert all(x.source == "bypass" for x in a.results + b.results + d.results)
        assert runs == 5 and engine.size == 0
    asyncio.run(check())


def test_failures_not_cached_and_bad_ids_rejected():
    async def check():
        engine = ParallelCache()
        attempts = 0
        async def fail(call):
            nonlocal attempts
            attempts += 1
            raise RuntimeError("tool failure")
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await engine.run_batch("task", "state", [c("a")], fail)
        assert attempts == 2
        assert engine.size == 0
        with pytest.raises(ValueError):
            await engine.run_batch("task", "state", [c("x"), c("x")], fail)
    asyncio.run(check())
