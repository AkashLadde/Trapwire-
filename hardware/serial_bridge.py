"""
=====================================================================================
TRAPWIRE — Hardware Serial Bridge & GSM Modem Controller
=====================================================================================
Connects the TrapWire Defender Backend (FastAPI WebSocket) to physical hardware:
 1. USB Serial MCU (ESP32 / Arduino Threat Strobe Siren & OLED).
 2. USB / Serial GSM Module (SIM800L / SIM900) for Out-of-Band Hardware SMS to 9901625399.
 3. Dual-NIC Network Tap telemetry forwarder.

Usage:
    python hardware/serial_bridge.py --port COM3 --baud 115200 --gsm-port COM4
=====================================================================================
"""

import sys
import time
import json
import asyncio
import argparse
import requests

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

ADMIN_PHONE = "9901625399"
SERVER_WS_URL = "ws://127.0.0.1:8000/api/threat-stream"
SERVER_HTTP_URL = "http://127.0.0.1:8000"


class GsmModem:
    """Controls a physical SIM800L / SIM900 GSM module over AT Commands via Serial."""
    def __init__(self, port: str = None, baud: int = 9600):
        self.port = port
        self.baud = baud
        self.ser = None
        if HAS_SERIAL and port:
            try:
                self.ser = serial.Serial(port, baud, timeout=3)
                time.sleep(1)
                self.send_at("AT")
                self.send_at("AT+CMGF=1") # Set SMS text mode
                print(f"[GSM MODEM] Initialized on {port} (Ready for SMS to +91 {ADMIN_PHONE})")
            except Exception as e:
                print(f"[GSM MODEM WARN] Could not open {port}: {e}")

    def send_at(self, cmd: str) -> str:
        if not self.ser:
            return ""
        self.ser.write((cmd + "\r\n").encode("utf-8"))
        time.sleep(0.5)
        resp = self.ser.read_all().decode("utf-8", errors="ignore")
        return resp

    def send_sms(self, phone: str, text: str):
        if not self.ser:
            print(f"[GSM SIMULATION] SMS to +91 {phone}: {text}")
            return True
        try:
            self.send_at("AT+CMGF=1")
            self.ser.write(f'AT+CMGS="+91{phone}"\r\n'.encode("utf-8"))
            time.sleep(0.5)
            self.ser.write(f"{text}\x1A".encode("utf-8")) # 0x1A = Ctrl+Z to send
            time.sleep(2)
            print(f"[GSM HARDWARE SMS SENT] To: +91 {phone} | Text: {text}")
            return True
        except Exception as e:
            print(f"[GSM SMS ERROR] {e}")
            return False


class HardwareBridge:
    def __init__(self, mcu_port: str = None, mcu_baud: int = 115200, gsm_port: str = None):
        self.mcu_port = mcu_port
        self.mcu_baud = mcu_baud
        self.mcu_ser = None
        self.gsm = GsmModem(gsm_port)

        if HAS_SERIAL and mcu_port:
            try:
                self.mcu_ser = serial.Serial(mcu_port, mcu_baud, timeout=1)
                print(f"[MCU BRIDGE] Connected to ESP32 / Arduino Siren on {mcu_port} @ {mcu_baud} baud.")
            except Exception as e:
                print(f"[MCU BRIDGE WARN] Could not connect to {mcu_port}: {e}")
        else:
            print("[MCU BRIDGE] Running in Virtual/Emulated mode (No physical USB MCU detected).")

    def forward_to_mcu(self, alert: dict):
        """Sends JSON alert packet to ESP32 over serial."""
        payload = json.dumps({
            "level": alert.get("level", "info"),
            "message": alert.get("message", "")[:45],
            "attacker_ip": alert.get("meta", {}).get("attacker_ip", "127.0.0.1"),
            "timestamp": int(alert.get("timestamp", time.time()))
        }) + "\n"

        if self.mcu_ser:
            try:
                self.mcu_ser.write(payload.encode("utf-8"))
                print(f"[SERIAL -> ESP32] Sent: {payload.strip()}")
            except Exception as e:
                print(f"[SERIAL WRITE ERROR] {e}")
        else:
            print(f"[VIRTUAL SERIAL -> ESP32] {payload.strip()}")

    def handle_critical_alert(self, alert: dict):
        # 1. Strobe Siren
        self.forward_to_mcu(alert)

        # 2. Hardware Out-of-Band SMS Dispatch
        msg = f"TRAPWIRE INTRUSION: {alert.get('message', 'Breach detected')} | Attacker IP: {alert.get('meta',{}).get('attacker_ip', '127.0.0.1')}"
        self.gsm.send_sms(ADMIN_PHONE, msg)

    async def listen_threat_stream(self):
        """Connects to TrapWire WebSocket on port 8000 and listens for live attacks."""
        print(f"[*] Connecting to TrapWire WebSocket: {SERVER_WS_URL} ...")
        
        while True:
            try:
                if HAS_WEBSOCKETS:
                    async with websockets.connect(SERVER_WS_URL) as ws:
                        print("[+] Connected to Live SOC Threat Stream!")
                        while True:
                            data_raw = await ws.recv()
                            alert = json.loads(data_raw)
                            print(f"\n[⚡ LIVE THREAT EVENT] [{alert.get('level', 'INFO').upper()}] {alert.get('message')}")
                            
                            level = alert.get("level", "info")
                            if level in ("critical", "warning", "emergency"):
                                self.handle_critical_alert(alert)
                            else:
                                self.forward_to_mcu(alert)
                else:
                    # Polling Fallback if websockets package not installed
                    resp = requests.get(f"{SERVER_HTTP_URL}/api/alerts/recent", timeout=2)
                    if resp.ok:
                        alerts = resp.json().get("alerts", [])
                        if alerts:
                            latest = alerts[0]
                            print(f"[POLL ALERT] {latest.get('message')}")
                            self.forward_to_mcu(latest)
                    await asyncio.sleep(2)
            except Exception as e:
                print(f"[STREAM RECONNECTING] Server offline or disconnected: {e}. Retrying in 3s...")
                await asyncio.sleep(3)


def auto_detect_ports():
    if not HAS_SERIAL:
        print("Note: pyserial is not installed. To connect physical hardware, install with: pip install pyserial websockets")
        return
    ports = list(serial.tools.list_ports.comports())
    print("\n--- Available Serial / COM Ports ---")
    if not ports:
        print(" No USB Serial hardware currently plugged in.")
    for p in ports:
        print(f"  • Port: {p.device} | Description: {p.description} | Hardware ID: {p.hwid}")
    print("------------------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="TRAPWIRE Physical Hardware Serial & GSM Bridge")
    parser.add_argument("--port", type=str, default=None, help="COM port for ESP32 / Arduino Siren (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate for ESP32 (default: 115200)")
    parser.add_argument("--gsm-port", type=str, default=None, help="COM port for SIM800L GSM modem (e.g. COM4 or /dev/ttyUSB1)")
    args = parser.parse_args()

    print("=" * 70)
    print(" TRAPWIRE — Physical Threat Siren & GSM Bridge v2.4")
    print(" Target Admin SMS: +91 99016 25399")
    print(" Defender Server:  http://127.0.0.1:8000")
    print("=" * 70)

    auto_detect_ports()

    bridge = HardwareBridge(mcu_port=args.port, mcu_baud=args.baud, gsm_port=args.gsm_port)

    try:
        asyncio.run(bridge.listen_threat_stream())
    except KeyboardInterrupt:
        print("\n[*] Hardware bridge stopped by user.")


if __name__ == "__main__":
    main()
