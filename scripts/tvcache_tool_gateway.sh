#!/usr/bin/env bash
# Start/stop host tool gateway (TCP → tvclient → tvcache-rust).
# Pi agents in Docker reach this via host.docker.internal:SYSML_TVCACHE_GATEWAY_PORT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CACHE_DIR="${SYSML_TVCACHE_DIR:-$ROOT/results/tvcache}"
PID_FILE="$CACHE_DIR/tool-gateway.pid"
LOG_FILE="$CACHE_DIR/tool-gateway.log"
SOCK="${SYSML_TVCACHE_SOCK:-$CACHE_DIR/tvcache.sock}"
LISTEN_HOST="${SYSML_TVCACHE_GATEWAY_HOST:-127.0.0.1}"
LISTEN_PORT="${SYSML_TVCACHE_GATEWAY_PORT:-17878}"
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
    export SYSML_TVCACHE_GATEWAY_HOST="$LISTEN_HOST"
    export SYSML_TVCACHE_GATEWAY_PORT="$LISTEN_PORT"
    export SYSML_TVCACHE_WORKDIR="${SYSML_TVCACHE_WORKDIR:-/home/user}"
    # Inherit SYSML_TVCACHE_METRICS from wave if set.
    nohup "$PY" -m parallel_tvcache.cache.tool_gateway \
      --sock "$SOCK" \
      --listen-host "$LISTEN_HOST" \
      --listen-port "$LISTEN_PORT" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    ready=0
    for _ in $(seq 1 50); do
      if "$PY" -c "import socket;s=socket.create_connection(('$LISTEN_HOST',$LISTEN_PORT),0.2);s.close()" 2>/dev/null; then
        ready=1
        break
      fi
      sleep 0.1
    done
    [[ "$ready" == 1 ]] || { echo "gateway TCP not ready on $LISTEN_HOST:$LISTEN_PORT (see $LOG_FILE)" >&2; exit 1; }
    echo "STARTED tool gateway pid=$(cat "$PID_FILE") tcp=$LISTEN_HOST:$LISTEN_PORT sock=$SOCK"
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
      echo "RUNNING pid=$(cat "$PID_FILE") tcp=$LISTEN_HOST:$LISTEN_PORT sock=$SOCK"
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
