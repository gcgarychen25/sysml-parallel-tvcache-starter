# Code ownership and layout

| Proposal area | Canonical location | Responsibility / status |
| --- | --- | --- |
| A: Measurement and experiments | `parallel_tvcache/measurement/` | Pi trace statistics and reward artifact inspection. Real timing instrumentation and A/B/C aggregation remain future work. |
| B: Shared runner and baselines | `parallel_tvcache/evaluation/`, `scripts/run_one.sh` | Harbor environment/Pi adapters; uncached launcher. Existing Rust-cache integration remains unimplemented. |
| Shared inference | `parallel_tvcache/inference/`, `configs/` | Model-only transport; NERSC is inference only. Transport defaults remain for the small-model smoke. |
| C/D: Cache design prototype | `parallel_tvcache/cache/` | In-memory read-only prototype only; not production integration. |
| C: Assigned Rust implementation | `vendor/tvcache-rust/` | Upstream checkout. Parallel protocol/storage work is not implemented. |
| D: Assigned Python client | `vendor/tvclient/` | Upstream checkout. Pi bridge and state/snapshot integration remain to implement. |
| Superseded remote harness | `archive/nersc-harness/`, `parallel_tvcache/legacy/` | Historical NERSC Podman attempts; not the active workflow. |
| Tests and example inputs | `tests/`, `fixtures/` | Unit tests and explicitly synthetic sessions. |
| Research artifacts | `jobs/`, `results/` | Preserved evidence; ignored by Git. Never treat fixtures or NOP controls as agent benchmark results. |
| Project planning | `proposals/`, `docs/` | Proposal, architecture, integration plan, and implementation gap audit. |

## Boundaries

- Measurement consumes saved events/artifacts; it does not start agents or import Harbor.
- Evaluation controls task execution and official verification. Optional Harbor adapters are not imported by package initialization.
- Inference forwards model API traffic. It does not execute tools or implement tool-value caching.
- Cache prototype depends on neither Harbor nor inference. It cannot substitute for the assigned Rust server/client.
- Production server/client interfaces should be agreed by B/C/D before implementation; no placeholder adapter silently claims to implement cached modes.

## Stable entry points

Run from the repository root:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/analyze_trace.py fixtures/pi_session.jsonl --benchmark synthetic-fixture
.venv/bin/python scripts/inspect_rewards.py jobs
.venv/bin/python scripts/demo_cache.py
bash scripts/run_one.sh
```

The final command requires a configured model and a working Docker environment. The synthetic analysis/demo commands do not evaluate DeepSWE. Python scripts now locate the source checkout directly without requiring PYTHONPATH.

Canonical optional Harbor class paths:

- `parallel_tvcache.evaluation.docker_disconnect:DockerDisconnectEnvironment`
- `parallel_tvcache.evaluation.loopback_pi:LoopbackPi`

Old flat imports and the old `python -m parallel_tvcache.model_transport` entry point remain compatibility shims for existing commands and job configurations. New code uses the canonical subpackages. The transport file copied into containers is the self-contained `inference/model_transport.py`, not its shim.

## Cleanup policy for this refactor

No experiment logs, jobs, credentials, upstream checkouts, virtual environments, or user files were deleted. Superseded helpers were moved and labeled. Old module files contain only compatibility imports. Generated caches remain ignored; removing them offers no architectural benefit and is unnecessary for using the codebase.
