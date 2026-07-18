#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# Smoke-test publish modes A–D (+ optional ngrok).
# Usage: ./scripts/test_publish_modes.sh [--skip-podman] [--skip-ce] [--skip-ngrok]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p .run
# Local tests must not inherit Code Engine PORT=8080 from the shell/.env
unset PORT 2>/dev/null || true

SKIP_PODMAN=0
SKIP_CE=0
SKIP_NGROK=1   # opt-in: --with-ngrok
PASS=0
FAIL=0
SOFT=0

log() { echo "$*"; }
ok() { echo "  PASS  $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }
soft() { echo "  SOFT  $*"; SOFT=$((SOFT + 1)); }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-podman) SKIP_PODMAN=1; shift ;;
    --skip-ce) SKIP_CE=1; shift ;;
    --with-ngrok) SKIP_NGROK=0; shift ;;
    --skip-ngrok) SKIP_NGROK=1; shift ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

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

load_env "$ROOT/../../.env"
load_env "$ROOT/../.env"
load_env "$ROOT/.env"

mcp_initialize() {
  local base="$1"
  curl -sS -o /tmp/mcp_init_body.txt -w '%{http_code}' -X POST "${base}/mcp" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H 'ngrok-skip-browser-warning: 1' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"mode-test","version":"0.1"}}}' \
    || echo "000"
}

# ── D) IDE stdio ─────────────────────────────────────────────────────────────
log ""
log "======== D) IDE MCP (stdio) ========"
IDE_OUT="$(./scripts/run.sh --mode ide 2>&1 || true)"
if printf '%s\n' "$IDE_OUT" | grep -q 'mcpServers' && printf '%s\n' "$IDE_OUT" | grep -q 'stdio'; then
  ok "run.sh --mode ide prints Cursor/VS Code snippets"
else
  bad "run.sh --mode ide missing snippets"
  printf '%s\n' "$IDE_OUT" | head -8
fi

# Short stdio initialize via python MCP client (stdio subprocess)
export ROOT
if ROOT="$ROOT" python3 <<'PY'
import json, os, subprocess, sys, time
root = os.environ.get("ROOT") or "."
parent = os.path.dirname(os.path.abspath(root))
env = os.environ.copy()
env["GATEWAY_TRANSPORT"] = "stdio"
env["GATEWAY_ENABLE_POLLER"] = "0"
env["PYTHONPATH"] = parent + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
proc = subprocess.Popen(
    [sys.executable, "-m", "slack_mcp_gateway", "--stdio"],
    cwd=parent,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True,
    bufsize=1,
)
def send(obj):
    line = json.dumps(obj)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0.1"}}})
# read one JSON-RPC response line (with timeout)
import select
ready, _, _ = select.select([proc.stdout], [], [], 15)
if not ready:
    proc.kill()
    print("TIMEOUT")
    sys.exit(1)
resp = proc.stdout.readline()
proc.terminate()
try:
    proc.wait(timeout=3)
except Exception:
    proc.kill()
data = json.loads(resp)
ok = "result" in data and "serverInfo" in data.get("result", {})
print("OK" if ok else f"BAD:{resp[:200]}")
sys.exit(0 if ok else 1)
PY
then
  ok "stdio MCP initialize → serverInfo"
else
  bad "stdio MCP initialize failed"
fi

# ── A) Local HTTP ────────────────────────────────────────────────────────────
log ""
log "======== A) Local HTTP ========"
LOCAL_PORT=3110
lsof -ti tcp:"$LOCAL_PORT" | xargs kill 2>/dev/null || true
sleep 0.5
# Prefer PORT for this process so server.py does not pick CE's PORT from .env
export PORT="$LOCAL_PORT"
export GATEWAY_PORT="$LOCAL_PORT"
export GATEWAY_TRANSPORT=streamable-http
export GATEWAY_ENABLE_POLLER=0
(
  cd "$ROOT/.."
  export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
  export PORT GATEWAY_PORT GATEWAY_TRANSPORT GATEWAY_ENABLE_POLLER
  # Avoid load_dotenv re-injecting PORT=8080 from sibling CE env if present
  unset IBMCLOUD_API_KEY 2>/dev/null || true
  nohup env PORT="$LOCAL_PORT" GATEWAY_PORT="$LOCAL_PORT" GATEWAY_TRANSPORT=streamable-http GATEWAY_ENABLE_POLLER=0 \
    python3 -m slack_mcp_gateway >"$ROOT/.run/mode_a.log" 2>&1 &
  echo $! >"$ROOT/.run/mode_a.pid"
)
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${LOCAL_PORT}/health" >/dev/null; then break; fi
  sleep 0.35
done
if H=$(curl -sf "http://127.0.0.1:${LOCAL_PORT}/health"); then
  ok "health: $H"
else
  bad "local health (see .run/mode_a.log)"
fi
CODE=$(mcp_initialize "http://127.0.0.1:${LOCAL_PORT}")
if [[ "$CODE" == "200" ]] || grep -q 'serverInfo\|protocolVersion' /tmp/mcp_init_body.txt 2>/dev/null; then
  ok "MCP initialize HTTP $CODE"
else
  bad "MCP initialize HTTP $CODE body=$(head -c 120 /tmp/mcp_init_body.txt 2>/dev/null)"
