#!/bin/bash
#SBATCH --account=ntrain5
#SBATCH --constraint=gpu
#SBATCH --qos=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=1
#SBATCH --mem=56G
#SBATCH --time=00:20:00
#SBATCH --job-name=sysml-model-smoke
set -euo pipefail
umask 077
cd "$SCRATCH/sysml_parallel_tvcache"
export PATH="$PWD/env/bin:$PWD/bin:$PATH"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export HF_HOME="$PWD/hf-cache"
export HF_HUB_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export DO_NOT_TRACK=1
store_dir="${TMPDIR:-/tmp}/sysml-${USER}-${SLURM_JOB_ID}"
mkdir -p "$store_dir/graph" "$store_dir/run"
cat > "$store_dir/storage.conf" <<EOF
[storage]
driver = "vfs"
runroot = "$store_dir/run"
graphroot = "$store_dir/graph"
EOF
export CONTAINERS_STORAGE_CONF="$store_dir/storage.conf"
# NERSC defaults unqualified names to registry.suse.com. Preserve Harbor's
# intended Docker Hub image and its exact digest; do not change the image.
cat > "$store_dir/registries.conf" <<'REGISTRIES'
unqualified-search-registries = ["docker.io"]
short-name-mode = "enforcing"
[aliases]
"gogost/gost" = "docker.io/gogost/gost"
"alpine" = "docker.io/library/alpine"
REGISTRIES
export CONTAINERS_REGISTRIES_CONF="$store_dir/registries.conf"
export PODMAN_COMPOSE_PROVIDER="$PWD/env/bin/podman-compose"
model_pid=''
broker_pid=''
cleanup() {
  if [[ -n "$broker_pid" ]]; then kill "$broker_pid" 2>/dev/null || true; fi
  if [[ -n "$model_pid" ]]; then kill "$model_pid" 2>/dev/null || true; fi
  podman ps -a --format '{{.ID}}' > "logs/gpu-${SLURM_JOB_ID}-remaining-containers.txt" || true
}
trap cleanup EXIT
hostname
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
# First establish the sandbox/verifier path before model initialization.
harbor run -p deep-swe/tasks/clack-async-autocomplete-options -a nop -k 1 -n 1 \
  --env parallel_tvcache.nersc_podman:NerscPodmanEnvironment --jobs-dir jobs --job-name "nop-${SLURM_JOB_ID}" --yes
env/bin/python - "$SLURM_JOB_ID" <<'PYREWARD'
import json, math, sys
from pathlib import Path
paths=list(Path('jobs/nop-'+sys.argv[1]).rglob('reward.json'))
assert len(paths)==1, f'Expected one negative-control reward, got {paths}'
r=json.loads(paths[0].read_text()).get('reward')
assert isinstance(r,(int,float)) and not isinstance(r,bool) and math.isfinite(r) and r==0, r
print('NEGATIVE_CONTROL_GRADED_ZERO', paths[0])
PYREWARD
# Stack diagnostics only for this model process and its children.
mkdir -p "$store_dir/diagnostics"
cat > "$store_dir/diagnostics/sitecustomize.py" <<'PYDIAG'
import faulthandler, signal
faulthandler.register(signal.SIGUSR1, all_threads=True)
PYDIAG
export PYTHONPATH="$store_dir/diagnostics:$PWD${PYTHONPATH:+:$PYTHONPATH}"
# Loopback only: not an unauthenticated public model endpoint.
model_launcher=()
if [[ -z "${SLURM_STEP_ID:-}" ]]; then model_launcher=(srun --cpu-bind=none); fi
"${model_launcher[@]}" env-model/bin/vllm serve Qwen/Qwen3-0.6B \
  --host 127.0.0.1 --port 18080 --served-model-name Qwen/Qwen3-0.6B \
  --max-model-len 8192 --max-num-seqs 1 --gpu-memory-utilization 0.3 \
  --enforce-eager --enable-auto-tool-choice --tool-call-parser hermes \
  --default-chat-template-kwargs '{"enable_thinking":false}' \
  > "logs/vllm-${SLURM_JOB_ID}.log" 2>&1 &
model_pid=$!
ready=0
for i in $(seq 1 300); do
  if curl --fail --silent http://127.0.0.1:18080/v1/models > "logs/models-${SLURM_JOB_ID}.json"; then ready=1; break; fi
  kill -0 "$model_pid" 2>/dev/null || { tail -n 70 "logs/vllm-${SLURM_JOB_ID}.log"; exit 3; }
  if [[ "$i" == 90 || "$i" == 180 ]]; then
    env-model/bin/python - "$model_pid" <<'PYSTACK'
import psutil,signal,sys
from pathlib import Path
p=psutil.Process(int(sys.argv[1]))
for child in p.children(recursive=True)+[p]:
    try:
        if Path(child.exe()).name.startswith(('python','vllm')):
            child.send_signal(signal.SIGUSR1)
    except (psutil.NoSuchProcess,psutil.AccessDenied):
        pass
PYSTACK
  fi
  sleep 2
done
[[ "$ready" == 1 ]] || { tail -n 70 "logs/vllm-${SLURM_JOB_ID}.log"; exit 4; }
cat > "logs/model-request-${SLURM_JOB_ID}.json" <<'JSON'
{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Reply with the single word ready."}],"max_tokens":16,"temperature":0,"stream":false}
JSON
curl --fail --silent --show-error http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' --data-binary "@logs/model-request-${SLURM_JOB_ID}.json" \
  > "logs/model-response-${SLURM_JOB_ID}.json"
# Resolve sandbox compatibility on the allocated node, without model task charges.

# Only proceed when the official negative control actually reaches verification.
# This transport is explicitly opt-in and does not alter run_one.sh or tools.
if [[ "${RUN_PI_SMOKE:-0}" == 1 ]]; then
  env/bin/python -m parallel_tvcache.model_transport host \
    --socket "$store_dir/model.sock" --backend-port 18080 \
    --records "model-records/$SLURM_JOB_ID" > "logs/broker-$SLURM_JOB_ID.log" 2>&1 &
  broker_pid=$!
  for i in $(seq 1 50); do
    [[ -S "$store_dir/model.sock" ]] && break
    sleep 0.1
  done
  [[ -S "$store_dir/model.sock" ]]
  env/bin/python - "$store_dir/model.sock" "$store_dir/model-compose.json" <<'PYCOMPOSE'
import json,sys
from pathlib import Path
Path(sys.argv[2]).write_text(json.dumps({'services': {'main': {'volumes': [
    {'type':'bind','source':sys.argv[1],'target':'/run/sysml-model.sock','read_only':False}
]}}}))
PYCOMPOSE
  export OPENAI_API_KEY=EMPTY
  export OPENAI_BASE_URL=http://127.0.0.1:18081/v1
  harbor run -p deep-swe/tasks/clack-async-autocomplete-options \
    -a parallel_tvcache.loopback_pi:LoopbackPi -m openai/Qwen/Qwen3-0.6B \
    --ak version=1.4.0 --ak model_api=openai-completions --ak thinking=off --ak max_turns=12 \
    -k 1 -n 1 --env parallel_tvcache.nersc_podman:NerscPodmanEnvironment --jobs-dir jobs --job-name "pi-$SLURM_JOB_ID" --yes \
    --extra-docker-compose "$store_dir/model-compose.json"
fi
