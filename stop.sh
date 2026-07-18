#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${SCRIPT_DIR}/.run"

stop_pid() {
  local f="$1" label="$2"
  [[ -f "$f" ]] || return 0
  local pid; pid="$(cat "$f")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping ${label} (pid ${pid})..."
    kill "$pid" 2>/dev/null || true
    sleep 0.4
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$f"
}

stop_pid "${RUN_DIR}/gateway.pid" "gateway"
stop_pid "${RUN_DIR}/ngrok.pid" "ngrok"

PORT="${GATEWAY_PORT:-3100}"
if lsof -ti tcp:"${PORT}" >/dev/null 2>&1; then
  lsof -ti tcp:"${PORT}" | xargs kill 2>/dev/null || true
fi
echo "Stopped."
