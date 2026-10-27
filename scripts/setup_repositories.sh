#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor
mkdir -p results
clone_if_missing() {
  local url="$1" dir="$2"
  if [[ -d "$dir/.git" ]]; then echo "Already cloned $dir"; return; fi
  git clone --depth 1 "$url" "$dir"
}
clone_if_missing https://github.com/datacurve-ai/deep-swe.git vendor/deep-swe
clone_if_missing https://github.com/abhivijay96/tvcache-rust.git vendor/tvcache-rust
clone_if_missing https://github.com/abhivijay96/tvclient.git vendor/tvclient
for dir in vendor/deep-swe vendor/tvcache-rust vendor/tvclient; do
  echo "$dir $(git -C "$dir" rev-parse HEAD)"
done | tee results/commit-versions.txt
