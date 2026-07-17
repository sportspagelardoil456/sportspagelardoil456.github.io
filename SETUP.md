# Setup — Slack + watsonx Orchestrate

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

Shared Slack / WxO / agent configuration lives here.  
**Deployment is split into two distinguished guides:**

| Path | Directory | Best for |
|------|-----------|----------|
| Local + ngrok | [`docs/local-ngrok/`](docs/local-ngrok/) | Laptop demo, fast iteration |
| IBM Code Engine | [`docs/code-engine/`](docs/code-engine/) | Always-on host, stable Slack/WxO URLs |

Index: [`docs/README.md`](docs/README.md)

The live admin dashboard **Setup** tab (`GET /api/setup`) shows env readiness, copy-paste commands, and example agent YAMLs for whichever host you are on.

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
6. Optional Events: Request URL = `https://YOUR_HOST/slack/events` → `message.channels` / `message.groups`  
   - ngrok: update whenever the tunnel URL changes — see [`docs/local-ngrok/`](docs/local-ngrok/)  
   - Code Engine: set once — see [`docs/code-engine/`](docs/code-engine/)  
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

1. Set `WXO_*` in `.env`  
2. Deploy via [local-ngrok](docs/local-ngrok/) **or** [code-engine](docs/code-engine/) so `/mcp` is reachable  
3. Register the remote MCP toolkit with that path’s real HTTPS URL  
4. Import an example agent YAML and put its `agent_id` in the binding  
5. Prefer `reply_mode: gateway_thread` + **answer-only** agent  

```bash
orchestrate toolkits add -k mcp -n slack_wxo_gateway \
  --url "https://YOUR_HOST/mcp" \
  --transport streamable_http \
  --tools "*"
```

---

## 4. Example agents

| Agent | File | Use when |
|-------|------|----------|
| `slack_gateway_answer_agent` | [`agents/slack_gateway_answer_agent.yaml`](agents/slack_gateway_answer_agent.yaml) | Channel answers (`gateway_thread`) |
| `slack_gateway_ops_agent` | [`agents/slack_gateway_ops_agent.yaml`](agents/slack_gateway_ops_agent.yaml) | Day-2 routing / diagnostics |
| `slack_gateway_test_agent` | [`agent.yaml`](agent.yaml) | Full toolkit smoke |

```bash
orchestrate agents import -f agents/slack_gateway_answer_agent.yaml
orchestrate agents deploy -n slack_gateway_answer_agent
```

Also in admin UI → **Setup → Example agents**.

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
3. Optional smoke agent — see the guide for your deployment path  
