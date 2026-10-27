# Final tentative proposal: code alignment (2026-10-23)

The proposal's scope matches the supplied handout: workload characterization; no-cache/current single-call/parallel-aware comparisons; server/client changes; design comparison; required tests; documented logs; pass@1/pass@5. No training is required. No new GPU allocation or model call was made for this review.

## Small proposal edits worth making

- Complete C/D ownership: C owns Rust batch storage/lookup and in-flight deduplication; D owns Python/Pi dispatch, partial hits, IDs, and state integration. B/C/D jointly validate the state interface early.
- Keep the handout's explicit tests: ordering, call-ID mapping, partial hits, concurrent duplicates. Also retain the storage-design comparison and required raw-log fields.
- Define the denominator for per-tool rows. The analyzer now counts calls of each type over all assistant messages, including zeros. This is an explicit initial convention to confirm with Bhaskar; a mixed read/bash turn is not two read calls.
- Define per-turn hit rate as full-hit turns / eligible tool-calling turns; report partial-hit turns separately. Count executed calls, hits, and waits from actual adapter events rather than infer them from Pi sessions.
- Define saved tool-wait percentage as 100 * (uncached wait - cached wait) / uncached wait under a documented matched-run protocol. Allow negative savings. Include lookup/state-restore/barrier overhead. Do not sum overlapping call durations as wall-clock waiting.
- At least five valid attempts per task are needed for a pass@5 estimate. Choose the task subset and trial budget before launching; report infrastructure failures separately from graded task failures.
- Describe the GitHub deliverable as “a repository that reproduces the tables and figures.” Publish only after checking licensing and removing credentials/private experiment data. No repository was published in this review.

## Existing implementation versus required work

| Deliverable | Current evidence | Remaining work / ownership |
| --- | --- | --- |
| Workload table | Pi session parser; overall and newly added per-tool emitted-call fractions/CDF data | A: real trajectories, per-benchmark runs, figures, attempt provenance, actual execute-entry/exit timestamps |
| No-cache mode | Built-in Pi launcher remains independent; real local NOP verifier control graded reward 0 with no exception | B: real model + Pi attempted task, validate trajectory and reward |
| Existing single-call TVCache | Assigned server/client cloned; design inspected; standalone mock is not integration | B with C/D: tool wrapper/broker and real sandbox snapshot/state restoration; validate a cache hit and official grade |
| Parallel-aware cache | Design notes and toy prototype only | C/D: Rust/client protocol changes, full/partial hits, IDs, in-flight leases/dedup, state semantics, real integration tests |
| Research setup variant | Copy-only prepare_task.py helper | B: copied base-image task, setup instructions and pinned repo revision, approved source/package access policy; preserve authoritative verifier |
| Comparison table | Native reward inspection helper only | A with B/C/D: common experiment manifests and adapter events, hit accounting, actual waits/overhead, pass@1/pass@5 aggregation, table export |
| Report/reproducibility | LOCAL_SMOKE_TEST.md and integration design | Everyone: final analysis/report, sanitized reproducible configs/log schema, figure generation and poster |

## Changes made in this review

- `parallel_tvcache/trace.py`: per-tool CDFs and parallel-turn fractions with explicit all-assistant-turn denominator; legacy histogram retained.
- `scripts/analyze_trace.py`: optional `--benchmark` label. Run separately for each benchmark; it does not infer benchmark identity or split mixed directories.
- `tests/test_trace.py`: mixed-tool/zero-call denominator cases and empty-trace coverage.
- Proposal: synchronized model candidate and tentative C/D responsibilities.
- Model/launcher defaults unchanged. `Qwen/Qwen3.8-27B` is a real official model repository, but no deployment of it has been verified here. The opt-in model relay currently validates a small-model ID and has small-model context limits; it needs configurable, validated model metadata before use with the proposed model. Do not relabel the small-model smoke as a 27B experiment.

## Smallest next milestones

1. B: establish a real inference endpoint, then run one uncached Pi task and inspect the official verifier output. Preserve the unmodified task for this infrastructure check.
2. A/B: agree on task/attempt/turn/call identity and timing schema; retain exact model revision, settings, task image, Pi/Harbor versions, cache mode and cache lifecycle. Do not mix synthetic fixtures or NOP controls into characterization.
3. B/C/D: validate one real sequential Rust-backed cache hit with restored state, then official grading. C/D can prototype the batch interface meanwhile.
4. Build the handout's setup-as-agent-actions task variant separately. The original task has agent no-network policy; agree on permitted clone/install access instead of silently disabling isolation.
5. Extend to C, run required integration tests, then collect matched A/B/C experiments with documented cold/warm cache boundaries.

## Runnable characterization command (data extraction only)

```sh
PYTHONPATH="$PWD" .venv/bin/python scripts/analyze_trace.py /absolute/path/to/one/benchmark/pi-sessions \
  --benchmark DeepSWE --output results/deepswe-characterization.json
```

Input must contain only intended real Pi sessions for that benchmark. The output is CDF data, not a rendered plot or proof of concurrent execution. The fixture remains a synthetic parser check only.

## Validation

- Full unit suite: `.venv/bin/python -m pytest -q` with local socket permission: **12 passed**. Initial sandbox run blocked the two loopback socket tests with `PermissionError`; no tests were skipped or weakened.
- Synthetic CLI check: `PYTHONPATH="$PWD" .venv/bin/python scripts/analyze_trace.py fixtures/pi_session.jsonl --benchmark synthetic-fixture --output results/proposal-review-synthetic-trace.json`: exit 0. The direct script invocation without PYTHONPATH failed to import the package in the current environment; explicit project import path works.
- No real model calls, GPU allocations, cache experiments, or verifier changes in this review.
