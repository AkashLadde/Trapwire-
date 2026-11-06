"""
=====================================================================================
TRAPWIRE — Physical Hardware Serial Bridge & Threat Stream Relay
=====================================================================================
Connects the TrapWire Defender Backend (FastAPI WebSocket) to physical hardware:
 1. USB Serial MCU (ESP32 DevKit V1 / NodeMCU Threat Siren, OLED, Buzzer & LEDs).
 2. Live Threat Telemetry forwarder for physical SOC alerting.

Usage:
    # Auto-detects COM port (e.g. COM7 on Windows or /dev/ttyUSB0 on Linux):
    python hardware/serial_bridge.py

    # Or specify port manually:
    python hardware/serial_bridge.py --port COM7 --baud 115200

    # Or fire an immediate physical hardware alarm test:
    python hardware/serial_bridge.py --test
=====================================================================================
"""

import os
import sys
import time
import json
import asyncio
import argparse
import requests

try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

DEFAULT_WS_URL = os.getenv("SERVER_WS_URL", "ws://127.0.0.1:8080/ws/alerts")
DEFAULT_HTTP_URL = os.getenv("SERVER_HTTP_URL", "http://127.0.0.1:8080")


def auto_detect_mcu_port():
    """Scans and automatically selects the ESP32 / USB-to-UART COM port."""
    if not HAS_SERIAL:
        return None
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    # 1. Look for known microcontroller USB-UART bridge chips
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(chip in desc or chip in hwid for chip in ["cp210", "ch340", "ch341", "ftdi", "uart", "usb serial", "esp32"]):
            return p.device
    # 2. If exactly one COM port exists, choose it
    if len(ports) == 1:
        return ports[0].device
    return None


def print_available_ports():
    if not HAS_SERIAL:
        print("[!] pyserial is not installed. Run: pip install pyserial websockets")
        return
    ports = list(serial.tools.list_ports.comports())
    print("\n--- Available USB Serial / COM Ports ---")
    if not ports:
        print("  [x] No USB Serial devices currently detected.")
    for p in ports:
        print(f"  • {p.device}: {p.description} [{p.hwid}]")
    print("----------------------------------------\n")


