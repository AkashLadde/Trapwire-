"""
TRAPWIRE — Physical Alert Node Bridge (app/hardware.py)
=======================================================

Turns every TRAPWIRE attack alert into a PHYSICAL alarm on an ESP32:

    * RED LED       -> fast-blinks during an attack, then stays latched ON
                       until someone acknowledges it
    * BUZZER        -> siren pattern for critical attacks, short beeps for
                       warnings / reports
    * 0.96" OLED    -> shows the attacker's details: attack type, IP, ISP,
                       location, incident ID, time, attack counter

HOW IT HOOKS IN
---------------
app/main.py calls ``hardware.notify(alert)`` from ``broadcast_alert()``.
Every alert in TRAPWIRE (brute force, SQLi, exfiltration, canary hit, the
Phase-2 lab's server-side detections ...) already flows through that one
function, so the hardware sees exactly what the SOC dashboard sees.

``notify()`` never blocks the web server: it drops the alert on a queue.
A dispatcher thread enriches it (ISP / location lookup if missing), and a
transport thread writes it to the ESP32 over USB serial or Wi-Fi. If no
ESP32 is plugged in, nothing breaks — the dashboard's "virtual OLED"
mirror still shows what the hardware would display.

TRANSPORTS (choose with environment variables)
----------------------------------------------
    USB serial (default)   auto-detects CP210x / CH340 / FTDI / ESP32-S3 boards
        TRAPWIRE_HW_PORT=COM5            force a port (Windows)
        TRAPWIRE_HW_PORT=/dev/ttyUSB0    force a port (Linux)
    Wi-Fi                  ESP32 runs a tiny web server on your LAN
        TRAPWIRE_HW_URL=http://192.168.1.60
    Disable completely
        TRAPWIRE_HW=off

WIRE PROTOCOL (one ASCII line per message, '\n' terminated)
-----------------------------------------------------------
Server -> ESP32
    ALERT|sev|type|ip|isp|location|incident|time|count|ack|detail
          sev: C = critical attack, W = warning/probe, R = report filed, T = test
    CLEAR            silence buzzer, turn LED off, back to idle screen
    MUTE|1 / MUTE|0  mute / unmute buzzer (LED + OLED keep working)
    PING             heartbeat
ESP32 -> Server
    READY|TRAPWIRE-ESP32|<fw>
    PONG|TRAPWIRE-ESP32|<fw>|<ack_count>|<muted>
    ACK|BUTTON|<ack_count>      physical silence button pressed

Manual hardware check without the web server:
    python -m app.hardware --list
    python -m app.hardware --test            (auto-detect port)
    python -m app.hardware --test COM5
"""

from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from datetime import datetime
from typing import Callable, Optional

import requests

try:  # pyserial is optional: without it we run in "mirror only" mode
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover
    serial = None
    list_ports = None

from app import state

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
HW_ENABLED = os.getenv("TRAPWIRE_HW", "auto").lower() not in ("0", "off", "false", "no")
HW_URL = os.getenv("TRAPWIRE_HW_URL", "").strip().rstrip("/")
HW_PORT = os.getenv("TRAPWIRE_HW_PORT", "").strip()
HW_BAUD = int(os.getenv("TRAPWIRE_HW_BAUD", "115200"))
TRANSPORT = "wifi" if HW_URL else "serial"

# USB-UART bridges commonly found on ESP32 dev boards
KNOWN_USB_VIDS = {
    0x10C4: "Silicon Labs CP210x",
    0x1A86: "WCH CH340/CH9102",
    0x0403: "FTDI",
    0x303A: "Espressif native USB",
}

SIREN_SECONDS = 15        # must match SIREN_MS in the ESP32 sketch
DEDUPE_SECONDS = 1.0      # same attack type + IP inside this window -> one frame
PING_EVERY = 5.0
STALE_FRAME_SECONDS = 30  # on (re)connect, replay the last frame if newer than this

# Non-attack authentication/session events: NEVER trigger the physical alarm,
# even if logged as warning/critical on the SOC feed.
NON_TRIGGERING_EVENT_TYPES = frozenset({
    "terminal_login_attempt",
    "login_attempt",
    "terminal_login_success",
    "terminal_login",
    "session_start",
    "portal_open",
    "attacker_online",
    "attacker_login",
    "hardware_ack",
    "normal_login",
    "info",
})

