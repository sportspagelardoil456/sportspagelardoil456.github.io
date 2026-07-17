# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# ---
"""Thin Slack Web API helpers."""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

log = logging.getLogger("slack_mcp_gateway.slack")

# Soft errors we don't spam at WARNING (scopes, idempotent reaction races)
_SOFT_ERRORS = frozenset(
    {
        "already_reacted",
        "no_reaction",
        "missing_scope",
        "not_in_channel",
        "channel_not_found",
    }
)
_missing_scope_logged: set[str] = set()


class SlackClient:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.bot_token}"}

    def api(self, method: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> dict[str, Any]:
        url = f"https://slack.com/api/{method}"
        if json is not None:
            r = requests.post(url, headers=self._headers(), json=json, timeout=20)
        else:
            r = requests.get(url, headers=self._headers(), params=params or {}, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            err = data.get("error") or "unknown"
            if err == "missing_scope":
                key = f"{method}:{err}"
                if key not in _missing_scope_logged:
                    _missing_scope_logged.add(key)
                    log.warning(
                        "Slack %s missing_scope (once) — add bot scopes and reinstall the app",
                        method,
                    )
                else:
                    log.debug("Slack %s error: %s", method, err)
            elif err in _SOFT_ERRORS:
                log.debug("Slack %s error: %s", method, err)
            else:
                log.warning("Slack %s error: %s", method, err)
        return data

    def history(self, channel: str, limit: int = 10) -> list[dict[str, Any]]:
        data = self.api("conversations.history", params={"channel": channel, "limit": limit})
        return list(data.get("messages") or [])

    def replies(self, channel: str, ts: str, limit: int = 50) -> list[dict[str, Any]]:
        data = self.api(
            "conversations.replies",
            params={"channel": channel, "ts": ts, "limit": limit},
        )
        return list(data.get("messages") or [])

    def list_channels(
        self,
        *,
        types: str = "public_channel,private_channel",
        exclude_archived: bool = True,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Paginated conversations.list (needs channels:read / groups:read)."""
        out: list[dict[str, Any]] = []
        cursor = ""
        page_limit = max(1, min(limit, 1000))
        while True:
            params: dict[str, Any] = {
                "types": types,
                "exclude_archived": str(exclude_archived).lower(),
                "limit": min(200, page_limit - len(out)) if page_limit else 200,
            }
            if cursor:
                params["cursor"] = cursor
            data = self.api("conversations.list", params=params)
            if not data.get("ok"):
                break
            for ch in data.get("channels") or []:
                out.append(
                    {
                        "id": ch.get("id"),
                        "name": ch.get("name"),
                        "is_private": bool(ch.get("is_private")),
                        "is_member": bool(ch.get("is_member")),
                        "num_members": ch.get("num_members"),
                        "topic": ((ch.get("topic") or {}).get("value") or "")[:120],
                        "purpose": ((ch.get("purpose") or {}).get("value") or "")[:120],
                    }
                )
                if len(out) >= page_limit:
                    return out
            cursor = (data.get("response_metadata") or {}).get("next_cursor") or ""
            if not cursor:
                break
        return out

    def has_bot_reply(self, channel: str, ts: str) -> bool:
        msgs = self.replies(channel, ts, limit=10)
        if not msgs:
            return False
        for m in msgs[1:]:
            if m.get("bot_id"):
                return True
        return False

    def post_thread_reply(self, channel: str, thread_ts: str, text: str) -> dict[str, Any]:
        return self.api(
            "chat.postMessage",
            json={"channel": channel, "thread_ts": thread_ts, "text": text},
        )

    def add_reaction(self, channel: str, timestamp: str, name: str) -> dict[str, Any]:
        return self.api(
            "reactions.add",
            json={"channel": channel, "timestamp": timestamp, "name": name},
        )

    def remove_reaction(self, channel: str, timestamp: str, name: str) -> dict[str, Any]:
        return self.api(
            "reactions.remove",
            json={"channel": channel, "timestamp": timestamp, "name": name},
        )

    def set_typing_indicator(
        self,
        channel: str,
        timestamp: str,
        *,
        active: bool = True,
        emoji: str = "hourglass_flowing_sand",
    ) -> dict[str, Any]:
        """
        Slack has no bot 'typing…' in channels; use a reaction as a thinking indicator.
        Requires reactions:write. already_reacted / no_reaction are treated as soft ok.
        """
        name = (emoji or "hourglass_flowing_sand").strip().strip(":")
        data = self.add_reaction(channel, timestamp, name) if active else self.remove_reaction(
            channel, timestamp, name
        )
        err = data.get("error")
        soft_ok = err in (None, "already_reacted", "no_reaction")
        return {
            "ok": bool(data.get("ok") or soft_ok),
            "active": active,
            "emoji": name,
            "error": None if soft_ok else err,
        }

    def message_context(
        self,
        channel: str,
        thread_ts: str,
        *,
        limit: int = 20,
        latest_user_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """Parent + recent replies as structured data and a prompt pack."""
        lim = max(2, min(limit, 100))
        msgs = self.replies(channel, thread_ts, limit=lim)
        if not msgs:
            return {
                "ok": False,
                "error": "no messages",
                "channel_id": channel,
                "thread_ts": thread_ts,
                "parent": None,
                "replies": [],
                "prompt_context": "",
            }

        def _norm(m: dict[str, Any]) -> dict[str, Any]:
            role = "bot" if m.get("bot_id") else "user"
            return {
                "ts": m.get("ts"),
                "role": role,
                "user": m.get("user"),
                "bot_id": m.get("bot_id"),
                "text": (m.get("text") or "").strip(),
            }

        parent = _norm(msgs[0])
        replies = [_norm(m) for m in msgs[1:]]
        # Keep last N replies in the prompt (parent always included)
        keep = replies[-(lim - 1) :] if replies else []
        lines = [
            "Slack thread context:",
            f"[parent] ({parent['role']}): {parent['text']}",
        ]
        for r in keep:
            lines.append(f"[{r['role']}] {r['text']}")
        if latest_user_text:
            lines.append("")
            lines.append(f"Latest user message:\n{latest_user_text.strip()}")
        return {
            "ok": True,
            "channel_id": channel,
            "thread_ts": thread_ts,
            "parent": parent,
            "replies": replies,
            "prompt_context": "\n".join(lines).strip(),
        }
