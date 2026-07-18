#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# One entrypoint for publish/run modes:
#   A http|local  — standalone local host (streamable-http)
#   B podman|docker — container
#   C ce|code-engine — IBM Code Engine deploy
#   D ide|stdio — Cursor / VS Code MCP (stdio)
#   ngrok — local + ngrok + toolkit (deploy_e2e.sh)
#
# Usage:
#   ./scripts/run.sh --mode http
#   ./scripts/run.sh --mode podman
#   ./scripts/run.sh --mode ce
#   ./scripts/run.sh --mode ide [--exec]
#   ./scripts/run.sh --mode ngrok
#   ./scripts/run.sh --help
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE=""
EXEC_STDIO=0
ENGINE="${CONTAINER_ENGINE:-}"
IMAGE="${IMAGE:-slack-wxo-gateway:local}"
HTTP_PORT="${GATEWAY_PORT:-3100}"
CTR_PORT="${PORT:-8080}"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \?//'
  cat <<EOF

Modes (docs: docs/PUBLISH-MODES.md):
  http | local     A) Local gateway HTTP + UI + /mcp  (port $HTTP_PORT)
  podman | docker  B) Build & run container           (port $CTR_PORT)
  ce | code-engine C) Deploy to IBM Code Engine
  ide | stdio      D) Print Cursor/VS Code mcp.json; --exec runs stdio server
  ngrok            Local + ngrok + register WxO toolkit (deploy_e2e.sh)

Env: GATEWAY_PORT, PORT, IMAGE, CONTAINER_ENGINE=podman|docker
EOF
}

load_env_file() {
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

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: need $1" >&2; exit 1; }; }

ensure_config() {
  [[ -f "$ROOT/.env" ]] || { cp "$ROOT/.env.example" "$ROOT/.env"; echo "Wrote .env from example — edit secrets."; }
  [[ -f "$ROOT/config.yaml" ]] || { cp "$ROOT/config.example.yaml" "$ROOT/config.yaml"; echo "Wrote config.yaml from example."; }
}

pick_engine() {
  if [[ -n "$ENGINE" ]]; then
    need "$ENGINE"
    return
  fi
  if command -v podman >/dev/null 2>&1; then ENGINE=podman
  elif command -v docker >/dev/null 2>&1; then ENGINE=docker
  else
    echo "ERROR: need podman or docker" >&2
    exit 1
  fi
}

mode_http() {
  ensure_config
  load_env_file "$ROOT/../.env"
  load_env_file "$ROOT/.env"
  need python3
  export GATEWAY_TRANSPORT="${GATEWAY_TRANSPORT:-streamable-http}"
  export GATEWAY_PORT="${GATEWAY_PORT:-$HTTP_PORT}"
  # Local HTTP mode: do not let a leftover Code Engine PORT=8080 win
  export PORT="${GATEWAY_PORT}"
  export GATEWAY_HOST="${GATEWAY_HOST:-0.0.0.0}"
  echo "==> [A] Local HTTP gateway on :${GATEWAY_PORT} (UI /, MCP /mcp)"
  echo "    Docs: docs/PUBLISH-MODES.md · docs/local-ngrok/"
  if [[ -f "$ROOT/../slack_mcp_gateway/__main__.py" ]] || [[ -f "$ROOT/__main__.py" ]]; then
    cd "$ROOT/.."
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    exec python3 -m slack_mcp_gateway
  fi
  # npm / flat layout
  export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
  exec python3 -c "
import sys, types
root = r'''${ROOT}'''
sys.path.insert(0, root)
pkg = types.ModuleType('slack_mcp_gateway')
pkg.__path__ = [root]
sys.modules['slack_mcp_gateway'] = pkg
from slack_mcp_gateway.server import main
main()
"
}

mode_container() {
  ensure_config
  pick_engine
  need "$ENGINE"
  echo "==> [B] Building image ${IMAGE} with ${ENGINE}"
  "$ENGINE" build -t "$IMAGE" "$ROOT"
  echo "==> [B] Running on host port ${CTR_PORT} → container 8080"
  exec "$ENGINE" run --rm -p "${CTR_PORT}:8080" \
    --env-file "$ROOT/.env" \
    -e PORT=8080 \
    -e GATEWAY_HOST=0.0.0.0 \
    -e GATEWAY_TRANSPORT=streamable-http \
    "$IMAGE"
}

mode_ce() {
  need ibmcloud
  echo "==> [C] Code Engine deploy (deploy_code_engine.sh)"
  echo "    Docs: docs/code-engine/"
  exec "$ROOT/deploy_code_engine.sh"
}

mode_ngrok() {
  echo "==> Local + ngrok + WxO toolkit (deploy_e2e.sh)"
  exec "$ROOT/deploy_e2e.sh"
}

print_ide_snippets() {
  cat <<EOF
==> [D] IDE MCP (Cursor / VS Code) — stdio

Cursor (~/.cursor/mcp.json):
{
  "mcpServers": {
    "slack-wxo-gateway": {
      "command": "npx",
      "args": ["-y", "@markusvankempen/slack-wxo-mcp-gateway", "--stdio"],
      "env": {
        "GATEWAY_TRANSPORT": "stdio",
        "SLACK_BOT_TOKEN": "\${SLACK_BOT_TOKEN}",
        "WXO_INSTANCE_URL": "\${WXO_INSTANCE_URL}",
        "WXO_API_KEY": "\${WXO_API_KEY}"
      }
    }
  }
}

VS Code (User mcp.json or .vscode/mcp.json):
{
  "servers": {
    "slack-wxo-gateway": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@markusvankempen/slack-wxo-mcp-gateway", "--stdio"],
      "env": {
        "GATEWAY_TRANSPORT": "stdio",
        "SLACK_BOT_TOKEN": "\${SLACK_BOT_TOKEN}",
        "WXO_INSTANCE_URL": "\${WXO_INSTANCE_URL}",
        "WXO_API_KEY": "\${WXO_API_KEY}"
      }
    }
  }
}

Remote IDE → hosted gateway (A/B/C):
  npx -y mcp-remote https://YOUR_HOST/mcp

Templates: examples/mcp/
Docs: docs/ide/ · docs/PUBLISH-MODES.md

Private checkout stdio (this tree):
  GATEWAY_TRANSPORT=stdio PYTHONPATH=$(dirname "$ROOT") python3 -m slack_mcp_gateway --stdio

EOF
}

