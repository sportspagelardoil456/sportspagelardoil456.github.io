#!/usr/bin/env bash
# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# Start gateway → ngrok → register remote MCP toolkit in WxO
# ---
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_DIR="${SCRIPT_DIR}/.run"
mkdir -p "$RUN_DIR"

load_env() {
  local f="$1" line key val
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "$line" == *"="* ]] || continue
    key="${line%%=*}"; val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    key="${key#"${key%%[![:space:]]*}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$val" =~ ^\"(.*)\"$ ]]; then val="${BASH_REMATCH[1]}"
    elif [[ "$val" =~ ^\'(.*)\'$ ]]; then val="${BASH_REMATCH[1]}"
    fi
    export "${key}=${val}"
  done <"$f"
}

load_env "${SCRIPT_DIR}/../../.env"
load_env "${SCRIPT_DIR}/../.env"
load_env "${SCRIPT_DIR}/.env"

GATEWAY_PORT="${GATEWAY_PORT:-3100}"
TOOLKIT_NAME="${TOOLKIT_NAME:-slack_wxo_gateway}"
KEEP_RUNNING="${KEEP_RUNNING:-1}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: need $1" >&2; exit 1; }; }
need python3
need ngrok
need orchestrate
need curl

echo "==> [1/4] Install Python deps..."
python3 -m pip install -q -r "${SCRIPT_DIR}/requirements.txt"

if [[ ! -f "${SCRIPT_DIR}/config.yaml" ]]; then
  cp "${SCRIPT_DIR}/config.example.yaml" "${SCRIPT_DIR}/config.yaml"
  echo "    Wrote config.yaml from example — edit bindings as needed."
fi

if lsof -ti tcp:"${GATEWAY_PORT}" >/dev/null 2>&1; then
  echo "    Freeing port ${GATEWAY_PORT}..."
  lsof -ti tcp:"${GATEWAY_PORT}" | xargs kill 2>/dev/null || true
  sleep 1
fi

echo "==> [2/4] Starting gateway on :${GATEWAY_PORT}..."
: >"${RUN_DIR}/gateway.log"
# Start gateway in background (prefer leaving this script's terminal open /
# KEEP_RUNNING=1 so the process group is not reaped by the IDE shell).
(
  cd "${ROOT}"
  export GATEWAY_PORT
  nohup python3 -m slack_mcp_gateway >>"${RUN_DIR}/gateway.log" 2>&1 &
  echo $! >"${RUN_DIR}/gateway.pid"
)
disown "$(cat "${RUN_DIR}/gateway.pid")" 2>/dev/null || true

for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${GATEWAY_PORT}/health" >/dev/null 2>&1; then
    echo "    Gateway up (pid $(cat "${RUN_DIR}/gateway.pid"))."
    break
  fi
  if ! kill -0 "$(cat "${RUN_DIR}/gateway.pid")" 2>/dev/null; then
    echo "ERROR: gateway exited. Log:" >&2
    tail -n 40 "${RUN_DIR}/gateway.log" >&2
    exit 1
  fi
  [[ "$i" -eq 40 ]] && { echo "ERROR: gateway not ready"; exit 1; }
  sleep 0.5
done

echo "==> [3/4] Starting ngrok..."
: >"${RUN_DIR}/ngrok.log"
# Leave Host as the ngrok hostname; gateway disables MCP DNS-rebinding checks
# so streamable HTTP /mcp works through the tunnel.
nohup ngrok http "${GATEWAY_PORT}" --log=stdout --log-format=logfmt >>"${RUN_DIR}/ngrok.log" 2>&1 &
echo $! >"${RUN_DIR}/ngrok.pid"
disown "$(cat "${RUN_DIR}/ngrok.pid")" 2>/dev/null || true

NGROK_URL=""
for i in $(seq 1 40); do
  NGROK_URL="$(
    curl -sS "http://127.0.0.1:4040/api/tunnels" 2>/dev/null \
      | python3 -c "
import sys,json
try:
  t=json.load(sys.stdin).get('tunnels') or []
  print(next((x['public_url'] for x in t if x.get('public_url','').startswith('https://')),''))
except Exception:
  print('')
" || true
  )"
  [[ -n "$NGROK_URL" ]] && break
  if ! kill -0 "$(cat "${RUN_DIR}/ngrok.pid")" 2>/dev/null; then
    echo "ERROR: ngrok died"; tail -n 30 "${RUN_DIR}/ngrok.log"; exit 1
  fi
  sleep 0.5
done
[[ -z "$NGROK_URL" ]] && { echo "ERROR: no ngrok URL"; exit 1; }

MCP_URL="${NGROK_URL}/mcp"
echo "    Public UI  : ${NGROK_URL}/"
echo "    MCP URL    : ${MCP_URL}"
echo "    Slack Events: ${NGROK_URL}/slack/events"
echo "$NGROK_URL" >"${RUN_DIR}/ngrok_url.txt"

echo "==> [4/4] Registering remote MCP toolkit '${TOOLKIT_NAME}'..."
orchestrate toolkits remove -n "${TOOLKIT_NAME}" 2>/dev/null || true
orchestrate toolkits add \
  -k mcp \
  -n "${TOOLKIT_NAME}" \
  --description "Slack↔WxO MCP Gateway (multi channel/agent)" \
  --url "${MCP_URL}" \
  --transport streamable_http \
  --tools "*"

echo ""
echo "============================================================"
echo " DONE"
echo "  Config UI : ${NGROK_URL}/"
echo "  MCP       : ${MCP_URL}"
echo "  Toolkit   : ${TOOLKIT_NAME}"
echo "  Stop      : ${SCRIPT_DIR}/stop.sh"
echo "============================================================"

if [[ "${KEEP_RUNNING}" != "1" ]]; then
  "${SCRIPT_DIR}/stop.sh"
fi
