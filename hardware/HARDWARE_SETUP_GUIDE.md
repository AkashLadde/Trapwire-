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

### A. ESP32 DevKit V1 (Wi-Fi + Bluetooth) with Dual LEDs (White & Red), OLED & Buzzer

If you have an **ESP32 Development Board (ESP32 DevKit V1 with Wi-Fi and Bluetooth)**, use this exact pinout table and the firmware at [`hardware/esp32_devkit_threat_siren/esp32_devkit_threat_siren.ino`](./esp32_devkit_threat_siren/esp32_devkit_threat_siren.ino):

| ESP32 DevKit V1 Pin | GPIO | Target Component | Component Pin | Notes & Resistor |
| :--- | :--- | :--- | :--- | :--- |
| **3V3** (or **VIN / 5V**) | Power | 0.96" I2C OLED (128x64) | **VCC** | Connect to 3V3. **Note:** If screen stays dark, move to **VIN/5V** (many OLED breakout modules have an onboard 3.3V LDO regulator that needs 5V to drive the internal charge pump). |
| **GND** | Ground | OLED + LEDs + Buzzer | **GND / (-)** | Connect to breadboard common ground rail |
| **D21** | GPIO 21 | 0.96" I2C OLED | **SDA** | ESP32 hardware I2C Data line (Internal pull-up enabled in sketch) |
| **D22** | GPIO 22 | 0.96" I2C OLED | **SCL** | ESP32 hardware I2C Clock line (Internal pull-up enabled in sketch) |
| **D18** | GPIO 18 | **White LED** | **Anode (+ / Long leg)** | In series with **220Ω - 330Ω** resistor. **Blinks rhythmically (500ms ON / 500ms OFF)** during **Normal Standby** |
| **D19** | GPIO 19 | **Red LED** | **Anode (+ / Long leg)** | In series with **220Ω - 330Ω** resistor. **Strobes rapidly (120ms)** during **Active Attack** |
| **D23** | GPIO 23 | **Piezo Buzzer** | **(+) or Signal** | **Completely silent in Standby**. Produces **Police Siren (960Hz / 650Hz wail)** during Attack |

#### Breadboard Wiring Summary for ESP32 DevKit V1:
1. **Common Ground**: Connect the ESP32 `GND` pin to the blue (-) ground rail on your breadboard.
2. **0.96" I2C OLED Module (128x64 pixels)**:
   - `VCC` $\rightarrow$ ESP32 `3V3` (if display does not light up, connect to `VIN / 5V`)
   - `GND` $\rightarrow$ Breadboard Ground rail
   - `SDA` $\rightarrow$ ESP32 `D21` (GPIO 21)
   - `SCL` $\rightarrow$ ESP32 `D22` (GPIO 22)
   - **Crucial Physical Check:** Read the silkscreen printed on your OLED module. Some modules are ordered `GND - VCC - SCL - SDA`, while others are `VCC - GND - SCL - SDA`. Ensure VCC and GND are not reversed!
3. **White LED (Normal Standby Armed Indicator)**:
   - Long leg (+) $\rightarrow$ 220Ω or 330Ω resistor $\rightarrow$ ESP32 `D18` (GPIO 18)
   - Short leg (-) $\rightarrow$ Breadboard Ground rail
   - *Behavior*: Blinks once per second (500ms ON, 500ms OFF) to indicate the system is actively guarding the perimeter.
4. **Red LED (Breach Alarm Strobe)**:
   - Long leg (+) $\rightarrow$ 220Ω or 330Ω resistor $\rightarrow$ ESP32 `D19` (GPIO 19)
   - Short leg (-) $\rightarrow$ Breadboard Ground rail
   - *Behavior*: Strictly OFF in standby. Blinks in a rapid tactical emergency strobe (120ms ON / 120ms OFF) during an attack.
5. **Active or Passive Buzzer (Audio Alert Siren)**:
   - Positive pin (+) $\rightarrow$ ESP32 `D23` (GPIO 23)
   - Negative pin (-) $\rightarrow$ Breadboard Ground rail
   - *Behavior*: Strictly SILENT in standby. Emits an alternating Police Siren sound (960 Hz / 650 Hz dual-tone wail) during an attack.

---

### Buzzer Troubleshooting: Fixing Continuous Sound Screaming
If your buzzer produces a continuous sound immediately upon powering on:
1. **Active-LOW Buzzer Inversion**:
   - Many buzzer breakout boards (such as the 3-pin KY-012 module with a PNP transistor) are **Active-LOW**, meaning they turn ON when driven `LOW` and turn OFF when driven `HIGH`.
   - In [`hardware/esp32_devkit_threat_siren/esp32_devkit_threat_siren.ino`](./esp32_devkit_threat_siren/esp32_devkit_threat_siren.ino), locate line 76:
     ```cpp
     #define BUZZER_ACTIVE_LOW  false
     ```
   - If your buzzer sounds continuously when idle, change this setting to:
     ```cpp
     #define BUZZER_ACTIVE_LOW  true
     ```
   - Re-upload the sketch to your ESP32.
2. **Active vs. Passive Buzzer**:
   - **Active Buzzer** (has a sticker on top and sealed epoxy bottom): Generates its own tone when DC voltage is applied. Driven by `digitalWrite()`.
   - **Passive Buzzer** (exposed green PCB backing): Requires an AC frequency signal to generate tone. Driven by `tone(PIN_BUZZER, freq)`.
   - The updated firmware automatically handles **both** passive and active buzzers by simultaneously pulsing `tone()` frequency and driving the digital GPIO level!
