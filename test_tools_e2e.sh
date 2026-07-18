#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
mkdir -p .run

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

load_env "${SCRIPT_DIR}/../../.env-code-engine"
load_env "${SCRIPT_DIR}/../../.env"
load_env "${SCRIPT_DIR}/../.env"
load_env "${SCRIPT_DIR}/.env"
[[ -f .run/code_engine_admin.env ]] && load_env .run/code_engine_admin.env

CHANNEL_ID="${SLACK_TEST_CHANNEL_ID:-C0BHWEZ7NLC}"
AGENT_NAME="${TEST_AGENT_NAME:-slack_gateway_test_agent}"
OPS_AGENT_NAME="${OPS_AGENT_NAME:-slack_gateway_ops_agent}"
CE_URL="${CE_APP_URL:-}"
[[ -z "$CE_URL" && -f .run/code_engine_url.txt ]] && CE_URL="$(cat .run/code_engine_url.txt)"
CE_URL="${CE_URL%/}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: need $1" >&2; exit 1; }; }
need orchestrate
need curl
need python3

echo "==> Activate orchestrate env NEW"
orchestrate env activate NEW -a "${WXO_API_KEY}" >/dev/null

# ── 1) Ensure toolkit points at CE (if URL known) ─────────────────────────────
if [[ -n "$CE_URL" ]]; then
  echo "==> Ensure toolkit slack_wxo_gateway → ${CE_URL}/mcp"
  orchestrate toolkits remove -n slack_wxo_gateway 2>/dev/null || true
  orchestrate toolkits add -k mcp -n slack_wxo_gateway \
    --description "Slack↔WxO MCP Gateway" \
    --url "${CE_URL}/mcp" \
    --transport streamable_http \
    --tools "*"
fi

# ── 2) Import / deploy agents (full tool list) ────────────────────────────────
echo "==> Import agents (test + ops)"
orchestrate agents remove -n "$AGENT_NAME" -k native 2>/dev/null || true
orchestrate agents import -f agent.yaml
orchestrate agents deploy -n "$AGENT_NAME"

orchestrate agents remove -n "$OPS_AGENT_NAME" -k native 2>/dev/null || true
orchestrate agents import -f agents/slack_gateway_ops_agent.yaml
orchestrate agents deploy -n "$OPS_AGENT_NAME"

# ── 3) Orchestrate CLI: agent smoke (all safe tools) ──────────────────────────
SMOKE_PROMPT="Run a full gateway tool smoke test for channel_id=${CHANNEL_ID}. Call every safe tool once and return ONLY a markdown table Tool|Status|Notes. Skip upsert_binding, post_thread_reply, and invoke_wxo_agent."

echo "==> orchestrate chat ask -n ${AGENT_NAME} (full smoke, then exit)"
# chat ask stays interactive after the first reply — send exit on stdin
set +e
printf 'exit\n' | orchestrate chat ask -n "$AGENT_NAME" "$SMOKE_PROMPT" 2>&1 \
  | tee .run/cli_smoke_ask.txt
ASK_RC=${PIPESTATUS[1]:-${PIPESTATUS[0]}}
set -e
echo "    chat ask exit=$ASK_RC"

