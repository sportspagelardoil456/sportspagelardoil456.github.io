#!/usr/bin/env bash
# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# Deploy Slack↔WxO MCP Gateway to IBM Code Engine (source build).
# ---
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
load_env "${SCRIPT_DIR}/../../.env-code-engine"
load_env "${SCRIPT_DIR}/../.env"
load_env "${SCRIPT_DIR}/.env"

APP_NAME="${CE_APP_NAME:-slack-wxo-gateway}"
SECRET_NAME="${CE_SECRET_NAME:-slack-wxo-gateway-secrets}"
PROJECT="${CE_PROJECT:-}"
CPU="${CE_CPU:-0.5}"
MEMORY="${CE_MEMORY:-1G}"
MIN_SCALE="${CE_MIN_SCALE:-1}"
MAX_SCALE="${CE_MAX_SCALE:-2}"
PORT="${CE_PORT:-8080}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: need $1" >&2; exit 1; }; }
need ibmcloud
need curl
need python3

if ! ibmcloud account show >/dev/null 2>&1; then
  echo "ERROR: not logged in to IBM Cloud."
  echo "  ibmcloud login --sso"
  echo "  # or: ibmcloud login --apikey \"\$IBMCLOUD_API_KEY\""
  echo "  ibmcloud target -r <region> -g <resource-group>"
  echo "  ibmcloud ce project select -n <project>"
  exit 1
fi

if [[ -n "$PROJECT" ]]; then
  echo "==> Selecting Code Engine project: $PROJECT"
  ibmcloud ce project select -n "$PROJECT"
fi

if ! ibmcloud ce project current >/dev/null 2>&1; then
  echo "ERROR: no Code Engine project selected (or CE plugin cannot reach account)."
  echo "  ibmcloud ce project list"
  echo "  ibmcloud ce project select -n <name>"
  echo "  # or: ibmcloud ce project create -n slack-wxo-gateway"
  exit 1
fi

echo "==> Current CE project:"
ibmcloud ce project current

# Admin auth (required for public CE URL)
if [[ -z "${GATEWAY_ADMIN_USER:-}" ]]; then
  GATEWAY_ADMIN_USER="admin"
fi
if [[ -z "${GATEWAY_ADMIN_PASSWORD:-}" ]]; then
  GATEWAY_ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  echo "    Generated GATEWAY_ADMIN_PASSWORD (save it): $GATEWAY_ADMIN_PASSWORD"
fi

for req in SLACK_BOT_TOKEN WXO_INSTANCE_URL WXO_API_KEY WXO_AGENT_ID; do
  if [[ -z "${!req:-}" ]]; then
    echo "ERROR: $req is not set (put it in .env)" >&2
    exit 1
  fi
done

echo "==> Upserting secret ${SECRET_NAME}..."
ibmcloud ce secret delete -n "$SECRET_NAME" -f --ignore-not-found >/dev/null 2>&1 || true
ibmcloud ce secret create -n "$SECRET_NAME" \
  --from-literal "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}" \
  --from-literal "SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET:-}" \
  --from-literal "WXO_INSTANCE_URL=${WXO_INSTANCE_URL}" \
  --from-literal "WXO_API_KEY=${WXO_API_KEY}" \
  --from-literal "WXO_AGENT_ID=${WXO_AGENT_ID}" \
  --from-literal "WO_MCSP_TOKEN_URL=${WO_MCSP_TOKEN_URL:-https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token}" \
  --from-literal "GATEWAY_ADMIN_USER=${GATEWAY_ADMIN_USER}" \
  --from-literal "GATEWAY_ADMIN_PASSWORD=${GATEWAY_ADMIN_PASSWORD}" \
  --from-literal "GATEWAY_HOST=0.0.0.0" \
  --from-literal "GATEWAY_REQUIRE_AUTH=true"

echo "==> Creating/updating app ${APP_NAME} (source build)..."
if ibmcloud ce app get -n "$APP_NAME" >/dev/null 2>&1; then
  ibmcloud ce app update -n "$APP_NAME" \
    --build-source "$SCRIPT_DIR" \
    --build-dockerfile Dockerfile \
    --port "$PORT" \
    --cpu "$CPU" \
    --memory "$MEMORY" \
    --min-scale "$MIN_SCALE" \
    --max-scale "$MAX_SCALE" \
    --env-from-secret "$SECRET_NAME" \
    --wait
else
  ibmcloud ce app create -n "$APP_NAME" \
    --build-source "$SCRIPT_DIR" \
    --build-dockerfile Dockerfile \
    --port "$PORT" \
    --cpu "$CPU" \
    --memory "$MEMORY" \
    --min-scale "$MIN_SCALE" \
    --max-scale "$MAX_SCALE" \
    --env-from-secret "$SECRET_NAME" \
    --wait
fi

mkdir -p "${SCRIPT_DIR}/.run"
APP_URL="$(ibmcloud ce app get -n "$APP_NAME" -o url)"
echo "$APP_URL" > "${SCRIPT_DIR}/.run/code_engine_url.txt"
# Persist generated password for test script (local only)
umask 077
cat > "${SCRIPT_DIR}/.run/code_engine_admin.env" <<EOF
GATEWAY_ADMIN_USER=${GATEWAY_ADMIN_USER}
GATEWAY_ADMIN_PASSWORD=${GATEWAY_ADMIN_PASSWORD}
CE_APP_URL=${APP_URL}
EOF

echo ""
echo "============================================================"
echo " DEPLOYED"
echo "  App URL : ${APP_URL}"
echo "  Admin   : ${GATEWAY_ADMIN_USER} / (see .run/code_engine_admin.env)"
echo "  MCP     : ${APP_URL}/mcp"
echo "  Health  : ${APP_URL}/health"
echo "  Slack Events: ${APP_URL}/slack/events"
echo "  Test    : ./test_code_engine.sh"
echo "============================================================"
echo ""
echo "Next: point WxO toolkit URL at ${APP_URL}/mcp (streamable_http)"
echo "      and Slack Event Subscriptions at ${APP_URL}/slack/events"
