#!/usr/bin/env bash
# Start/stop host tool gateway (Unix socket → tvclient → tvcache-rust).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CACHE_DIR="${SYSML_TVCACHE_DIR:-$ROOT/results/tvcache}"
PID_FILE="$CACHE_DIR/tool-gateway.pid"
LOG_FILE="$CACHE_DIR/tool-gateway.log"
SOCK="${SYSML_TVCACHE_SOCK:-$CACHE_DIR/tvcache.sock}"
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3
export PYTHONPATH="${ROOT}/vendor/tvclient:${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$CACHE_DIR"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

case "${1:-}" in
  start)
    if is_running; then
      echo "tool gateway already running pid=$(cat "$PID_FILE")"
      exit 0
    fi
    bash "$ROOT/scripts/tvcache_server.sh" start
    export SYSML_TVCACHE_SOCK="$SOCK"
    nohup "$PY" -m parallel_tvcache.cache.tool_gateway --sock "$SOCK" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    for _ in $(seq 1 50); do
      [[ -S "$SOCK" ]] && break
      sleep 0.1
    done
    [[ -S "$SOCK" ]] || { echo "gateway sock missing: $SOCK (see $LOG_FILE)" >&2; exit 1; }
    echo "STARTED tool gateway pid=$(cat "$PID_FILE") sock=$SOCK"
    ;;
  stop)
    if is_running; then
      kill "$(cat "$PID_FILE")" 2>/dev/null || true
      rm -f "$PID_FILE"
      echo "STOPPED tool gateway"
    else
      rm -f "$PID_FILE"
      echo "tool gateway not running"
    fi
    rm -f "$SOCK"
    ;;
  status)
    if is_running; then
      echo "RUNNING pid=$(cat "$PID_FILE") sock=$SOCK"
      exit 0
    fi
    echo "STOPPED"
    exit 1
    ;;
  *)
    echo "Usage: bash scripts/tvcache_tool_gateway.sh {start|stop|status}" >&2
    exit 2
    ;;
esac
