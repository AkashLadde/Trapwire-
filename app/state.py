"""
Central in-memory state for the TRAPWIRE demo.

NOTE: This is a local educational demo. State lives in memory only
(no database) so it resets whenever the server restarts. That's fine
for a capstone demo; your P1 "Future Scope" slide already lists real
DB integration as planned future work.
"""
import time
import uuid
from typing import Optional

# ---- Credentials (intentionally realistic-but-weak password for the demo) ----
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026!"

# The attacker UI will offer this exact wordlist. The real password is
# buried in the middle so the brute-force always fails a few times first
# -> that failure count is what flags the eventual successful login as
# "suspicious" (a simple but real intrusion-detection heuristic).
ATTACK_WORDLIST = [
    "123456",
    "password",
    "admin123",
    "admin@123",
    "Welcome@123",
    "qwerty123",
    "Admin@2026!",  # <-- correct password
    "letmein123",
]

# failed login attempts, keyed by client IP
LOGIN_ATTEMPTS: dict[str, int] = {}

# every alert shown on the company Security Center tab
ALERTS: list[dict] = []

# every canary-token trigger (i.e. every time the attacker "opened" the
# decoy file and it phoned home)
CANARY_HITS: list[dict] = []

# metadata about the current/most-recent simulated breach, used to build
# the DPDP compliance PDF report (72-hour clock, etc.)
BREACH: dict = {}

# websocket connections belonging to *trusted* admin sessions, used to
# push live alerts
ADMIN_SOCKETS: list = []

# every report that has been auto-generated and "submitted" to the
# (simulated) Data Protection Board of India
SUBMITTED_REPORTS: list[dict] = []


def new_alert(message: str, level: str = "warning", meta: Optional[dict] = None):
    alert = {
        "id": str(uuid.uuid4())[:8],
        "message": message,
        "level": level,  # "info" | "warning" | "critical"
        "timestamp": time.time(),
        "meta": meta or {},
    }
    ALERTS.append(alert)
    return alert


def reset_all():
    LOGIN_ATTEMPTS.clear()
    ALERTS.clear()
    CANARY_HITS.clear()
    BREACH.clear()
    SUBMITTED_REPORTS.clear()
