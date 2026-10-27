# Cursor handoff: DeepSWE workload characterization

Updated: 2026-10-27. Open this directory as the Cursor workspace:

`/Users/garychen/Desktop/sysml_final_project/sysml_parallel_tvcache_starter`

## 1. Your task

Start the proposal's workload-characterization work. Produce:

| Benchmark | Tool type | Turns with >1 tool call (%) | Calls-per-turn CDF |
| --- | --- | --- | --- |
| DeepSWE | All tools | Measured value | Exported plot + source data |
| DeepSWE | Each observed tool type | Measured value | Exported curve per type |

Use uncached real agent attempts. Characterization does not depend on completing Rust TVCache integration. A/B/C cache hit rates and time-savings comparisons are later work.

## 2. Verified project status

- Official Harbor 0.24.0 + Pi 1.4.0 ran a real unmodified DeepSWE task with NERSC inference and a separate local verifier.
- Real model: Qwen/Qwen3-0.6B. It returned one text response, made **zero tool calls**, and submitted an empty patch.
- Grading: reward 0, no Harbor exception; P2P 643/643, F2P 0/82. This validates inference/launch/grading, not tool execution or useful characterization.
- An earlier attempt crashed the model sampler. It also received a numeric reward: a reward file alone does not prove agent execution succeeded.
- Last full unit suite: **12 passed**. Gateway image build and source/import compatibility checks passed.
- Parser already exports overall/per-tool emitted-call fractions and CDF data. No real execution-overlap instrumentation, plot generator, or campaign manifest/aggregator yet.
- The handout's setup-as-agent-actions task variant has not been created. `prepare_task.py` only copies files.
- Assigned Rust server and Python client are cloned. Neither is integrated with Pi. `cache/prototype.py` is an in-memory toy only.
- Both m4999 jobs and local gateways/tunnels were released after the test. Historical node names, volume names and ports are not live infrastructure.

Evidence to inspect first:

1. `results/M4999_REAL_SMOKE_TEST.md` — completed smoke, commands, failure/fix, limits.
2. `jobs/m4999-pi-60365877/clack-async-autocomplete-options__rjQ77gP/result.json` — native successful pipeline result.
3. Same trial: `agent/pi/sessions/*.jsonl`, `agent/pi.txt`, `agent/model-network-probe.txt`, `verifier/reward.json`, `verifier/ctrf.json`, `verifier/test-stdout.txt`.
4. `results/m4999-60365877-trace.json` — actual one-turn/zero-call statistics.
5. `jobs/m4999-pi-60365657/` and `results/nersc/inference-60365657/vllm.log` — backend failure, not a task-quality sample.

`results/LOCAL_SMOKE_TEST.md` is chronological; its current-status paragraph and later dated entries supersede old checkpoints.

## 3. Key files and ownership boundaries

| File / directory | Purpose | What to change for characterization |
| --- | --- | --- |
| `docs/project_assignment.pdf` | Actual assignment | Read the workload and setup requirements |
| `proposals/team39-proposal-draft.md` | Local proposal draft | Planning context; final user/team decisions take precedence |
| `parallel_tvcache/measurement/trace.py` | Pi session parser, fractions and CDF data | Input selection, provenance, explicit denominators; separate real timing analysis |
| `scripts/analyze_trace.py` | Analysis CLI | Keep raw session support; add structured campaign selection/output as needed |
| `tests/test_trace.py` | Parser/denominator tests | Add meaningful coverage for failure selection, branches and mixed-tool turns |
| `parallel_tvcache/evaluation/loopback_pi.py` | Official Pi subclass + model relay | Generalize hardcoded small-model checks/limits; add optional timing instrumentation without changing tool semantics |
| `parallel_tvcache/evaluation/docker_disconnect.py` | Local Docker no-network adapter | Preserve NIC-disconnection enforcement; not a cache implementation |
| `parallel_tvcache/inference/model_transport.py` | Fixed-route Unix model broker and loopback relay | Model ID defaults/transport settings must match the selected server |
| `scripts/nersc_serve_model.sbatch` | Inference-only Slurm helper | Currently hardcoded 0.6B; generalize model/revision/context/resources before a different model |
| `configs/model-gateway.Dockerfile` | Docker-side Unix socket gateway | Used between Mac tunnel and isolated agent |
| `scripts/run_one.sh` | Independent built-in Pi no-cache launcher | Stock Docker path; does not automatically use the tested custom adapters/overlay |
| `scripts/prepare_task.py` | Copy official task to a separate directory | Implement/review variant manually; copying alone changes no setup behavior |
| `scripts/check_trial.py` | Numeric reward check | Combine with Pi/backend checks; it does not detect all agent failures |
| `vendor/deep-swe/tasks/clack-async-autocomplete-options/` | Original smoke task | Keep original pristine; inspect Dockerfile, task.toml and instruction.md |
| `vendor/pi/packages/agent/src/agent-loop.ts` | Inspected Pi 1.4 dispatch source | Understand actual execution and sequential settings before instrumenting |
| `docs/integration-plan.md` | Future cache integration design | Background only; do not block characterization on B/C cache implementation |

