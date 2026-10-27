# Architecture and research boundary

## Execution layers

```
DeepSWE task corpus -> Harbor job/trials/verifier
                           |
                           v
                   Pi agent loop (Node/TS)
                         /   \
         OpenAI-compatible   tool batch (many call IDs)
           vLLM server        |
                              v
                   [Integration to implement]
                              |
                    Python tvclient executor
                       /           \
              Rust TVCache       sandbox execution,
                server          restore/fork semantics
```

- Model inference is NOT served by TVCache, and TVCache is NOT an attention KV cache.
- The baseline smoke test intentionally runs Pi normally, without TVCache.
- `parallel_tvcache/cache/prototype.py` is an independently tested, in-memory *read-only* batching model. It is not the Rust server and is not wired into Pi.
- The professor explicitly asks for new parallel-call support in **both** assigned repositories.

## Milestones / definition of done

### M0: full task grading (Harbor + Pi, no cache)
- [ ] Running Docker and network/endpoint configuration.
- [ ] Successful, non-infrastructure-error single-task run.
- [ ] Valid verifier report (`reward.json`, including reward 0 if attempted but not solved).
- [ ] Captured Pi session JSONL and task/agent version manifest.

### M1: parallel workload characterization
- [ ] Prove actual simultaneous start/end overlap with start/end timestamps.
- [ ] CDF and parallel-turn fractions per task/tool; repeat trajectories of the same task.
- [ ] Track environment changes, attempted task and call IDs.

### M2: faithful sequential-cache baseline
- [ ] Wire the assigned Rust server + Python client into the same Pi harness.
- [ ] Confirm correct sandbox snapshot / restore on mutating commands.
- [ ] Regression tests of sequential tool calls and raw, stateful history.

### M3: production parallel support (**not implemented in this starter**)
- [ ] Extend TVCache server graph schema and lookup protocol to represent a turn with N calls.
- [ ] Extend Python client to accept `[{call_id, tool, arguments}, ...]`, return per-call hits and correct mapping.
- [ ] Choose per-call, per-turn or hybrid design based on explicit dependency/state semantics.
- [ ] Deal with duplicate tool calls in one batch and concurrent in-flight duplicate requests.
- [ ] Avoid reusing outputs across incompatible sandbox states; preserve file-system side effects.
- [ ] Track cache lookup, sandbox fork, execution, barrier, per-call and per-turn wall time.

### M4: controlled experiment
- [ ] A no-cache; B current single-call Rust cache; C new parallel-aware Rust cache.
- [ ] Same task versions, model, prompts, scheduling, resource envelope, seeds where supported.
- [ ] pass@1/pass@5, per-call/per-turn hit, tool-wait saved; raw task/attempt/call_id JSONL.
- [ ] At least one controlled correctness microbenchmark with guaranteed full, partial and in-flight reuse.

## Correctness subtleties

Pi 1.4.0 source defaults to parallel dispatch and maps results back to call IDs, but global sequential mode or any tool marked `executionMode: "sequential"` serializes the batch. This source inspection is not a measurement of a DeepSWE run. *Simultaneously issued* does not mean *commutative*. Two tools modifying the same file can race (Pi also has a per-file mutation queue). Do not treat the batch as an unordered set unless the calls are demonstrably independent, and avoid caching read-only calls across a concurrent mutation unless a stable snapshot boundary exists.

Snapshot/replay matters. For mutating calls (e.g. package installation or `git clone`), cached output alone is insufficient: the next sandbox must contain the resulting files and process state as expected by the agent.

The in-memory prototype only caches read-only calls when given a stable `state_id`. Production integration must establish or restore this state via the real sandbox and original TVCache graph.

## A note on benchmark variants

The handout requires using a base image *without setup commands*, then asking the agent to clone/build before solving the task. The original DeepSWE v1.1 tasks use prebuilt images. M0 intentionally tests their **unmodified** task to establish grader compatibility; M1--M4 need a separately versioned task variant with setup shifted into the instruction. Do not modify the official task in place. Avoid breaking held-out verifier environment or accidentally granting agent access to solution/tests.

## Source organization

See [codebase-map.md](codebase-map.md) for proposal ownership, package boundaries, stable commands, and archived helpers. This refactor changes source organization only; it does not complete any unchecked research milestone.
