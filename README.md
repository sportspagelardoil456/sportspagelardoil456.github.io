# Slack ↔ WxO MCP Gateway

**GitHub (docs):** [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)  
**npm (planned):** [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway)  
**Author:** [Markus van Kempen](https://github.com/markusvankempen)

> This repository publishes **documentation only**. Application source is not included here (yet).

Hosted gateway that makes the “every Slack message → watsonx Orchestrate agent” story easy to reuse:

> **One config site:** map many Slack channels → many WxO agents.  
> Poller (and optional Slack Events) wake agents.  
> Same host exposes an **MCP toolkit** (`/mcp`) for WxO / Cursor / other clients.

WxO `byo_slack` still only does @mention/DM. This gateway is the custom integration layer.

---

## Quick start (hosted)

1. Deploy or run your gateway host (private build / npm when published).
2. Copy [`.env.example`](.env.example) → `.env` and [`config.example.yaml`](config.example.yaml) → `config.yaml`.
3. Open the admin UI (default `http://localhost:3100/`) — bindings, config, logs, MCP tools, diagnostics.
4. Register `/mcp` with watsonx Orchestrate or your MCP client (see below).

### Via npm / npx (when published)

```bash
npx @markusvankempen/slack-wxo-mcp-gateway
```

Requires Node 18+ and Python 3.10+.

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

**Setup (Slack + WxO):** [`SETUP.md`](SETUP.md) — also live in admin UI → **Setup**  
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
