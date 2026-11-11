# TRAPWIRE — ESP32 Physical Threat Alert Node

When TRAPWIRE detects an attack, this board sounds a **buzzer**, flashes a
**red LED**, and shows the **attacker's details on a 0.96" OLED** (attack type,
IP, ISP, location, incident ID, DPB acknowledgement number). Everything the SOC
dashboard sees, the hardware sees — because the server calls `hardware.notify()`
from the same `broadcast_alert()` that feeds the dashboard.

It is **optional**: if no board is connected, the server still runs and the
dashboard shows a "virtual OLED" mirror of exactly what the hardware would show.

---

## 1. Parts

| Part | Notes |
|------|-------|
| ESP32 DevKit v1 (30/38-pin) | any ESP32 with USB works |
| SSD1306 OLED 128×64, I²C | the common 4-pin 0.96" module (addr `0x3C`) |
| Active buzzer module (3-pin) | "active" = beeps on its own. Passive piezo? set `BUZZER_PASSIVE 1` |
| Red LED + 220 Ω resistor | or a red LED module |
| Green LED + 220 Ω resistor | optional (armed/idle indicator) |
| Jumper wires, breadboard | — |
| *(optional)* relay + 12 V strobe | for a real warning light |

The on-board **BOOT button** is the silence/mute button — no extra button needed.

---

## 2. Wiring

| Signal | ESP32 pin | To |
|--------|-----------|----|
| OLED SDA | **GPIO 21** | OLED SDA |
| OLED SCL | **GPIO 22** | OLED SCL |
| OLED VCC | 3V3 | OLED VCC |
| OLED GND | GND | OLED GND |
| Red LED | **GPIO 25** | LED + (via 220 Ω), LED − to GND |
| Buzzer | **GPIO 26** | buzzer signal/`I/O`, buzzer − to GND, + to 3V3/VIN |
| Green LED (opt.) | **GPIO 27** | LED + (via 220 Ω) → GND |
| Relay (opt.) | **GPIO 33** | relay IN |
| Silence/Mute | GPIO 0 | on-board BOOT button (already wired) |

```
 ESP32                         SSD1306 OLED
 3V3  ───────────────────────  VCC
 GND  ───────────────────────  GND
 G21  ───────────────────────  SDA
 G22  ───────────────────────  SCL

 G25 ──[220Ω]──|>|── GND       (red LED)
 G27 ──[220Ω]──|>|── GND       (green LED, optional)
 G26 ─────────────── buzzer signal  (buzzer + to 3V3, − to GND)
```

If your OLED shows nothing: try address `0x3D` (change `OLED_ADDR` in the sketch).
If the buzzer is silent or always on: your module is active-LOW — set
`#define BUZZER_ON_LEVEL LOW`. A passive piezo instead of a module needs
`#define BUZZER_PASSIVE 1`.

---

## 3. Flash the firmware

1. Arduino IDE → **Boards Manager** → install **esp32** (Espressif).
2. **Library Manager** → install **Adafruit SSD1306** (accept the Adafruit GFX dependency).
3. Open `hardware/esp32_threat_siren/esp32_threat_siren.ino`.
4. Board = **ESP32 Dev Module**, select the COM port, **Upload**.
5. Open Serial Monitor at **115200** — you should see `READY|TRAPWIRE-ESP32|1.0`
   and the OLED shows **ARMED — monitoring**.

Bench test without the web app:

```bash
pip install pyserial
python -m app.hardware --list        # show detected boards
python -m app.hardware --test        # fire a fake SQLi alert, siren for ~15 s
```

---

## 4. Connect it to the server

### USB (default, easiest)
Just plug the ESP32 in **before** starting the server. It auto-detects the port
(CP210x / CH340 / FTDI / native-USB). To force a port:

```bash
# Windows
set TRAPWIRE_HW_PORT=COM5
# Linux / macOS
export TRAPWIRE_HW_PORT=/dev/ttyUSB0
```

Then start TRAPWIRE as usual (`uvicorn app.main:app --port 8080` or
`python run_servers.py`). On the dashboard → **Hardware Nodes & IoT** tab you'll
see **ESP32 — Connected**, firmware version, and the live OLED mirror.

### Wi-Fi (no cable to the server)
In the sketch set `#define ENABLE_WIFI 1` and fill in `WIFI_SSID` / `WIFI_PASS`,
re-flash, read the printed IP, then start the server with:

```bash
export TRAPWIRE_HW_URL=http://192.168.1.60   # the ESP32's IP
```

### Turn hardware off entirely
```bash
export TRAPWIRE_HW=off
```

---

## 5. What each alert looks like

| TRAPWIRE event | LED | Buzzer | OLED |
|----------------|-----|--------|------|
| Brute force / SQLi / exfiltration / canary hit (critical) | fast blink 15 s → stays ON | 15 s warble siren | full attacker details, 2 pages |
| Probe / XSS / recon / VPN hop (warning) | 2 quick flashes | 2 short beeps | attacker details |
| DPB report filed | 1 flash | 1 beep | shows the DPB ack number |
| Hardware self-test | 3 s | 3 s | "SELF TEST" |
| Silence (BOOT button or dashboard) | off | off | back to ARMED |

The red LED **latches ON** after a critical siren so you can see an attack
happened even after the noise stops — until someone presses **BOOT** (logged as
"physical alarm acknowledged" on the dashboard) or clicks **Silence**.

---

## 6. Wire protocol (for your viva)

One ASCII line per message, `\n`-terminated. Server → ESP32:

```
ALERT|sev|type|ip|isp|location|incident|time|count|ack|detail
   sev: C critical · W warning · R report filed · T self-test
CLEAR            silence + idle screen
MUTE|1 / MUTE|0  mute / unmute buzzer
PING             heartbeat
```

ESP32 → server: `READY|...`, `PONG|...|ackCount|muted`, `ACK|BUTTON|<n>`.
It's plain text, so you can test the board with any serial terminal.