Flat files such as `parallel_tvcache/trace.py` are compatibility shims. Edit canonical subpackages. `archive/nersc-harness/` and `parallel_tvcache/legacy/` are obsolete remote-agent experiments, not the active deployment.

## 4. Recommended implementation order

1. **Re-establish a tool-capable uncached pilot.**
   - Choose a real coding model; Qwen3.8-27B is only a proposed candidate, not validated deployment here.
   - Verify available GPU memory, model revision, supported vLLM/tool parser, context window and generation limits. Do not blindly substitute the model name in one file.
   - Update the server helper, relay model checks/defaults and Pi model metadata consistently.
   - Validate actual sandbox inference, then run one unmodified task. Inspect model responses, real tool calls, final artifacts and the authoritative verifier.
   - Reward 0 is acceptable. Do not force tool calls or search for passing answers. A successful zero-call response remains a valid observed outcome; keep it in the manifest. A coding model should demonstrate real tool use before scaling the campaign.

2. **Create the handout's research task variant.**
   - Copy the task; move repo clone/build/dependency setup from the agent image into the agent instructions/actions. Preserve the base commit and isolate future history/solutions.
   - Keep the verifier authoritative and separate. Preserve final patch collection (this task collects committed changes with `git diff BASE HEAD`).
   - The original task disables agent networking. Resolve permitted source/package access with the advisor; do not silently open arbitrary internet access just to clone/install.
   - Pin the base image and variant definition. Merely adding setup instructions to the already-prepared official image does not implement the requirement.

3. **Add manifest-driven collection and real timing.**
   - Record benchmark/task/variant, attempt/session identity, model revision/settings, image digest, Pi/Harbor versions and run purpose.
   - Separate smoke tests, synthetic fixtures, NOP controls, infrastructure errors and research attempts. Preserve every outcome and exclusion reason.
   - Add timing at actual tool `execute` entry/exit using the same monotonic clock. Retain tool/arguments, call ID, turn ID, attempt/task and error/cancellation status. Use `hit=false` / cache mode `none` for uncached runs.
   - Pi dispatch/preparation `tool_execution_start` events are not sufficient to establish actual overlap. Use a pass-through wrapper/extension that awaits the original implementation and preserves results, errors, cancellation and scheduling.
   - Do not edit installed Harbor globally. Prefer a versioned optional adapter/extension in the repo.

4. **Generate the characterization outputs.**
   - Start with a small predeclared pilot subset and budget; choose final scale after checking cost and trace quality.
   - Export CSV/JSON table data and CDF plots. Preserve raw sessions/events for reanalysis.
   - Report task/attempt/turn counts, model/variant, exclusions and aggregation weighting alongside the figures.
   - Report observed lack of parallel calls honestly. Do not hardcode batches or alter tasks based on whether they produce desired parallelism.

## 5. Measurement conventions and current parser hazards

