"""
TRAPWIRE — Hardware Alert Triggering Verification Suite
======================================================
Verifies that:
  1. Attacker login / session / non-attack events produce ZERO hardware frames
     (buzzer stays off, LED stays armed/idle, OLED stays idle), even if marked
     warning or critical.
  2. Real allowlisted attacks fire hardware frames with full attacker telemetry
     (type, IP, ISP, location, incident ID) and update the virtual OLED mirror.
  3. Silence, mute, and physical BOOT-button acknowledgement still work.
  4. End-to-end HTTP checks (when the server on 127.0.0.1:8080 is running)
     confirm the live FastAPI + hardware pipeline behaves identically.
"""

import queue
import sys
import time
import requests

from app import hardware, state


def _drain_tx() -> list[str]:
    lines = []
    while True:
        try:
            _, line = hardware._tx.get_nowait()
            lines.append(line)
        except queue.Empty:
            break
    return lines


def _alert_frames(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.startswith("ALERT|")]


def run_unit_tests():
    print("=== 1. Unit Tests: Attacker Login & Non-Attack Events ===")
    state.reset_all()
    hardware.reset()
    _drain_tx()

    non_attack_cases = [
        ("terminal_login_attempt", "warning", "⚠️ ATTACKER LOGIN ATTEMPT: attempting authentication on Kali", {"type": "terminal_login_attempt", "ip": "198.51.100.45"}),
        ("login_attempt", "warning", "Attacker login attempt from 198.51.100.45", {"type": "login_attempt", "ip": "198.51.100.45"}),
        ("terminal_login_success", "critical", "🚨 HACKER WORKSTATION ACTIVE: Attacker 'root' successfully logged in to OffSec Pentest Console", {"type": "terminal_login_success", "ip": "198.51.100.45"}),
        ("terminal_login", "critical", "Attacker terminal login", {"type": "terminal_login", "ip": "198.51.100.45"}),
        ("session_start", "warning", "Console session started", {"type": "session_start", "ip": "198.51.100.45"}),
        ("portal_open", "warning", "Portal opened", {"type": "portal_open", "ip": "198.51.100.45"}),
        ("attacker_online_msg", "critical", "Attacker online on Kali workstation", {}),
        ("attacker_logged_in_msg", "critical", "Attacker logged in from 198.51.100.45", {}),
        ("unknown_non_attack_critical", "critical", "Routine telemetry heartbeat anomaly", {"type": "telemetry_ping"}),
        ("normal_admin_login", "info", "Admin 'admin' logged in normally from 127.0.0.1.", {"suppress_sms": True}),
    ]

    for name, level, msg, meta in non_attack_cases:
        res = hardware.process_alert({
            "id": f"t-{name}",
            "message": msg,
            "level": level,
            "timestamp": time.time(),
            "meta": meta,
        })
        assert res is None, f"Expected None for non-attack '{name}', got {res!r}"

    frames = _alert_frames(_drain_tx())
    assert len(frames) == 0, f"Expected ZERO hardware frames for login/non-attack events, got: {frames}"
    st = hardware.status()
    assert st["attack_count"] == 0, f"Expected attack_count=0, got {st['attack_count']}"
    assert st["alarm_active"] is False, "Expected alarm_active=False after login events"
    assert st["mirror"]["frame"] is None, f"Expected idle OLED mirror, got {st['mirror']['frame']}"
    print("PASS: All 10 attacker-login / session / non-attack events produced ZERO hardware frames.")

    print("=== 2. Unit Test: Real Attack Fires Exactly One Hardware Frame ===")
    attack_res = hardware.process_alert({
        "id": "t-sqli-1",
        "message": "💉 SQL INJECTION EXPLOIT DETECTED",
        "level": "critical",
        "timestamp": time.time(),
        "meta": {
            "type": "sqli_attack",
            "ip": "198.51.100.45",
            "isp": "TEST-NET-2 Simulated ISP",
            "city": "Lab City",
            "country": "TestLand",
            "incident_id": "INC-TEST0001",
            "payload": "' UNION SELECT 1,2,3--",
            "target": "/lab/shop/product",
        },
    })
    assert attack_res is not None and attack_res.startswith("ALERT|C|SQL INJECTION|"), f"Unexpected frame: {attack_res!r}"
    attack_frames = _alert_frames(_drain_tx())
    assert len(attack_frames) == 1, f"Expected EXACTLY ONE hardware frame, got {len(attack_frames)}: {attack_frames}"
    assert "198.51.100.45" in attack_frames[0]
    assert "TEST-NET-2 Simulated ISP" in attack_frames[0]
    assert "Lab City, TestLand" in attack_frames[0]
    assert "INC-TEST0001" in attack_frames[0]

    st = hardware.status()
    assert st["attack_count"] == 1
    assert st["alarm_active"] is True
    assert st["mirror"]["led"] == "blink"
    assert st["mirror"]["buzzer"] is True
    assert st["mirror"]["frame"]["type"] == "SQL INJECTION"
    print("PASS: Real SQLi attack fired exactly 1 hardware frame and activated virtual OLED/LED/buzzer.")

    print("=== 3. Unit Tests: Allowlisted Attack Coverage & Silence/Mute/BOOT Ack ===")
    allowlist_samples = [
        ("bruteforce_start", "critical", {"type": "bruteforce_start", "ip": "1.1.1.1"}, "BRUTE FORCE"),
        ("xss", "critical", {"attack_type": "xss", "confirmed": True, "ip": "1.1.1.2"}, "XSS ATTACK"),
        ("path_traversal", "critical", {"attack_type": "path_traversal", "confirmed": True, "ip": "1.1.1.3"}, "PATH TRAVERSAL"),
        ("idor", "critical", {"attack_type": "idor", "confirmed": True, "ip": "1.1.1.4"}, "IDOR / BOLA"),
        ("ssrf", "critical", {"attack_type": "ssrf", "confirmed": True, "ip": "1.1.1.5"}, "SSRF"),
        ("honeytoken", "critical", {"attack_type": "honeytoken", "confirmed": True, "ip": "1.1.1.6"}, "HONEYTOKEN USE"),
        ("data_exfiltration", "critical", {"type": "data_exfiltration", "ip": "1.1.1.7"}, "DATA EXFIL"),
        ("canary_token", "critical", {"token": "abc-123", "ip": "1.1.1.8"}, "CANARY HIT"),
        ("fingerprint", "critical", {"token": "abc-123", "screen": "1920x1080", "platform": "Linux", "ip": "1.1.1.9"}, "FINGERPRINTED"),
        ("malware_exec", "warning", {"type": "malware_exec", "ip": "1.1.1.10"}, "EXPLOIT EXEC"),
    ]
    for label, lvl, meta, expected_type in allowlist_samples:
        hardware.reset()
        _drain_tx()
        line = hardware.process_alert({
            "id": f"t-{label}",
            "message": f"Attack simulation: {label}",
            "level": lvl,
            "timestamp": time.time(),
            "meta": meta,
        })
        assert line is not None and f"|{expected_type}|" in line, f"Expected {expected_type} frame for {label}, got {line!r}"
        assert len(_alert_frames(_drain_tx())) == 1
    print(f"PASS: All {len(allowlist_samples)} allowlisted attack vectors triggered hardware frames.")

    # Mute, silence, and physical button ack checks
    hardware.set_mute(True)
    assert hardware.status()["muted"] is True
    assert "MUTE|1" in _drain_tx()
    hardware.set_mute(False)
    assert hardware.status()["muted"] is False
    assert "MUTE|0" in _drain_tx()

    hardware.silence(by="dashboard")
    assert hardware.status()["alarm_active"] is False
    assert "CLEAR" in _drain_tx()

    # Physical BOOT button acknowledgement must clear alarm and NOT re-trigger hardware
    hardware.process_alert({
        "id": "t-rearm",
        "message": "SQL injection",
        "level": "critical",
        "timestamp": time.time(),
        "meta": {"type": "sqli_attack", "ip": "9.9.9.9"},
    })
    _drain_tx()
    assert hardware.status()["alarm_active"] is True
    hardware._on_button_ack()
    assert hardware.status()["alarm_active"] is False
    assert hardware.status()["last_ack_by"] == "physical button"
    assert len(_alert_frames(_drain_tx())) == 0
    print("PASS: Mute, dashboard silence, and physical BOOT-button ack work properly.")


