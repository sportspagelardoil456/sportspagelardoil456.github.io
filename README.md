# Slack ↔ WxO MCP Gateway

**npm:** [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway)  
**GitHub:** [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)  
**Author:** [Markus van Kempen](https://github.com/markusvankempen)

Hosted gateway that makes the “every Slack message → watsonx Orchestrate agent” story easy to reuse:

> **One config site:** map many Slack channels → many WxO agents.  
> Poller (and optional Slack Events) wake agents.  
> Same host exposes an **MCP toolkit** (`/mcp`) for WxO / Cursor / other clients.

WxO `byo_slack` still only does @mention/DM. This gateway is the custom integration layer.

---

## Install & run

### Via npm / npx (recommended)

Requires **Node 18+** and **Python 3.10+**.

```bash
cp .env.example .env                 # SLACK_BOT_TOKEN, WXO_* …
cp config.example.yaml config.yaml   # set slack_channel_id + agent_id

npx @markusvankempen/slack-wxo-mcp-gateway
```

Or install globally:

```bash
npm install -g @markusvankempen/slack-wxo-mcp-gateway
slack-wxo-mcp-gateway
```

Open **http://localhost:3100/** — admin UI (bindings, config, live logs, MCP tools, diagnostics).

### From source (this repo)

```bash
git clone https://github.com/markusvankempen/slack-wxo-mcp-gateway.git
cd slack-wxo-mcp-gateway
cp .env.example .env
cp config.example.yaml config.yaml
python3 -m pip install -r requirements.txt
# package root must be importable as slack_mcp_gateway:
PYTHONPATH=.. python3 -m slack_mcp_gateway
# or:
npx .
```

Full path (ngrok + WxO toolkit):

```bash
./deploy_e2e.sh
./stop.sh
```

---

## Mental model

```text
Slack channels          Gateway (this host)           WxO
─────────────────       ─────────────────────         ────────────────
#support   ──────┐
#orders    ──────┼──►  config.yaml bindings  ──►  agent A / B / C
#ops       ──────┘      poller + /slack/events      Runs API
                        MCP tools @ /mcp
                        Config UI @ /
```

---

## Config (`config.yaml`)

| Field | Meaning |
|-------|---------|
| `slack_channel_id` | e.g. `C0BHWEZ7NLC` |
| `wxo.agent_id` | Target Orchestrate agent |
| `mode` | `poll` \| `events` \| `both` |
| `reply_mode` | `gateway_thread` = gateway posts Slack thread after Runs API; `agent_tools` = only start agent |
| `poll_sec` / `lookback_sec` | Poller timing |

Secrets: use `${ENV_VAR}` (loaded from `.env`).

---

## Endpoints

| Path | Role |
|------|------|
| `/` | Admin UI |
| `/mcp` | MCP streamable HTTP |
| `/slack/events` | Slack Event Subscriptions |
| `/health` | Liveness |
| `/api/logs` | Log ring buffer |
| `/api/tools` | MCP tool catalog |
| `/api/diagnostics` | Slack + WxO checks |
| `/api/poll` | One poll cycle |
| `/api/config` | Masked JSON / raw YAML |

### Admin dashboard auth

```bash
GATEWAY_ADMIN_USER=admin
GATEWAY_ADMIN_PASSWORD=choose-a-strong-password
```

Protects `/` and `/api/*`. **Public:** `/health`, `/mcp`, `/slack/events`.

### IBM Code Engine

```bash
./deploy_code_engine.sh
./test_code_engine.sh
```

Register the toolkit:

```bash
orchestrate toolkits add -k mcp -n slack_wxo_gateway \
  --url "https://YOUR-HOST/mcp" \
  --transport streamable_http \
  --tools "*"
```

### MCP tools (14)

**Config:** `list_bindings`, `upsert_binding`  
**Slack:** `list_slack_channels`, `list_recent_messages`, `list_thread_replies`, `get_message_context`, `post_thread_reply`, `set_typing_indicator`  
**WxO:** `list_wxo_agents`, `invoke_wxo_agent`  
**Ops:** `poll_once`, `get_gateway_status`, `get_recent_logs`, `run_diagnostics_tool`

Bot scopes: `channels:read`, `groups:read`, `reactions:write` (reinstall Slack app after adding).

**Agents:**

| Agent | Role |
|-------|------|
| [`agent.yaml`](agent.yaml) → `slack_gateway_test_agent` | Full-toolkit smoke |
| [`agents/slack_gateway_ops_agent.yaml`](agents/slack_gateway_ops_agent.yaml) | Day-2 ops / routing |
| [`agents/slack_gateway_answer_agent.yaml`](agents/slack_gateway_answer_agent.yaml) | Channel answers (`gateway_thread`) |

**Use cases + test plan:** [`USE_CASES.md`](USE_CASES.md)  
**Publish (npm / GitHub):** [`PUBLISH.md`](PUBLISH.md)

---

## Reply modes

**`gateway_thread` (default)** — poller/Events → Runs API → gateway `chat.postMessage` in thread. Use the answer-only agent (no `done`).

**`agent_tools`** — gateway only starts the agent; agent uses its own Slack tools.

---

## Cursor / Claude (remote MCP)

Point your MCP client at the hosted `/mcp` URL (streamable HTTP), for example:

```json
{
  "mcpServers": {
    "slack-wxo-gateway": {
      "url": "https://YOUR-HOST/mcp"
    }
  }
}
```

Package identity for registries:

- npm: `@markusvankempen/slack-wxo-mcp-gateway`
- MCP name: `io.github.markusvankempen/slack-wxo-mcp-gateway`
- Homepage: [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)

---

## License

[Apache-2.0](LICENSE) — © Markus van Kempen  
[https://github.com/markusvankempen](https://github.com/markusvankempen)
