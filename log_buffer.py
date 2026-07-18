# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# ---
"""In-memory ring buffer for gateway logs (admin UI + MCP)."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Optional


class LogBuffer(logging.Handler):
    def __init__(self, capacity: int = 2000):
        super().__init__()
        self.capacity = capacity
        self._lock = threading.Lock()
        self._entries: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._seq = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        with self._lock:
            self._seq += 1
            self._entries.append(
                {
                    "id": self._seq,
                    "ts": record.created if getattr(record, "created", None) else time.time(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": msg,
                }
            )

    def snapshot(
        self,
        *,
        limit: int = 200,
        since_id: int = 0,
        level: Optional[str] = None,
        q: Optional[str] = None,
    ) -> dict[str, Any]:
        level_u = (level or "").upper().strip()
        query = (q or "").lower().strip()
        with self._lock:
            items = list(self._entries)
            latest_id = self._seq
        if since_id > 0:
            items = [e for e in items if e["id"] > since_id]
        if level_u and level_u != "ALL":
            rank = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
            min_rank = rank.get(level_u, 0)
            items = [e for e in items if rank.get(e["level"], 0) >= min_rank]
        if query:
            items = [
                e
                for e in items
                if query in e["message"].lower() or query in e["logger"].lower()
            ]
        items = items[-max(1, min(limit, self.capacity)) :]
        return {
            "latest_id": latest_id,
            "count": len(items),
            "entries": items,
        }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


LOG_BUFFER = LogBuffer(capacity=2500)


def attach_log_buffer(level: int = logging.INFO) -> LogBuffer:
    """Attach ring buffer to the root logger (idempotent, no duplicates)."""
    handler = LOG_BUFFER
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    if handler not in root.handlers:
        root.addHandler(handler)
    return handler
