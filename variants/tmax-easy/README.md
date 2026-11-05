# TMax easy (short + bash-only)

Local Harbor extracts from Hugging Face [`TMaxxx/TMax-15K-Harbor`](https://huggingface.co/datasets/TMaxxx/TMax-15K-Harbor) (`tasks.zip`), filtered to **short task** + **bash-only**.

- Task lists: `configs/experiment-tasks-tmax-easy1.txt` · `…-easy10.txt` · `…-easy8.txt` (valid T2 subset)
- Env: `configs/models/qwen3.8-27b-tmax-easy10-pi.env.example`
- Results: `docs/workload_characterization_report.md` cells **T1/T2**

```bash
set -a && source configs/models/qwen3.8-27b-tmax-easy10-pi.env.example && set +a
export SYSML_NERSC_USER=<user>
export SYSML_REMOTE_ROOT=/pscratch/sd/<letter>/<user>/sysml_parallel_tvcache
bash scripts/run_experiment.sh none   # stock LoopbackPi; do not pass --parallel-test
```
