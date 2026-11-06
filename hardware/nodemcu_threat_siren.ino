/*
 * =====================================================================================
 * TRAPWIRE — NodeMCU (ESP8266) Physical Threat Siren & SOC Hardware Defense Node
 * =====================================================================================
 * Hardware Components:
 *   1. NodeMCU ESP8266 Dev Board (ESP-12E / LoLin / Amica)
 *   2. 0.96" I2C OLED Display (SSD1306, 128x64, Address 0x3C)
 *   3. White LED (Normal Operation / Heartbeat Guard)
 *   4. Red LED (Breach Strobe / Attack Alarm)
 *   5. Active Piezo Buzzer (Audio Alert Siren)
 *
 * Pin Connections on NodeMCU:
 *   - OLED SDA         -> Pin D2 (GPIO 4)
 *   - OLED SCL         -> Pin D1 (GPIO 5)
 *   - OLED VCC         -> Pin 3V3 (or VIN)
 *   - OLED GND         -> Pin GND
 *   - White LED (+)    -> Pin D5 (GPIO 14) via 220-330 ohm resistor
 *   - White LED (-)    -> Pin GND
 *   - Red LED (+)      -> Pin D6 (GPIO 12) via 220-330 ohm resistor
 *   - Red LED (-)      -> Pin GND
 *   - Buzzer (+)       -> Pin D7 (GPIO 13)
 *   - Buzzer (-)       -> Pin GND
 *
 * Required Arduino Libraries (Install via Arduino IDE Library Manager):
 *   1. "Adafruit SSD1306" by Adafruit
 *   2. "Adafruit GFX Library" by Adafruit
 *   3. "ArduinoJson" (v6 or v7) by Benoit Blanchon
 *
 * Communication:
 *   Receives JSON threat packets over USB Serial at 115200 baud from serial_bridge.py
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

// NodeMCU Pin Mapping
#define PIN_WHITE_LED  14  // NodeMCU Pin D5 (GPIO 14) - Standby / Normal Guard
#define PIN_RED_LED    12  // NodeMCU Pin D6 (GPIO 12) - Threat Strobe
#define PIN_BUZZER     13  // NodeMCU Pin D7 (GPIO 13) - Audio Alarm

// Buzzer Polarity Configuration:
// Set to false for standard buzzers and active-HIGH modules; set to true if buzzer sounds on LOW.
#define BUZZER_ACTIVE_LOW  false
#define BUZZER_ON_LEVEL    (BUZZER_ACTIVE_LOW ? LOW : HIGH)
#define BUZZER_OFF_LEVEL   (BUZZER_ACTIVE_LOW ? HIGH : LOW)

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
String currentDpbAck = "NONE";

// Non-Blocking Timing Variables
unsigned long lastWhiteBlinkToggle = 0;
bool whiteLedState = false;

unsigned long lastRedBlinkToggle = 0;
bool redLedState = false;

unsigned long lastSirenToggle = 0;
bool sirenToneHigh = false;

void silenceBuzzer() {
  noTone(PIN_BUZZER);
  digitalWrite(PIN_BUZZER, BUZZER_OFF_LEVEL);
}

void playPoliceSiren(unsigned long now) {
  if (now - lastSirenToggle >= 250) {
    lastSirenToggle = now;
    sirenToneHigh = !sirenToneHigh;
    if (sirenToneHigh) {
      tone(PIN_BUZZER, 960);
    } else {
      tone(PIN_BUZZER, 650);
    }
  }
}

void drawStandbyScreen() {
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
  display.println("NODE: NodeMCU ESP8266");

  display.setCursor(4, 42);
  display.println("HONEYPOT: ISOLATED");

  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(18, 55);
  display.println("SYSTEM GUARD: ACTIVE");

  display.display();
}

void drawThreatScreen(const String& level, const String& ip, const String& msg) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Inverted header for alarm impact
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
  display.print("ACTION: HONEYPOT DECOY");

  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(4, 55);
  display.println("DPDP BOARD: NOTIFIED");

  display.display();
}

void setup() {
  // Start Serial for host PC / serial_bridge.py communication
  Serial.begin(115200);
  delay(200);

  // Initialize GPIO Pins
  pinMode(PIN_WHITE_LED, OUTPUT);
  pinMode(PIN_RED_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Initial Pin States: Everything strictly OFF initially
  digitalWrite(PIN_WHITE_LED, LOW);
  digitalWrite(PIN_RED_LED, LOW);
  silenceBuzzer();

  // Initialize I2C for NodeMCU (SDA=D2/GPIO4, SCL=D1/GPIO5)
  Wire.begin(4, 5);

  // Initialize OLED (0x3C is standard SSD1306 address)
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("[ERROR] SSD1306 OLED allocation failed. Check D1/D2 wiring."));
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(14, 15);
    display.println("TRAPWIRE DEFENSE");
    display.setCursor(10, 30);
    display.println("INITIALIZING NODE...");
    display.display();
    delay(500);
  }

  drawStandbyScreen();
  Serial.println(F("{\"node\":\"NodeMCU-ESP8266\",\"status\":\"READY\",\"baud\":115200}"));
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
  unsigned long now = millis();

  // 1. Read JSON Commands / Manual Test Commands from USB Serial
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      if (line.equalsIgnoreCase("attack") || line.equalsIgnoreCase("test") || line.equalsIgnoreCase("siren")) {
        currentState = STATE_CRITICAL;
        lastThreatTime = now;
        currentAttackerIp = "192.168.1.105";
        currentAttackType = "TEST POLICE SIREN";
        drawThreatScreen("critical", currentAttackerIp, currentAttackType);
      } else if (line.equalsIgnoreCase("reset") || line.equalsIgnoreCase("standby") || line.equalsIgnoreCase("stop")) {
        currentState = STATE_STANDBY;
        digitalWrite(PIN_RED_LED, LOW);
        silenceBuzzer();
        drawStandbyScreen();
      } else {
        processIncomingThreatJson(line);
      }
    }
  }

  // 2. Hardware Alarm State Machine
  if (currentState == STATE_CRITICAL || currentState == STATE_WARNING) {
    // Attack Mode: White LED strictly OFF
    digitalWrite(PIN_WHITE_LED, LOW);

    // Red LED fast emergency strobe (120ms)
    if (now - lastRedBlinkToggle >= 120) {
      lastRedBlinkToggle = now;
      redLedState = !redLedState;
      digitalWrite(PIN_RED_LED, redLedState ? HIGH : LOW);
    }

    // Play Police Siren
    playPoliceSiren(now);

    // Auto-Reset back to Standby after alarm duration expires
    if (now - lastThreatTime > ALARM_DURATION_MS) {
      currentState = STATE_STANDBY;
      digitalWrite(PIN_RED_LED, LOW);
      silenceBuzzer();
      drawStandbyScreen();
      Serial.println(F("{\"event\":\"AUTO_RESET\",\"status\":\"STANDBY\"}"));
    }
  } 
  else {
    // Normal Standby Mode: Red LED strictly OFF, Buzzer strictly silent
    digitalWrite(PIN_RED_LED, LOW);
    silenceBuzzer();

    // White LED rhythmic blink (500ms ON / 500ms OFF)
    if (now - lastWhiteBlinkToggle >= 500) {
      lastWhiteBlinkToggle = now;
      whiteLedState = !whiteLedState;
      digitalWrite(PIN_WHITE_LED, whiteLedState ? HIGH : LOW);
    }
  }
}

