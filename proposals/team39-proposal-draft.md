# Team 39 — Parallel-aware TVCache

*Draft for discussion. Please suggest changes before we finalize the proposal.*

## 1. Results we want to produce

**Workload characterization**

| Benchmark | Tool type | Turns with >1 tool call (%) | Calls-per-turn CDF |
| --- | --- | --- | --- |
| DeepSWE | All tools | TBD | TBD curve |
| DeepSWE | Each observed tool type | TBD | TBD curve per type |
| Another benchmark, if expected | All tools / each type | TBD | TBD curves |

- CDF: x = calls per turn; y = fraction of turns with at most that many calls.
- Check timestamps to distinguish multiple calls from concurrent execution.

**Cache comparison**

| Configuration | Per-call hit rate | Per-turn hit rate | Tool-wait time saved vs. A | pass@1 | pass@5 |
| --- | --- | --- | --- | --- | --- |
| A. No cache reuse | N/A | N/A | Reference (0) | TBD | TBD |
| B. Existing single-call TVCache | TBD | TBD | TBD | TBD | TBD |
| C. Parallel-aware TVCache | TBD | TBD | TBD | TBD | TBD |

- Use matched tasks/model settings and official grading. Include cache overhead and the slowest remaining miss in partial-hit timing.
- Also deliver the server/client changes, a design comparison, and documented logs.
- Required tests: ordering, call-ID mapping, partial hits, and concurrent duplicates.

## 2. Proposed implementation plan

1. **Agree on the experiment stack.**
   - **DeepSWE (benchmark/tasks) + Harbor (evaluation framework) + Pi (agent harness) + Qwen3.8-27B (proposed model; deployment/settings to validate).**
   - NERSC serves the model. Mac/Docker runs tasks and grading.
   - Agree on task/trial counts. Confirm whether another benchmark is expected.
2. **Build shared infrastructure for characterization and both baselines.**
   - Implement one runner with no-cache and existing-TVCache modes.
   - Add shared trace collection and timing. Produce workload measurements and baseline results.
   - Establish the tool/cache interface and environment-state handling with C/D.
   - Reuse this infrastructure for the parallel-aware mode.
   - Move repository setup into agent actions for research runs, as required.
3. **Implement the parallel-cache improvements.**
   - Compare per-call, whole-turn, and hybrid designs together.
   - Extend Rust storage/lookup and Python/Pi integration.
   - Handle full/partial hits, call IDs, state changes, and concurrent duplicates.
   - Prototype against the agreed interface while baseline infrastructure develops.
4. **Evaluate and analyze together.**
   - Run all three modes through the same pipeline.
   - Complete the tables and CDF plots. Check task success and explain time savings.

## 3. Tentative ownership

1. **Student A — Measurement and experiment collection**
   - Trace instrumentation, workload characterization, and CDFs.
   - Repeated runs and comparison measurements across all three modes.
2. **Student B — Shared runner and both baselines**
   - Task/model setup, grading, and no-cache/current-cache modes.
   - Existing-TVCache integration and the interface reused by C/D.
3. **Student C — Parallel-aware server**
   - Rust storage, batch lookup, and in-flight deduplication.
   - Server tests and shared state/interface design with B/D.
4. **Student D — Parallel-aware client/integration**
   - Client dispatch, partial hits, call IDs, and state handling.
   - End-to-end tests and shared state/interface design with B/C.

**Note:** Guohao prefers early infrastructure/integration work, but is flexible depending on others' preferences. Everyone contributes to stack/design decisions, analysis, and the poster.

## 4. Timeline

- **Oct 26:** agree on scope and roles; submit proposal.
- **Nov 9 — midpoint presentation:** initial workload characterization, both baseline results, and parallel-cache design.
- **Nov 23:** parallel-cache implementation/tests and evaluation results.
- **Nov 30:** finish joint analysis and result figures/tables.
- **Dec 7 — final poster:** use the last week to prepare and rehearse the presentation.

## 5. Questions for our team / Bhaskar

- Which model variant and task/trial budget are realistic for pass@5? Is another benchmark expected?
- How should per-tool-type parallelism be counted in mixed-tool turns?
- What state-restoration guarantees are needed? Can unsafe mutations initially be serialized?
- Which area would each person prefer? What should we prioritize if integration takes longer?
