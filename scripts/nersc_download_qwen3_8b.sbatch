#!/bin/bash
#SBATCH --qos=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --job-name=sysml-hf-dl
# Submit with: sbatch --account=PLACEHOLDER_ACCOUNT nersc_download_qwen3_8b.sbatch
# Requires SYSML_REMOTE_ROOT in the environment (export before sbatch, or use --export).
set -euo pipefail
umask 077
: "${SYSML_REMOTE_ROOT:?Set SYSML_REMOTE_ROOT to your NERSC project directory}"
cd "$SYSML_REMOTE_ROOT"
mkdir -p logs
# CPU-only download: does not request GPUs.
env-model/bin/python scripts/download_qwen3_8b.py
du -sh hf-cache/hub/models--Qwen--Qwen3-8B hf-cache/hub/blobs