class HardwareBridge:
    def __init__(self, mcu_port: str = None, mcu_baud: int = 115200, ws_url: str = DEFAULT_WS_URL, http_url: str = DEFAULT_HTTP_URL):
        self.mcu_port = mcu_port
        self.mcu_baud = mcu_baud
        self.ws_url = ws_url
        self.http_url = http_url
        self.mcu_ser = None

        if HAS_SERIAL:
            if not self.mcu_port:
                self.mcu_port = auto_detect_mcu_port()

            if self.mcu_port:
                try:
                    self.mcu_ser = serial.Serial(self.mcu_port, self.mcu_baud, timeout=1)
                    print(f"[+] [MCU BRIDGE] Connected to ESP32 on {self.mcu_port} @ {self.mcu_baud} baud.")
                    # Allow ESP32 reset sequence to settle
                    time.sleep(1.8)
                    # Send startup handshake
                    self.send_startup_ping()
                except serial.SerialException as e:
                    print(f"[!] [MCU PORT BUSY] Could not open {self.mcu_port}: {e}")
                    print("    TIP: Make sure the Arduino IDE Serial Monitor is CLOSED so this script can access the port.")
                except Exception as e:
                    print(f"[!] [MCU BRIDGE ERROR] {e}")
            else:
                print("[-] [MCU BRIDGE] Running in Virtual/Emulated mode (No physical ESP32 detected on USB).")
        else:
            print("[-] [MCU BRIDGE] Running in Virtual mode (pyserial library not installed).")

    def send_startup_ping(self):
        """Sends an initial diagnostic handshake to the ESP32."""
        payload = json.dumps({
            "level": "info",
            "attack_type": "SYSTEM READY",
            "message": "TRAPWIRE HARDWARE ONLINE",
            "attacker_ip": "127.0.0.1",
            "timestamp": int(time.time())
        }) + "\n"
        if self.mcu_ser:
            try:
                self.mcu_ser.write(payload.encode("utf-8"))
                print(f"[SERIAL -> ESP32] Handshake sent: {payload.strip()}")
            except Exception as e:
                print(f"[SERIAL WRITE ERROR] {e}")

    def forward_to_mcu(self, alert: dict):
        """Formats and transmits the threat packet over USB Serial to the ESP32."""
        meta = alert.get("meta") or {}
        attacker_ip = meta.get("attacker_ip") or meta.get("ip") or "185.20.209.0"
        if attacker_ip in ("127.0.0.1", "localhost", "::1", "unknown"):
            attacker_ip = "185.20.209.0"

        raw_msg = alert.get("message", "Threat event detected")
        raw_type = (meta.get("attack_type") or meta.get("type") or "").lower()
        msg_upper = raw_msg.upper()

        if "sql" in raw_type or "sql" in msg_upper:
            atk_type = "SQL INJECTION"
        elif "xss" in raw_type or "xss" in msg_upper:
            atk_type = "STORED XSS"
        elif "traversal" in raw_type or "traversal" in msg_upper or "lfi" in msg_upper:
            atk_type = "PATH TRAVERSAL"
        elif "idor" in raw_type or "idor" in msg_upper:
            atk_type = "IDOR / BOLA"
        elif "ssrf" in raw_type or "ssrf" in msg_upper:
            atk_type = "SSRF EXPLOIT"
        elif "honeytoken" in raw_type or "honeytoken" in msg_upper:
            atk_type = "HONEYTOKEN HIT"
        elif "exfiltrat" in raw_type or "export" in msg_upper:
            atk_type = "EXFILTRATION"
        elif "login" in raw_type or "brute" in msg_upper or "auth" in msg_upper:
            atk_type = "BRUTE FORCE"
        elif "canary" in raw_type or "canary" in msg_upper:
            atk_type = "CANARY TRAP"
        elif "test" in raw_type or "test" in msg_upper:
            atk_type = "HARDWARE TEST"
        else:
            atk_type = "CYBER BREACH"

        level = alert.get("level", "critical")
        if level in ("critical", "emergency", "warning", "high"):
            level_str = "critical"
        else:
            level_str = "info"

        if level_str == "info":
            return

        payload = json.dumps({
            "level": level_str,
            "attack_type": atk_type[:15],
            "message": atk_type[:15],
            "attacker_ip": attacker_ip[:15],
            "timestamp": int(alert.get("timestamp", time.time()))
        }) + "\n"

        if self.mcu_ser and self.mcu_ser.is_open:
            try:
                self.mcu_ser.write(payload.encode("utf-8"))
                self.mcu_ser.flush()
                print(f"[⚡ SERIAL -> ESP32] Alert Packet Transmitted: {payload.strip()}")
            except Exception as e:
                print(f"[!] [SERIAL TRANSMIT ERROR] {e}")
        else:
            print(f"[VIRTUAL SERIAL -> ESP32] {payload.strip()}")

    def handle_threat_event(self, alert: dict):
        level = alert.get("level", "info").lower()
        print(f"\n[⚡ LIVE THREAT EVENT] [{level.upper()}] {alert.get('message')}")
        self.forward_to_mcu(alert)

    async def listen_threat_stream(self):
        """Subscribes to the live Defender WebSocket alert feed."""
        print(f"[*] Subscribing to TrapWire Alert Stream: {self.ws_url} ...")

        retry_count = 0
        while True:
            try:
                if HAS_WEBSOCKETS:
                    async with websockets.connect(self.ws_url) as ws:
                        print("[+] Connected to Live SOC Alert WebSocket! Standing by for threat events...")
                        retry_count = 0
                        while True:
                            data_raw = await ws.recv()
                            try:
                                alert = json.loads(data_raw)
                                self.handle_threat_event(alert)
                            except Exception as json_err:
                                print(f"[PARSE ERROR] {json_err}")
                else:
                    # HTTP Polling fallback
                    poll_url = f"{self.http_url}/api/alerts/recent"
                    resp = requests.get(poll_url, timeout=3)
                    if resp.ok:
                        alerts = resp.json().get("alerts", [])
                        if alerts:
                            self.handle_threat_event(alerts[0])
                    await asyncio.sleep(2)
            except Exception as e:
                retry_count += 1
                wait_sec = min(3 * retry_count, 10)
                print(f"[STREAM RECONNECTING] Server unavailable: {e}. Retrying in {wait_sec}s...")
                await asyncio.sleep(wait_sec)


def main():
    parser = argparse.ArgumentParser(description="TRAPWIRE Physical Hardware Serial Bridge & Threat Relay")
    parser.add_argument("--port", type=str, default=None, help="COM port for ESP32 (e.g. COM7 or /dev/ttyUSB0). If omitted, auto-detects.")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--ws", type=str, default=DEFAULT_WS_URL, help="TrapWire WebSocket URL")
    parser.add_argument("--server", type=str, default=DEFAULT_HTTP_URL, help="TrapWire HTTP URL")
    parser.add_argument("--test", action="store_true", help="Send an immediate test breach packet to trigger the hardware siren.")
    args = parser.parse_args()

    print("=" * 72)
    print(" TRAPWIRE — Physical Threat Siren Hardware Bridge v2.5")
    print(f" Defender Server:  {args.server}")
    print(f" WebSocket Stream: {args.ws}")
    print("=" * 72)

    print_available_ports()

    bridge = HardwareBridge(
        mcu_port=args.port,
        mcu_baud=args.baud,
        ws_url=args.ws,
        http_url=args.server
    )

    if args.test:
        print("\n[*] Firing Instant Physical Alarm Test Packet to ESP32...")
        test_alert = {
            "level": "critical",
            "message": "SQL INJECTION EXPLOIT DETECTED",
            "timestamp": int(time.time()),
            "meta": {
                "attacker_ip": "185.220.101.45",
                "isp": "Stiftung Erneuerbare Freiheit",
                "type": "sqli_attack"
            }
        }
        bridge.handle_threat_event(test_alert)
        print("[+] Test packet transmitted. Check physical White LED, Red LED, Buzzer, and OLED.\n")

    try:
        asyncio.run(bridge.listen_threat_stream())
    except KeyboardInterrupt:
        print("\n[*] Hardware serial bridge stopped by user.")


if __name__ == "__main__":
    main()
