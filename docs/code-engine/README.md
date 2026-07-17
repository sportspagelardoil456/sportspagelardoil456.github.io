# IBM Code Engine path

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

Deploy the gateway as a **Code Engine application** with a stable public HTTPS URL. Best for always-on Slack polling and production-like WxO toolkits.

```text
IBM Code Engine app
  https://….codeengine.appdomain.cloud
       │
       ├── /          admin UI (Basic Auth)
       ├── /mcp       WxO toolkit (streamable_http) — public
       ├── /slack/events   Slack Events — public
       └── /health    liveness — public
```

---

## Prerequisites

| Tool / account | Notes |
|----------------|--------|
| IBM Cloud CLI + Code Engine plugin | `ibmcloud ce` |
| Logged-in target | Region + resource group + CE **project** selected |
| Slack + WxO credentials | In local `.env` before deploy (pushed as CE secret) |
| watsonx Orchestrate CLI | To register `/mcp` after deploy |

---

## 1. Configure secrets locally

```bash
cd slack_mcp_gateway
cp .env.example .env
# Required for deploy script:
#   SLACK_BOT_TOKEN, WXO_INSTANCE_URL, WXO_API_KEY, WXO_AGENT_ID
# Strongly recommended:
#   GATEWAY_ADMIN_USER, GATEWAY_ADMIN_PASSWORD
# Optional:
#   SLACK_SIGNING_SECRET  (Events mode)
#   CE_PROJECT, CE_APP_NAME, IBMCLOUD_API_KEY
```

Optional IBM Cloud API key file (common pattern): sibling `.env-code-engine` with `IBMCLOUD_API_KEY=…`.

---

## 2. Log in and select project

```bash
ibmcloud login --sso
# or: ibmcloud login --apikey "$IBMCLOUD_API_KEY"

ibmcloud target -r ca-tor -g <resource-group>   # example region
ibmcloud ce project list
ibmcloud ce project select -n <your-ce-project>
# or: ibmcloud ce project create -n slack-wxo-gateway
```

---

## 3. Deploy

```bash
./deploy_code_engine.sh
```

What it does:

1. Upserts CE secret (`SLACK_*`, `WXO_*`, admin auth, `GATEWAY_REQUIRE_AUTH=true`)  
2. Source-builds the app from `Dockerfile` (no local Docker required)  
3. Writes `.run/code_engine_url.txt` and `.run/code_engine_admin.env` (local only — **do not commit**)  

Smoke test:

```bash
./test_code_engine.sh
# or: ./test_code_engine.sh https://YOUR-APP…codeengine.appdomain.cloud
```

---

## 4. Register WxO toolkit (stable URL)

```bash
CE_URL="$(cat .run/code_engine_url.txt)"   # or paste App URL from CE console

orchestrate toolkits remove -n slack_wxo_gateway 2>/dev/null || true
orchestrate toolkits add -k mcp -n slack_wxo_gateway \
  --description "Slack↔WxO MCP Gateway (Code Engine)" \
  --url "${CE_URL}/mcp" \
  --transport streamable_http \
  --tools "*"
```

Import agents (same YAMLs as local path):

```bash
orchestrate agents import -f agents/slack_gateway_answer_agent.yaml
orchestrate agents deploy -n slack_gateway_answer_agent
```

Put the agent id into the binding via admin UI (**Config**) or `config.yaml`.

---

## 5. Slack

1. Invite bot; set channel binding (`reply_mode: gateway_thread` recommended).  
2. Admin UI: `https://YOUR-CE-APP/` — Basic Auth from `.run/code_engine_admin.env`.  
3. Optional Events: Request URL = `https://YOUR-CE-APP/slack/events` (stable — no daily rebind).  

---

## 6. Verify

```bash
curl -sS "$(cat .run/code_engine_url.txt)/health"
# Expect: {"status":"ok", ... "admin_auth": true}

# Admin (401 without creds, 200 with)
source .run/code_engine_admin.env
curl -sS -u "${GATEWAY_ADMIN_USER}:${GATEWAY_ADMIN_PASSWORD}" \
  "$(cat .run/code_engine_url.txt)/api/setup" | head -c 200
```

Then: Diagnostics in the UI → post a Slack message in the bound channel.

End-to-end tool suite (from a machine with `orchestrate` + Slack):

```bash
./test_tools_e2e.sh
```

---

## Code Engine env / scaling notes

| Setting | Typical | Why |
|---------|---------|-----|
| `GATEWAY_REQUIRE_AUTH=true` | set by deploy | Fail closed if admin creds missing |
| `min-scale` | `1` | Keep poller warm (scale-to-zero pauses polling) |
| `PORT` / CE port | `8080` | Platform injects `PORT` |
| Secret name | `slack-wxo-gateway-secrets` | Overridable via `CE_SECRET_NAME` |
| App name | `slack-wxo-gateway` | Overridable via `CE_APP_NAME` |

Update secrets after rotating Slack/WxO keys: re-run `./deploy_code_engine.sh` (recreates secret + updates app).

---

## Code Engine–specific pitfalls

| Issue | Fix |
|-------|-----|
| Toolkit placeholder URL | Must be the real `*.codeengine.appdomain.cloud` host |
| Admin UI open on the internet | Always set `GATEWAY_ADMIN_*`; deploy sets `GATEWAY_REQUIRE_AUTH` |
| Poller quiet after scale-to-zero | Set `CE_MIN_SCALE=1` (default in script) |
| Config edits on ephemeral disk | Prefer admin UI / bindings API; bake defaults in image or externalize if you need durable YAML |
| Slack Events still on old ngrok URL | Point Slack at the CE `/slack/events` URL |

---

## When to use local ngrok instead

Use **[Local + ngrok](../local-ngrok/)** for fast iteration without IBM Cloud deploy cycles. Switch back here for a URL that Slack and WxO can keep forever.
