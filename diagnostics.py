# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# ---
"""Gateway diagnostic checks for admin UI + MCP."""

from __future__ import annotations

import time
from typing import Any, Optional

import requests

from .config import GatewayConfig, WxOBinding, load_config
from .slack_api import SlackClient
from .wxo_api import WxOClient


def _check(name: str, ok: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail, **extra}


def run_diagnostics(
    *,
    invoke_test: bool = False,
    channel_id: Optional[str] = None,
    cfg: Optional[GatewayConfig] = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    checks: list[dict[str, Any]] = []
    started = time.time()

    # Config / bindings
    n = len(cfg.bindings)
    enabled = [b for b in cfg.bindings if b.enabled]
    checks.append(
        _check(
            "bindings",
            n > 0 and len(enabled) > 0,
            f"{n} binding(s), {len(enabled)} enabled, "
            f"{len(cfg.poll_bindings())} poll / {len(cfg.events_bindings())} events",
            bindings=[
                {
                    "name": b.name,
                    "channel": b.slack_channel_id,
                    "agent_id": b.wxo.agent_id,
                    "mode": b.mode,
                    "reply_mode": b.reply_mode,
                    "enabled": b.enabled,
                    "ready": bool(
                        b.slack_channel_id
                        and b.wxo.agent_id
                        and b.wxo.instance_url
                        and b.wxo.api_key
                    ),
                }
                for b in cfg.bindings
            ],
        )
    )

    # Slack auth
    tok = (cfg.slack_bot_token or "").strip()
    if not tok.startswith("xoxb-") or len(tok) < 20:
        checks.append(_check("slack_auth", False, "SLACK_BOT_TOKEN missing or placeholder"))
    else:
        try:
            auth = requests.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=15,
            ).json()
            if auth.get("ok"):
                checks.append(
                    _check(
                        "slack_auth",
                        True,
                        f"ok user={auth.get('user')} team={auth.get('team')}",
                        user=auth.get("user"),
                        team=auth.get("team"),
                        bot_id=auth.get("bot_id"),
                    )
                )
            else:
                checks.append(
                    _check("slack_auth", False, f"auth.test failed: {auth.get('error')}")
                )
        except Exception as e:
            checks.append(_check("slack_auth", False, f"auth.test error: {e}"))

    # Per-binding channel peek (optional first / selected)
    target = None
    if channel_id:
        target = cfg.binding_for_channel(channel_id)
    elif enabled:
        target = enabled[0]

    if target and tok.startswith("xoxb-") and len(tok) >= 20:
        try:
            slack = SlackClient(tok)
            hist = slack.history(target.slack_channel_id, limit=3)
            checks.append(
                _check(
                    "slack_channel_history",
                    True,
                    f"{target.name} ({target.slack_channel_id}): {len(hist)} recent message(s)",
                    channel_id=target.slack_channel_id,
                )
            )
        except Exception as e:
            checks.append(
                _check(
                    "slack_channel_history",
                    False,
                    f"{target.name}: {e}",
                    channel_id=target.slack_channel_id,
                )
            )

    # WxO token (defaults or target binding)
    wxo_bind: Optional[WxOBinding] = None
    if target:
        wxo_bind = target.wxo
    elif cfg.wxo_defaults.get("api_key") and cfg.wxo_defaults.get("instance_url"):
        wxo_bind = WxOBinding(
            agent_id=cfg.wxo_defaults.get("agent_id", ""),
            instance_url=cfg.wxo_defaults.get("instance_url", ""),
            api_key=cfg.wxo_defaults.get("api_key", ""),
            token_url=cfg.wxo_defaults.get(
                "token_url",
                "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
            ),
        )

    if not wxo_bind or not wxo_bind.api_key or not wxo_bind.instance_url:
        checks.append(_check("wxo_token", False, "WXO instance_url / api_key not configured"))
    else:
        try:
            client = WxOClient(wxo_bind)
            token = client.token()
            checks.append(
                _check(
                    "wxo_token",
                    bool(token),
                    f"token ok (len={len(token)}) instance={wxo_bind.instance_url}",
                )
            )
            if invoke_test and wxo_bind.agent_id:
                result = client.invoke_agent(
                    "Reply with exactly: diagnostic_ok",
                    wait=True,
                    return_assistant_text=True,
                )
                text = (result.get("assistant_text") or "").strip()
                ok = result.get("status") == "completed" and bool(text)
                checks.append(
                    _check(
                        "wxo_invoke",
                        ok,
                        f"status={result.get('status')} answer={text[:120]!r}",
                        run_id=result.get("run_id"),
                        agent_id=wxo_bind.agent_id,
                    )
                )
            elif invoke_test:
                checks.append(
                    _check("wxo_invoke", False, "no agent_id on selected binding/defaults")
                )
        except Exception as e:
            checks.append(_check("wxo_token", False, f"token/invoke error: {e}"))

    ok_all = all(c["ok"] for c in checks)
    return {
        "ok": ok_all,
        "elapsed_ms": int((time.time() - started) * 1000),
        "checks": checks,
    }
