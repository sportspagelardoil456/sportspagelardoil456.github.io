# Local + ngrok path

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

Run the gateway on your machine, expose it with **ngrok**, then register the tunnel URL as a WxO remote MCP toolkit.

```text
Laptop :3100  ──ngrok──►  https://xxxx.ngrok-free.app
                              │
                              ├── /          admin UI
                              ├── /mcp       WxO toolkit (streamable_http)
                              └── /slack/events   (optional Events mode)
```

---

## Prerequisites

| Tool | Notes |
|------|--------|
| Python 3.10+ | Gateway runtime |
| [ngrok](https://ngrok.com/) | Logged in (`ngrok config add-authtoken …`) |
| watsonx Orchestrate CLI (`orchestrate`) | Env activated with your API key |
| Slack app | Bot token + scopes — see [SETUP.md](../../SETUP.md) |

---

## 1. Configure locally

```bash
cd slack_mcp_gateway   # private package / checkout root
cp .env.example .env
cp config.example.yaml config.yaml
# Edit .env: SLACK_BOT_TOKEN, WXO_INSTANCE_URL, WXO_API_KEY, WXO_AGENT_ID
# Edit config.yaml: slack_channel_id + agent binding
```

Optional admin auth for the local UI:

```bash
GATEWAY_ADMIN_USER=admin
GATEWAY_ADMIN_PASSWORD=change-me
```

---

## 2. One-shot deploy (recommended)

From the gateway directory:

```bash
./deploy_e2e.sh
```

This will:

1. Install Python deps  
2. Start the gateway on `GATEWAY_PORT` (default **3100**)  
3. Start `ngrok http 3100`  
4. Register toolkit `slack_wxo_gateway` → `https://YOUR-NGROK/mcp`  

Outputs (also under `.run/`):

| File | Content |
|------|---------|
| `.run/ngrok_url.txt` | Public HTTPS base |
| `.run/gateway.pid` / `ngrok.pid` | Process IDs |
| `.run/gateway.log` / `ngrok.log` | Logs |

Stop everything:

```bash
./stop.sh
```

---

## 3. Manual steps (if not using deploy_e2e)

```bash
# Terminal A — gateway (from parent of slack_mcp_gateway package)
export GATEWAY_PORT=3100
PYTHONPATH=.. python3 -m slack_mcp_gateway
# or: npx @markusvankempen/slack-wxo-mcp-gateway   # when published

# Terminal B — tunnel
ngrok http 3100
# Copy the https://….ngrok-free.app URL
```

Register WxO toolkit (use the **real** ngrok host — placeholders fail SSRF DNS checks):

```bash
orchestrate toolkits remove -n slack_wxo_gateway 2>/dev/null || true
orchestrate toolkits add -k mcp -n slack_wxo_gateway \
  --description "Slack↔WxO MCP Gateway (local ngrok)" \
  --url "https://YOUR-NGROK-HOST/mcp" \
  --transport streamable_http \
  --tools "*"
```

---

## 4. Slack + agents

1. Invite bot to the channel; set `slack_channel_id` in Config / `config.yaml`.  
2. Prefer `mode: poll` and `reply_mode: gateway_thread`.  
3. Import answer agent: [`agents/slack_gateway_answer_agent.yaml`](../../agents/slack_gateway_answer_agent.yaml)  
4. If using **Events**: Slack Request URL = `https://YOUR-NGROK/slack/events`  
   - **Re-set this every time the ngrok URL changes** (free ngrok rotates).  

---

## 5. Verify

```bash
curl -sS "$(cat .run/ngrok_url.txt)/health"
# Open admin UI: $(cat .run/ngrok_url.txt)/
# Diagnostics tab → Run diagnostics
# Post a human message in the bound Slack channel
```

Smoke via WxO:

```bash
orchestrate agents import -f agent.yaml
orchestrate agents deploy -n slack_gateway_test_agent
orchestrate chat ask -n slack_gateway_test_agent \
  'Run a full gateway tool smoke test. Return Tool|Status|Notes.'
```

---

## Ngrok-specific pitfalls

| Issue | Fix |
|-------|-----|
| WxO “Session terminated” / MCP flaky | Gateway uses `stateless_http`; restart gateway + re-register toolkit |
| Toolkit add fails DNS / SSRF | Use the live ngrok HTTPS URL, not `localhost` or a placeholder |
| Slack Events URL verification fails | Update Request URL after every ngrok restart |
| Browser ngrok interstitial | Use API clients / WxO server-side; or paid ngrok without interstitial |
| Tunnel down when laptop sleeps | Keep laptop awake or switch to [Code Engine](../code-engine/) |

---

## When to leave this path

Use **[Code Engine](../code-engine/)** when you need a stable URL, 24/7 poller, or Slack Events without rebinding ngrok each day.
