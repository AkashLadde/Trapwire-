/*
 * =====================================================================================
 * TRAPWIRE — ESP32 DevKit V1 Physical Threat Siren & SOC Defense Node
 * =====================================================================================
 * Target Board:
 *   ESP32 Development Board (ESP32 DevKit V1 with Wi-Fi & Bluetooth, 30-pin or 36-pin)
 *
 * Connected Components:
 *   1. 0.96" 128x64 I2C OLED Display Module (SSD1306 / SH1106 / SSD1315)
 *   2. White LED (Normal Guard Status / Standby Armed)
 *   3. Red LED (Threat Intrusion Strobe / Active Attack In Progress)
 *   4. Piezo Buzzer (Active or Passive Audio Warning Siren)
 *
 * Exact Pin Connections on ESP32 DevKit V1:
 *   - OLED VCC         -> 3V3 (or VIN/5V if display stays dark due to onboard LDO dropout)
 *   - OLED GND         -> GND pin on ESP32
 *   - OLED SDA         -> GPIO 21 (Pin labeled D21)
 *   - OLED SCL         -> GPIO 22 (Pin labeled D22)
 *   - White LED (+)    -> GPIO 18 (Pin labeled D18) via 220Ω-330Ω resistor
 *   - White LED (-)    -> GND pin on ESP32
 *   - Red LED (+)      -> GPIO 19 (Pin labeled D19) via 220Ω-330Ω resistor
 *   - Red LED (-)      -> GND pin on ESP32
 *   - Buzzer (+)       -> GPIO 23 (Pin labeled D23)
 *   - Buzzer (-)       -> GND pin on ESP32
 *
 * Required Arduino Libraries:
 *   1. "Adafruit SSD1306" by Adafruit
 *   2. "Adafruit GFX Library" by Adafruit
 *   3. "ArduinoJson" (v6 or v7) by Benoit Blanchon
 *
 * Serial Communication:
 *   Baud rate: 115200 baud over USB Serial (connected to serial_bridge.py)
 * =====================================================================================
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

// -------------------------------------------------------------------------------------
// OLED Configuration (0.96" 128x64 I2C)
// -------------------------------------------------------------------------------------
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_RESET     -1  // Reset pin # (or -1 if sharing Arduino reset pin)

#define I2C_SDA_PIN    21  // ESP32 default hardware I2C SDA (D21)
#define I2C_SCL_PIN    22  // ESP32 default hardware I2C SCL (D22)

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool oledReady = false;
uint8_t detectedOledAddress = 0x3C;

// -------------------------------------------------------------------------------------
// GPIO Pin Assignments
// -------------------------------------------------------------------------------------
#define PIN_WHITE_LED  18  // GPIO 18 (D18) - Normal Guard / Standby Status
#define PIN_RED_LED    19  // GPIO 19 (D19) - Threat Alarm Strobe
#define PIN_BUZZER     23  // GPIO 23 (D23) - Warning Audio Siren

// -------------------------------------------------------------------------------------
// Operational States
// -------------------------------------------------------------------------------------
enum DefenseState {
  STATE_STANDBY,
  STATE_WARNING,
  STATE_CRITICAL
};

DefenseState currentState = STATE_STANDBY;
unsigned long lastThreatTime = 0;
const unsigned long ALARM_DURATION_MS = 9000; // Alarm active for 9s before auto-reset

String currentAttackerIp = "0.0.0.0";
String currentAttackType = "STANDBY";

// Strobe Timing Variables
unsigned long lastStrobeToggle = 0;
bool strobeState = false;

// Universal Buzzer Driver (supports both Active and Passive Piezo Buzzers)
void soundBuzzer(bool on) {
  if (on) {
    digitalWrite(PIN_BUZZER, HIGH);
    #if defined(ESP32)
    tone(PIN_BUZZER, 2400); // 2.4kHz tone for passive buzzers
    #endif
  } else {
    digitalWrite(PIN_BUZZER, LOW);
    #if defined(ESP32)
    noTone(PIN_BUZZER);
    #endif
  }
}

// -------------------------------------------------------------------------------------
// I2C Hardware Bus Scanner
// Scans all 127 addresses to verify physical connection and address of OLED module
// -------------------------------------------------------------------------------------
uint8_t scanI2CAddress() {
  Serial.println(F("\n========================================================"));
  Serial.println(F("[I2C SCANNER] Probing I2C bus on SDA=GPIO21, SCL=GPIO22..."));
  Serial.println(F("========================================================"));

  uint8_t foundAddress = 0;
  int count = 0;

  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();

    if (error == 0) {
      Serial.print(F("[I2C SCANNER] Found I2C device at address 0x"));
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);

      if (address == 0x3C || address == 0x3D) {
        Serial.println(F("  <-- MATCH: 0.96\" 128x64 OLED Display!"));
        foundAddress = address;
      } else {
        Serial.println(F("  <-- Other I2C Device"));
      }
      count++;
    } else if (error == 4) {
      Serial.print(F("[I2C ERROR] Unknown error at address 0x"));
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
    }
  }

  if (count == 0) {
    Serial.println(F("[I2C WARNING] NO I2C DEVICES FOUND ON BUS!"));
    Serial.println(F("[TROUBLESHOOTING CHECKLIST]:"));
    Serial.println(F("  1. Check VCC wire: Must be connected to ESP32 3V3 (or VIN/5V)."));
    Serial.println(F("  2. Check GND wire: Must be connected to ESP32 GND."));
    Serial.println(F("  3. Check SDA wire: Must be connected to GPIO 21 (D21)."));
    Serial.println(F("  4. Check SCL wire: Must be connected to GPIO 22 (D22)."));
    Serial.println(F("  5. Check OLED pinout order: Some boards are GND-VCC-SCL-SDA, others are VCC-GND-SCL-SDA."));
    Serial.println(F("========================================================\n"));
  } else {
    Serial.println(F("========================================================\n"));
  }

  return foundAddress;
}

// -------------------------------------------------------------------------------------
// Initialize OLED with charge pump overrides for maximum compatibility
// -------------------------------------------------------------------------------------
bool initOledDisplay(uint8_t addr) {
  // Try Adafruit begin
  if (!display.begin(SSD1306_SWITCHCAPVCC, addr, false, false)) {
    return false;
  }

  // Send hardware charge-pump & contrast activation commands:
  // SSD1306 internal charge pump on
  display.ssd1306_command(SSD1306_CHARGEPUMP);
  display.ssd1306_command(0x14);

  // SH1106 internal DC-DC converter fallback (harmless to SSD1306)
  display.ssd1306_command(0xAD);
  display.ssd1306_command(0x8B);

  // Set maximum contrast and turn display panel ON
  display.ssd1306_command(SSD1306_SETCONTRAST);
  display.ssd1306_command(0xFF);
  display.ssd1306_command(SSD1306_DISPLAYON);

  return true;
}

// -------------------------------------------------------------------------------------
// OLED Screens: Standby Guard & Threat Incident
// -------------------------------------------------------------------------------------
void drawStandbyScreen() {
  if (!oledReady) return;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Header Banner with line
  display.setTextSize(1);
  display.setCursor(8, 2);
  display.println(F("TRAPWIRE DEFENDER"));
  display.drawLine(0, 12, 127, 12, SSD1306_WHITE);

  // Status Details
  display.setCursor(4, 17);
  display.println(F("STATUS: ARMED & READY"));

  display.setCursor(4, 29);
  display.println(F("NODE: ESP32 DevKit V1"));

  display.setCursor(4, 41);
  display.println(F("HONEYPOT: ACTIVE GUARD"));

  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(14, 55);
  display.println(F("DPDP 2023 PROTECTED"));

  display.display();
}

void drawThreatScreen(const String& level, const String& ip, const String& msg) {
  if (!oledReady) return;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Inverted header for maximum visual alert
  display.fillRect(0, 0, 128, 14, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(6, 3);
  if (level == "critical" || level == "emergency") {
    display.println(F("! CRITICAL BREACH !"));
  } else {
    display.println(F("! SUSPICIOUS PROBE !"));
  }

  // Incident Details
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(2, 18);
  display.print(F("SRC: "));
  display.println(ip.length() > 0 ? ip : F("185.220.101.45"));

  display.setCursor(2, 30);
  display.print(F("VEC: "));
  String shortMsg = msg.substring(0, 14);
  display.println(shortMsg.length() > 0 ? shortMsg : F("EXPLOIT PROBE"));

  display.setCursor(2, 42);
  display.print(F("DECOY: QUARANTINED"));

  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(4, 55);
  display.println(F("DPB STATUTORY: FILED"));

  display.display();
}

// -------------------------------------------------------------------------------------
// Setup Routine
// -------------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);

  // Configure GPIO Pins
  pinMode(PIN_WHITE_LED, OUTPUT);
  pinMode(PIN_RED_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Initial state: LEDs OFF, Buzzer OFF
  digitalWrite(PIN_WHITE_LED, LOW);
  digitalWrite(PIN_RED_LED, LOW);
  soundBuzzer(false);

  // Configure ESP32 I2C pins with internal pull-ups enabled
  pinMode(I2C_SDA_PIN, INPUT_PULLUP);
  pinMode(I2C_SCL_PIN, INPUT_PULLUP);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(100000); // 100 kHz standard mode for maximum noise tolerance
  delay(100);

  // 1. Run I2C Hardware Bus Scan
  uint8_t oledAddr = scanI2CAddress();
  if (oledAddr != 0) {
    detectedOledAddress = oledAddr;
  }

  // 2. Initialize OLED Display (tries detected address, then 0x3C, then 0x3D)
  if (initOledDisplay(detectedOledAddress)) {
    oledReady = true;
    Serial.print(F("[+] OLED initialized successfully at address 0x"));
    Serial.println(detectedOledAddress, HEX);
  } else if (initOledDisplay(0x3C)) {
    oledReady = true;
    detectedOledAddress = 0x3C;
    Serial.println(F("[+] OLED initialized successfully at fallback address 0x3C."));
  } else if (initOledDisplay(0x3D)) {
    oledReady = true;
    detectedOledAddress = 0x3D;
    Serial.println(F("[+] OLED initialized successfully at fallback address 0x3D."));
  } else {
    oledReady = false;
    Serial.println(F("[-] OLED display allocation failed. The system will continue with LEDs & buzzer."));
  }

  // =========================================================================
  // HARDWARE POWER-ON SELF-TEST DIAGNOSTIC (Verifies OLED, LEDs & Buzzer)
  // =========================================================================
  if (oledReady) {
    display.clearDisplay();
    display.drawRect(0, 0, 128, 64, SSD1306_WHITE); // Outer test border
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(14, 10);
    display.println(F("TRAPWIRE DEFENSE"));
    display.setCursor(16, 24);
    display.println(F("0.96\" OLED: OK!"));
    display.setCursor(16, 36);
    display.print(F("I2C ADDR: 0x"));
    display.println(detectedOledAddress, HEX);
    display.setCursor(14, 48);
    display.println(F("HARDWARE ARMED"));
    display.display();
  }

  // Step 1: Light White LED
  digitalWrite(PIN_WHITE_LED, HIGH);
  delay(350);

  // Step 2: Light Red LED & chirp buzzer
  digitalWrite(PIN_RED_LED, HIGH);
  soundBuzzer(true);
  delay(150);
  soundBuzzer(false);
  digitalWrite(PIN_RED_LED, LOW);
  delay(500);

  // Settle into Standby Guard State
  digitalWrite(PIN_WHITE_LED, HIGH);
  digitalWrite(PIN_RED_LED, LOW);
  soundBuzzer(false);

  drawStandbyScreen();

  Serial.print(F("{\"node\":\"ESP32-DEVKIT-V1\",\"status\":\"ARMED\",\"baud\":115200,\"oled\":"));
  Serial.print(oledReady ? F("\"CONNECTED\"") : F("\"DISCONNECTED\""));
  Serial.print(F(",\"i2c_addr\":\"0x"));
  Serial.print(detectedOledAddress, HEX);
  Serial.println(F("\"}"));
}

// -------------------------------------------------------------------------------------
// JSON Threat Stream Parser
// -------------------------------------------------------------------------------------
void processIncomingThreatJson(const String& jsonStr) {
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, jsonStr);
  if (err) {
    return;
  }

  const char* levelStr = doc["level"] | "info";
  const char* messageStr = doc["message"] | "Threat event detected";
  const char* ipStr = doc["attacker_ip"] | "185.220.101.45";

  String lvl = String(levelStr);
  lvl.toLowerCase();

  if (lvl == "critical" || lvl == "emergency") {
    currentState = STATE_CRITICAL;
    lastThreatTime = millis();
    currentAttackerIp = String(ipStr);
    currentAttackType = String(messageStr);
    drawThreatScreen("critical", currentAttackerIp, currentAttackType);
  } else if (lvl == "warning") {
    currentState = STATE_WARNING;
    lastThreatTime = millis();
    currentAttackerIp = String(ipStr);
    currentAttackType = String(messageStr);
    drawThreatScreen("warning", currentAttackerIp, currentAttackType);
  }
}

// -------------------------------------------------------------------------------------
// Main Loop
// -------------------------------------------------------------------------------------
void loop() {
  // 1. Process USB Serial commands from serial_bridge.py
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      processIncomingThreatJson(line);
    }
  }

  // 2. Hardware Alarm State Machine
  unsigned long now = millis();

  if (currentState == STATE_CRITICAL) {
    // White Guard LED OFF during active breach
    digitalWrite(PIN_WHITE_LED, LOW);

    // Fast Red Strobe (120ms cycle) & Audio Siren
    if (now - lastStrobeToggle > 120) {
      lastStrobeToggle = now;
      strobeState = !strobeState;
      digitalWrite(PIN_RED_LED, strobeState ? HIGH : LOW);
      soundBuzzer(strobeState);
    }

    // Auto-Reset back to Standby after alarm timeout
    if (now - lastThreatTime > ALARM_DURATION_MS) {
      currentState = STATE_STANDBY;
      digitalWrite(PIN_RED_LED, LOW);
      soundBuzzer(false);
      digitalWrite(PIN_WHITE_LED, HIGH); // Restore White Guard LED
      drawStandbyScreen();
      Serial.println(F("{\"event\":\"AUTO_RESET\",\"status\":\"STANDBY\"}"));
    }
  } 
  else if (currentState == STATE_WARNING) {
    // Warning Probe: Slower pulse (300ms cycle)
    digitalWrite(PIN_WHITE_LED, LOW);

    if (now - lastStrobeToggle > 300) {
      lastStrobeToggle = now;
      strobeState = !strobeState;
      digitalWrite(PIN_RED_LED, strobeState ? HIGH : LOW);
      soundBuzzer(strobeState);
    }

    if (now - lastThreatTime > (ALARM_DURATION_MS / 2)) {
      currentState = STATE_STANDBY;
      digitalWrite(PIN_RED_LED, LOW);
      soundBuzzer(false);
      digitalWrite(PIN_WHITE_LED, HIGH);
      drawStandbyScreen();
    }
  } 
  else {
    // Standby Mode: White LED solid ON, Red LED OFF, Buzzer OFF
    digitalWrite(PIN_WHITE_LED, HIGH);
    digitalWrite(PIN_RED_LED, LOW);
    soundBuzzer(false);
  }
}
