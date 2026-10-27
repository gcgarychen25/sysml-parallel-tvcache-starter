# Copy and paste this prompt into Codex on your laptop

You are working in this repository: `sysml_parallel_tvcache_starter` for Cornell CS5470 Team 39.

**Goal:** PROVE, with real local execution and saved evidence, whether current official Harbor + its built-in Pi adapter can run one DeepSWE v1.1 task and correctly invoke its verifier. Then establish baseline tool-call traces and prepare the architecture for the assigned Rust TVCache integration. The goal of this task is a reliable, minimal baseline smoke test—not inventing a caching speedup or training a model.

Please read `README.md`, `docs/architecture.md`, `scripts/run_one.sh`, `docs/project_assignment.pdf`, and `parallel_tvcache/*` before acting. The official project assigns `abhivijay96/tvcache-rust` and `abhivijay96/tvclient`, NOT the original Python TVCache server.

## Stage 0 — local validation (no model API charges)

1. Inventory OS/architecture, available RAM and disk, `docker version`/daemon, `git`, `uv`, `python`, `harbor`, `node`, and whether an inference endpoint or API key is configured. Do not print or commit any secrets.
2. Run `python -m pytest -q`, `python scripts/demo_cache.py`, and `python scripts/analyze_trace.py fixtures/pi_session.jsonl`. Fix test failures before proceeding.
3. Check current local Harbor documentation with `harbor run --help`, `harbor agent list`, and `harbor agent schema pi`. Adjust `scripts/run_one.sh` for the installed CLI version where necessary. Do not silently replace Harbor with Pier.
4. Clone or update the three source repositories with `bash scripts/setup_repositories.sh`, recording actual commit hashes and versions. Verify the chosen DeepSWE task has `task.toml`, `instruction.md`, and a verifier definition, including `[[verifier.collect]]` and separate verifier environment.
5. Check that DeepSWE's `allow_internet = false` / `network_mode = no-network` policy and your local Docker configuration permit Pi's installation and inference endpoint. On macOS Docker Desktop, network restrictions might require a Linux runner. Report rather than silently disabling benchmark isolation.

## Stage 1 — choose a runnable model endpoint

Prefer an already configured endpoint/account. Prompt me if needed for a model ID or authorization, and do not assume a public OpenAI API key or A100 machine exists. For a vLLM server, verify reachability **from the Docker sandbox**, not only from the host. Set `MODEL=provider/model-id`, `HARBOR_MODEL_BASE_URL`, `HARBOR_MODEL_API_KEY_NAME`, `HARBOR_PI_MODEL_API=openai-completions` as required by the Harbor Pi adapter (check actual installed source and `harbor agent schema pi`). Avoid exposing keys in logs. If local machine is only an M1 Pro with 16 GB, don't try to run a large coding LLM locally; use an available API or an actual remote vLLM endpoint, with my approval for possible API charges.

## Stage 2 — the REAL one-task DeepSWE evaluation

1. Start with `clack-async-autocomplete-options` from official DeepSWE v1.1 **unmodified**, to isolate environment/verifier compatibility from our research task modifications.
2. Run `python scripts/preflight.py --task-id "$TASK_ID" --model "$MODEL"`, then `bash scripts/run_one.sh` with one task, one trial, concurrency one, Pi agent and Harbor's Docker environment.
3. Inspect the Harbor job status, `result.json`, the verifier's `reward.json`, grader stdout, and Pi's saved `pi/sessions/*.jsonl` trajectory. A reward of 0 is a *graded attempted task* (agent did not solve it), not a harness or verifier failure. No `reward.json` or infrastructure error means the integration has NOT been validated.
4. If the run fails, diagnose the precise root cause and fix only repository scripts/config/adapter compatibility necessary for this test. Do not alter hidden verifier tests to force a pass, do not use reference solution as the agent's answer, and do not claim successful grading without evidence.
5. If resources are available, also run a `harbor run ... -a nop` negative-control trial using the same task to test the verifier workflow (and optionally `oracle` only if allowed by the benchmark's policy; keep any reference solution isolated from the agent). Confirm negative-control reward is 0 rather than treating task completion as success.
6. Run `python scripts/check_trial.py jobs` to require a numeric reward. Parse Pi session traces via `python scripts/analyze_trace.py jobs --output results/pi-trace.json`. Confirm multiple tool-call objects in an assistant message, and independently check whether tool execution actually overlaps in time. `>1` tool call in a message alone does NOT prove concurrency. If the current model rarely emits parallel calls, report it; do not fabricate or hard-code a transcript.

## Stage 3 — first steps toward TVCache integration (after Stage 2)

1. Inspect both assigned source repos (Rust server and Python `tvclient`). Note `TvcacheToolExecutor.lookup_or_execute(history)` expects cumulative sequential history and its sandbox abstraction needs real snapshot/fork support.
2. Map Harbor's Pi tool dispatch and sandbox lifecycle. Decide the smallest bridge between Pi (TypeScript) and the Python TVCache client without accidentally running tools on the laptop instead of the per-task Docker environment. A custom tool wrapper / agent adapter may be necessary. Pi's `tool_call` extension hook can block or modify input but cannot, by itself, return a successful cached tool output; do NOT claim that trace-only hooks implement caching.
3. Write a concrete integration plan (files to modify, call/response schema, call-ID mapping, environment state identity, stable sandbox snapshots, partial-hit semantics, in-flight dedup, concurrency policy for mutating calls). Implement a minimal real sequential Rust-backed lookup if time and resources allow, with tests. Keep the uncached baseline unchanged and the cache mode explicitly off by default.
4. The standalone `parallel_tvcache/prototype.py` is only a mock read-only model. Do not present its hit rate as a real DeepSWE benchmark result or as the complete professor-assigned server/client extension.

## Stage 4 — deliver your report

Create `results/LOCAL_SMOKE_TEST.md` with a table containing:

- Exact commit SHA and versions: Harbor, Pi, DeepSWE, Rust TVCache, Python `tvclient`.
- OS, Docker daemon/version, endpoint category (no secrets), selected task ID and task image.
- Commands you actually ran, exit codes, key errors, and paths to logs.
- Did Pi launch? Did model calls succeed? Did tool calls execute? Did verifier run? Is a valid numeric reward present? Did any trial solve the task? Did parallel calls actually appear/overlap? Distinguish these questions.
- Remaining work to complete A no cache / B original TVCache / C parallel-aware TVCache and the handout's setup-as-agent-actions requirement.

Stop if you are blocked by missing credentials, inaccessible hardware, Docker limitations, or tasks requiring substantial paid API usage. Report the exact blocker and the next runnable command rather than guessing or claiming completion. Do not modify reference verifier tests, do not weaken network/isolation just to get a green result, and never commit `.env`, secret material, task outputs, or huge model weights.

Make improvements directly in the starter repository, run unit tests after each meaningful change, and return a concise summary of changes plus `results/LOCAL_SMOKE_TEST.md`.
