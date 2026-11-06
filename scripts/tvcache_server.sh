#!/usr/bin/env bash
# Start/stop/status for paper TVCache (vendor/tvcache-rust) on 127.0.0.1:7878.
#
#   bash scripts/tvcache_server.sh start
#   bash scripts/tvcache_server.sh status
#   bash scripts/tvcache_server.sh stop
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE_DIR="${SYSML_TVCACHE_DIR:-$ROOT/results/tvcache}"
PID_FILE="$CACHE_DIR/tvcache-rust.pid"
LOG_FILE="$CACHE_DIR/tvcache-rust.log"
PORT="${SYSML_TVCACHE_PORT:-7878}"
HOST="${SYSML_TVCACHE_HOST:-127.0.0.1}"
BIN_DIR="$ROOT/vendor/tvcache-rust"
BIN="$BIN_DIR/target/debug/tvcache"

mkdir -p "$CACHE_DIR"

is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

ensure_binary() {
  if [[ -x "$BIN" ]]; then
    return 0
  fi
  echo "Building tvcache-rust (first run)…"
  # Avoid Cursor sandbox CARGO_TARGET_DIR redirect — keep binary in vendor/.
  (cd "$BIN_DIR" && unset CARGO_TARGET_DIR && export CARGO_TARGET_DIR="$BIN_DIR/target" && cargo build)
  [[ -x "$BIN" ]] || { echo "Missing $BIN after cargo build" >&2; exit 1; }
}

cmd_start() {
  if is_running; then
    echo "tvcache-rust already running pid=$(cat "$PID_FILE") log=$LOG_FILE"
    return 0
  fi
  ensure_binary
  # Server binds 0.0.0.0:7878; HOST is for clients.
  # Detach from Cursor/agent process groups (see tool gateway).
  if command -v setsid >/dev/null 2>&1; then
    setsid "$BIN" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  else
    # macOS: double-fork + setsid so IDE shell teardown cannot reap us.
    python3 - "$PID_FILE" "$LOG_FILE" "$BIN" <<'PY'
import os, sys
pid_file, log_file, binary = sys.argv[1:4]
if os.fork() > 0:
    sys.exit(0)
os.setsid()
if os.fork() > 0:
    sys.exit(0)
os.chdir("/")
fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(fd, 1)
os.dup2(fd, 2)
if fd > 2:
    os.close(fd)
with open(pid_file, "w", encoding="utf-8") as f:
    f.write(str(os.getpid()))
os.execv(binary, [binary])
PY
  fi
  for _ in $(seq 1 50); do
    if (echo >/dev/tcp/127.0.0.1/"$PORT") >/dev/null 2>&1; then
      echo "STARTED tvcache-rust pid=$(cat "$PID_FILE") client=$HOST:$PORT log=$LOG_FILE"
      return 0
    fi
    sleep 0.1
  done
  echo "tvcache-rust did not accept connections on :$PORT — see $LOG_FILE" >&2
  exit 1
}

cmd_stop() {
  if is_running; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "STOPPED tvcache-rust"
  else
    rm -f "$PID_FILE"
    echo "tvcache-rust not running"
  fi
}

cmd_status() {
  if is_running; then
    echo "RUNNING pid=$(cat "$PID_FILE") client=$HOST:$PORT log=$LOG_FILE"
    exit 0
  fi
  echo "STOPPED"
  exit 1
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  restart) cmd_stop; cmd_start ;;
  *)
    echo "Usage: bash scripts/tvcache_server.sh {start|stop|status|restart}" >&2
    exit 2
    ;;
esac