NON_TRIGGERING_PHRASES = (
    "attacker online",
    "attacker logged in",
    "attacker login attempt",
    "hacker workstation active",
    "successfully logged in to offsec",
    "attempting authentication on kali",
    "logged in normally",
    "session_start",
    "portal_open",
    "alarm silenced",
    "physical alarm acknowledged",
)

# Explicit allowlist of real attack / detection types allowed to drive the
# ESP32 hardware (mapping normalized event/attack_type -> (OLED label, default sev)).
ALLOWED_ATTACK_TYPES = {
    # Brute-force & suspicious company auth intrusion
    "failed_login": ("BRUTE FORCE", None),
    "bruteforce_start": ("BRUTE FORCE", "C"),
    "brute_force": ("BRUTE FORCE", "C"),
    "bruteforce": ("BRUTE FORCE", "C"),
    "suspicious_login": ("INTRUSION", "C"),
    # SQL Injection
    "sqli_attack": ("SQL INJECTION", "C"),
    "sql_injection": ("SQL INJECTION", None),
    "sqli": ("SQL INJECTION", None),
    # Data exfiltration / export
    "data_exfiltration": ("DATA EXFIL", "C"),
    "export": ("DATA EXFIL", "C"),
    # Canary & device-fingerprint attribution
    "canary_hit": ("CANARY HIT", "C"),
    "canary": ("CANARY HIT", "C"),
    "forensic_attribution": ("FINGERPRINTED", "C"),
    # Cross-Site Scripting (XSS)
    "xss_attack": ("XSS ATTACK", None),
    "xss_exploit": ("XSS ATTACK", None),
    "xss": ("XSS ATTACK", None),
    # Path Traversal / LFI
    "traversal_attack": ("PATH TRAVERSAL", None),
    "path_traversal": ("PATH TRAVERSAL", None),
    "lfi": ("PATH TRAVERSAL", None),
    # Phase-2 lab server-side detections (app/lab.py)
    "idor": ("IDOR / BOLA", None),
    "ssrf": ("SSRF", None),
    "honeytoken": ("HONEYTOKEN USE", "C"),
    "honeytoken_use": ("HONEYTOKEN USE", "C"),
    # Malware / exploit execution & active target recon scan
    "malware_exec": ("EXPLOIT EXEC", None),
    "exploit_runner": ("EXPLOIT EXEC", None),
    "port_scan": ("PORT SCAN", "W"),
    "recon": ("PORT SCAN", "W"),
}

TYPE_LABELS = {k: label for k, (label, _) in ALLOWED_ATTACK_TYPES.items()}

# --------------------------------------------------------------------------
# Shared state (read by the dashboard through status())
# --------------------------------------------------------------------------
_lock = threading.Lock()
_STATUS: dict = {
    "enabled": HW_ENABLED,
    "transport": TRANSPORT,
    "port": HW_PORT or None,
    "url": HW_URL or None,
    "connected": False,        # port open / ESP32 reachable
    "firmware": None,          # set when READY / PONG received
    "last_seen": None,         # last time the ESP32 talked to us
    "last_error": None,
    "frames_sent": 0,
    "attack_count": 0,
    "alarm_active": False,     # LED latched on, waiting for acknowledgement
    "muted": False,
    "last_ack_at": None,
    "last_ack_by": None,
}
# what the OLED is showing right now (mirrored on the dashboard)
_MIRROR: dict = {"frame": None, "since": None, "crit": None, "crit_since": None}
DISPLAY_HOLD = 10         # seconds a W/R/T screen stays before the OLED goes back

_events: "queue.Queue[dict]" = queue.Queue()   # raw alerts -> dispatcher
_tx: "queue.Queue[tuple]" = queue.Queue()       # (created_at, line) -> transport
_last_frame_line: Optional[tuple] = None        # (created_at, line)
_dedupe: dict = {}
_ack_counter: Optional[int] = None

_LOOP: Optional[asyncio.AbstractEventLoop] = None
_ALERT_SINK: Optional[Callable] = None
_GEO_RESOLVER: Optional[Callable[[str], dict]] = None
_started = False


def _set(**kw):
    with _lock:
        _STATUS.update(kw)


