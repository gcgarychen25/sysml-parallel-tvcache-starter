#!/bin/bash
#SBATCH --account=ntrain5
#SBATCH --constraint=cpu
#SBATCH --qos=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --job-name=sysml-nop
set -euo pipefail
cd "$SCRATCH/sysml_parallel_tvcache"
export PATH="$PWD/env/bin:$PWD/bin:$PATH"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
# Use this allocation's node-local storage; do not modify user Podman config.
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
cleanup() {
  podman ps -a --format '{{.ID}}' > "logs/nop-${SLURM_JOB_ID}-remaining-containers.txt" || true
}
trap cleanup EXIT
hostname
harbor --version
podman info --format '{{.Host.Security.Rootless}}'
harbor run -p deep-swe/tasks/clack-async-autocomplete-options -a nop -k 1 -n 1 --env parallel_tvcache.nersc_podman:NerscPodmanEnvironment --jobs-dir jobs --job-name "nop-${SLURM_JOB_ID}" --yes
