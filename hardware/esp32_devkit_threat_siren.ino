/*
 * =====================================================================================
 * TRAPWIRE — ESP32 DevKit V1 Physical Threat Siren & SOC Defense Node
 * =====================================================================================
 * Target Board:
 *   ESP32 Development Board (ESP32 DevKit V1 with Wi-Fi & Bluetooth, 30-pin / 36-pin)
 *
 * Connected Components:
 *   1. 0.96" I2C OLED Display (SSD1306, 128x64, Auto-detects 0x3C / 0x3D)
 *   2. White LED (Normal Operation / System Armed & Guarding)
 *   3. Red LED (Breach Alarm Strobe / Active Attack In Progress)
 *   4. Active or Passive Buzzer (Tactical Audio Warning Siren)
 *
 * Pin Connections on ESP32 DevKit V1:
 *   - OLED VCC         -> 3V3 pin on ESP32
 *   - OLED GND         -> GND pin on ESP32
 *   - OLED SDA         -> GPIO 21 (Pin D21)
 *   - OLED SCL         -> GPIO 22 (Pin D22)
 *   - White LED (+)    -> GPIO 18 (Pin D18) via 220Ω-330Ω resistor
 *   - White LED (-)    -> GND pin on ESP32
 *   - Red LED (+)      -> GPIO 19 (Pin D19) via 220Ω-330Ω resistor
 *   - Red LED (-)      -> GND pin on ESP32
 *   - Buzzer (+)       -> GPIO 23 (Pin D23)
 *   - Buzzer (-)       -> GND pin on ESP32
 *
 * Required Arduino Libraries (Install via Arduino IDE Library Manager):
 *   1. "Adafruit SSD1306" by Adafruit
 *   2. "Adafruit GFX Library" by Adafruit
 *   3. "ArduinoJson" (v6 or v7) by Benoit Blanchon
 *
 * Communication:
 *   Receives JSON threat telemetry at 115200 baud over USB Serial from serial_bridge.py
 * =====================================================================================
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

// OLED Configuration (128x64 I2C)
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool oledReady = false;

// ESP32 DevKit V1 Pin Assignments
#define PIN_WHITE_LED  18  // GPIO 18 (D18) - Normal Guard / Standby Status
#define PIN_RED_LED    19  // GPIO 19 (D19) - Threat Alarm Strobe
#define PIN_BUZZER     23  // GPIO 23 (D23) - Piezo Warning Siren

// Operational States
enum DefenseState {
  STATE_STANDBY,
  STATE_WARNING,
  STATE_CRITICAL
};

DefenseState currentState = STATE_STANDBY;
unsigned long lastThreatTime = 0;
const unsigned long ALARM_DURATION_MS = 9000; // Alarm active for 9 seconds before auto-reset

String currentAttackerIp = "0.0.0.0";
String currentAttackType = "STANDBY";

// Strobe Timing Variables
unsigned long lastStrobeToggle = 0;
bool strobeState = false;

// Universal Buzzer Driver (Supports both Active & Passive Piezo Buzzers)
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

void drawStandbyScreen() {
  if (!oledReady) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Header Banner
  display.setTextSize(1);
  display.setCursor(8, 2);
  display.println("TRAPWIRE DEFENDER");
  display.drawLine(0, 12, 127, 12, SSD1306_WHITE);

  // Body
  display.setCursor(4, 18);
  display.println("STATUS: ARMED & READY");
  
  display.setCursor(4, 30);
  display.println("NODE: ESP32 DevKit V1");

  display.setCursor(4, 42);
  display.println("HONEYPOT: DECEPTION ON");

  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(14, 55);
  display.println("GUARD: ACTIVE & SECURE");

  display.display();
}

void drawThreatScreen(const String& level, const String& ip, const String& msg) {
  if (!oledReady) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Inverted header for visual impact
  display.fillRect(0, 0, 128, 14, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(6, 3);
  if (level == "critical") {
    display.println("! CRITICAL BREACH !");
  } else {
    display.println("! SUSPICIOUS PROBE !");
  }

  // Details
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(2, 18);
  display.print("SRC IP: ");
  display.println(ip.length() > 0 ? ip : "185.220.101.45");

  display.setCursor(2, 30);
  display.print("VECTOR: ");
  String shortMsg = msg.substring(0, 14);
  display.println(shortMsg.length() > 0 ? shortMsg : "EXPLOIT");

  display.setCursor(2, 42);
  display.print("DECOY: QUARANTINED");

  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(4, 55);
  display.println("DPDP BOARD: NOTIFIED");

  display.display();
}

void setup() {
  // Start USB Serial communication
  Serial.begin(115200);
  delay(250);

  // Configure GPIO Pins
  pinMode(PIN_WHITE_LED, OUTPUT);
  pinMode(PIN_RED_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Turn everything off initially
  digitalWrite(PIN_WHITE_LED, LOW);
  digitalWrite(PIN_RED_LED, LOW);
  soundBuzzer(false);

  // Initialize standard ESP32 I2C bus (SDA=GPIO21, SCL=GPIO22)
  Wire.begin(21, 22);

  // Auto-probe OLED address (0x3C default, 0x3D fallback)
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oledReady = true;
  } else if (display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
    oledReady = true;
  } else {
    Serial.println(F("[WARN] OLED not detected at 0x3C or 0x3D. (Check D21/D22 wires). LEDs and buzzer will still work."));
  }

  // =========================================================================
  // HARDWARE POWER-ON SELF-TEST DIAGNOSTIC (Verifies wiring immediately!)
  // =========================================================================
  if (oledReady) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(14, 12);
    display.println("TRAPWIRE DEFENSE");
    display.setCursor(10, 28);
    display.println("DIAGNOSTIC SELF-TEST");
    display.setCursor(14, 46);
    display.println("TESTING HARDWARE...");
    display.display();
  }

  // 1. Light White LED
  digitalWrite(PIN_WHITE_LED, HIGH);
  delay(300);

  // 2. Light Red LED & Chirp Buzzer
  digitalWrite(PIN_RED_LED, HIGH);
  soundBuzzer(true);
  delay(180);
  soundBuzzer(false);
  digitalWrite(PIN_RED_LED, LOW);
  delay(200);

  // Settle into Standby Guard State: White LED ON, Red LED OFF, Buzzer OFF
  digitalWrite(PIN_WHITE_LED, HIGH);
  digitalWrite(PIN_RED_LED, LOW);
  soundBuzzer(false);

  drawStandbyScreen();
  Serial.println(F("{\"node\":\"ESP32-DEVKIT-V1\",\"status\":\"ARMED\",\"baud\":115200,\"self_test\":\"PASS\"}"));
}

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

void loop() {
  // 1. Process Real-Time JSON Telemetry from serial_bridge.py
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
    // Normal White LED OFF during active breach
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