# --------------------------------------------------------------------------
# Public API (called from app/main.py)
# --------------------------------------------------------------------------
def start(loop: asyncio.AbstractEventLoop,
          alert_sink: Optional[Callable] = None,
          geo_resolver: Optional[Callable[[str], dict]] = None):
    """Start the dispatcher + transport threads (idempotent)."""
    global _LOOP, _ALERT_SINK, _GEO_RESOLVER, _started
    _LOOP, _ALERT_SINK, _GEO_RESOLVER = loop, alert_sink, geo_resolver
    if _started or not HW_ENABLED:
        return
    _started = True
    threading.Thread(target=_dispatcher, name="trapwire-hw-dispatch", daemon=True).start()
    target = _wifi_transport if TRANSPORT == "wifi" else _serial_transport
    threading.Thread(target=target, name="trapwire-hw-transport", daemon=True).start()
    if TRANSPORT == "serial" and serial is None:
        _set(last_error="pyserial not installed (pip install pyserial) — mirror-only mode")
    print(f"[HARDWARE] Alert node bridge started (transport={TRANSPORT})")


def notify(alert: dict):
    """Hand an alert to the hardware. Never raises, never blocks."""
    if not HW_ENABLED:
        return
    try:
        meta = alert.get("meta") or {}
        if meta.get("source") == "hardware":
            return  # our own "alarm acknowledged" messages
        _events.put_nowait(dict(alert))
    except Exception as e:  # pragma: no cover
        print(f"[HARDWARE] notify error: {e}")


def silence(by: str = "dashboard"):
    """Stop buzzer + LED and return the OLED to the idle screen."""
    _tx.put((time.time(), "CLEAR"))
    with _lock:
        _STATUS.update(alarm_active=False, last_ack_at=time.time(), last_ack_by=by)
        _MIRROR.update(frame=None, since=time.time(), crit=None, crit_since=None)


def set_mute(muted: bool):
    _set(muted=bool(muted))
    _tx.put((time.time(), f"MUTE|{1 if muted else 0}"))


def reset():
    """Called by /api/reset-demo."""
    global _last_frame_line
    while True:
        try:
            _events.get_nowait()
        except queue.Empty:
            break
    silence(by="reset")
    _last_frame_line = None
    _dedupe.clear()
    _set(attack_count=0, frames_sent=0)


def status() -> dict:
    now = time.time()
    with _lock:
        s = dict(_STATUS)
        frame = dict(_MIRROR["frame"]) if _MIRROR["frame"] else None
        since = _MIRROR["since"]
        # a warning/report screen times out -> latched attack screen or idle
        if frame and frame["sev"] != "C" and now - (since or now) > DISPLAY_HOLD:
            if s["alarm_active"] and _MIRROR["crit"]:
                frame, since = dict(_MIRROR["crit"]), _MIRROR["crit_since"]
            else:
                frame, since = None, None
    s["firmware_ok"] = bool(s["last_seen"] and now - s["last_seen"] < 3 * PING_EVERY + 2)
    s["pyserial"] = serial is not None
    # what the LED/buzzer are doing right now, for the virtual panel
    led, buzzer = "off", False
    if frame:
        age = now - (since or now)
        if frame["sev"] == "C":
            led = "blink" if age < SIREN_SECONDS else "solid"
            buzzer = age < SIREN_SECONDS and not s["muted"]
        elif frame["sev"] == "W":
            led = "blink" if age < 3 else ("solid" if s["alarm_active"] else "off")
            buzzer = age < 1.2 and not s["muted"]
        else:
            led = "solid" if s["alarm_active"] else "off"
            buzzer = age < 0.5 and not s["muted"]
    elif s["alarm_active"]:
        led = "solid"
    s["mirror"] = {"frame": frame, "since": since, "led": led, "buzzer": buzzer}
    return s


# --------------------------------------------------------------------------
# Alert -> frame
# --------------------------------------------------------------------------
def _clean(value, limit: int) -> str:
    """ASCII-only, no separators/newlines, trimmed (the OLED font is ASCII)."""
    text = str(value or "").replace("|", "/").replace("\r", " ").replace("\n", " ")
    text = text.encode("ascii", "ignore").decode("ascii").strip()
    return " ".join(text.split())[:limit]


