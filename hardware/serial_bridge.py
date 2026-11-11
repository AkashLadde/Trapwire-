"""
=====================================================================================
TRAPWIRE — OPTIONAL Standalone Hardware Serial Bridge
=====================================================================================
You usually DON'T need this file. Since firmware v1.0 the ESP32 bridge is built
straight into the server (app/hardware.py): plug the board in by USB, start
TRAPWIRE, done. The red LED, buzzer and OLED fire automatically and the SOC
dashboard shows a live "virtual OLED" mirror.

Use THIS standalone relay only when the ESP32 is attached to a DIFFERENT machine
than the one running the server (e.g. the server is on a Raspberry Pi in a rack
and the alert node sits on your desk). It subscribes to the server's live alert
WebSocket and forwards each alert to the ESP32 over USB serial, using the EXACT
SAME wire protocol as the built-in bridge — so the same flashed sketch
(hardware/esp32_threat_siren/) works either way.

    IMPORTANT: run EITHER the built-in bridge OR this relay, never both on the
    same board — they would fight over the serial port. On the SERVER, disable
    the built-in bridge first:
            export TRAPWIRE_HW=off        (Windows: set TRAPWIRE_HW=off)
    then run this relay on the machine the board is plugged into.

Usage:
    pip install pyserial websockets requests
    python hardware/serial_bridge.py                         # auto-detect port + localhost
    python hardware/serial_bridge.py --port COM7 --server http://192.168.1.10:8080
    python hardware/serial_bridge.py --test                  # fire one test frame
    python hardware/serial_bridge.py --list                  # list serial ports
=====================================================================================
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests

# One source of truth: reuse the built-in bridge's alert->frame logic so this
# relay and app/hardware.py always speak an identical protocol to the firmware.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import hardware  # noqa: E402

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

try:
    import websockets  # optional; we fall back to HTTP polling without it
    import asyncio
    HAS_WS = True
except ImportError:
    HAS_WS = False

DEFAULT_HTTP = os.getenv("SERVER_HTTP_URL", "http://127.0.0.1:8080")


def open_serial(port, baud):
    if serial is None:
        print("pyserial missing:  pip install pyserial")
        return None
    port = port or hardware.find_serial_port()
    if not port:
        print("No ESP32 USB-serial port found. Specify one with --port COM7 or --list.")
        return None
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = port, baud, 0.1
    ser.dtr = False
    ser.rts = False
    ser.open()
    time.sleep(2.0)  # let the board finish booting
    print(f"[+] ESP32 connected on {port} @ {baud}")
    return ser


_count = {"n": 0}


def alert_to_line(alert):
    """Turn a server alert dict into an ALERT|... line, or None to skip."""
    frame = hardware._classify(alert)
    if not frame:
        return None
    _count["n"] += 1
    frame["count"] = _count["n"]
    return hardware._encode(frame)


def ws_url_from_http(http_url):
    return http_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + "/ws/alerts"


def run_ws(ser, http_url):
    async def _main():
        url = ws_url_from_http(http_url)
        print(f"[*] Subscribing to live alert stream {url}")
        while True:
            try:
                async with websockets.connect(url) as ws:
                    print("[+] Alert stream connected. Waiting for threats...")
                    while True:
                        raw = await ws.recv()
                        try:
                            alert = json.loads(raw)
                        except Exception:
                            continue
                        line = alert_to_line(alert)
                        if line and ser:
                            ser.write((line + "\n").encode("ascii", "ignore"))
                            print(f"    -> {line[:80]}")
            except Exception as e:
                print(f"[!] stream dropped ({e}); retrying in 3s")
                await asyncio.sleep(3)
    asyncio.run(_main())


def run_poll(ser, http_url):
    """Fallback when the websockets lib isn't installed: poll recent alerts."""
    print("[*] websockets not installed — polling /api/alerts/recent every 1s")
    seen = set()
    sess = requests.Session()
    while True:
        try:
            data = sess.get(f"{http_url}/api/alerts/recent", timeout=3).json()
            for alert in reversed(data.get("alerts", [])):
                aid = alert.get("id")
                if aid in seen:
                    continue
                seen.add(aid)
                line = alert_to_line(alert)
                if line and ser:
                    ser.write((line + "\n").encode("ascii", "ignore"))
                    print(f"    -> {line[:80]}")
        except Exception as e:
            print(f"[!] poll error: {e}")
        time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser(description="TRAPWIRE optional standalone hardware relay")
    ap.add_argument("--port", help="serial port (COM7 / /dev/ttyUSB0); auto-detect if omitted")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--server", default=DEFAULT_HTTP, help="TRAPWIRE HTTP base URL")
    ap.add_argument("--test", action="store_true", help="send one test frame and exit")
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    args = ap.parse_args()

    if args.list:
        if list_ports is None:
            print("pyserial missing:  pip install pyserial")
            return
        for p in list_ports.comports():
            print(f"{p.device:16} {p.description}")
        print("auto-detected:", hardware.find_serial_port())
        return

    ser = open_serial(args.port, args.baud)
    if not ser:
        return

    if args.test:
        frame = {"sev": "C", "type": "SQL INJECTION", "ip": "198.51.100.45",
                 "isp": "TEST-NET-2 (Bench Self-Test)", "loc": "Lab Bench, Local",
                 "incident": "INC-TEST1234", "time": datetime.now().strftime("%H:%M:%S"),
                 "count": 1, "ack": "DPB-TEST", "detail": "/lab/shop/product?id=1"}
        line = hardware._encode(frame)
        ser.write((line + "\n").encode())
        print(f"[+] sent test frame: {line}\n    Check the red LED, buzzer and OLED.")
        time.sleep(12)
        ser.write(b"CLEAR\n")
        ser.close()
        return

    print("[i] Make sure the server was started with TRAPWIRE_HW=off so the built-in")
    print("    bridge isn't also holding this port.\n")
    try:
        if HAS_WS:
            run_ws(ser, args.server)
        else:
            run_poll(ser, args.server)
    except KeyboardInterrupt:
        print("\n[*] bridge stopped.")
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
