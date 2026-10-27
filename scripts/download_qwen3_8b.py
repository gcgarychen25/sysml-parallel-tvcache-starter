#!/usr/bin/env python3
"""Download Qwen/Qwen3-8B into a Hugging Face cache. No GPU required.

Set SYSML_REMOTE_ROOT to the NERSC project directory (or any writable root).
Example: export SYSML_REMOTE_ROOT=/pscratch/sd/<letter>/<user>/sysml_parallel_tvcache
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

path = snapshot_download(repo_id="Qwen/Qwen3-8B")
print("DOWNLOADED", path, flush=True)
print("REVISION", Path(path).name, flush=True)