def run_live_http_tests(base_url: str = "http://127.0.0.1:8080"):
    print("=== 4. Live HTTP Integration Test (Attacker Login vs Real Attack) ===")
    try:
        r = requests.get(f"{base_url}/api/hardware/status", timeout=2)
        if r.status_code != 200:
            print(f"SKIP: Server at {base_url} returned {r.status_code}")
            return
    except Exception as exc:
        print(f"SKIP: Server at {base_url} not reachable ({exc})")
        return

    requests.get(f"{base_url}/api/reset-demo", timeout=5)
    requests.post(f"{base_url}/lab/reset", timeout=5)
    time.sleep(0.2)

    # 1) Simulate attacker login attempt & login success -> ZERO hardware triggers
    requests.post(f"{base_url}/api/attacker-session-event", json={
        "event": "terminal_login_attempt",
        "user": "root",
        "password_attempt": "wrong",
    }, timeout=5)
    requests.post(f"{base_url}/api/attacker-session-event", json={
        "event": "terminal_login_success",
        "user": "root",
        "password_attempt": "toor",
    }, timeout=5)
    time.sleep(0.3)

    hw_after_login = requests.get(f"{base_url}/api/hardware/status", timeout=5).json()
    assert hw_after_login["active_alarm"] is False, f"Alarm fired on login! {hw_after_login}"
    assert hw_after_login["hardware"]["attack_count"] == 0, f"attack_count incremented on login! {hw_after_login}"
    assert hw_after_login["hardware"]["mirror"]["frame"] is None, f"OLED frame shown on login! {hw_after_login}"
    print("PASS: Live HTTP attacker login left ESP32 hardware completely silent (attack_count=0, mirror=None).")

    # 2) Simulate an actual attack (SQLi against lab endpoint) -> hardware fires
    r_atk = requests.get(
        f"{base_url}/lab/shop/product",
        params={"id": "-1 UNION SELECT id, username, password, role FROM lab_users-- "},
        timeout=5,
    )
    assert r_atk.status_code == 200
    time.sleep(0.4)

    hw_after_attack = requests.get(f"{base_url}/api/hardware/status", timeout=5).json()
    assert hw_after_attack["active_alarm"] is True, f"Alarm did not fire on attack! {hw_after_attack}"
    assert hw_after_attack["hardware"]["attack_count"] >= 1, f"attack_count not incremented on attack! {hw_after_attack}"
    frame = hw_after_attack["hardware"]["mirror"]["frame"]
    assert frame is not None and frame["type"] == "SQL INJECTION", f"Unexpected OLED frame: {frame}"
    print("PASS: Live HTTP SQLi attack triggered hardware alarm and OLED display:", frame["type"])

    # Clean up demo state after test
    requests.get(f"{base_url}/api/reset-demo", timeout=5)
    requests.post(f"{base_url}/lab/reset", timeout=5)


if __name__ == "__main__":
    run_unit_tests()
    run_live_http_tests()
    print("\nALL HARDWARE TRIGGERING TESTS PASSED.")