3. **3-Pin Buzzer Modules**:
   - If using a 3-pin module labeled `S`, `+`, `-`:
     - `S` (Signal) $\rightarrow$ ESP32 `D23`
     - `+` (VCC) $\rightarrow$ ESP32 `3V3` (or `VIN`)
     - `-` (GND) $\rightarrow$ ESP32 `GND`

---

### 0.96" I2C OLED Display Troubleshooting Checklist
If your 0.96" OLED screen is completely dark, blank, or not working:
1. **Built-in I2C Scanner Diagnosis**:
   - Open Arduino IDE, open Tools > Serial Monitor, and set baud rate to **115200**.
   - Press the **EN / RST** button on your ESP32.
   - The sketch will automatically scan all I2C addresses and print:
     ```
     [I2C SCANNER] Found I2C device at address 0x3C! (or 0x3D)
     [+] OLED initialized successfully!
     ```
   - If it prints `[I2C WARNING] NO I2C DEVICES FOUND ON BUS!`, your DuPont jumper wires are loose, or SDA/SCL are swapped, or VCC is not receiving power.
2. **Power Rail Dropout (3.3V vs 5V / VIN)**:
   - Almost all 0.96" I2C OLED breakouts contain a tiny voltage regulator on the back (labeled `662K`).
   - When fed with 3.3V from ESP32's 3V3 pin, the voltage drops to ~2.8V, which is too low for the internal charge pump to generate the ~7.5V required to illuminate the OLED pixels.
   - **Fix:** Move the OLED's `VCC` jumper wire to the ESP32's `VIN` or `5V` pin (power from USB).
3. **SDA & SCL Pin Swapping**:
   - Ensure the OLED's `SDA` is plugged into ESP32 `D21` (GPIO 21).
   - Ensure the OLED's `SCL` is plugged into ESP32 `D22` (GPIO 22).
4. **Driver IC Compatibility**:
   - Some 0.96" modules use the **SH1106** or **SSD1315** controller instead of **SSD1306**.
   - Our updated firmware automatically sends charge-pump activation commands for both SSD1306 (`0x8D, 0x14`) and SH1106 (`0xAD, 0x8B`) at maximum contrast (`0xFF`), ensuring both display types illuminate.

---

### B. Legacy ESP32 Setup with WS2812B NeoPixel

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

### C. NodeMCU (ESP8266) with Dual LEDs (White & Red), OLED & Buzzer

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

### Option 1: Uploading to ESP32 DevKit V1 (White & Red LEDs, OLED, Buzzer)
1. Open the [Arduino IDE](https://www.arduino.cc/en/software).
2. Install the ESP32 Board package via *Tools > Board > Boards Manager*:
   - Search for **esp32** by *Espressif Systems* and click **Install**.
3. Install required libraries (*Sketch > Include Library > Manage Libraries*):
   - `Adafruit SSD1306`
   - `Adafruit GFX Library`
   - `ArduinoJson` (v6 or v7)
4. Open the sketch: [`hardware/esp32_devkit_threat_siren.ino`](./esp32_devkit_threat_siren.ino).
5. Under *Tools*, configure:
   - **Board**: `DOIT ESP32 DEVKIT V1` (or `ESP32 Dev Module`)
   - **Upload Speed**: `115200` (or `921600`)
   - **Port**: Select your ESP32 COM port (e.g., `COM3` on Windows or `/dev/ttyUSB0` on Linux)
6. Click **Upload** (➡️ arrow icon).
   - *Pro Tip*: If Arduino IDE shows `Connecting........_____.....`, press and hold the **BOOT** button on the ESP32 for 1-2 seconds until the percentage counter appears, then release it.
7. Once uploaded:
   - **Self-Test Routine**: White LED blinks twice, Red LED blinks twice, and buzzer gives a brief 300ms chirp.
   - **Standby Mode**:
     - The **White LED** will **blink rhythmically** (500ms ON / 500ms OFF) to indicate the system is armed.
     - The **Red LED** is **strictly OFF**.
     - The **Buzzer** is **strictly SILENT**.
     - The **OLED** displays `TRAPWIRE DEFENDER - STATUS: ARMED & READY`.
   - **Attack Mode** (when an attack hits or when testing):
     - The **White LED** turns OFF.
     - The **Red LED** blinks in an **emergency strobe** (120ms ON / 120ms OFF).
     - The **Buzzer** sounds an authentic **Police Siren** (alternating 960Hz / 650Hz dual-tone wail).
     - The **OLED** displays `! CRITICAL BREACH !` with attacker IP and exploit vector.
     - Automatically resets back to Standby after 9 seconds.

### Quick Testing in Arduino IDE (Serial Monitor)
You can test the siren, OLED, and LEDs directly inside the Arduino IDE without even running the server:
1. In Arduino IDE, click *Tools > Serial Monitor* and set the baud rate to **115200** (with *Newline* or *Both NL & CR*).
2. Type `attack` or `test` or `siren` and press **Enter**:
   - The ESP32 immediately turns OFF the white LED, begins strobing the red LED, sounds the police siren, and renders the incident screen on the OLED for 9 seconds!
3. Type `reset` or `standby` to return immediately to Standby mode (white LED blinking, buzzer silent).

### Option 2: Uploading to NodeMCU (ESP8266)
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