# Always also run Runs API (reliable non-interactive record)
echo "==> Runs API invoke for ${AGENT_NAME}"
export SMOKE_PROMPT CHANNEL_ID
export TEST_AGENT_NAME="$AGENT_NAME"
python3 <<'PY'
import os, json, requests, time
from pathlib import Path
base=os.environ["WXO_INSTANCE_URL"].rstrip("/")
token=requests.post(
    os.environ.get("WO_MCSP_TOKEN_URL","https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token"),
    json={"apikey": os.environ["WXO_API_KEY"]}, timeout=20,
).json()
token=token.get("token") or token.get("access_token")
h={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
agents=requests.get(base+"/v1/orchestrate/agents", headers=h, timeout=30).json()
agents=agents if isinstance(agents, list) else agents.get("data") or []
name=os.environ.get("TEST_AGENT_NAME","slack_gateway_test_agent")
a=next(x for x in agents if x.get("name")==name)
prompt=os.environ["SMOKE_PROMPT"]
r=requests.post(base+"/v1/orchestrate/runs", headers=h, json={
    "agent_id": a["id"],
    "message": {"role": "user", "content": prompt},
}, timeout=30)
r.raise_for_status()
run=r.json(); run_id=run["run_id"]; thread_id=run["thread_id"]
print("run_id", run_id)
for i in range(100):
    time.sleep(3)
    st=requests.get(f"{base}/v1/orchestrate/runs/{run_id}", headers=h, timeout=20).json().get("status")
    if i % 3 == 0: print(f"  [{i}] {st}")
    if st in ("completed","failed","error","cancelled"):
        break
msgs=requests.get(f"{base}/v1/orchestrate/threads/{thread_id}/messages", headers=h, timeout=30).json()
messages=msgs if isinstance(msgs, list) else msgs.get("data") or []
out=[]
for m in messages:
    if m.get("role")!="assistant": continue
    c=m.get("content")
    text="\n".join(p.get("text","") for p in c if isinstance(p,dict)) if isinstance(c,list) else str(c)
    if text.strip() and text.strip().lower() not in ("done","skip"):
        out.append(text)
Path(".run/cli_smoke_api.txt").write_text("\n\n".join(out)[-12000:])
print(out[-1][:4000] if out else "(no assistant text)")
PY

# ── 4) Slack path via gateway MCP tools (post + poll) ─────────────────────────
echo "==> Slack e2e via CE MCP tools (post_thread_reply + list_recent_messages)"
python3 <<'PY'
import json, os, time, requests
from pathlib import Path

ce = (os.environ.get("CE_APP_URL") or "").rstrip("/")
if not ce and Path(".run/code_engine_url.txt").exists():
    ce = Path(".run/code_engine_url.txt").read_text().strip().rstrip("/")
channel = os.environ.get("SLACK_TEST_CHANNEL_ID", "C0BHWEZ7NLC")
url = f"{ce}/mcp"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

def parse_sse(text):
    out = []
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                out.append(json.loads(line[6:]))
            except Exception:
                pass
    return out[-1] if out else {"raw": text[:400]}

def call(name, arguments, sid=None):
    h = dict(headers)
    if sid:
        h["mcp-session-id"] = sid
    r = requests.post(
        url,
        headers=h,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        timeout=90,
    )
    sid2 = r.headers.get("mcp-session-id") or sid
    return parse_sse(r.text), sid2, r.status_code

# init
r = requests.post(
    url,
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e", "version": "0.1"},
        },
    },
    timeout=30,
)
sid = r.headers.get("mcp-session-id")
requests.post(url, headers={**headers, **({"mcp-session-id": sid} if sid else {})}, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=30)

marker = f"gateway-e2e-{int(time.time())}"
# find a parent ts
hist, sid, code = call("list_recent_messages", {"channel_id": channel, "limit": 5}, sid)
print("list_recent_messages", code, str(hist)[:300])
msgs = []
try:
    text = hist["result"]["content"][0]["text"]
    msgs = json.loads(text)
except Exception:
    pass
parent = (msgs[0]["ts"] if msgs else None) or str(time.time())

post, sid, code = call(
    "post_thread_reply",
    {"channel_id": channel, "thread_ts": parent, "text": f"[e2e] {marker} — Slack tool path OK"},
    sid,
)
print("post_thread_reply", code, str(post)[:400])

poll, sid, code = call("poll_once", {"channel_id": channel}, sid)
print("poll_once", code, str(poll)[:300])

status, sid, code = call("get_gateway_status", {}, sid)
print("get_gateway_status", code, str(status)[:300])

Path(".run/slack_e2e.json").write_text(
    json.dumps({"marker": marker, "parent_ts": parent, "post": post, "poll": poll, "status": status}, indent=2, default=str)
)
print("marker", marker)
print("Wrote .run/slack_e2e.json — check Slack channel", channel, "thread", parent)
PY

# ── 5) Optional: ops agent one-shot (real-world binding check) ────────────────
echo "==> Ops agent: list bindings + status"
set +e
printf 'exit\n' | orchestrate chat ask -n "$OPS_AGENT_NAME" \
  "Using tools only: list_bindings and get_gateway_status. Summarize which Slack channels are routed and whether the gateway is healthy." \
  2>&1 | tee .run/cli_ops_ask.txt
set -e

echo ""
echo "============================================================"
echo " E2E DONE"
echo "  CLI smoke : .run/cli_smoke_ask.txt (or cli_smoke_api.txt)"
echo "  Slack e2e : .run/slack_e2e.json"
echo "  Ops ask   : .run/cli_ops_ask.txt"
echo "  Channel   : ${CHANNEL_ID}"
echo "============================================================"