def _classify(alert: dict) -> Optional[dict]:
    level = str(alert.get("level") or "").strip().lower()
    msg = alert.get("message", "") or ""
    msg_lower = msg.lower()
    meta = alert.get("meta") or {}

    if meta.get("source") == "hardware":
        return None

    raw_key = meta.get("type") or meta.get("attack_type") or meta.get("event") or ""
    key = str(raw_key).strip().lower().replace("-", "_").replace(" ", "_")

    # Reject attacker-login / session / non-attack messages regardless of severity
    if key in NON_TRIGGERING_EVENT_TYPES:
        return None
    if any(phrase in msg_lower for phrase in NON_TRIGGERING_PHRASES):
        return None

    # Treat explicit info-level events as non-triggering unless marked confirmed
    if level == "info" and not meta.get("confirmed"):
        return None

    # Drive hardware from an explicit allowlist rather than severity alone
    if "HARDWARE INTEGRATION TEST" in msg or key == "hardware_test":
        sev, typ = "T", "SELF TEST"
    elif meta.get("filename") and meta.get("ack_number"):
        sev = "R"
        typ = "FINAL REPORT" if meta.get("stage") == "final" else "PRELIM REPORT"
    elif key in ALLOWED_ATTACK_TYPES:
        typ, default_sev = ALLOWED_ATTACK_TYPES[key]
        if meta.get("confirmed") or level == "critical":
            sev = "C"
        elif level == "warning":
            sev = "W"
        else:
            sev = default_sev or "W"
    elif (meta.get("screen") or meta.get("platform")) and (
        meta.get("token") or "forensic attribution" in msg_lower
    ):
        sev, typ = "C", "FINGERPRINTED"
    elif meta.get("token"):
        sev, typ = "C", "CANARY HIT"
    else:
        return None

    ip = meta.get("ip") or meta.get("attacker_ip") or state.BREACH.get("attacker_ip") or ""
    isp = meta.get("isp") or meta.get("attacker_isp") or ""
    city, country = meta.get("city") or "", meta.get("country") or ""
    if not isp and ip and ip == state.BREACH.get("attacker_ip"):
        isp = state.BREACH.get("attacker_isp", "")
    loc = ", ".join(x for x in (city, country) if x) or state.BREACH.get("attacker_location", "")

    detail = meta.get("endpoint") or meta.get("target") or meta.get("payload") or ""
    if meta.get("attempt"):
        detail = f"attempt #{meta['attempt']}"

    return {
        "sev": sev,
        "type": typ,
        "ip": ip,
        "isp": isp,
        "loc": loc,
        "incident": meta.get("incident_id") or state.BREACH.get("incident_id") or "",
        "time": datetime.fromtimestamp(alert.get("timestamp") or time.time()).strftime("%H:%M:%S"),
        "ack": meta.get("ack_number") or "",
        "detail": detail,
        "confirmed": bool(meta.get("confirmed")),
    }


def _encode(f: dict) -> str:
    fields = [
        "ALERT", f["sev"], _clean(f["type"], 16), _clean(f["ip"], 39), _clean(f["isp"], 42),
        _clean(f["loc"], 32), _clean(f["incident"], 14), _clean(f["time"], 8),
        str(f["count"]), _clean(f["ack"], 24), _clean(f["detail"], 32),
    ]
    return "|".join(fields)


def process_alert(alert: dict) -> Optional[str]:
    """Classify one alert, update mirror/status, and enqueue an ALERT frame if allowed.

    Returns the encoded ALERT wire line when enqueued, or None if ignored/deduped.
    """
    global _last_frame_line
    meta = alert.get("meta") or {}
    if meta.get("source") == "hardware":
        return None
    frame = _classify(alert)
    if not frame:
        return None
    # fill ISP / location when the alert only carried an IP
    if frame["ip"] and (not frame["isp"] or not frame["loc"]) and _GEO_RESOLVER:
        try:
            geo = _GEO_RESOLVER(frame["ip"].split(" ")[0]) or {}
            frame["isp"] = frame["isp"] or geo.get("isp", "")
            if not frame["loc"]:
                frame["loc"] = ", ".join(x for x in (geo.get("city"), geo.get("country")) if x)
        except Exception:
            pass

    now = time.time()
    key = (frame["sev"], frame["type"], frame["ip"])
    if now - _dedupe.get(key, 0) < DEDUPE_SECONDS:
        return None
    _dedupe[key] = now

    with _lock:
        if frame["sev"] in ("C", "W"):
            _STATUS["attack_count"] += 1
        if frame["sev"] == "C":
            _STATUS["alarm_active"] = True
        frame["count"] = _STATUS["attack_count"]

        # don't let a warning / report overwrite a live critical screen
        cur = _MIRROR["frame"]
        cur_age = now - (_MIRROR["since"] or 0)
        keep_crit = (cur and cur["sev"] == "C" and frame["sev"] in ("W", "R")
                     and cur_age < SIREN_SECONDS)
        if not keep_crit:
            _MIRROR.update(frame=frame, since=now)
        if frame["sev"] == "C":
            _MIRROR.update(crit=frame, crit_since=now)

    line = _encode(frame)
    _last_frame_line = (now, line)
    _tx.put((now, line))
    return line


