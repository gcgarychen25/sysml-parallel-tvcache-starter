# CS5470 SYSML — Team 39: Parallel Tool-Value Cache

**Starter code (October 2026).** Target: DeepSWE v1.1 + official Harbor + Pi + vLLM model + assigned Rust TVCache / Python `tvclient`.

> Current evidence: a real uncached Harbor + Pi run using m4999-hosted Qwen3-0.6B completed with reward 0 and no Harbor exception. The model made zero tool calls, so tool execution, parallelism, and Rust TVCache integration remain unvalidated. See `results/M4999_REAL_SMOKE_TEST.md` for the actual run and its limitations.

**Teammates:** start with [docs/TEAM_SHARE.md](docs/TEAM_SHARE.md) and the shared pilot [configs/characterization-pilot-v1.md](configs/characterization-pilot-v1.md). Do not zip this folder wholesale (secrets live under `.local-smoke/`). Use `bash scripts/pack_team_share.sh`.

For Cursor handoff on the NERSC/Mac path, see [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md) (ops notes; keep credentials local).

## Folder map

```text
parallel_tvcache/
  measurement/     A: trace characterization and reward inspection
  evaluation/      B: Harbor/Pi environment adapters
  inference/       Shared model-only transport
  cache/           C/D: standalone design prototype (not Rust integration)
  legacy/          Superseded remote Podman adapter
scripts/           Stable command-line entry points
configs/           Runtime configuration and gateway Dockerfile
vendor/            Assigned upstream Rust server / Python client (ignored)
tests/, fixtures/  Tests and synthetic inputs
archive/           Superseded remote harness scripts
proposals/, docs/   Proposal, design, implementation status
jobs/, results/    Preserved private experiment evidence (ignored)
```

See [codebase ownership and entry points](docs/codebase-map.md). Flat Python module names remain compatibility shims; new code uses the subpackages above.

## 1. Prerequisites

- A macOS/Linux host with Docker daemon running (Linux is preferable for strict no-network enforcement). DeepSWE container images can be large.
- Python 3.12+ and `uv`, `git`, network access, and model API key or reachable vLLM endpoint.
- Install a current Harbor version that has `-a pi`, separate verifier mode and `[[verifier.collect]]`; confirm `harbor run --help`, `harbor agent list`, `harbor agent schema pi` locally.
- Read `https://github.com/datacurve-ai/deep-swe` task licensing and validator policy.

## 2. Installation

```bash
uv venv && source .venv/bin/activate
uv pip install -e '.[dev]'
uv tool install harbor       # if already installed, consider `uv tool upgrade harbor`
bash scripts/setup_repositories.sh
cp configs/example.env .env
# edit MODEL and any endpoint flags; keep credentials in your shell, not git
python scripts/preflight.py --task-id clack-async-autocomplete-options --model "$MODEL"
```

If using a provider directly, `MODEL=openai/<your-model>` and export `OPENAI_API_KEY` before launching.

For a local or remote OpenAI-compatible vLLM server, set the model slug, `HARBOR_MODEL_BASE_URL` (reachable **from inside Docker**), `HARBOR_MODEL_API_KEY_NAME=OPENAI_API_KEY`, `HARBOR_PI_MODEL_API=openai-completions`, and export `OPENAI_API_KEY=EMPTY` if no authentication. The launcher currently maps custom endpoints through the `openai/` provider using `OPENAI_BASE_URL` and `OPENAI_API_KEY` (Harbor 0.24.0); other provider mappings need explicit validation. Set `PI_VERSION` to pin the agent release. Endpoint reachability and task network policy still need runtime verification.

## 3. One-task real evaluation (no cache)

```bash
bash scripts/run_one.sh
python scripts/inspect_rewards.py jobs
python scripts/check_trial.py jobs   # requires a numeric verifier reward
python scripts/analyze_trace.py jobs --output results/pi-trace.json
```

The task is `clack-async-autocomplete-options`. It is an actual DeepSWE v1.1 task. The script uses `harbor run -p <local task> -a pi -m <model> -k 1 -n 1` and stores artifacts under `jobs/`.

**Interpretation:** first demand that Harbor runs agent *and verifier* without an infrastructure error. A completed trial with reward=0 is still a correct grading run; it does not prove model success. Inspect `reward.json`/`result.json`, verifier logs, and the Pi session. If it fails, the `CODEX_PROMPT.md` explicitly asks Codex to diagnose before switching runners.

**Caveat:** this first smoke uses the *official unmodified* DeepSWE image. The assignment also requires an experiment variant that moves environment setup from the image into agent-controlled tool calls. Make a copy with `python scripts/prepare_task.py <task-id>` and update it after the baseline passes.

## 4. Local tests and prototype

```bash
python -m pytest -q
python scripts/demo_cache.py
python scripts/analyze_trace.py fixtures/pi_session.jsonl
```

The prototype demonstrates full/partial hits, ID remapping, concurrent duplicate suppression and conservative state-aware cache invalidation. It **deliberately bypasses mutating calls**, which is NOT a substitute for production TVCache sandbox snapshot/fork support.

## 5. Research work still needed

Read `docs/architecture.md`. Next, integrate the assigned Rust server and Python client with Pi's tool execution path. The Pi harness is in TypeScript and the assigned client is Python; do not mistake an event-only trace extension for a working cache interception mechanism. The final system must preserve true parallel execution, side effects, sandbox state, and IDs across partial cache hits. The final evaluation must compare A (no cache), B (existing single-call TVCache), C (parallel-aware TVCache) and measure pass@1/pass@5 and actual tool-wait saved.

## References

- Handout: `docs/project_assignment.pdf` (copied from the supplied file)
- https://github.com/abhivijay96/tvcache-rust
- https://github.com/abhivijay96/tvclient
- https://github.com/TVCache/TVCache (original Python example)
- https://github.com/harbor-framework/harbor
- https://github.com/earendil-works/pi
- https://github.com/datacurve-ai/deep-swe

## Smoke-test evidence and integration design

See `results/LOCAL_SMOKE_TEST.md` for the local/NERSC commands, provenance and observed blockers, and [docs/integration-plan.md](docs/integration-plan.md) for the proposed Pi-to-Python bridge and snapshot requirements. Superseded NERSC harness scripts are archived under `archive/nersc-harness/`. The active deployment uses NERSC only for model inference and local Docker for the harness/verifier. The loopback adapter is separate from the ordinary built-in Pi launcher; consult the report for what actually executed.

## Proposal and implementation status

See [the proposal/code alignment review](docs/proposal-code-alignment.md) for the final tentative deliverables, implemented support, and remaining work. The trace analyzer now exports per-tool CDF data and emitted-call parallel-turn fractions with an explicit denominator. Use `--benchmark DeepSWE` on a directory containing only that benchmark’s intended Pi sessions. This does not measure execution overlap or produce benchmark evidence from fixtures.
