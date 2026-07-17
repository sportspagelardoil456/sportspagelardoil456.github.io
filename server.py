#!/usr/bin/env python3
# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# Research | Floor 7.5 — https://pages.github.ibm.com/mvankempen/homepage/
# No bug too small, no syntax too weird.
# ---
"""
Slack ↔ WxO MCP Gateway

- Hosted config: map many Slack channels → many WxO agents
- Background poller (+ optional Slack Events)
- MCP tools (streamable HTTP at /mcp) for invoke / post / list
- Simple config UI at /

Usage:
  cd slack_mcp_gateway
  cp config.example.yaml config.yaml   # edit bindings
  python server.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .auth import admin_credentials, check_admin_auth
from .config import (
    DEFAULT_CONFIG_PATH,
    config_as_public_dict,
    get_config_path,
    load_config,
    save_config,
    set_config_path,
    upsert_binding as config_upsert_binding,
)
from .diagnostics import run_diagnostics
from .log_buffer import LOG_BUFFER, attach_log_buffer
from .poller import process_message, run_poll_once, start_poller
from .slack_api import SlackClient
from .tools_catalog import catalog as tools_catalog
from .wxo_api import WxOClient

HERE = Path(__file__).resolve().parent


def _load_env_files() -> None:
    """Load parent envs first, then local .env (override). Reject placeholder tokens."""
    # Parents first (no override), then local gateway .env overrides.
    load_dotenv(HERE.parent.parent / ".env")
    load_dotenv(HERE.parent / ".env")
    load_dotenv(HERE.parent / "mvk.env")
    load_dotenv(HERE / ".env", override=True)

    # channel_poller alias
    if not os.getenv("SLACK_BOT_TOKEN") and os.getenv("slack_Bot_oAuthToken"):
        os.environ["SLACK_BOT_TOKEN"] = os.environ["slack_Bot_oAuthToken"]
    if not os.getenv("SLACK_SIGNING_SECRET") and os.getenv("slack_Signing_Secret"):
        os.environ["SLACK_SIGNING_SECRET"] = os.environ["slack_Signing_Secret"]
    if not os.getenv("WXO_INSTANCE_URL") and os.getenv("WO_NEW_INSTANCE_URL"):
        os.environ["WXO_INSTANCE_URL"] = os.environ["WO_NEW_INSTANCE_URL"]
    if not os.getenv("WXO_API_KEY") and os.getenv("WO_NEW_API_KEY"):
        os.environ["WXO_API_KEY"] = os.environ["WO_NEW_API_KEY"]

    tok = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
    if tok in ("", "xoxb-...", "xoxb-your-bot-token") or (
        tok.startswith("xoxb-") and len(tok) < 20
    ):
        # Fall back to mvk / parent if local .env still has the example placeholder
        for key in ("slack_Bot_oAuthToken",):
            alt = (os.getenv(key) or "").strip()
            if alt.startswith("xoxb-") and len(alt) > 20:
                os.environ["SLACK_BOT_TOKEN"] = alt
                break


_load_env_files()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
attach_log_buffer()
log = logging.getLogger("slack_mcp_gateway")

# FastMCP defaults host=127.0.0.1 which enables DNS-rebinding protection and
# rejects ngrok Host headers (421). Disable for tunnel/public MCP use.
_mcp_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
if os.getenv("GATEWAY_ALLOWED_HOSTS"):
    _mcp_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[h.strip() for h in os.environ["GATEWAY_ALLOWED_HOSTS"].split(",") if h.strip()],
    )

mcp = FastMCP(
    "slack-wxo-gateway",
    instructions=(
        "Hosted Slack gateway for watsonx Orchestrate. "
        "Tools invoke WxO agents and post Slack thread replies. "
        "Channel→agent routing is configured on the gateway host."
    ),
    transport_security=_mcp_security,
    # WxO remote toolkits open short-lived MCP sessions; sticky session state
    # breaks with "Session terminated". Stateless mode fixes tool calls.
    stateless_http=True,
)


# ─── MCP tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_bindings() -> str:
    """List configured Slack channel → WxO agent bindings (secrets masked)."""
    cfg = load_config()
    return json.dumps(config_as_public_dict(cfg)["bindings"], indent=2)


@mcp.tool()
def list_recent_messages(channel_id: str, limit: int = 10) -> str:
    """List recent Slack messages in a channel (debug / agent use)."""
    cfg = load_config()
    if not cfg.slack_bot_token:
        return json.dumps({"error": "slack bot_token not configured"})
    slack = SlackClient(cfg.slack_bot_token)
    msgs = slack.history(channel_id, limit=max(1, min(limit, 50)))
    out = [
        {
            "ts": m.get("ts"),
            "user": m.get("user"),
            "bot_id": m.get("bot_id"),
            "text": (m.get("text") or "")[:500],
        }
        for m in msgs
    ]
    return json.dumps(out, indent=2)


@mcp.tool()
def post_thread_reply(channel_id: str, thread_ts: str, text: str) -> str:
    """Post a threaded Slack reply under thread_ts."""
    cfg = load_config()
    if not cfg.slack_bot_token:
        return json.dumps({"error": "slack bot_token not configured"})
    slack = SlackClient(cfg.slack_bot_token)
    data = slack.post_thread_reply(channel_id, thread_ts, text)
    return json.dumps(
        {"ok": data.get("ok"), "error": data.get("error"), "ts": (data.get("message") or {}).get("ts")}
    )


@mcp.tool()
def invoke_wxo_agent(
    text: str,
    channel_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    wait: bool = True,
) -> str:
    """
    Invoke a watsonx Orchestrate agent via the Runs API.

    If channel_id is set, uses that binding's agent/instance.
    Else if agent_id is set, uses wxo_defaults + that agent_id.
    """
    cfg = load_config()
    binding = None
    if channel_id:
        binding = cfg.binding_for_channel(channel_id)
        if not binding:
            return json.dumps({"error": f"no binding for channel {channel_id}"})
        wxo = WxOClient(binding.wxo)
    else:
        from .config import WxOBinding

        aid = agent_id or cfg.wxo_defaults.get("agent_id") or ""
        if not aid:
            return json.dumps({"error": "agent_id or channel_id required"})
        wxo = WxOClient(
            WxOBinding(
                agent_id=aid,
                instance_url=cfg.wxo_defaults.get("instance_url", ""),
                api_key=cfg.wxo_defaults.get("api_key", ""),
                token_url=cfg.wxo_defaults.get(
                    "token_url",
                    "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
                ),
            )
        )
    result = wxo.invoke_agent(text, wait=wait, return_assistant_text=True)
    return json.dumps(result, indent=2)


@mcp.tool()
def poll_once(channel_id: Optional[str] = None) -> str:
    """
    Run one poll cycle for a channel (or all poll bindings).
    Useful for schedulers / manual wake-up.
    """
    names = run_poll_once(channel_id)
    if channel_id and not names:
        return json.dumps({"error": f"no binding for {channel_id}"})
    return json.dumps({"ok": True, "bindings": names})


@mcp.tool()
def list_thread_replies(channel_id: str, thread_ts: str, limit: int = 30) -> str:
    """List replies in a Slack thread (includes parent as first message)."""
    cfg = load_config()
    if not cfg.slack_bot_token:
        return json.dumps({"error": "slack bot_token not configured"})
    slack = SlackClient(cfg.slack_bot_token)
    msgs = slack.replies(channel_id, thread_ts, limit=max(1, min(limit, 100)))
    out = [
        {
            "ts": m.get("ts"),
            "user": m.get("user"),
            "bot_id": m.get("bot_id"),
            "text": (m.get("text") or "")[:500],
            "thread_ts": m.get("thread_ts"),
        }
        for m in msgs
    ]
    return json.dumps(out, indent=2)


@mcp.tool()
def get_gateway_status() -> str:
    """Health + binding counts + poller state."""
    cfg = load_config()
    return json.dumps(
        {
            "status": "ok",
            "bindings": len(cfg.bindings),
            "poll_bindings": len(cfg.poll_bindings()),
            "events_bindings": len(cfg.events_bindings()),
            "poller": True,
            "mcp": "/mcp",
            "config_path": str(get_config_path()),
        },
        indent=2,
    )


@mcp.tool()
def get_recent_logs(limit: int = 50, level: str = "INFO", q: str = "") -> str:
    """Return recent gateway log lines from the in-memory ring buffer."""
    snap = LOG_BUFFER.snapshot(
        limit=max(1, min(limit, 500)),
        level=level or "INFO",
        q=q or None,
    )
    return json.dumps(snap, indent=2)


@mcp.tool()
def run_diagnostics_tool(
    invoke_test: bool = False,
    channel_id: Optional[str] = None,
) -> str:
    """Run Slack auth + WxO token (+ optional invoke) diagnostic checks."""
    return json.dumps(
        run_diagnostics(invoke_test=invoke_test, channel_id=channel_id),
        indent=2,
    )


@mcp.tool()
def list_slack_channels(
    types: str = "public_channel,private_channel",
    exclude_archived: bool = True,
    limit: int = 200,
) -> str:
    """
    List Slack channels the bot can see (id + name) for binding setup.
    Needs scopes: channels:read, groups:read (for private).
    """
    cfg = load_config()
    if not cfg.slack_bot_token:
        return json.dumps({"error": "slack bot_token not configured"})
    slack = SlackClient(cfg.slack_bot_token)
    channels = slack.list_channels(
        types=types or "public_channel,private_channel",
        exclude_archived=exclude_archived,
        limit=max(1, min(limit, 1000)),
    )
    return json.dumps({"ok": True, "count": len(channels), "channels": channels}, indent=2)


@mcp.tool()
def list_wxo_agents(limit: int = 100, channel_id: Optional[str] = None) -> str:
    """
    List watsonx Orchestrate agents (id, name, description) for binding picker.
    Uses the binding's WxO creds if channel_id is set, else wxo_defaults.
    """
    cfg = load_config()
    from .config import WxOBinding

    if channel_id:
        binding = cfg.binding_for_channel(channel_id)
        if not binding:
            return json.dumps({"error": f"no binding for channel {channel_id}"})
        wxo = WxOClient(binding.wxo)
    else:
        if not cfg.wxo_defaults.get("instance_url") or not cfg.wxo_defaults.get("api_key"):
            return json.dumps({"error": "wxo_defaults instance_url/api_key not configured"})
        wxo = WxOClient(
            WxOBinding(
                agent_id=cfg.wxo_defaults.get("agent_id", "") or "unused",
                instance_url=cfg.wxo_defaults.get("instance_url", ""),
                api_key=cfg.wxo_defaults.get("api_key", ""),
                token_url=cfg.wxo_defaults.get(
                    "token_url",
                    "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
                ),
            )
        )
    try:
        agents = wxo.list_agents(limit=max(1, min(limit, 200)))
        return json.dumps({"ok": True, "count": len(agents), "agents": agents}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@mcp.tool()
def upsert_binding(
    slack_channel_id: str,
    agent_id: str,
    name: Optional[str] = None,
    enabled: bool = True,
    mode: str = "poll",
    reply_mode: str = "gateway_thread",
    poll_sec: float = 4.0,
    lookback_sec: float = 600.0,
    instance_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Add or update a Slack channel → WxO agent binding in config.yaml.
    Match by slack_channel_id (preferred) or name. Poller reloads next cycle.
    """
    try:
        result = config_upsert_binding(
            slack_channel_id=slack_channel_id,
            agent_id=agent_id,
            name=name,
            enabled=enabled,
            mode=mode,
            reply_mode=reply_mode,
            poll_sec=poll_sec,
            lookback_sec=lookback_sec,
            instance_url=instance_url,
            api_key=api_key,
        )
        log.info(
            "upsert_binding %s channel=%s agent=%s",
            result.get("action"),
            slack_channel_id,
            agent_id,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@mcp.tool()
def get_message_context(
    channel_id: str,
    thread_ts: str,
    limit: int = 20,
    latest_user_text: Optional[str] = None,
) -> str:
    """
    Fetch parent + recent thread replies as a prompt context pack.
    Useful for follow-ups so the agent sees full thread history.
    """
    cfg = load_config()
    if not cfg.slack_bot_token:
        return json.dumps({"error": "slack bot_token not configured"})
    slack = SlackClient(cfg.slack_bot_token)
    ctx = slack.message_context(
        channel_id,
        thread_ts,
        limit=max(2, min(limit, 100)),
        latest_user_text=latest_user_text,
    )
    return json.dumps(ctx, indent=2)


@mcp.tool()
def set_typing_indicator(
    channel_id: str,
    message_ts: str,
    active: bool = True,
    emoji: str = "hourglass_flowing_sand",
) -> str:
    """
    Show/hide a 'thinking' reaction on a Slack message (bots have no channel typing API).
    Requires reactions:write. Default emoji: hourglass_flowing_sand.
    """
    cfg = load_config()
    if not cfg.slack_bot_token:
        return json.dumps({"error": "slack bot_token not configured"})
    slack = SlackClient(cfg.slack_bot_token)
    data = slack.set_typing_indicator(
        channel_id,
        message_ts,
        active=active,
        emoji=emoji or "hourglass_flowing_sand",
    )
    return json.dumps(data, indent=2)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _deny_unless_admin(request: Request):
    """Return 401/503 response when admin auth fails; else None."""
    return check_admin_auth(request)


def _verify_slack_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    if not secret:
        log.warning("signing_secret empty — skipping Slack signature check")
        return True
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except (ValueError, TypeError):
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    mac = hmac.new(secret.encode(), base.encode(), hashlib.sha256)
    expected = "v0=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)


@mcp.custom_route("/", methods=["GET"])
async def ui(request: Request) -> HTMLResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    html = (HERE / "ui.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    """Public liveness (no auth) — used by Code Engine / load balancers."""
    cfg = load_config()
    return JSONResponse(
        {
            "status": "ok",
            "bindings": len(cfg.bindings),
            "poll_bindings": len(cfg.poll_bindings()),
            "poller": True,
            "mcp": "/mcp",
            "admin_auth": bool(admin_credentials()),
        }
    )


@mcp.custom_route("/api/config", methods=["GET"])
async def api_config(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    return JSONResponse(config_as_public_dict(load_config()))


@mcp.custom_route("/api/config/raw", methods=["GET"])
async def api_config_raw_get(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    path = get_config_path()
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = (HERE / "config.example.yaml").read_text(encoding="utf-8")
    return JSONResponse({"yaml": text, "path": str(path)})


@mcp.custom_route("/api/config/raw", methods=["PUT"])
async def api_config_raw_put(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    try:
        body = await request.json()
        yaml_text = body.get("yaml") or ""
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return JSONResponse({"error": "YAML must be a mapping"}, status_code=400)
        save_config(data)
        log.info("Config saved via admin UI (%d bindings)", len((data.get("bindings") or [])))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@mcp.custom_route("/api/logs", methods=["GET"])
async def api_logs(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    qp = request.query_params
    try:
        limit = int(qp.get("limit") or 200)
    except ValueError:
        limit = 200
    try:
        since_id = int(qp.get("since_id") or 0)
    except ValueError:
        since_id = 0
    snap = LOG_BUFFER.snapshot(
        limit=limit,
        since_id=since_id,
        level=qp.get("level") or "ALL",
        q=qp.get("q") or None,
    )
    return JSONResponse(snap)


@mcp.custom_route("/api/logs", methods=["DELETE"])
async def api_logs_clear(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    LOG_BUFFER.clear()
    log.info("Log buffer cleared via admin UI")
    return JSONResponse({"ok": True})


@mcp.custom_route("/api/tools", methods=["GET"])
async def api_tools(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    return JSONResponse(tools_catalog())


@mcp.custom_route("/api/diagnostics", methods=["POST"])
async def api_diagnostics(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = run_diagnostics(
        invoke_test=bool(body.get("invoke_test")),
        channel_id=body.get("channel_id") or None,
    )
    return JSONResponse(result)


@mcp.custom_route("/api/poll", methods=["POST"])
async def api_poll(request: Request) -> JSONResponse:
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    try:
        body = await request.json()
    except Exception:
        body = {}
    channel_id = body.get("channel_id") or None
    names = run_poll_once(channel_id)
    if channel_id and not names:
        return JSONResponse({"error": f"no binding for {channel_id}"}, status_code=404)
    log.info("Manual poll via admin UI: %s", names)
    return JSONResponse({"ok": True, "bindings": names})


@mcp.custom_route("/api/example-multi", methods=["GET"])
async def api_example_multi(request: Request) -> JSONResponse:
    """YAML snippet showing multi-channel / multi-agent setup."""
    denied = _deny_unless_admin(request)
    if denied is not None:
        return denied  # type: ignore[return-value]
    example = """# Multi-channel example — one binding per Slack channel
# Get channel IDs: Slack → channel → View channel details → copy ID
# Get agent IDs: WxO UI → Agents → open agent → id in URL / API

bindings:
  - name: support_channel
    enabled: true
    slack_channel_id: C0BHWEZ7NLC          # #support
    mode: poll                             # poll | events | both
    poll_sec: 4
    lookback_sec: 600
    reply_mode: gateway_thread             # gateway posts the answer
    wxo:
      agent_id: 1e8612b5-73f1-43aa-a105-dbde4e409d3b   # slack_gateway_answer_agent

  - name: sales_channel
    enabled: true
    slack_channel_id: C0123456789          # #sales
    mode: poll
    poll_sec: 5
    reply_mode: gateway_thread
    wxo:
      agent_id: ${WXO_SALES_AGENT_ID}      # different agent
      # optional override if this channel uses another WxO instance:
      # instance_url: https://...
      # api_key: ${WXO_SALES_API_KEY}

  - name: incidents_events
    enabled: false
    slack_channel_id: C0987654321
    mode: events                           # requires Slack Events → /slack/events
    reply_mode: gateway_thread
    wxo:
      agent_id: ${WXO_INCIDENT_AGENT_ID}
"""
    return JSONResponse({"yaml": example})


@mcp.custom_route("/slack/events", methods=["POST"])
async def slack_events(request: Request) -> JSONResponse:
    raw = await request.body()
    cfg = load_config()
    ts = request.headers.get("x-slack-request-timestamp", "")
    sig = request.headers.get("x-slack-signature", "")
    if not _verify_slack_signature(raw, ts, sig, cfg.slack_signing_secret):
        return JSONResponse({"error": "invalid signature"}, status_code=403)

    try:
        body: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge", "")})

    if body.get("type") != "event_callback":
        return JSONResponse({"ok": True})

    event = body.get("event") or {}
    channel = event.get("channel") or ""
    binding = cfg.binding_for_channel(channel)
    if not binding or binding.mode not in ("events", "both"):
        return JSONResponse({"ok": True, "ignored": "no events binding"})

    if event.get("bot_id") or event.get("subtype") in (
        "bot_message",
        "message_changed",
        "message_deleted",
    ):
        return JSONResponse({"ok": True})

    text = (event.get("text") or "").strip()
    message_ts = event.get("ts") or ""
    thread_ts = event.get("thread_ts") or message_ts
    if not text or not message_ts:
        return JSONResponse({"ok": True})

    # Process synchronously for demo; production should use a background task
    # to meet Slack's 3s ack deadline.
    try:
        process_message(
            cfg,
            binding,
            text=text,
            channel=channel,
            ts=message_ts,
            thread_ts=thread_ts,
        )
    except Exception:
        log.exception("slack event processing failed")
    return JSONResponse({"ok": True})


def main() -> None:
    # Code Engine sets PORT; prefer that, then GATEWAY_PORT, then 3100.
    port = int(os.getenv("PORT") or os.getenv("GATEWAY_PORT") or "3100")
    os.environ["GATEWAY_PORT"] = str(port)

    # On ephemeral CE disks, default config to /tmp if GATEWAY_CONFIG unset and
    # the package path is not writable.
    cfg_path = Path(os.getenv("GATEWAY_CONFIG") or str(DEFAULT_CONFIG_PATH))
    if os.getenv("GATEWAY_CONFIG") is None and not os.access(str(HERE), os.W_OK):
        cfg_path = Path("/tmp/slack_mcp_gateway_config.yaml")
        os.environ["GATEWAY_CONFIG"] = str(cfg_path)

    set_config_path(cfg_path)
    if not cfg_path.exists():
        example = HERE / "config.example.yaml"
        if example.exists():
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            log.info("Wrote initial %s from example", cfg_path)

    if admin_credentials():
        log.info("Admin dashboard Basic Auth enabled (user=%s)", admin_credentials()[0])
    else:
        log.warning(
            "Admin dashboard is OPEN (set GATEWAY_ADMIN_USER + GATEWAY_ADMIN_PASSWORD to lock it)"
        )

    cfg = load_config(force=True)
    tok = (cfg.slack_bot_token or "").strip()
    if not tok.startswith("xoxb-") or len(tok) < 20 or tok.endswith("..."):
        log.error(
            "SLACK_BOT_TOKEN missing/invalid (got %r). "
            "Set a real xoxb- token in slack_mcp_gateway/.env or ../.env — "
            "not the placeholder xoxb-...",
            (tok[:12] + "…") if tok else "",
        )
    else:
        try:
            import requests

            auth = requests.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=15,
            ).json()
            if auth.get("ok"):
                log.info("Slack auth.test ok user=%s team=%s", auth.get("user"), auth.get("team"))
            else:
                log.error("Slack auth.test failed: %s — check bot token / reinstall app", auth.get("error"))
        except Exception:
            log.exception("Slack auth.test request failed")

    start_poller()

    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    log.info("Starting Slack↔WxO MCP Gateway on %s:%s (MCP /mcp, UI /)", host, port)
    # streamable-http serves MCP at /mcp and includes custom_route endpoints
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
