# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# ---
"""watsonx Orchestrate Runs API helpers."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from .config import WxOBinding

log = logging.getLogger("slack_mcp_gateway.wxo")


class WxOClient:
    def __init__(self, binding: WxOBinding):
        self.binding = binding

    def token(self) -> str:
        r = requests.post(
            self.binding.token_url,
            json={"apikey": self.binding.api_key},
            timeout=20,
        )
        r.raise_for_status()
        d = r.json()
        tok = d.get("token") or d.get("access_token") or ""
        if not tok:
            raise RuntimeError("WxO token endpoint returned no token")
        return tok

    def invoke_agent(
        self,
        text: str,
        *,
        wait: bool = True,
        return_assistant_text: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "Content-Type": "application/json",
        }
        base = self.binding.instance_url.rstrip("/")
        r = requests.post(
            f"{base}/v1/orchestrate/runs",
            headers=headers,
            json={
                "agent_id": self.binding.agent_id,
                "message": {"role": "user", "content": text},
            },
            timeout=30,
        )
        r.raise_for_status()
        run = r.json()
        run_id = run["run_id"]
        thread_id = run.get("thread_id")
        log.info(
            "WxO run started run_id=%s agent=%s text=%r",
            run_id,
            self.binding.agent_id,
            text[:80],
        )
        out: dict[str, Any] = {
            "run_id": run_id,
            "thread_id": thread_id,
            "agent_id": self.binding.agent_id,
            "status": "started",
            "assistant_text": "",
        }
        if not wait:
            return out

        status = "unknown"
        for _ in range(60):
            time.sleep(2)
            st = requests.get(
                f"{base}/v1/orchestrate/runs/{run_id}",
                headers=headers,
                timeout=20,
            ).json()
            status = st.get("status") or "unknown"
            if status in ("completed", "failed", "error", "cancelled"):
                break
        out["status"] = status

        if return_assistant_text and thread_id and status == "completed":
            out["assistant_text"] = self._last_assistant_text(base, headers, thread_id)
        return out

    def list_agents(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """List Orchestrate agents (id, name, description, tool count)."""
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "Content-Type": "application/json",
        }
        base = self.binding.instance_url.rstrip("/")
        r = requests.get(
            f"{base}/v1/orchestrate/agents",
            headers=headers,
            params={"limit": max(1, min(limit, 200))},
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
        agents = payload if isinstance(payload, list) else payload.get("data") or []
        out: list[dict[str, Any]] = []
        for a in agents:
            if not isinstance(a, dict):
                continue
            tools = a.get("tools") or []
            out.append(
                {
                    "id": a.get("id") or a.get("agent_id"),
                    "name": a.get("name") or a.get("display_name"),
                    "display_name": a.get("display_name") or a.get("name"),
                    "description": (a.get("description") or "")[:240],
                    "llm": a.get("llm"),
                    "tools_count": len(tools) if isinstance(tools, list) else 0,
                }
            )
        out.sort(key=lambda x: (x.get("name") or "").lower())
        return out

    def _last_assistant_text(
        self, base: str, headers: dict[str, str], thread_id: str
    ) -> str:
        """Prefer the last non-noise assistant text (skip bare 'done' / 'skip')."""
        msgs_resp = requests.get(
            f"{base}/v1/orchestrate/threads/{thread_id}/messages",
            headers=headers,
            timeout=20,
        )
        msgs_resp.raise_for_status()
        payload = msgs_resp.json()
        messages = payload if isinstance(payload, list) else payload.get("data", [])
        noise = {"done", "skip", "ok", "agent is typing...", "agent is typing…"}
        texts: list[str] = []
        for msg in messages:
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            chunks: list[str] = []
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        chunks.append(part["text"])
            elif isinstance(content, str):
                chunks.append(content)
            for t in chunks:
                s = (t or "").strip()
                if s and s.lower() not in noise and not s.lower().startswith("debug_"):
                    texts.append(s)
        return texts[-1] if texts else ""
