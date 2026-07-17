# ---
# Author: Markus van Kempen | mvk@ca.ibm.com
# ---
"""Background multi-channel poller (channel → WxO agent bindings)."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Optional

from .config import ChannelBinding, GatewayConfig, load_config
from .slack_api import SlackClient
from .wxo_api import WxOClient

log = logging.getLogger("slack_mcp_gateway.poller")

_MENTION = re.compile(r"<@[A-Z0-9]+>")
# Noise final outputs from Option B-style agents — never post these to Slack.
_NOISE = frozenset(
    {
        "done",
        "skip",
        "ok",
        "agent is typing...",
        "agent is typing…",
    }
)
_seen: dict[str, set[str]] = {}
_thread: Optional[threading.Thread] = None
_stop = threading.Event()


def _clean_text(text: str) -> str:
    return _MENTION.sub("", text or "").strip()


def _is_noise(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    if t in _NOISE:
        return True
    if t.startswith("debug_"):
        return True
    return False


def process_message(
    cfg: GatewayConfig,
    binding: ChannelBinding,
    *,
    text: str,
    channel: str,
    ts: str,
    thread_ts: Optional[str] = None,
) -> dict:
    """Shared path for poller + Slack Events."""
    clean = _clean_text(text)
    if not clean or _is_noise(clean):
        return {"ok": False, "reason": "empty_or_noise"}

    slack = SlackClient(cfg.slack_bot_token)
    parent_ts = thread_ts or ts
    is_thread_followup = bool(thread_ts and thread_ts != ts)

    # Only skip top-level messages that already have a bot thread reply.
    # Follow-ups in an existing thread must still be answered.
    if not is_thread_followup and slack.has_bot_reply(channel, parent_ts):
        log.info("Skip %s/%s — already has bot reply (top-level)", channel, parent_ts)
        return {"ok": True, "skipped": "bot_reply"}

    # Thinking reaction on the human message (needs reactions:write)
    slack.set_typing_indicator(channel, ts, active=True)

    try:
        # For in-thread follow-ups, send parent + recent replies as context
        prompt = clean
        if is_thread_followup:
            ctx = slack.message_context(
                channel, parent_ts, limit=20, latest_user_text=clean
            )
            if ctx.get("ok") and ctx.get("prompt_context"):
                prompt = ctx["prompt_context"]

        wxo = WxOClient(binding.wxo)
        if binding.reply_mode == "agent_tools":
            result = wxo.invoke_agent(prompt, wait=True, return_assistant_text=False)
            return {"ok": True, "mode": "agent_tools", **result}

        # gateway_thread: get answer and post thread here
        result = wxo.invoke_agent(prompt, wait=True, return_assistant_text=True)
        answer = (result.get("assistant_text") or "").strip()
        if _is_noise(answer):
            # Common when agent is Option B (posts via tool, final text is "done").
            log.info(
                "Skip posting noise answer %r for %s/%s (tool may have posted already)",
                answer,
                channel,
                parent_ts,
            )
            return {
                "ok": True,
                "skipped": "noise_answer",
                "assistant_text": answer,
                "run_id": result.get("run_id"),
            }
        if not answer:
            answer = "(no response from agent)"

        post = slack.post_thread_reply(channel, parent_ts, answer)
        return {
            "ok": bool(post.get("ok")),
            "mode": "gateway_thread",
            "assistant_text": answer,
            "run_id": result.get("run_id"),
            "slack_error": post.get("error"),
        }
    finally:
        slack.set_typing_indicator(channel, ts, active=False)


def _maybe_handle(
    cfg: GatewayConfig,
    binding: ChannelBinding,
    slack: SlackClient,
    seen: set[str],
    m: dict,
    *,
    default_thread_ts: Optional[str] = None,
) -> None:
    ts = m.get("ts") or ""
    if not ts or ts in seen:
        return
    if m.get("bot_id") or m.get("subtype"):
        seen.add(ts)
        return
    try:
        age = time.time() - float(ts)
    except ValueError:
        seen.add(ts)
        return
    if age > binding.lookback_sec:
        seen.add(ts)
        return
    text = (m.get("text") or "").strip()
    if not text or _is_noise(text):
        seen.add(ts)
        return

    seen.add(ts)
    thread_ts = m.get("thread_ts") or default_thread_ts
    log.info(
        "[%s] new message ts=%s thread_ts=%s text=%r",
        binding.name,
        ts,
        thread_ts,
        text[:100],
    )
    try:
        process_message(
            cfg,
            binding,
            text=text,
            channel=binding.slack_channel_id,
            ts=ts,
            thread_ts=thread_ts,
        )
    except Exception:
        log.exception("[%s] process_message failed", binding.name)


def _poll_binding(cfg: GatewayConfig, binding: ChannelBinding) -> None:
    channel = binding.slack_channel_id
    if not channel or not cfg.slack_bot_token:
        return
    if not binding.wxo.agent_id or not binding.wxo.instance_url or not binding.wxo.api_key:
        log.warning("Binding %s missing WxO credentials — skip", binding.name)
        return

    slack = SlackClient(cfg.slack_bot_token)
    seen = _seen.setdefault(channel, set())
    msgs = slack.history(channel, limit=15)

    # 1) Top-level channel messages
    for m in reversed(msgs):
        _maybe_handle(cfg, binding, slack, seen, m)

    # 2) In-thread human replies (follow-ups like "what is 2+2" under hello)
    for m in msgs:
        parent_ts = m.get("ts") or ""
        if not parent_ts:
            continue
        reply_count = int(m.get("reply_count") or 0)
        latest = m.get("latest_reply") or ""
        if reply_count <= 0 and not latest:
            continue
        # Only inspect threads that had recent activity
        try:
            if latest and (time.time() - float(latest)) > binding.lookback_sec:
                continue
        except ValueError:
            pass
        replies = slack.replies(channel, parent_ts, limit=30)
        for rm in replies[1:]:  # skip parent
            _maybe_handle(
                cfg,
                binding,
                slack,
                seen,
                rm,
                default_thread_ts=parent_ts,
            )


def _seed_seen(cfg: GatewayConfig) -> None:
    if not cfg.slack_bot_token:
        return
    slack = SlackClient(cfg.slack_bot_token)
    for binding in cfg.poll_bindings():
        ch = binding.slack_channel_id
        if not ch:
            continue
        seen = _seen.setdefault(ch, set())
        hist = slack.history(ch, limit=20)
        for m in hist:
            if m.get("ts"):
                seen.add(m["ts"])
            # Seed existing thread replies so we don't replay old follow-ups
            if int(m.get("reply_count") or 0) > 0 and m.get("ts"):
                for rm in slack.replies(ch, m["ts"], limit=50):
                    if rm.get("ts"):
                        seen.add(rm["ts"])
        log.info("[%s] seeded %d messages for %s", binding.name, len(seen), ch)


def _loop() -> None:
    log.info("Poller thread started")
    while not _stop.is_set():
        try:
            cfg = load_config()
            bindings = cfg.poll_bindings()
            if not bindings:
                _stop.wait(5)
                continue
            sleep_for = min(b.poll_sec for b in bindings) or 4.0
            for binding in bindings:
                _poll_binding(cfg, binding)
            _stop.wait(sleep_for)
        except Exception:
            log.exception("Poller loop error")
            _stop.wait(5)
    log.info("Poller thread stopped")


def start_poller() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    cfg = load_config()
    try:
        _seed_seen(cfg)
    except Exception:
        log.exception("Seed seen failed")
    _thread = threading.Thread(target=_loop, name="slack-mcp-poller", daemon=True)
    _thread.start()


def stop_poller() -> None:
    _stop.set()


def run_poll_once(channel_id: Optional[str] = None) -> list[str]:
    """One-shot poll for MCP tool / scheduler."""
    cfg = load_config()
    if channel_id:
        b = cfg.binding_for_channel(channel_id)
        if not b:
            return []
        _poll_binding(cfg, b)
        return [b.name]
    names = []
    for b in cfg.poll_bindings():
        _poll_binding(cfg, b)
        names.append(b.name)
    return names
