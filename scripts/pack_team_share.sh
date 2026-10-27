#!/usr/bin/env bash
# Build a teammate-safe archive: source + configs + tests, no secrets/vendor/jobs/results.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROOT/dist"
out="${1:-$ROOT/dist/sysml_parallel_tvcache_team_share_$stamp.tar.gz}"
staging="$ROOT/.share-staging"
rm -rf "$staging"
mkdir -p "$staging/sysml_parallel_tvcache_starter"

# Fail closed if secret-looking files would be copied.
if [[ -e .local-smoke/gateway.env || -e .local-smoke/model-api-key ]]; then
  echo "Note: .local-smoke secrets exist locally and will be excluded." >&2
fi

rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.uv-cache' \
  --exclude '.cargo-cache' \
  --exclude '.local-smoke' \
  --exclude '.pytest_cache' \
  --exclude '.share-staging' \
  --exclude 'dist' \
  --exclude 'vendor' \
  --exclude 'jobs' \
  --exclude 'results' \
  --exclude 'logs' \
  --exclude '*.egg-info' \
  --exclude '__pycache__' \
  --exclude '.env' \
  --exclude '*.log' \
  --exclude '**/secrets' \
  --exclude '*api-key*' \
  ./ "$staging/sysml_parallel_tvcache_starter/"

# Ensure ignored dirs have keepers so structure is obvious.
mkdir -p "$staging/sysml_parallel_tvcache_starter/vendor" \
         "$staging/sysml_parallel_tvcache_starter/jobs" \
         "$staging/sysml_parallel_tvcache_starter/results"
[[ -f vendor/.gitkeep ]] && cp vendor/.gitkeep "$staging/sysml_parallel_tvcache_starter/vendor/"
printf '%s\n' 'Private locally; re-create with harbor runs.' > "$staging/sysml_parallel_tvcache_starter/jobs/README.md"
printf '%s\n' 'Private locally; share only agreed characterization exports.' > "$staging/sysml_parallel_tvcache_starter/results/README.md"

tar -C "$staging" -czf "$out" sysml_parallel_tvcache_starter
rm -rf "$staging"
# Sanity: archive must not contain secret filenames (allow configs/example.env).
if tar -tzf "$out" | grep -E '(^|/)\.local-smoke/|(^|/)gateway\.env$|(^|/)model-api-key$|(^|/)\.env$' >/dev/null; then
  echo "Refusing: archive contains secret-like paths" >&2
  rm -f "$out"
  exit 1
fi
echo "WROTE $out"
ls -lh "$out"
