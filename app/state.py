"""
Central runtime state for the TRAPWIRE server, backed by MySQL/SQLite persistence
(`app/database.py`). No fake breach defaults or dummy records are seeded here.
"""

import os
import time
import uuid
from typing import Optional

# Admin credentials (configurable via environment variables / .env)
ADMIN_USERNAME = os.getenv("TRAPWIRE_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("TRAPWIRE_ADMIN_PASS", "Admin@2026!")

# Failed login attempts, keyed by client IP
LOGIN_ATTEMPTS: dict[str, int] = {}

# Alerts mirrored from DB and streamed over WebSockets
ALERTS: list[dict] = []

# Canary-token phone-home triggers
CANARY_HITS: list[dict] = []

# Active / most-recent incident metadata (empty until a real incident occurs)
BREACH: dict = {}

# WebSocket connections belonging to authenticated non-suspicious admin sessions
ADMIN_SOCKETS: list = []

# Submitted DPB breach notifications
SUBMITTED_REPORTS: list[dict] = []


def new_alert(message: str, level: str = "warning", meta: Optional[dict] = None) -> dict:
    alert = {
        "id": str(uuid.uuid4())[:8],
        "message": message,
        "level": level,  # "info" | "warning" | "critical"
        "timestamp": time.time(),
        "meta": meta or {},
    }
    ALERTS.append(alert)
    return alert


def reset_all() -> None:
    LOGIN_ATTEMPTS.clear()
    ALERTS.clear()
    CANARY_HITS.clear()
    BREACH.clear()
    SUBMITTED_REPORTS.clear()
