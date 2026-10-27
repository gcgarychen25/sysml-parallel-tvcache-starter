# Pi to assigned Rust TVCache: proposed minimal bridge

Status: design only. The uncached Harbor + Pi baseline has not passed; do not enable this bridge before it does. See `results/LOCAL_SMOKE_TEST.md` for the measured blockers. No reference solutions are inputs to this design.

## Smallest sequential baseline (B)

1. Add a separate `parallel_tvcache/harbor_pi.py` installed-agent adapter based on official `Pi`. Keep `scripts/run_one.sh` on `-a pi`. A new `scripts/run_cached.sh` must explicitly opt into B/C and record its mode.
2. Add a Pi tool implementation wrapper (`extensions/tvcache-tools.ts`) using `registerTool`/SDK tool definitions, retaining the native tool name, schema, output blocks, `details`, and error semantics. A `tool_call` event can veto execution but cannot return a successful cache hit; `tool_result` runs after the tool, too late to save work. The wrapper must replace `execute`, not merely observe events.
3. Use one Python broker (`parallel_tvcache/bridge.py`) and one `TvcacheToolExecutor` per attempt. The broker keeps cumulative sequential `ToolCall` objects and awaits `lookup_or_execute(history)`. It must not call that executor concurrently: its persistent TCP client and mutable live-sandbox history are sequential.
4. Implement `parallel_tvcache/harbor_sandbox.py` against the actual per-task environment. Commands and file operations execute in that environment under the same user/cwd/env as Pi, never via laptop `subprocess` tools. Pi currently lives *inside* the task environment: a snapshot hit cannot silently move only the Python executor to another sandbox while Pi still reads the old `/app`. Either restore/synchronize the existing task workspace safely or provide a tool environment indirection shared by **all** wrapped tools; export the final workspace back to Harbor before `[[verifier.collect]]` runs.
5. Implement genuine non-destructive cold snapshots, restore, fork, reference release, and deletion. Harbor `BaseEnvironment` does not expose the required generic `fork()` API. `docker commit` alone does not preserve mounted workspace changes or process state. Choose a backend with tested snapshot semantics or explicitly constrain the supported state model and test it. This is the largest prerequisite, not a few-line wrapper.
6. Keep Harbor's separate verifier authoritative. Do not substitute `tvclient.test()` / cached reward for a fresh official verifier run. Preserve the task's commit-based collection; uncommitted edits are absent from `git diff BASE HEAD`.

## Proposed transport and identities

Use framed JSON messages over a private host-controlled channel. Do not open unrestricted networking in the task for the cache or LLM. A Unix socket or host-mediated exec/stdio transport needs a confinement review: it must expose only the attempt's tool operations, not arbitrary host execution or verifier/solution data.

Request envelope:

```json
{"version":1,"request_id":"unique-rpc-id","attempt_id":"harbor-trial-id","task_namespace":"task+image+instruction+tool-schema-digests","turn_id":7,"state_id":"immutable-snapshot-handle","calls":[{"call_id":"pi-id","tool":"read","arguments":{"path":"/app/file"},"mutates_state":false}]}
```

Response envelope:

```json
{"version":1,"request_id":"unique-rpc-id","state_before":"snapshot-A","state_after":"snapshot-A","results":[{"call_id":"pi-id","tool":"read","content":[{"type":"text","text":"value"}],"details":{},"is_error":false,"source":"hit","lookup_ns":123,"execution_start_ns":null,"execution_end_ns":null}]}
```

The envelope is a proposal, not the assigned Rust wire protocol. Python translates it to the existing binary TCP `TVCacheClient`. Do not change the Rust protocol for B. Exclude transient request/call IDs from semantic cache keys; include task/image/instruction/tool-version namespace, cwd, relevant env, canonical arguments and the stateful prefix. Return results in input order and rebind every result to the current Pi call ID. Store lossless structured tool results via a versioned JSON string inside the client's string-valued cache.

Use an append-only per-attempt ledger and at-most-once response replay for RPC retries. Do not retry mutating execution after an uncertain disconnect. Propagate cancellation and tool errors and never publish failed/partial values as successful hits. Avoid relying on the client's `"Failed to execute"` string heuristic for arbitrary Pi outputs: use a typed adapter error path.

## Parallel extension (C)

Compare per-call keys, whole-turn keys, and a hybrid. Recommended first experiment: hybrid read-only per-call lookups from one immutable pre-turn snapshot; preserve ordered state transitions for mutating batches. This recommendation is not a validated design.

- Extend `tvclient/executor.py` with a distinct batch API and broker ownership; do not wrap existing per-rollout `lookup_or_execute` in `asyncio.gather`.
- Extend `tvclient/{client,protocol}.py` and Rust `src/{types,request_handler}.rs`, `src/tcg/{node,tool_call_graph}.rs` with versioned batch/reservation support, per-call masks/results, and state/snapshot references. Keep sequential requests backward compatible.
- Full hits: return all current IDs without executing tools. Partial hits: execute only misses against the same stable state and await a barrier, maintaining result order.
- In-flight dedup must work across processes/attempts at the server or shared broker. Add atomic reservation/lease/fulfillment with timeout and leader-failure handling; a trie mutex alone does not deduplicate tool execution.
- Conservatively serialize/bypass mixed or mutating batches until a deterministic state transition and snapshot replay is proven. Do not treat arbitrary bash commands as read-only. Preserve Pi's same-file mutation queue and global/per-tool sequential settings.
- Log monotonic timestamps **inside actual tool `execute` entry/exit**, task/attempt/turn/call IDs, state identity, lookup/fork/restore/barrier time, status and hit/miss. Pi's dispatch-start event occurs during preparation before actual parallel dispatch; its intervals alone may overstate execution overlap. Session tool-result persistence timestamps do not establish starts.

Before B/C benchmarks require sandbox-side tests for full/partial hits, reordered IDs, state invalidation, restored file side effects, two-attempt duplicates, cancellation/leader failure, and the final Harbor patch/grade. Measure A/B/C under identical task, model, prompts and resources. The standalone prototype's hit rate is not benchmark evidence.

## Optional no-network inference transport (separate from caching)

`parallel_tvcache/model_transport.py` implements a fixed model-API Unix-socket broker and a sandbox loopback relay. It forwards only `GET /v1/models` and `POST /v1/chat/completions` to a fixed host-loopback port, checks the expected model, bounds request bodies, drops incoming credentials, and saves request/response records. `parallel_tvcache/loopback_pi.py` is an opt-in subclass of official Harbor Pi that starts the relay during installation and checks the unchanged agent no-network policy before calling the official Pi run method. It does not wrap/modify tools or implement TVCache. The ordinary `-a pi` launcher is independent.

Local real-socket tests verify SSE byte preservation, denied arbitrary/absolute/query routes, and credential non-forwarding. This does **not** establish that Unix socket mounting, unprivileged task permissions, inference during Harbor's no-network phase, or the complete task run works on NERSC; those require actual execution. A failed external HTTP probe is only one probe, not a general isolation proof. Broker records are private experiment data; do not publish them without review.
