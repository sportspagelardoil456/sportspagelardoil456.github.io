# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# ---
"""Catalog of implemented + suggested MCP tools for the admin UI."""

from __future__ import annotations

from typing import Any

IMPLEMENTED: list[dict[str, Any]] = [
    {
        "name": "list_bindings",
        "description": "List Slack channel → WxO agent bindings (secrets masked).",
        "params": [],
        "category": "config",
    },
    {
        "name": "upsert_binding",
        "description": "Add/update a channel→agent binding in config.yaml.",
        "params": [
            "slack_channel_id",
            "agent_id",
            "name?",
            "enabled?",
            "mode?",
            "reply_mode?",
            "poll_sec?",
            "lookback_sec?",
            "instance_url?",
            "api_key?",
        ],
        "category": "config",
    },
    {
        "name": "list_slack_channels",
        "description": "conversations.list — discover channel IDs for bindings.",
        "params": ["types?", "exclude_archived?", "limit?"],
        "category": "slack",
    },
    {
        "name": "list_recent_messages",
        "description": "List recent Slack messages in a channel.",
        "params": ["channel_id", "limit?"],
        "category": "slack",
    },
    {
        "name": "list_thread_replies",
        "description": "List replies in a Slack thread (parent + follow-ups).",
        "params": ["channel_id", "thread_ts", "limit?"],
        "category": "slack",
    },
    {
        "name": "get_message_context",
        "description": "Parent + last N replies as a prompt context pack.",
        "params": ["channel_id", "thread_ts", "limit?", "latest_user_text?"],
        "category": "slack",
    },
    {
        "name": "post_thread_reply",
        "description": "Post a threaded Slack reply under thread_ts.",
        "params": ["channel_id", "thread_ts", "text"],
        "category": "slack",
    },
    {
        "name": "set_typing_indicator",
        "description": "Add/remove thinking reaction (hourglass) on a message.",
        "params": ["channel_id", "message_ts", "active?", "emoji?"],
        "category": "slack",
    },
    {
        "name": "list_wxo_agents",
        "description": "List Orchestrate agents (id + name) for binding picker.",
        "params": ["limit?", "channel_id?"],
        "category": "wxo",
    },
    {
        "name": "invoke_wxo_agent",
        "description": "Invoke a WxO agent via Runs API (by channel binding or agent_id).",
        "params": ["text", "channel_id?", "agent_id?", "wait?"],
        "category": "wxo",
    },
    {
        "name": "poll_once",
        "description": "Run one poll cycle for a channel (or all poll bindings).",
        "params": ["channel_id?"],
        "category": "ops",
    },
    {
        "name": "get_gateway_status",
        "description": "Health + binding counts + poller state.",
        "params": [],
        "category": "ops",
    },
    {
        "name": "get_recent_logs",
        "description": "Return recent gateway log lines (ring buffer).",
        "params": ["limit?", "level?", "q?"],
        "category": "ops",
    },
    {
        "name": "run_diagnostics",
        "description": "Run Slack auth + WxO token (+ optional invoke) checks.",
        "params": ["invoke_test?", "channel_id?"],
        "category": "ops",
    },
]

SUGGESTED: list[dict[str, Any]] = [
    {
        "name": "delete_binding",
        "description": "Remove a channel→agent binding by channel_id or name.",
        "why": "Paired with upsert for full MCP-driven config CRUD.",
    },
    {
        "name": "invite_bot_to_channel",
        "description": "conversations.join / invite bot into a channel by id.",
        "why": "Finish multi-channel setup without leaving Slack admin.",
    },
]


def catalog() -> dict[str, Any]:
    return {
        "endpoint": "/mcp",
        "transport": "streamable_http",
        "server": "slack-wxo-gateway",
        "implemented": IMPLEMENTED,
        "suggested": SUGGESTED,
    }