def _dispatcher():
    """alerts -> enriched frames -> transport queue + dashboard mirror."""
    while True:
        alert = _events.get()
        try:
            process_alert(alert)
        except Exception as e:  # pragma: no cover
            print(f"[HARDWARE] dispatch error: {e}")


# --------------------------------------------------------------------------
# Incoming lines from the ESP32
# --------------------------------------------------------------------------
def _handle_line(line: str):
    global _ack_counter
    line = line.strip()
    if not line:
        return
    parts = line.split("|")
    head = parts[0].upper()
    if head in ("READY", "PONG"):
        _set(firmware=f"{parts[1] if len(parts) > 1 else 'ESP32'} v{parts[2] if len(parts) > 2 else '?'}",
             last_seen=time.time(), last_error=None)
        if head == "PONG" and len(parts) > 4:
            _set(muted=parts[4] == "1")
        if len(parts) > 3 and parts[3].isdigit():
            n = int(parts[3])
            if _ack_counter is not None and n > _ack_counter:
                _on_button_ack()
            _ack_counter = n
    elif head == "ACK":
        _set(last_seen=time.time())
        n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        if n is None or _ack_counter is None or n > _ack_counter:
            _on_button_ack()
        if n is not None:
            _ack_counter = n
    elif head == "LOG":
        print(f"[ESP32] {line[4:]}")


def _on_button_ack():
    with _lock:
        _STATUS.update(alarm_active=False, last_ack_at=time.time(), last_ack_by="physical button")
        _MIRROR.update(frame=None, since=time.time(), crit=None, crit_since=None)
    if _ALERT_SINK and _LOOP:
        alert = state.new_alert(
            "🔕 PHYSICAL ALARM ACKNOWLEDGED: Security staff pressed the silence button on the "
            "ESP32 alert node. Siren stopped; incident remains open on the SOC dashboard.",
            level="info",
            meta={"source": "hardware", "type": "hardware_ack", "suppress_sms": True},
        )
        try:
            asyncio.run_coroutine_threadsafe(_ALERT_SINK(alert), _LOOP)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Transports
# --------------------------------------------------------------------------
def find_serial_port() -> Optional[str]:
    if list_ports is None:
        return None
    candidates = []
    for p in list_ports.comports():
        if p.vid in KNOWN_USB_VIDS:
            candidates.append(p.device)
        elif any(k in (p.description or "").upper() for k in ("CP210", "CH340", "CH910", "USB SERIAL", "UART")):
            candidates.append(p.device)
    return candidates[0] if candidates else None


def _drain_stale():
    """Throw away frames queued while disconnected; replay only a fresh one."""
    while True:
        try:
            _tx.get_nowait()
        except queue.Empty:
            break
    if _last_frame_line and time.time() - _last_frame_line[0] < STALE_FRAME_SECONDS:
        _tx.put(_last_frame_line)


