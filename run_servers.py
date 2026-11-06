"""
TRAPWIRE — Master Dual-Server Launcher
Runs both independent servers concurrently:
  1. Company Defender Portal & DPDP Engine on http://127.0.0.1:8080
  2. Kali Linux Attacker Pentest Console on http://127.0.0.1:9000
"""

import os
import sys
import time
import subprocess
import threading

os.environ["COMPANY_URL"] = "http://127.0.0.1:8080"
os.environ["TRAPWIRE_TARGET_PORTAL"] = "http://127.0.0.1:8080"


def run_company_server():
    print("[SERVER 1] Launching Company Portal on http://127.0.0.1:8080 ...")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", "8080"
    ])


def run_attacker_server():
    print("[SERVER 2] Launching Attacker Portal on http://127.0.0.1:9000 ...")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "app.attacker_server:app",
        "--host", "127.0.0.1", "--port", "9000"
    ])


if __name__ == "__main__":
    print("=" * 72)
    print("  TRAPWIRE — DUAL-SERVER ARCHITECTURE LAUNCHER")
    print("  Company Portal (Defender):  http://127.0.0.1:8080")
    print("  Attacker Portal (OffSec):   http://127.0.0.1:9000")
    print("=" * 72)

    t1 = threading.Thread(target=run_company_server, daemon=True)
    t2 = threading.Thread(target=run_attacker_server, daemon=True)

    t1.start()
    time.sleep(1)
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Terminating servers...")
        sys.exit(0)
