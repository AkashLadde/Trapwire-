/*
 * =====================================================================================
 * TRAPWIRE — Physical Threat Siren & SOC Strobe Alarm (ESP32 / Arduino Sketch)
 * =====================================================================================
 * Hardware Features:
 *  1. SSD1306 128x64 I2C OLED Display: Renders live incident title, attacker IP, and time.
 *  2. WS2812B NeoPixel RGB LED: Red flashing strobe on CRITICAL intrusion, Amber on PROBE.
 *  3. Active Piezo Buzzer: Audio alert chirp when attacker engages honeypot or canaries.
 *  4. Serial USB Interface: Receives JSON threat events from TrapWire backend serial_bridge.py
 *
 * Pin Connections (ESP32):
 *  - OLED SDA   -> GPIO 21
 *  - OLED SCL   -> GPIO 22
 *  - NeoPixel   -> GPIO 18
 *  - Buzzer (+) -> GPIO 19
 *  - VCC / GND  -> 3.3V / GND
 * =====================================================================================
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

#define PIN_NEOPIXEL 18
#define NUM_PIXELS   8
Adafruit_NeoPixel strip(NUM_PIXELS, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

#define PIN_BUZZER   19

// Threat State
enum ThreatLevel { NORMAL, WARNING, CRITICAL };
ThreatLevel currentThreat = NORMAL;
String lastAlertMsg = "SYSTEM SECURE";
String lastAttackerIp = "0.0.0.0";
unsigned long lastAlarmTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Initialize NeoPixels
  strip.begin();
  strip.setBrightness(120);
  setStrobeColor(0, 150, 255); // Standby Cyan

  // Initialize OLED
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(10, 10);
    display.println("TRAPWIRE DEFENDER");
    display.setCursor(10, 25);
    display.println("HARDWARE NODE v2.4");
    display.setCursor(10, 45);
    display.println("STATUS: STANDBY");
    display.display();
  }

  Serial.println("{\"node_id\": \"ESP32-THREAT-SIREN\", \"status\": \"READY\", \"firmware\": \"2.4.0\"}");
}

void loop() {
  // Check incoming serial threat packets from serial_bridge.py
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      parseThreatPacket(input);
    }
  }

  // Handle Threat Strobe & Sound
  if (currentThreat == CRITICAL) {
    // Red Flashing Strobe + Siren Pulsing
    unsigned long now = millis();
    if ((now / 200) % 2 == 0) {
      setStrobeColor(255, 0, 0); // Bright Red
      digitalWrite(PIN_BUZZER, HIGH);
    } else {
      setStrobeColor(0, 0, 0);
      digitalWrite(PIN_BUZZER, LOW);
    }
    
    // Auto-cooldown to Warning after 15 seconds if no new critical alert
    if (now - lastAlarmTime > 15000) {
      currentThreat = WARNING;
      digitalWrite(PIN_BUZZER, LOW);
      setStrobeColor(255, 120, 0); // Amber
      renderOled();
    }
  } else if (currentThreat == WARNING) {
    setStrobeColor(255, 140, 0); // Amber
    digitalWrite(PIN_BUZZER, LOW);
  } else {
    // Normal / Secure
    setStrobeColor(0, 180, 255); // Cyber Cyan
    digitalWrite(PIN_BUZZER, LOW);
  }
  
  delay(50);
}

void parseThreatPacket(String jsonStr) {
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, jsonStr);

  if (err) {
    // Fallback if plain text command received
    if (jsonStr.startsWith("ALARM:CRITICAL")) {
      currentThreat = CRITICAL;
      lastAlertMsg = "CRITICAL INTRUSION";
      lastAlarmTime = millis();
      renderOled();
    } else if (jsonStr.startsWith("ALARM:CLEAR")) {
      currentThreat = NORMAL;
      lastAlertMsg = "SYSTEM SECURE";
      renderOled();
    }
    return;
  }

  const char* level = doc["level"] | "info";
  const char* msg   = doc["message"] | "Threat event";
  const char* ip    = doc["attacker_ip"] | "127.0.0.1";

  lastAlertMsg = String(msg);
  lastAttackerIp = String(ip);
  lastAlarmTime = millis();

  if (strcmp(level, "critical") == 0 || strcmp(level, "emergency") == 0) {
    currentThreat = CRITICAL;
    soundAlarmChirp();
  } else if (strcmp(level, "warning") == 0) {
    currentThreat = WARNING;
  } else {
    currentThreat = NORMAL;
  }

  renderOled();
}

void renderOled() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // Header
  display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
  display.setCursor(4, 2);
  if (currentThreat == CRITICAL) {
    display.print("! TRAPWIRE BREACH !");
  } else if (currentThreat == WARNING) {
    display.print("TRAPWIRE THREAT WATCH");
  } else {
    display.print("TRAPWIRE SOC MON");
  }

  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 16);
  display.print("STATUS: ");
  if (currentThreat == CRITICAL) display.println("CRITICAL INTRUSION");
  else if (currentThreat == WARNING) display.println("PROBE / RECON");
  else display.println("SECURE / ARMED");

  display.setCursor(0, 28);
  display.print("IP: ");
  display.println(lastAttackerIp);

  display.setCursor(0, 40);
  display.println(lastAlertMsg.substring(0, 21));
  display.setCursor(0, 50);
  if (lastAlertMsg.length() > 21) {
    display.println(lastAlertMsg.substring(21, 42));
  }

  display.display();
}

void setStrobeColor(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < NUM_PIXELS; i++) {
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();
}

void soundAlarmChirp() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(80);
    digitalWrite(PIN_BUZZER, LOW);
    delay(40);
  }
}