mode_ide() {
  print_ide_snippets
  if [[ "$EXEC_STDIO" -ne 1 ]]; then
    echo "Tip: ./scripts/run.sh --mode ide --exec   # run stdio server now"
    return 0
  fi
  ensure_config
  load_env_file "$ROOT/../.env"
  load_env_file "$ROOT/.env"
  need python3
  export GATEWAY_TRANSPORT=stdio
  echo "==> [D] Starting stdio MCP (Ctrl+C to stop; IDEs usually spawn this themselves)"
  if [[ -d "$(dirname "$ROOT")/slack_mcp_gateway" ]]; then
    cd "$(dirname "$ROOT")"
    export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
    exec python3 -m slack_mcp_gateway --stdio
  fi
  export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
  exec python3 -c "
import sys, types
root = r'''${ROOT}'''
sys.path.insert(0, root)
sys.argv = ['slack_mcp_gateway', '--stdio']
pkg = types.ModuleType('slack_mcp_gateway')
pkg.__path__ = [root]
sys.modules['slack_mcp_gateway'] = pkg
from slack_mcp_gateway.server import main
main()
"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode|-m) MODE="${2:-}"; shift 2 ;;
    --exec) EXEC_STDIO=1; shift ;;
    --image) IMAGE="${2:-}"; shift 2 ;;
    --port) HTTP_PORT="${2:-}"; CTR_PORT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

[[ -n "$MODE" ]] || { usage; exit 1; }

case "$MODE" in
  http|local|a|A) mode_http ;;
  podman) ENGINE=podman; mode_container ;;
  docker) ENGINE=docker; mode_container ;;
  b|B) mode_container ;;
  ce|code-engine|c|C) mode_ce ;;
  ide|stdio|d|D|cursor|vscode) mode_ide ;;
  ngrok|e2e) mode_ngrok ;;
  *) echo "Unknown mode: $MODE" >&2; usage; exit 1 ;;
esac
