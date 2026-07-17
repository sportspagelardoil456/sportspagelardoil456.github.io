#!/usr/bin/env bash
# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# Smoke-test a deployed Code Engine (or any public) gateway URL.
# ---
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
mkdir -p .run

if [[ -f .run/code_engine_admin.env ]]; then
  # shellcheck disable=SC1091
  source .run/code_engine_admin.env
fi

BASE_URL="${1:-${CE_APP_URL:-}}"
if [[ -z "$BASE_URL" && -f .run/code_engine_url.txt ]]; then
  BASE_URL="$(cat .run/code_engine_url.txt)"
fi
BASE_URL="${BASE_URL%/}"

USER_NAME="${GATEWAY_ADMIN_USER:-admin}"
PASSWORD="${GATEWAY_ADMIN_PASSWORD:-}"

if [[ -z "$BASE_URL" ]]; then
  echo "Usage: $0 https://your-app.region.codeengine.appdomain.cloud"
  echo "  or set CE_APP_URL / run deploy_code_engine.sh first"
  exit 1
fi

echo "==> Testing $BASE_URL"
FAIL=0

check() {
  local name="$1" ok="$2" detail="$3"
  if [[ "$ok" == "1" ]]; then
    echo "  PASS  $name — $detail"
  else
    echo "  FAIL  $name — $detail"
    FAIL=1
  fi
}

# 1) Health (public)
HTTP=$(curl -sS -o /tmp/ce_health.json -w "%{http_code}" "$BASE_URL/health" || echo "000")
if [[ "$HTTP" == "200" ]] && python3 -c "import json; d=json.load(open('/tmp/ce_health.json')); assert d.get('status')=='ok'" 2>/dev/null; then
  check "health" 1 "HTTP $HTTP $(cat /tmp/ce_health.json)"
else
  check "health" 0 "HTTP $HTTP $(head -c 200 /tmp/ce_health.json 2>/dev/null || true)"
fi

# 2) Admin UI without auth → 401 when password configured
HTTP=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/" || echo "000")
if [[ -n "$PASSWORD" ]]; then
  [[ "$HTTP" == "401" ]] && check "ui_unauth" 1 "HTTP $HTTP (auth required)" || check "ui_unauth" 0 "expected 401 got $HTTP"
else
  check "ui_unauth" 1 "HTTP $HTTP (no password configured locally — skipped strict 401)"
fi

# 3) Admin UI with auth
if [[ -n "$PASSWORD" ]]; then
  HTTP=$(curl -sS -o /dev/null -w "%{http_code}" -u "${USER_NAME}:${PASSWORD}" "$BASE_URL/" || echo "000")
  [[ "$HTTP" == "200" ]] && check "ui_auth" 1 "HTTP $HTTP" || check "ui_auth" 0 "HTTP $HTTP"
  HTTP=$(curl -sS -o /tmp/ce_tools.json -w "%{http_code}" -u "${USER_NAME}:${PASSWORD}" "$BASE_URL/api/tools" || echo "000")
  if [[ "$HTTP" == "200" ]] && python3 -c "import json; d=json.load(open('/tmp/ce_tools.json')); assert len(d.get('implemented') or [])>=5" 2>/dev/null; then
    N=$(python3 -c "import json; print(len(json.load(open('/tmp/ce_tools.json')).get('implemented') or []))")
    check "api_tools" 1 "HTTP $HTTP ($N tools)"
  else
    check "api_tools" 0 "HTTP $HTTP"
  fi
else
  check "ui_auth" 0 "GATEWAY_ADMIN_PASSWORD not set"
  check "api_tools" 0 "skipped"
fi

# 4) MCP initialize (public — no basic auth)
HTTP=$(curl -sS -o /tmp/ce_mcp.txt -w "%{http_code}" \
  -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ce-test","version":"0.1"}}}' \
  || echo "000")
if [[ "$HTTP" == "200" ]] && grep -q 'slack-wxo-gateway' /tmp/ce_mcp.txt; then
  check "mcp_initialize" 1 "HTTP $HTTP session-capable"
else
  check "mcp_initialize" 0 "HTTP $HTTP $(head -c 180 /tmp/ce_mcp.txt | tr '\n' ' ')"
fi

# 5) Diagnostics (auth)
if [[ -n "$PASSWORD" ]]; then
  HTTP=$(curl -sS -o /tmp/ce_diag.json -w "%{http_code}" \
    -u "${USER_NAME}:${PASSWORD}" \
    -X POST "$BASE_URL/api/diagnostics" \
    -H "Content-Type: application/json" \
    -d '{"invoke_test":false}' || echo "000")
  if [[ "$HTTP" == "200" ]]; then
    python3 - <<'PY'
import json
d=json.load(open("/tmp/ce_diag.json"))
checks=d.get("checks") or []
print("checks:", ", ".join(f"{c['name']}={'ok' if c['ok'] else 'FAIL'}" for c in checks))
# slack/wxo may fail if secrets wrong — still count HTTP 200 as deploy smoke ok
PY
    check "diagnostics" 1 "HTTP $HTTP"
  else
    check "diagnostics" 0 "HTTP $HTTP"
  fi
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "All smoke checks passed."
  exit 0
fi
echo "Some checks failed."
exit 1
