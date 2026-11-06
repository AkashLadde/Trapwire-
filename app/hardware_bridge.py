"""
TRAPWIRE -- Native Server-Side Hardware Serial Bridge (Asynchronous & Non-Blocking)
Directly connects app.main:app to the physical ESP32 DevKit V1 / NodeMCU
over USB Serial (e.g. COM7 on Windows, /dev/ttyUSB0 on Linux).

Uses a background daemon thread and queue so serial communication NEVER
blocks the FastAPI event loop or HTTP request handling.
"""

import os
import sys
import time
import json
import queue
import threading

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


class MCUHardwareManager:
    def __init__(self, port: str = None, baud: int = 115200):
        self.port = port or os.getenv("TRAPWIRE_MCU_PORT", None)
        self.baud = baud
        self.ser = None
        self._queue = queue.Queue(maxsize=100)
        self._running = True
        self._worker_thread = threading.Thread(target=self._serial_worker, daemon=True)
        self._worker_thread.start()

    def auto_detect_port(self) -> str:
        """Finds the ESP32 CP210x, CH340, FTDI, or USB-UART COM port."""
        if not HAS_SERIAL:
            return None
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            return None

        # 1. Search for known UART bridge chips
        for p in ports:
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            if any(k in desc or k in hwid for k in ["cp210", "ch340", "ch341", "ftdi", "uart", "esp32", "silicon labs"]):
                return p.device

        # 2. Prefer COM7 if present
        for p in ports:
            if p.device.upper() == "COM7":
                return p.device

        # 3. Single port fallback
        if len(ports) == 1:
            return ports[0].device
        return None

    def _serial_worker(self):
        """Dedicated background daemon that maintains connection and writes alerts."""
        while self._running:
            try:
                # 1. Ensure serial port is connected
                if not (self.ser and self.ser.is_open):
                    target_port = self.port or self.auto_detect_port()
                    if target_port:
                        try:
                            # Explicitly disable DTR/RTS so the ESP32 doesn't reset on connect
                            s = serial.Serial()
                            s.port = target_port
                            s.baudrate = self.baud
                            s.timeout = 0.5
                            s.dtr = False
                            s.rts = False
                            s.open()
                            self.ser = s
                            self.port = target_port
                            print(f"[+] [HARDWARE BRIDGE] Connected to ESP32 on {self.port} @ {self.baud} baud.")
                        except Exception:
                            self.ser = None
                            time.sleep(2.0)
                    else:
                        time.sleep(2.0)

                # 2. Read queued alert packet
                try:
                    packet = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # 3. Transmit over serial
                if self.ser and self.ser.is_open:
                    line = json.dumps(packet) + "\n"
                    try:
                        self.ser.write(line.encode("ascii", errors="ignore"))
                        self.ser.flush()
                        print(f"[MCU ALERT TRANSMITTED -> ESP32] {line.strip()}")
                    except Exception as e:
                        print(f"[!] [HARDWARE SERIAL WRITE ERROR] {e}")
                        try:
                            self.ser.close()
                        except Exception:
                            pass
                        self.ser = None
                else:
                    print(f"[VIRTUAL HARDWARE RELAY] {packet}")

            except Exception:
                time.sleep(1.0)

    def format_threat_packet(self, alert: dict) -> dict:
        """Extracts clean attack_type, attacker_ip, and threat level."""
        meta = alert.get("meta") or {}
        raw_msg = alert.get("message", "INTRUSION DETECTED")

        # 1. Determine Attacker IP
        ip = meta.get("attacker_ip") or meta.get("ip") or alert.get("ip") or "185.20.209.0"
        if ip in ("127.0.0.1", "localhost", "::1", "unknown"):
            ip = meta.get("vpn_ip") or meta.get("resolved_ip") or "185.20.209.0"

        # Strip ipv6 prefix if present
        if ip.startswith("::ffff:"):
            ip = ip[7:]

        # 2. Determine Clean Attack Type
        raw_type = (meta.get("attack_type") or meta.get("type") or "").lower()
        msg_upper = raw_msg.upper()

        if "sql" in raw_type or "sql" in msg_upper:
            atk_type = "SQL INJECTION"
        elif "xss" in raw_type or "xss" in msg_upper:
            atk_type = "STORED XSS"
        elif "traversal" in raw_type or "traversal" in msg_upper or "lfi" in msg_upper:
            atk_type = "PATH TRAVERSAL"
        elif "idor" in raw_type or "idor" in msg_upper or "bola" in msg_upper:
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

        return {
            "level": level_str,
            "attack_type": atk_type[:15],
            "attacker_ip": ip[:15],
            "message": atk_type[:15],
            "timestamp": int(time.time())
        }

    def broadcast_to_mcu(self, alert: dict) -> bool:
        """Enqueues the threat packet for non-blocking background serial transmission."""
        packet = self.format_threat_packet(alert)

        # Do not fire alarm for normal info events
        if packet["level"] == "info":
            return False

        try:
            self._queue.put_nowait(packet)
            return True
        except queue.Full:
            return False


# Singleton instance shared across the application
hardware_bridge = MCUHardwareManager()
