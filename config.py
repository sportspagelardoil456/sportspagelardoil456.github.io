# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# ---
"""Load / save gateway config (YAML) with ${ENV} expansion."""

from __future__ import annotations

import os
import re
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = HERE / "config.yaml"
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

_lock = threading.RLock()
_cache: Optional["GatewayConfig"] = None
_config_path: Path = DEFAULT_CONFIG_PATH


def _expand_env(value: str) -> str:
    def repl(m: re.Match[str]) -> str:
        key, default = m.group(1), m.group(2)
        env = os.getenv(key)
        if env is not None and env != "":
            return env
        return default if default is not None else m.group(0)

    return ENV_PATTERN.sub(repl, value)


def _expand_tree(obj: Any) -> Any:
    if isinstance(obj, str):
        return _expand_env(obj)
    if isinstance(obj, list):
        return [_expand_tree(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand_tree(v) for k, v in obj.items()}
    return obj


@dataclass
class WxOBinding:
    agent_id: str
    instance_url: str = ""
    api_key: str = ""
    token_url: str = (
        "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token"
    )


@dataclass
class ChannelBinding:
    name: str
    slack_channel_id: str
    wxo: WxOBinding
    enabled: bool = True
    mode: str = "poll"  # poll | events | both
    poll_sec: float = 4.0
    lookback_sec: float = 600.0
    reply_mode: str = "gateway_thread"  # gateway_thread | agent_tools


@dataclass
class GatewayConfig:
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    wxo_defaults: dict[str, str] = field(default_factory=dict)
    bindings: list[ChannelBinding] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def binding_for_channel(self, channel_id: str) -> Optional[ChannelBinding]:
        for b in self.bindings:
            if b.enabled and b.slack_channel_id == channel_id:
                return b
        return None

    def poll_bindings(self) -> list[ChannelBinding]:
        return [
            b
            for b in self.bindings
            if b.enabled and b.mode in ("poll", "both")
        ]

    def events_bindings(self) -> list[ChannelBinding]:
        return [
            b
            for b in self.bindings
            if b.enabled and b.mode in ("events", "both")
        ]


def _parse_binding(item: dict[str, Any], defaults: dict[str, str]) -> ChannelBinding:
    wxo_raw = dict(item.get("wxo") or {})
    wxo = WxOBinding(
        agent_id=str(wxo_raw.get("agent_id") or defaults.get("agent_id") or ""),
        instance_url=str(
            wxo_raw.get("instance_url") or defaults.get("instance_url") or ""
        ).rstrip("/"),
        api_key=str(wxo_raw.get("api_key") or defaults.get("api_key") or ""),
        token_url=str(
            wxo_raw.get("token_url")
            or defaults.get("token_url")
            or "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token"
        ),
    )
    return ChannelBinding(
        name=str(item.get("name") or item.get("slack_channel_id") or "unnamed"),
        slack_channel_id=str(item.get("slack_channel_id") or ""),
        wxo=wxo,
        enabled=bool(item.get("enabled", True)),
        mode=str(item.get("mode") or "poll"),
        poll_sec=float(item.get("poll_sec") or 4),
        lookback_sec=float(item.get("lookback_sec") or 600),
        reply_mode=str(item.get("reply_mode") or "gateway_thread"),
    )


def load_config(path: Optional[Path] = None, *, force: bool = False) -> GatewayConfig:
    global _cache, _config_path
    path = path or _config_path
    with _lock:
        if _cache is not None and not force and path == _config_path:
            return _cache
        _config_path = path
        if not path.exists():
            example = HERE / "config.example.yaml"
            cfg = GatewayConfig(raw={})
            if example.exists():
                raw = yaml.safe_load(example.read_text()) or {}
                expanded = _expand_tree(raw)
                return _from_expanded(expanded, raw)
            _cache = cfg
            return cfg

        raw = yaml.safe_load(path.read_text()) or {}
        expanded = _expand_tree(raw)
        _cache = _from_expanded(expanded, raw)
        return _cache


def _from_expanded(expanded: dict[str, Any], raw: dict[str, Any]) -> GatewayConfig:
    slack = expanded.get("slack") or {}
    defaults = expanded.get("wxo_defaults") or {}
    bindings = [
        _parse_binding(item, defaults)
        for item in (expanded.get("bindings") or [])
        if isinstance(item, dict)
    ]
    return GatewayConfig(
        slack_bot_token=str(slack.get("bot_token") or ""),
        slack_signing_secret=str(slack.get("signing_secret") or ""),
        wxo_defaults={k: str(v) for k, v in defaults.items()},
        bindings=bindings,
        raw=raw,
    )


def save_config(data: dict[str, Any], path: Optional[Path] = None) -> GatewayConfig:
    """Persist YAML and reload cache."""
    global _cache, _config_path
    path = path or _config_path
    with _lock:
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        _config_path = path
        _cache = None
        return load_config(path, force=True)


def config_as_public_dict(cfg: GatewayConfig) -> dict[str, Any]:
    """UI-safe view (mask secrets)."""
    def mask(s: str) -> str:
        if not s or s.startswith("${"):
            return s
        if len(s) <= 8:
            return "****"
        return s[:4] + "…" + s[-4:]

    bindings = []
    for b in cfg.bindings:
        bindings.append(
            {
                "name": b.name,
                "enabled": b.enabled,
                "slack_channel_id": b.slack_channel_id,
                "mode": b.mode,
                "poll_sec": b.poll_sec,
                "lookback_sec": b.lookback_sec,
                "reply_mode": b.reply_mode,
                "wxo": {
                    "agent_id": b.wxo.agent_id,
                    "instance_url": b.wxo.instance_url,
                    "api_key": mask(b.wxo.api_key),
                    "token_url": b.wxo.token_url,
                },
            }
        )
    return {
        "slack": {
            "bot_token": mask(cfg.slack_bot_token),
            "signing_secret": mask(cfg.slack_signing_secret),
        },
        "wxo_defaults": {
            **cfg.wxo_defaults,
            "api_key": mask(cfg.wxo_defaults.get("api_key", "")),
        },
        "bindings": bindings,
        "raw": deepcopy(cfg.raw),
    }


def set_config_path(path: Path) -> None:
    global _config_path, _cache
    with _lock:
        _config_path = path
        _cache = None


def get_config_path() -> Path:
    return _config_path


def upsert_binding(
    *,
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
) -> dict[str, Any]:
    """
    Add or update a binding in config.yaml (matched by slack_channel_id, else name).
    Preserves other top-level keys and unrelated bindings.
    """
    channel = (slack_channel_id or "").strip()
    aid = (agent_id or "").strip()
    if not channel:
        raise ValueError("slack_channel_id is required")
    if not aid:
        raise ValueError("agent_id is required")
    if mode not in ("poll", "events", "both"):
        raise ValueError("mode must be poll|events|both")
    if reply_mode not in ("gateway_thread", "agent_tools"):
        raise ValueError("reply_mode must be gateway_thread|agent_tools")

    with _lock:
        path = _config_path
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("config root must be a mapping")

        bindings = list(raw.get("bindings") or [])
        if not isinstance(bindings, list):
            bindings = []

        binding_name = (name or "").strip() or channel
        wxo: dict[str, Any] = {"agent_id": aid}
        if instance_url:
            wxo["instance_url"] = instance_url.rstrip("/")
        if api_key:
            wxo["api_key"] = api_key

        new_item: dict[str, Any] = {
            "name": binding_name,
            "enabled": bool(enabled),
            "slack_channel_id": channel,
            "mode": mode,
            "poll_sec": float(poll_sec),
            "lookback_sec": float(lookback_sec),
            "reply_mode": reply_mode,
            "wxo": wxo,
        }

        idx = next(
            (
                i
                for i, b in enumerate(bindings)
                if isinstance(b, dict) and str(b.get("slack_channel_id") or "") == channel
            ),
            None,
        )
        if idx is None and name:
            idx = next(
                (
                    i
                    for i, b in enumerate(bindings)
                    if isinstance(b, dict) and str(b.get("name") or "") == name
                ),
                None,
            )

        action = "created"
        if idx is not None:
            # Preserve any extra keys / env-style secrets on existing wxo block
            old = dict(bindings[idx])
            old_wxo = dict(old.get("wxo") or {})
            old_wxo.update(wxo)
            new_item["wxo"] = old_wxo
            # keep name if caller omitted
            if not (name or "").strip():
                new_item["name"] = str(old.get("name") or binding_name)
            bindings[idx] = new_item
            action = "updated"
        else:
            bindings.append(new_item)

        raw["bindings"] = bindings
        # ensure slack / wxo_defaults stubs exist for first-time files
        raw.setdefault("slack", {"bot_token": "${SLACK_BOT_TOKEN}", "signing_secret": "${SLACK_SIGNING_SECRET}"})
        raw.setdefault(
            "wxo_defaults",
            {
                "token_url": "${WO_MCSP_TOKEN_URL:-https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token}",
                "instance_url": "${WXO_INSTANCE_URL}",
                "api_key": "${WXO_API_KEY}",
            },
        )

        cfg = save_config(raw, path)
        public = config_as_public_dict(cfg)
        match = next(
            (b for b in public["bindings"] if b["slack_channel_id"] == channel),
            new_item,
        )
        return {"ok": True, "action": action, "binding": match, "path": str(path)}