- Current turn = each saved assistant message, including valid final zero-call messages.
- Overall parallel-turn fraction = turns with >1 emitted call / all assistant turns.
- Current per-tool rows count calls of that type over the same all-turn denominator, including absent-tool turns. A read+bash turn is not a multi-read turn. Confirm this convention with Bhaskar; label it explicitly.
- The parser scans arbitrary `.jsonl` files recursively, counts assistant error messages, ignores malformed lines, and does not resolve session branch ancestry. Do not run it on all `jobs/` and treat that as a clean dataset. Add explicit attempt/session selection and audit branches/duplicates before scaling.
- A zero-call trial is not automatically an infrastructure failure. Classify using backend/agent status and retain valid zero-call trials; exclude controls and wrong-model/variant smoke runs by run purpose.
- Distinguish emitted multi-call turns from actual concurrent execution. Compute wall-clock overlap from execute intervals; summing call durations overstates wall time.

## 6. NERSC and runtime constraints

- **Use only m4999 project GPU credits.** Latest authorization supersedes earlier ntrain5 use. Request `--account=m4999 --constraint=gpu`; prior GPU jobs were recorded as `m4999_g`. Verify current association/balance before spending.
- SSH alias: `perlmutter`; user/identity are local-only (see ignored private notes). Renew with `sshproxy` locally if expired. Never collect password/MFA/key contents in chat.
- Remote root: set `SYSML_REMOTE_ROOT` (example shape `/pscratch/sd/<letter>/<user>/sysml_parallel_tvcache`); model environment: `env-model`; cached weights: `hf-cache`.
- Proven allocation shape: 1 GPU, 32 logical CPUs, 56G memory, shared_interactive, 20-minute maximum. Request once; avoid duplicate pending/running jobs and release owned jobs promptly.
- Keep NERSC inference-only. Mac runs Harbor/Pi/task/verifier containers.
- Runtime: vLLM 0.31.0, torch 2.13.0+cu130. FlashInfer flock failed on shared home. The working helper uses node-local JIT caches and `VLLM_USE_FLASHINFER_SAMPLER=0`. Preserve and document this until retested.
- Valid vLLM option: `--default-chat-template-kwargs`, not `--chat-template-kwargs`.
- Model API uses a private key. Mac loopback SSH forwarding feeds a Docker gateway; task uses a read-only named-volume Unix socket and local relay. Never assume the Mac tunnel alone makes inference reachable from a no-network task.
- Ignored `.local-smoke/` may contain credentials and old compose overlays. Do not print or commit secrets. Old overlay volume names need fresh resources, not literal reuse.
- `results/`, `jobs/`, `vendor/` are ignored. Preserve evidence/checkouts; do not delete them during cleanup or publish them wholesale.

## 7. Safe commands to start in Cursor

From the workspace root:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/analyze_trace.py fixtures/pi_session.jsonl --benchmark synthetic-fixture
.venv/bin/python scripts/check_trial.py jobs/m4999-pi-60365877
.venv/bin/python scripts/analyze_trace.py jobs/m4999-pi-60365877 \
  --benchmark DeepSWE --output results/cursor-smoke-analysis.json
```

The fixture is synthetic; the real smoke is a zero-call attempt. Neither is a research characterization campaign. Socket tests need local loopback permission. No GPU job starts from these commands.

For live smoke reproduction, read `results/M4999_REAL_SMOKE_TEST.md`; adapt its node/port/volume names to a new allocation and preserve all no-network checks. Ordinary `scripts/run_one.sh` alone will not recreate the successful custom-adapter/bridge setup.

## 8. First completion checkpoint

A useful first Cursor deliverable is: one correctly graded uncached tool-using pilot; an explicit run manifest; actual tool timing JSONL; and a table/CDF export from selected real sessions. Keep the original smoke path working and record exact commands/results/blockers in `results/LOCAL_SMOKE_TEST.md`. Do not claim full characterization or parallel execution from source inspection or synthetic tests.
