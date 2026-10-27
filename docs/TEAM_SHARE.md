# Sharing this repo with teammates

## Do not zip the whole working directory

A raw folder copy can include secrets and private evidence:

| Path | Why exclude |
| --- | --- |
| `.local-smoke/` | API keys / gateway env |
| `.env` | credentials |
| `jobs/`, `results/` | personal run evidence (share only agreed exports) |
| `vendor/` | large checkouts; run `scripts/setup_repositories.sh` |
| `.venv/`, caches | machine-local |

## Safe ways to share

```bash
# Option A: teammate-safe tarball (recommended for Slack/Drive)
bash scripts/pack_team_share.sh
# writes ../sysml_parallel_tvcache_team_share_<timestamp>.tar.gz

# Option B: git (after git init + first commit of non-secret files)
git status   # confirm .local-smoke, jobs, results, vendor are ignored
```

## Start here for the model-comparison pilot

1. Read [configs/characterization-pilot-v1.md](../configs/characterization-pilot-v1.md)
2. Copy `configs/example.env` → `.env` (local only)
3. `uv venv && uv pip install -e '.[dev]' && bash scripts/setup_repositories.sh`
4. Match fixed knobs: Harbor 0.24.0, Pi 1.4.0, thinking off, max_turns 50, temp 0.7, top_p 0.9, 5 attempts × 3 tasks

## Placeholders each person fills locally

- Model id string
- Inference endpoint / API key (never commit)
- NERSC `SYSML_REMOTE_ROOT` and Slurm `--account=...` (Gary only for 9B)
- Fresh tunnel/volume/job names per allocation
