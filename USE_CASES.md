# Real-world use cases — Slack ↔ WxO MCP Gateway

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

These are the scenarios this gateway is meant for — beyond “hello / 2+2”.
Each case maps to concrete tools, a test path, and pass criteria.

---

## Agents (defaults)

| Agent | File | Purpose |
|-------|------|---------|
| `slack_gateway_test_agent` | [`agent.yaml`](agent.yaml) | Full-toolkit **smoke** agent (all 14 tools) |
| `slack_gateway_ops_agent` | [`agents/slack_gateway_ops_agent.yaml`](agents/slack_gateway_ops_agent.yaml) | **Ops** agent for day-2 routing / diagnostics |
| `slack_gateway_answer_agent` | [`agents/slack_gateway_answer_agent.yaml`](agents/slack_gateway_answer_agent.yaml) | Answer-only agent for `reply_mode: gateway_thread` (no Slack tools, no `done`) |

Both toolkit agents ship with **all** `slack_wxo_gateway:*` tools by default.

---

## Use case A — Multi-channel support desk

**Story:** `#support`, `#billing`, and `#vip` each map to a different WxO agent. Humans type freely (no @mention). Replies stay in-thread; follow-ups like “what about ticket 12?” keep working.

**Config**

```yaml
bindings:
  - name: support
    slack_channel_id: C_SUPPORT
    mode: poll
    reply_mode: gateway_thread
    wxo: { agent_id: ${WXO_SUPPORT_AGENT_ID} }
  - name: billing
    slack_channel_id: C_BILLING
    mode: poll
    reply_mode: gateway_thread
    wxo: { agent_id: ${WXO_BILLING_AGENT_ID} }
```

**Tools involved:** poller → `invoke` (Runs API) → `post_thread_reply` (gateway side); MCP: `list_bindings`, `upsert_binding`, `get_message_context`.

**How to test**

```bash
# Ops agent creates/updates a binding (pipe exit — chat ask stays interactive)
printf 'exit\n' | orchestrate chat ask -n slack_gateway_ops_agent \
  "upsert_binding channel C0BHWEZ7NLC to agent <answer-agent-id> name demo reply_mode gateway_thread mode poll"

# Human path
# 1) Post "hello" in the Slack channel
# 2) Reply in-thread "what is 2+2"
# Expect: one helpful reply each time, no bare "done"
```

**Pass:** threaded answers; follow-ups answered; no duplicate `done`.

---

## Use case B — Incident / on-call channel

**Story:** `#incidents` wakes a triage agent on every message. Operator (or ops agent) checks gateway health and recent logs when Slack goes quiet.

**Tools:** `run_diagnostics_tool`, `get_recent_logs`, `get_gateway_status`, `poll_once`, `list_recent_messages`.

**How to test**

```bash
orchestrate chat ask -n slack_gateway_ops_agent \
  "Run run_diagnostics_tool (invoke_test=false) and get_recent_logs limit 20. Is the gateway healthy?"
```

**Pass:** diagnostics show Slack auth + WxO token OK; logs show poll/process lines.

---

## Use case C — Self-serve channel → agent routing (admin in chat)

**Story:** An admin asks the ops agent: “Route `#sales` to the sales agent.” The agent discovers IDs and writes `config.yaml` via MCP — no YAML edit on the host.

**Tools:** `list_slack_channels`, `list_wxo_agents`, `upsert_binding`, `list_bindings`, `poll_once`.

**How to test**

```bash
orchestrate chat ask -n slack_gateway_ops_agent \
  "List Slack channels and WxO agents. Show current bindings. Do not upsert unless I confirm."
```

**Pass:** real channel/agent IDs returned (or SOFT_FAIL `missing_scope` on `list_slack_channels` until `channels:read` is granted).

---

## Use case D — Thread-aware follow-up (context pack)

**Story:** User continues an existing Slack thread. The gateway (or ops agent) loads parent + replies so the answer agent sees full context.

**Tools:** `get_message_context`, `list_thread_replies`, `post_thread_reply` / gateway_thread poller.

**How to test**

```bash
./test_tools_e2e.sh
# or manually:
orchestrate chat ask -n slack_gateway_test_agent \
  "For channel C0BHWEZ7NLC, list_recent_messages, then get_message_context on the newest ts."
```

**Pass:** `prompt_context` includes parent + replies; in Slack, follow-up questions get answered in-thread.

---

## Use case E — Hosted MCP on Code Engine (no laptop / ngrok)

**Story:** Production toolkit URL is the CE app `/mcp`. WxO agents call tools from the cloud; dashboard is Basic-auth protected.

**How to test**

```bash
./deploy_code_engine.sh          # once
./test_code_engine.sh            # health + auth + MCP
./test_tools_e2e.sh              # orchestrate CLI + Slack tool path
```

**Pass:** `test_code_engine.sh` all PASS; CLI smoke table mostly PASS; Slack shows `[e2e] gateway-e2e-…` thread reply.

---

## Full regression (recommended)

```bash
cd slack_mcp_gateway

# 1) Platform smoke (CE)
./test_code_engine.sh

# 2) Toolkit + agents + CLI + Slack
./test_tools_e2e.sh

# 3) Manual Slack (human)
#    In bound channel: "hello" then in-thread "summarize this thread"
```

| Layer | Command / action | Expect |
|-------|------------------|--------|
| CE URL | `curl $CE/health` | `status=ok`, `admin_auth=true` |
| Dashboard | open `$CE/` | Basic Auth prompt |
| MCP | toolkit registered to `$CE/mcp` | tools list in WxO |
| CLI agent | `orchestrate chat ask -n slack_gateway_test_agent '…smoke…'` | Tool\|Status table |
| Slack tools | `test_tools_e2e.sh` step 4 | `[e2e]` message in channel |
| Slack humans | post + thread follow-up | answer-only agent, no `done` |

---

## Slack scopes for full fidelity

| Scope | Unlocks |
|-------|---------|
| `channels:history` / `groups:history` | poll + recent messages |
| `chat:write` | thread replies |
| `channels:read` / `groups:read` | `list_slack_channels` |
| `reactions:write` | `set_typing_indicator` (⏳) |

Reinstall the Slack app after adding scopes.