fi
if [[ -n "${GATEWAY_ADMIN_USER:-}" && -n "${GATEWAY_ADMIN_PASSWORD:-}" ]]; then
  U=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${LOCAL_PORT}/")
  A=$(curl -s -o /dev/null -w '%{http_code}' -u "${GATEWAY_ADMIN_USER}:${GATEWAY_ADMIN_PASSWORD}" "http://127.0.0.1:${LOCAL_PORT}/")
  [[ "$U" == "401" ]] && ok "UI unauthorized without creds ($U)" || soft "UI without auth=$U (auth may be off)"
  [[ "$A" == "200" ]] && ok "UI authorized ($A)" || bad "UI with auth=$A"
else
  soft "GATEWAY_ADMIN_* not set — skip auth checks"
fi
kill "$(cat "$ROOT/.run/mode_a.pid" 2>/dev/null)" 2>/dev/null || true
lsof -ti tcp:"$LOCAL_PORT" | xargs kill 2>/dev/null || true

# ── B) Podman ────────────────────────────────────────────────────────────────
log ""
log "======== B) Podman ========"
if [[ "$SKIP_PODMAN" -eq 1 ]]; then
  soft "skipped (--skip-podman)"
elif ! command -v podman >/dev/null; then
  soft "podman not installed"
else
  CTR_PORT=18080
  podman rm -f slack-wxo-mode-b 2>/dev/null || true
  if podman build -t slack-wxo-gateway:mode-test "$ROOT" >"$ROOT/.run/mode_b_build.log" 2>&1; then
    ok "podman build"
  else
    bad "podman build (see .run/mode_b_build.log)"
  fi
  podman run -d --name slack-wxo-mode-b -p "${CTR_PORT}:8080" \
    --env-file "$ROOT/.env" \
    -e PORT=8080 -e GATEWAY_HOST=0.0.0.0 -e GATEWAY_ENABLE_POLLER=0 \
    slack-wxo-gateway:mode-test >"$ROOT/.run/mode_b.cid" 2>"$ROOT/.run/mode_b_run.log" || true
  for i in $(seq 1 50); do
    if curl -sf "http://127.0.0.1:${CTR_PORT}/health" >/dev/null; then break; fi
    sleep 0.4
  done
  if H=$(curl -sf "http://127.0.0.1:${CTR_PORT}/health"); then
    ok "container health: $H"
  else
    bad "container health (podman logs:)"
    podman logs slack-wxo-mode-b 2>&1 | tail -20 || true
  fi
  CODE=$(mcp_initialize "http://127.0.0.1:${CTR_PORT}")
  if [[ "$CODE" == "200" ]] || grep -q 'serverInfo\|protocolVersion' /tmp/mcp_init_body.txt 2>/dev/null; then
    ok "container MCP initialize HTTP $CODE"
  else
    bad "container MCP initialize $CODE"
  fi
  podman rm -f slack-wxo-mode-b >/dev/null 2>&1 || true
fi

# ── C) Code Engine ───────────────────────────────────────────────────────────
log ""
log "======== C) Code Engine ========"
CE_URL=""
if [[ -f "$ROOT/.run/code_engine_url.txt" ]]; then
  CE_URL="$(tr -d '[:space:]' <"$ROOT/.run/code_engine_url.txt")"
fi
if [[ "$SKIP_CE" -eq 1 ]]; then
  soft "skipped (--skip-ce)"
elif [[ -z "$CE_URL" ]]; then
  soft "no .run/code_engine_url.txt — deploy first with --mode ce"
else
  if H=$(curl -sf "${CE_URL}/health"); then
    ok "CE health: $H"
  else
    bad "CE health at $CE_URL"
  fi
  CODE=$(mcp_initialize "$CE_URL")
  if [[ "$CODE" == "200" ]] || grep -q 'serverInfo\|protocolVersion' /tmp/mcp_init_body.txt 2>/dev/null; then
    ok "CE MCP initialize HTTP $CODE"
  else
    bad "CE MCP initialize $CODE"
  fi
  if [[ -f "$ROOT/.run/code_engine_admin.env" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/.run/code_engine_admin.env"
    A=$(curl -s -o /dev/null -w '%{http_code}' -u "${GATEWAY_ADMIN_USER}:${GATEWAY_ADMIN_PASSWORD}" "${CE_URL}/api/setup")
    if [[ "$A" == "200" ]]; then
      ok "CE /api/setup auth ($A)"
    elif [[ "$A" == "404" ]]; then
      soft "CE /api/setup=404 — app image predates Setup API; redeploy with ./scripts/run.sh --mode ce"
    else
      bad "CE /api/setup=$A"
    fi
  else
    soft "no code_engine_admin.env for UI auth check"
  fi
  if [[ -x "$ROOT/test_code_engine.sh" ]]; then
    if "$ROOT/test_code_engine.sh" "$CE_URL" >"$ROOT/.run/mode_c_test.log" 2>&1; then
      ok "test_code_engine.sh"
    else
      bad "test_code_engine.sh (see .run/mode_c_test.log)"
      tail -15 "$ROOT/.run/mode_c_test.log" || true
    fi
  fi
fi

# ── Ngrok (optional) ─────────────────────────────────────────────────────────
log ""
log "======== Ngrok (optional) ========"
if [[ "$SKIP_NGROK" -eq 1 ]]; then
  soft "skipped (pass --with-ngrok to run deploy_e2e)"
elif ! command -v ngrok >/dev/null; then
  soft "ngrok not installed"
else
  soft "ngrok full e2e is long — run: ./scripts/run.sh --mode ngrok manually"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
log ""
log "======== SUMMARY ========"
log "PASS=$PASS  FAIL=$FAIL  SOFT=$SOFT"
[[ "$FAIL" -eq 0 ]]
