# TRAPWIRE — Comprehensive Hardware Integration & Setup Guide

This guide details how to integrate **physical IoT and embedded hardware** with the **TrapWire Cyber Defense System**. Adding physical hardware elevates the capstone demonstration into a true hybrid **Cyber-Physical Intrusion Detection & Response (CP-IDS)** appliance.

---

## 1. Hardware Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │      TRAPWIRE DEFENDER SERVER          │
                      │       (FastAPI on Port 8080)           │
                      │    MySQL Database + DPDP Engine        │
                      └───────▲──────────────────▲─────────────┘
                              │                  │
                (USB Serial / WebSockets)        │ (HTTP Telemetry /decoy hit)
                              │                  │
            ┌─────────────────▼────────┐  ┌──────┴─────────────────────┐
            │   HARDWARE SERIAL BRIDGE │  │   RASPBERRY PI 4 SENSOR    │
            │   (hardware/serial_bridge.py)│  │   (hardware/raspberry_pi_node.py)
            └─────────┬──────────────┬─┘  └────────────────────────────┘
                      │              │                   │
         ┌────────────▼───┐    ┌──────────────────────────────────────────────┐
         │ ESP32 STROBE   │    │ PHYSICAL NETWORK DECOY                       │
         │ SIREN & OLED   │    │ Decoy SSH:2222, Telnet:2323                  │
         │ Visual Strobe  │    │ Captures rogue LAN scans & attacks           │
         │ Audio Alarm    │    └──────────────────────────────────────────────┘
         └────────────────┘
```

---

## 2. Bill of Materials (Components List)

| Item | Component | Recommended Model | Purpose | Approx Cost (INR) |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Microcontroller** | ESP32-WROOM-32 Dev Module | Drives threat strobe, OLED & buzzer | ₹350 - ₹450 |
| **2** | **Display** | 0.96" I2C OLED (SSD1306, 128x64) | Shows live attacker IP & incident text | ₹180 - ₹220 |
| **3** | **Visual Strobe** | WS2812B NeoPixel 8-LED Stick / Ring | Flashes Crimson Red on breach | ₹120 - ₹180 |
| **4** | **Audio Alarm** | 5V Active Piezo Buzzer Module | Emits high-priority chirps/sirens | ₹40 - ₹60 |
| **5** | **Hardware Controller** | CH340 / CP2102 USB Bridge | Connects ESP32 to server | ₹100 - ₹150 |
| **6** | **Edge Sensor** | Raspberry Pi 4 Model B (or Pi 3B+ / Zero 2W) | LAN honeypot bait & network sniffer | Existing / Lab |
| **7** | **Cables & Power** | MicroUSB Data Cables + Breadboard + Jumper Wires | Interconnection | ₹100 |

---

## 3. Wiring Schematics & Pin Connections

### A. ESP32 Threat Siren & OLED Display

| ESP32 Pin | Target Device | Target Pin | Description |
| :--- | :--- | :--- | :--- |
| **3V3** | OLED Display | **VCC** | 3.3V Power |
| **GND** | OLED Display | **GND** | Ground |
| **GPIO 21** | OLED Display | **SDA** | I2C Data Line |
| **GPIO 22** | OLED Display | **SCL** | I2C Clock Line |
| **GPIO 18** | WS2812 NeoPixel | **DIN / Data** | RGB Signal Pin |
| **5V / VIN**| WS2812 NeoPixel | **5V / VCC** | 5V Power for LEDs |
| **GND** | WS2812 NeoPixel | **GND** | Common Ground |
| **GPIO 19** | Active Buzzer | **(+) / Signal**| Trigger Pin |
| **GND** | Active Buzzer | **(-)** | Ground |

### B. SIM800L GSM Module (Optional Physical SMS Relay)

> **Note:** The SIM800L module uses a standard Mini-SIM card with active SMS balance.

| USB-to-TTL Adapter Pin | SIM800L Module Pin | Notes |
| :--- | :--- | :--- |
| **TX** | **RXD** | Serial Receive |
| **RX** | **TXD** | Serial Transmit |
| **GND** | **GND** | Common Ground |
| **External 4.2V 2A** | **VCC** | SIM800L requires 3.7V - 4.2V (2A burst current) |

---

## 4. Flashing & Running the Firmware

### Step 1: Upload Arduino Code to ESP32
1. Open the [Arduino IDE](https://www.arduino.cc/en/software).
2. Install the ESP32 Board package via *Tools > Board Manager*.
3. Install required libraries (*Sketch > Include Library > Manage Libraries*):
   - `Adafruit SSD1306`
   - `Adafruit GFX Library`
   - `Adafruit NeoPixel`
   - `ArduinoJson` (v6 or v7)
4. Open the file `hardware/esp32_threat_siren.ino`.
5. Select your ESP32 board and COM port, then click **Upload**.
6. When uploaded, the OLED will display `TRAPWIRE DEFENDER - STATUS: STANDBY` and the NeoPixels will glow Cyber Cyan.

---

## 5. Starting the Hardware Bridge Daemon

The hardware serial bridge links the TrapWire backend on Port 8080 with your USB-connected hardware:

```bash
# 1. Install optional serial dependencies
pip install pyserial websockets

# 2. Run the bridge (automatically detects connected COM ports)
python hardware/serial_bridge.py --port COM3 --baud 115200
```

*(On Linux / macOS / Raspberry Pi, use `/dev/ttyUSB0` or `/dev/ttyACM0`)*

---

## 6. Deploying the Raspberry Pi LAN Sensor

On your Raspberry Pi located on the physical network:

```bash
# 1. Clone or copy the Trapwire repository onto the Raspberry Pi
cd Trapwire

# 2. Run the edge honeypot bait listener
python hardware/raspberry_pi_node.py --server http://<YOUR_SERVER_IP>:8080 --node-id PI-HONEYPOT-01
```

The Raspberry Pi will now:
- Listen on decoy ports (SSH `2222`, Telnet `2323`, SCADA Modbus `5020`, Web Camera `8088`).
- Send heartbeat telemetry to the **Hardware Nodes** tab on the Company Dashboard.
- When an intruder scans the network or attempts to connect to these ports, it instantly triggers an intrusion alert and flashes the physical siren.

---

## 7. Dual-Server Demonstration Workflow

To demonstrate the complete ecosystem:

```bash
# Start both servers simultaneously
python run_servers.py
```

1. **Defender Console**: Open `http://127.0.0.1:8080` (Company Portal). Log in with `admin` / `Admin@2026!`.
2. **Attacker Console**: Open `http://127.0.0.1:9000` in a separate browser window or device.
3. **Simulate Attack**: On Port 9000, attempt root login or fire the **SQL Injection** / **Canary Trap** exploit.
4. **Observe Response**:
   - The Attacker receives simulated fake data.
   - The Company Dashboard immediately triggers an **Emergency Alert Banner** and audio buzzer.
   - The physical ESP32 OLED displays the attacker IP and flashes crimson strobe LEDs.
   - The automated **DPDP statutory compliance breach report** is generated and acknowledged.
