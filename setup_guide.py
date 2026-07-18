# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
"""Admin Setup tab content: Slack / WxO checklists, env readiness, example agents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# Bot token scopes the gateway expects (soft-fail when missing for helpers).
SLACK_BOT_SCOPES = [
    {"scope": "channels:history", "why": "Read public channel messages (poller)"},
    {"scope": "groups:history", "why": "Read private channel messages (poller)"},
    {"scope": "chat:write", "why": "Post thread replies (gateway_thread)"},
    {"scope": "channels:read", "why": "list_slack_channels (public)"},
    {"scope": "groups:read", "why": "list_slack_channels (private)"},
    {"scope": "reactions:write", "why": "Typing ⏳ via set_typing_indicator"},
    {"scope": "app_mentions:read", "why": "Optional if you also use byo_slack @mentions"},
]

ENV_CHECKS: list[dict[str, str]] = [
    {
        "key": "SLACK_BOT_TOKEN",
        "required": "yes",
        "hint": "xoxb-… from Slack app → OAuth & Permissions",
    },
    {
        "key": "SLACK_SIGNING_SECRET",
        "required": "events",
        "hint": "Required only for mode: events|both (Slack → /slack/events)",
    },
    {
        "key": "WXO_INSTANCE_URL",
        "required": "yes",
        "hint": "Orchestrate instance base URL (no trailing slash)",
    },
    {
        "key": "WXO_API_KEY",
        "required": "yes",
        "hint": "WxO / MCSP API key for Runs API",
    },
    {
        "key": "WXO_AGENT_ID",
        "required": "recommended",
        "hint": "Default agent for bindings (${WXO_AGENT_ID})",
    },
    {
        "key": "WO_MCSP_TOKEN_URL",
        "required": "optional",
        "hint": "Defaults to IBM SaaS IAM token URL if unset",
    },
    {
        "key": "GATEWAY_ADMIN_USER",
        "required": "recommended",
        "hint": "Basic Auth for / and /api/* (pair with PASSWORD)",
    },
    {
        "key": "GATEWAY_ADMIN_PASSWORD",
        "required": "recommended",
        "hint": "Basic Auth password — never commit",
    },
    {
        "key": "GATEWAY_REQUIRE_AUTH",
        "required": "optional",
        "hint": "Set true on Code Engine so dashboard fails closed if auth missing",
    },
]

AGENT_CATALOG: list[dict[str, str]] = [
    {
        "id": "slack_gateway_answer_agent",
        "path": "agents/slack_gateway_answer_agent.yaml",
        "role": "Channel answers",
        "when": "reply_mode: gateway_thread — agent returns text only; gateway posts Slack thread. No Slack tools; never say done.",
    },
    {
        "id": "slack_gateway_ops_agent",
        "path": "agents/slack_gateway_ops_agent.yaml",
        "role": "Day-2 ops",
        "when": "Routing, bindings, diagnostics, optional post_thread_reply via MCP toolkit.",
    },
    {
        "id": "slack_gateway_test_agent",
        "path": "agent.yaml",
        "role": "Smoke / e2e",
        "when": "Full 14-tool smoke via orchestrate chat ask before production.",
    },
]


def _env_set(key: str) -> bool:
    val = (os.getenv(key) or "").strip()
    if not val:
        return False
    # Treat common placeholders as unset
    bad = ("xoxb-...", "change-me", "your-", "REPLACE", "xxx")
    low = val.lower()
    return not any(b.lower() in low for b in bad)


def env_checklist() -> list[dict[str, Any]]:
    rows = []
    for item in ENV_CHECKS:
        key = item["key"]
        present = _env_set(key)
        rows.append(
            {
                "key": key,
                "set": present,
                "required": item["required"],
                "hint": item["hint"],
            }
        )
    return rows


def load_agent_examples() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for meta in AGENT_CATALOG:
        path = HERE / meta["path"]
        yaml_text = path.read_text(encoding="utf-8") if path.exists() else f"# missing: {meta['path']}\n"
        out.append(
            {
                "id": meta["id"],
                "path": meta["path"],
                "role": meta["role"],
                "when": meta["when"],
                "yaml": yaml_text,
                "import_cmd": f"orchestrate agents import -f {meta['path']}\norchestrate agents deploy -n {meta['id']}",
            }
        )
    return out


def public_base_url(request_base: str | None = None) -> str:
    if request_base:
        return request_base.rstrip("/")
    port = os.getenv("PORT") or os.getenv("GATEWAY_PORT") or "3100"
    return f"http://localhost:{port}"


def setup_payload(*, base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    mcp_url = f"{base}/mcp"
    return {
        "base_url": base,
        "endpoints": {
            "admin": f"{base}/",
            "mcp": mcp_url,
            "slack_events": f"{base}/slack/events",
            "health": f"{base}/health",
        },
        "env": env_checklist(),
        "slack": {
            "scopes": SLACK_BOT_SCOPES,
            "steps": [
                "Create a Slack app (api.slack.com/apps) → From scratch.",
                "OAuth & Permissions → add Bot Token Scopes listed below → Install to workspace.",
                "Copy Bot User OAuth Token → SLACK_BOT_TOKEN (must start with xoxb-).",
                "Basic Information → Signing Secret → SLACK_SIGNING_SECRET (needed for Events).",
                "Invite the bot to each channel: /invite @YourBot",
                "Copy Channel ID (channel details) into config.yaml bindings.slack_channel_id.",
                f"For mode: events|both → Event Subscriptions → Request URL = {base}/slack/events; subscribe to message.channels / message.groups.",
                "After adding channels:read, groups:read, or reactions:write → Reinstall the app.",
            ],
            "events_note": "Poll mode needs no Events URL. Prefer poll for multi-channel; use events if you want push + lower latency.",
        },
        "wxo": {
            "steps": [
                "Set WXO_INSTANCE_URL + WXO_API_KEY (+ optional WXO_AGENT_ID) in .env.",
                "Deploy/start this gateway so /mcp is reachable (local+ngrok, or Code Engine).",
                "Register the remote MCP toolkit (command below) — URL must resolve (no placeholder host).",
                "Import an example agent YAML (Setup → Example agents) and deploy it.",
                "Put that agent's id into the channel binding (Config tab) with reply_mode: gateway_thread for answer-only agents.",
                "Run Diagnostics → Slack + WxO; then send a test message in the Slack channel.",
            ],
            "toolkit_add": (
                f'orchestrate toolkits add -k mcp -n slack_wxo_gateway \\\n'
                f'  --description "Slack↔WxO MCP Gateway" \\\n'
                f'  --url "{mcp_url}" \\\n'
                f'  --transport streamable_http \\\n'
                f'  --tools "*"'
            ),
            "toolkit_remove": "orchestrate toolkits remove -n slack_wxo_gateway",
            "list_tools": "orchestrate tools list | rg -i slack_wxo",
            "chat_smoke": (
                "orchestrate chat ask -n slack_gateway_test_agent \\\n"
                "  'Run a full gateway tool smoke test. Return Tool|Status|Notes table.'"
            ),
        },
        "reply_modes": [
            {
                "mode": "gateway_thread",
                "label": "Recommended",
                "detail": "Gateway calls Runs API, then chat.postMessage in-thread. Use slack_gateway_answer_agent (no Slack tools, never say done).",
            },
            {
                "mode": "agent_tools",
                "label": "Advanced",
                "detail": "Gateway only starts the agent; agent must post via its own Slack tools. Can conflict with byo_slack finals.",
            },
        ],
        "deploy_paths": [
            {
                "id": "local-http",
                "title": "A · Local HTTP",
                "dir": "docs/PUBLISH-MODES.md",
                "summary": "./scripts/run.sh --mode http — UI + /mcp + poller on laptop.",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/PUBLISH-MODES.md",
            },
            {
                "id": "podman",
                "title": "B · Docker / Podman",
                "dir": "docs/PUBLISH-MODES.md",
                "summary": "./scripts/run.sh --mode podman — same image locally.",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/PUBLISH-MODES.md",
            },
            {
                "id": "code-engine",
                "title": "C · IBM Code Engine",
                "dir": "docs/code-engine/",
                "summary": "./scripts/run.sh --mode ce — always-on HTTPS + secrets.",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/tree/main/docs/code-engine",
            },
            {
                "id": "ide",
                "title": "D · Cursor / VS Code IDE",
                "dir": "docs/ide/",
                "summary": "./scripts/run.sh --mode ide — stdio mcp.json (or mcp-remote to A/B/C).",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/tree/main/docs/ide",
            },
        ],
        "ide_clients": [
            {
                "id": "cursor",
                "title": "Cursor",
                "config": "~/.cursor/mcp.json",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/ide/cursor.md",
                "remote_snippet": f'npx -y mcp-remote "{mcp_url}"',
            },
            {
                "id": "vscode",
                "title": "VS Code",
                "config": "User/mcp.json or .vscode/mcp.json",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/ide/vscode.md",
                "remote_snippet": f'{{ "type": "http", "url": "{mcp_url}" }}',
            },
            {
                "id": "bob",
                "title": "IBM Bob",
                "config": "~/.bob/settings/mcp_settings.json",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/ide/bob.md",
                "remote_snippet": f'npx -y mcp-remote "{mcp_url}"',
            },
            {
                "id": "antigravity",
                "title": "Google Antigravity",
                "config": "~/.gemini/config/mcp_config.json",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/ide/antigravity.md",
                "remote_snippet": f'npx -y mcp-remote "{mcp_url}"',
            },
            {
                "id": "claude-desktop",
                "title": "Claude Desktop",
                "config": "claude_desktop_config.json",
                "docs_url": "https://github.com/markusvankempen/slack-wxo-mcp-gateway/blob/main/docs/ide/claude-desktop.md",
                "remote_snippet": f'npx -y mcp-remote "{mcp_url}"',
            },
        ],
        "why_tags": [
            {
                "tag": "every-message",
                "limitation": "byo_slack is mainly @mention/DM",
                "lift": "Poller/Events wake agents on every human channel message",
            },
            {
                "tag": "multi-channel",
                "limitation": "Hard to map many channels → many agents",
                "lift": "One bindings table + admin UI / upsert_binding",
            },
            {
                "tag": "thread-followups",
                "limitation": "In-thread questions often ignored",
                "lift": "Poller reads thread replies and sends context",
            },
            {
                "tag": "gateway-thread",
                "limitation": "Noisy done/typing finals in Slack",
                "lift": "Gateway posts answers; filters noise finals",
            },
            {
                "tag": "mcp-toolkit",
                "limitation": "Agents need a remote MCP edge with real DNS",
                "lift": "Hosted /mcp streamable HTTP for WxO + IDEs + LangGraph/etc.",
            },
        ],
        "tips": [
            "Why MCP: docs/WHY-THIS-MCP.md — lifts byo_slack every-message / multi-channel / thread limits.",
            "Other frameworks connect TO this MCP (docs/frameworks/) — we do not embed LangChain inside the server.",
            "Pick one deploy path: docs/local-ngrok/ or docs/code-engine/ — do not mix tunnel URLs with CE secrets casually.",
            "Public (no admin auth): /health, /mcp, /slack/events. UI + /api/* use Basic Auth when GATEWAY_ADMIN_* are set.",
            "WxO toolkit URL must be a real DNS name — placeholders fail SSRF DNS checks.",
            "In-thread follow-ups are handled by the poller (conversations.replies); top-level bot-reply skip does not block follow-ups.",
            "Noise finals (done, skip, …) are filtered before posting in gateway_thread mode.",
            "Admin password + Slack/WxO secrets belong in .env / Code Engine secrets — never in config.yaml committed to git.",
        ],
        "agents": load_agent_examples(),
        "env_example": (HERE / ".env.example").read_text(encoding="utf-8")
        if (HERE / ".env.example").exists()
        else "",
    }
