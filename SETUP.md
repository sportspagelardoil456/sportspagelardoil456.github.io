# Setup — Slack + watsonx Orchestrate

**Docs:** [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)  
**Author:** [Markus van Kempen](https://github.com/markusvankempen)

The live admin dashboard **Setup** tab mirrors this guide (`GET /api/setup`) with env readiness, copy-paste commands, and example agent YAMLs.

---

## 1. Environment

Copy [`.env.example`](.env.example) → `.env`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `SLACK_BOT_TOKEN` | yes | Bot OAuth token (`xoxb-…`) |
| `SLACK_SIGNING_SECRET` | for events | Verifies Slack Events → `/slack/events` |
| `WXO_INSTANCE_URL` | yes | Orchestrate instance URL |
| `WXO_API_KEY` | yes | Runs API / MCSP key |
| `WXO_AGENT_ID` | recommended | Default binding agent |
| `GATEWAY_ADMIN_USER` / `PASSWORD` | recommended | Basic Auth for UI + `/api/*` |

Public without auth: `/health`, `/mcp`, `/slack/events`.

---

## 2. Slack app

1. [api.slack.com/apps](https://api.slack.com/apps) → Create From scratch  
2. **OAuth & Permissions** → Bot Token Scopes (below) → Install  
3. Copy **Bot User OAuth Token** → `SLACK_BOT_TOKEN`  
4. **Signing Secret** → `SLACK_SIGNING_SECRET` (if using Events)  
5. `/invite @YourBot` in each channel; copy **Channel ID** into bindings  
6. Optional Events: Request URL `https://YOUR_HOST/slack/events` → `message.channels` / `message.groups`  
7. Reinstall after adding new scopes  

### Bot scopes

| Scope | Why |
|-------|-----|
| `channels:history` / `groups:history` | Poller reads messages |
| `chat:write` | Gateway posts thread replies |
| `channels:read` / `groups:read` | `list_slack_channels` |
| `reactions:write` | Typing indicator |
| `app_mentions:read` | Optional with byo_slack |

Prefer **poll** mode for multi-channel; use **events** when you want push delivery.

---

## 3. watsonx Orchestrate

1. Set `WXO_*` in `.env` and start/deploy the gateway  
2. Register the remote MCP toolkit (real DNS — no placeholders):

```bash
orchestrate toolkits add -k mcp -n slack_wxo_gateway \
  --url "https://YOUR_HOST/mcp" \
  --transport streamable_http \
  --tools "*"
```

3. Import an example agent (see below) and put its `agent_id` in `config.yaml`  
4. Prefer `reply_mode: gateway_thread` + **answer-only** agent  

---

## 4. Example agents

| Agent | File | Use when |
|-------|------|----------|
| `slack_gateway_answer_agent` | `agents/slack_gateway_answer_agent.yaml` | Channel answers (`gateway_thread`) |
| `slack_gateway_ops_agent` | `agents/slack_gateway_ops_agent.yaml` | Day-2 routing / diagnostics |
| `slack_gateway_test_agent` | `agent.yaml` | Full toolkit smoke |

```bash
orchestrate agents import -f agents/slack_gateway_answer_agent.yaml
orchestrate agents deploy -n slack_gateway_answer_agent
```

Full YAML bodies are available in the admin UI → **Setup → Example agents** (and in the private package; this docs repo may ship examples separately).

---

## 5. Config binding (minimal)

See [`config.example.yaml`](config.example.yaml):

```yaml
bindings:
  - name: support
    enabled: true
    slack_channel_id: C0…
    mode: poll
    reply_mode: gateway_thread
    wxo:
      agent_id: ${WXO_AGENT_ID}
```

---

## 6. Verify

1. Admin UI → **Diagnostics** (Slack auth + WxO token)  
2. Post a human message in the bound Slack channel  
3. Optional: `orchestrate chat ask -n slack_gateway_test_agent '…smoke…'`  