def _serial_transport():
    while True:
        if serial is None:
            time.sleep(5)
            continue
        port = HW_PORT or find_serial_port()
        if not port:
            _set(connected=False, port=None, last_error="No ESP32 USB-serial port found — plug it in")
            time.sleep(3)
            continue
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, HW_BAUD, 0
            ser.dtr = False  # avoid resetting the board where the driver allows it
            ser.rts = False
            ser.open()
        except Exception as e:
            _set(connected=False, port=port, last_error=f"Cannot open {port}: {e}")
            time.sleep(3)
            continue

        print(f"[HARDWARE] ESP32 connected on {port} @ {HW_BAUD}")
        _set(connected=True, port=port, last_error=None)
        time.sleep(2.0)  # many boards still reboot on open; give it time
        _drain_stale()
        _tx.put((time.time(), f"MUTE|{1 if _STATUS['muted'] else 0}"))
        buf, last_ping = b"", 0.0
        try:
            while True:
                try:
                    _, line = _tx.get(timeout=0.05)
                    ser.write((line + "\n").encode("ascii", "ignore"))
                    if line.startswith("ALERT"):
                        with _lock:
                            _STATUS["frames_sent"] += 1
                except queue.Empty:
                    pass
                waiting = ser.in_waiting
                if waiting:
                    buf += ser.read(waiting)
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        _handle_line(raw.decode("ascii", "ignore"))
                    buf = buf[-512:]
                if time.time() - last_ping > PING_EVERY:
                    ser.write(b"PING\n")
                    last_ping = time.time()
        except Exception as e:
            print(f"[HARDWARE] ESP32 on {port} disconnected: {e}")
            _set(connected=False, last_error=f"Disconnected: {e}")
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(2)


def _wifi_transport():
    session = requests.Session()
    last_ping, was_connected = 0.0, False
    while True:
        try:
            _, line = _tx.get(timeout=0.5)
            try:
                r = session.post(f"{HW_URL}/cmd", data=line.encode("ascii", "ignore"),
                                 headers={"Content-Type": "text/plain"}, timeout=2.5)
                if r.ok and line.startswith("ALERT"):
                    with _lock:
                        _STATUS["frames_sent"] += 1
            except Exception as e:
                _set(connected=False, last_error=f"ESP32 at {HW_URL} unreachable: {e}")
        except queue.Empty:
            pass
        if time.time() - last_ping > PING_EVERY:
            last_ping = time.time()
            try:
                r = session.get(f"{HW_URL}/ping", timeout=2.0)
                if r.ok:
                    if not was_connected:
                        _set(connected=True, last_error=None)
                        _drain_stale()
                    was_connected = True
                    _handle_line(r.text)
                else:
                    raise RuntimeError(f"HTTP {r.status_code}")
            except Exception as e:
                was_connected = False
                _set(connected=False, last_error=f"ESP32 at {HW_URL} unreachable: {e}")


# --------------------------------------------------------------------------
# CLI: quick bench test of the wiring without running the web server
# --------------------------------------------------------------------------
def _cli():  # pragma: no cover
    import sys
    args = sys.argv[1:]
    if serial is None:
        print("pyserial missing:  pip install pyserial")
        return
    if not args or args[0] == "--list":
        for p in list_ports.comports():
            vid = f"{p.vid:04X}" if p.vid else "----"
            tag = KNOWN_USB_VIDS.get(p.vid, "")
            print(f"{p.device:15} VID {vid}  {p.description}  {tag}")
        print("auto-detected:", find_serial_port())
        return
    if args[0] == "--test":
        port = args[1] if len(args) > 1 else (HW_PORT or find_serial_port())
        if not port:
            print("No port found. Use: python -m app.hardware --test COM5")
            return
        ser = serial.Serial(port, HW_BAUD, timeout=0.2)
        print(f"Opened {port}; waiting for ESP32 boot ...")
        time.sleep(2.5)
        frame = {"sev": "C", "type": "SQL INJECTION", "ip": "198.51.100.45",
                 "isp": "TEST-NET-2 (Bench Self-Test)", "loc": "Lab Bench, Local",
                 "incident": "INC-TEST1234", "time": datetime.now().strftime("%H:%M:%S"),
                 "count": 1, "ack": "", "detail": "/lab/shop/product?id=1"}
        line = _encode(frame)
        ser.write((line + "\n").encode())
        print("sent:", line)
        end = time.time() + 6
        while time.time() < end:
            got = ser.readline().decode("ascii", "ignore").strip()
            if got:
                print("esp32:", got)
        print("Siren should be sounding. Sending CLEAR in 10 s (or press BOOT button) ...")
        time.sleep(10)
        ser.write(b"CLEAR\n")
        ser.close()
        print("done.")


if __name__ == "__main__":  # pragma: no cover
    _cli()
