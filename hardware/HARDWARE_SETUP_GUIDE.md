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

---

### B. NodeMCU (ESP8266) with Dual LEDs (White & Red), OLED & Buzzer

If you have a **NodeMCU ESP8266** with discrete **White LED**, **Red LED**, **0.96" OLED**, and an **Active Buzzer**, use this exact wiring table and the firmware at `hardware/nodemcu_threat_siren.ino`:

| NodeMCU Pin | GPIO | Target Component | Component Pin | Notes & Resistor |
| :--- | :--- | :--- | :--- | :--- |
| **3V3** | 3.3V | OLED SSD1306 | **VCC** | 3.3V Power rail |
| **GND** | GND | OLED + LEDs + Buzzer | **GND / (-)** | Common Ground rail on breadboard |
| **D1** | GPIO 5 | OLED SSD1306 | **SCL / SCK** | I2C Clock line |
| **D2** | GPIO 4 | OLED SSD1306 | **SDA** | I2C Data line |
| **D5** | GPIO 14 | **White LED** | **Anode (+ / Long leg)** | In series with **220Ω - 330Ω** resistor. Indicates **System Armed / Normal Guard** |
| **D6** | GPIO 12 | **Red LED** | **Anode (+ / Long leg)** | In series with **220Ω - 330Ω** resistor. Strobes rapidly on **Threat / Attack** |
| **D7** | GPIO 13 | **Active Buzzer** | **(+) or Signal** | Emits high-priority tactical warning chimes on attack |

#### Breadboard Wiring Summary for NodeMCU:
1. **Common Ground**: Connect NodeMCU `GND` to the blue (-) ground rail on your breadboard.
2. **OLED (I2C SSD1306 128x64)**:
   - `VCC` $\rightarrow$ NodeMCU `3V3`
   - `GND` $\rightarrow$ Breadboard Ground rail
   - `SCL` $\rightarrow$ NodeMCU `D1` (GPIO 5)
   - `SDA` $\rightarrow$ NodeMCU `D2` (GPIO 4)
3. **White LED (Normal Standby Guard)**:
   - Long leg (+) $\rightarrow$ 220Ω or 330Ω resistor $\rightarrow$ NodeMCU `D5` (GPIO 14)
   - Short leg (-) $\rightarrow$ Breadboard Ground rail
4. **Red LED (Breach Alarm Strobe)**:
   - Long leg (+) $\rightarrow$ 220Ω or 330Ω resistor $\rightarrow$ NodeMCU `D6` (GPIO 12)
   - Short leg (-) $\rightarrow$ Breadboard Ground rail
5. **Active Buzzer (Audio Alert Siren)**:
   - Positive pin (+) $\rightarrow$ NodeMCU `D7` (GPIO 13)
   - Negative pin (-) $\rightarrow$ Breadboard Ground rail

---

## 4. Flashing & Running the Firmware

### Option 1: Uploading to NodeMCU (ESP8266)
1. Open the [Arduino IDE](https://www.arduino.cc/en/software).
2. Add ESP8266 Board URL in *File > Preferences > Additional Boards Manager URLs*:
   ```
   http://arduino.esp8266.com/stable/package_esp8266com_index.json
   ```
3. Go to *Tools > Board > Boards Manager*, search for **esp8266** by ESP8266 Community, and click **Install**.
4. Install required libraries via *Sketch > Include Library > Manage Libraries*:
   - `Adafruit SSD1306`
   - `Adafruit GFX Library`
   - `ArduinoJson` (version 6 or 7)
5. Open `hardware/nodemcu_threat_siren.ino` in Arduino IDE.
6. Under *Tools*, configure:
   - **Board**: `NodeMCU 1.0 (ESP-12E Module)`
   - **Upload Speed**: `115200`
   - **Port**: Select your NodeMCU's COM port (e.g. `COM3` on Windows or `/dev/ttyUSB0` on Linux)
7. Click **Upload**.
8. Once uploaded:
   - The **White LED** will light up solid (System Armed).
   - The **OLED** will display `TRAPWIRE DEFENDER - STATUS: ARMED & READY`.
   - The **Red LED** and **Buzzer** remain silent until an attack arrives.

### Option 2: Uploading to ESP32
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
