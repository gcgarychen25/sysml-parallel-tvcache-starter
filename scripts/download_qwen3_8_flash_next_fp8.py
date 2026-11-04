#!/usr/bin/env python3
"""Download Qwen/Qwen3.8-Flash-Next-FP8 into a Hugging Face cache. No GPU required.

BF16 Flash-Next will not fit 4×A100-40GB; FP8 is the official smaller checkpoint
(~250 GB recipe VRAM — still tight on 160 GB; fit-check with shorter max_model_len
or more GPUs if OOM).

Set SYSML_REMOTE_ROOT before running on a node that can reach Hugging Face.
"""
from pathlib import Path
import os
import sys

root = os.environ.get("SYSML_REMOTE_ROOT", "").strip()
if not root:
    print("Set SYSML_REMOTE_ROOT to the remote project directory before downloading.", file=sys.stderr)
    raise SystemExit(2)
ROOT = Path(root)
os.environ["HF_HOME"] = str(ROOT / "hf-cache")

from huggingface_hub import snapshot_download

repo = os.environ.get("SYSML_HF_REPO", "Qwen/Qwen3.8-Flash-Next-FP8").strip()
path = snapshot_download(repo_id=repo)
print("DOWNLOADED", path, flush=True)
print("REVISION", Path(path).name, flush=True)
print("REPO", repo, flush=True)
