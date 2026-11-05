# TMax easy (short + bash-only)

Local Harbor **task** extracts from Hugging Face [`TMaxxx/TMax-15K-Harbor`](https://huggingface.co/datasets/TMaxxx/TMax-15K-Harbor) (`tasks.zip`), filtered to **short task** + **bash-only**.

This is a **task suite**, not a harness. Cells **T1/T2** run these folders with stock Harbor **`LoopbackPi`** (`SYSML_HARBOR_AGENT=pi`) — same agent path as Exp A DeepSWE cells; only the benchmark folders change. Not Mini-SWE; not Multitool.

- Task lists: `configs/experiment-tasks-tmax-easy1.txt` · `…-easy10.txt` · `…-easy8.txt` (valid T2 subset)
- Env: `configs/models/qwen3.8-27b-tmax-easy-pi.env.example` (T1) · `…-tmax-easy10-pi.env.example` (T2)
- Write-up: `docs/workload_characterization_report.md` cells **T1/T2**
- Local evidence: `results/characterization/tmax-qwen38-27b-easy{1,10}-t100-xh/`

```bash
set -a && source configs/models/qwen3.8-27b-tmax-easy10-pi.env.example && set +a
export SYSML_NERSC_USER=<user>
export SYSML_REMOTE_ROOT=/pscratch/sd/<letter>/<user>/sysml_parallel_tvcache
bash scripts/run_experiment.sh none   # stock LoopbackPi; do not pass --parallel-test
```
