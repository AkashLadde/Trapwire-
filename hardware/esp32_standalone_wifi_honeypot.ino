/*
 * =====================================================================================
 * TRAPWIRE — ESP32 Standalone Wi-Fi Honeypot Bait Sensor & Threat Siren
 * (Raspberry Pi Alternative — Runs 100% on ESP32 Microcontroller)
 * =====================================================================================
 * Features on a Single ₹400 ESP32:
 *  1. Standalone Wi-Fi Honeypot Sockets: Listens on Decoy SSH (2222), Telnet (23), and SCADA (502).
 *  2. Real-Time Telemetry: Dispatches HTTP POST threat alerts to TrapWire Server (/api/hardware/telemetry).
 *  3. SSD1306 0.96" I2C OLED Display: Shows live Attacker IP, Port hit, and Incident ID.
 *  4. WS2812B NeoPixel RGB Strobe: Flashes Crimson Red during active intrusion.
 *  5. Active Piezo Buzzer: Emits audible tactical warning sirens on attack triggers.
 *
 * Pin Connections (ESP32 Dev Module):
 *  - OLED SDA      -> GPIO 21
 *  - OLED SCL      -> GPIO 22
 *  - NeoPixel Data -> GPIO 18
 *  - Active Buzzer -> GPIO 19
 *  - VCC / GND     -> 3.3V / GND (or 5V / VIN for NeoPixel)
 * =====================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

// ------------------------------------------------------------- Configuration
const char* WIFI_SSID     = "YOUR_WIFI_SSID";       // Enter your Wi-Fi Name
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";   // Enter your Wi-Fi Password
const char* TRAPWIRE_HOST = "http://192.168.1.100:8000"; // Replace with your PC/Server IP

const char* NODE_ID       = "ESP32-EDGE-SENSOR-01";
const char* LOCATION      = "Physical Network Node (Office/Lab)";

// ------------------------------------------------------------- Hardware Pins
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

#define PIN_NEOPIXEL 18
#define NUM_PIXELS   8
Adafruit_NeoPixel strip(NUM_PIXELS, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

#define PIN_BUZZER   19

// Decoy Bait TCP Servers
WiFiServer sshBaitServer(2222);
WiFiServer telnetBaitServer(23);
WiFiServer modbusBaitServer(502);

// State Tracker
enum ThreatState { STANDBY, INTRUSION_DETECTED };
ThreatState currentState = STANDBY;
String lastAttackerIp = "None";
int lastAttackerPort = 0;
String lastServiceHit = "None";
unsigned long lastAlarmTime = 0;
unsigned long lastHeartbeatTime = 0;

void setStrobe(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < NUM_PIXELS; i++) {
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();
}

void renderOled(const char* header, const char* line1, const char* line2, const char* line3) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 2);
  display.println(header);
  display.drawLine(0, 12, 128, 12, SSD1306_WHITE);
  
  display.setCursor(0, 18);
  display.println(line1);
  display.setCursor(0, 32);
  display.println(line2);
  display.setCursor(0, 48);
  display.println(line3);
  display.display();
}

void triggerPhysicalAlarm(const char* attackerIp, int port, const char* service) {
  currentState = INTRUSION_DETECTED;
  lastAlarmTime = millis();
  lastAttackerIp = attackerIp;
  lastAttackerPort = port;
  lastServiceHit = service;

  char l1[32], l2[32], l3[32];
  snprintf(l1, sizeof(l1), "ATTACKER: %s", attackerIp);
  snprintf(l2, sizeof(l2), "SERVICE : %s (%d)", service, port);
  snprintf(l3, sizeof(l3), "STATUS  : ALERT DISPATCH");
  renderOled("! INTRUSION DETECTED !", l1, l2, l3);

  // Send HTTP Telemetry to TrapWire Server
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = String(TRAPWIRE_HOST) + "/api/hardware/telemetry";
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["node_id"] = NODE_ID;
    doc["location"] = LOCATION;
    doc["service"] = service;
    doc["port"] = port;
    doc["attacker_ip"] = attackerIp;
    doc["raw_payload"] = "PORT_SCAN_TCP_PROBE";
    doc["level"] = "critical";

    String requestBody;
    serializeJson(doc, requestBody);
    int httpCode = http.POST(requestBody);
    Serial.printf("[TELEMETRY DISPATCH] HTTP Code: %d\n", httpCode);
    http.end();
  }
}

void checkBaitSockets() {
  // Check SSH Bait (Port 2222)
  WiFiClient sshClient = sshBaitServer.available();
  if (sshClient) {
    String clientIp = sshClient.remoteIP().toString();
    Serial.printf("[HONEYPOT HIT] SSH Probe from %s on port 2222\n", clientIp.c_str());
    sshClient.println("SSH-2.0-OpenSSH_8.4p1 TrapWire-Bait-Node\r\n");
    delay(100);
    sshClient.stop();
    triggerPhysicalAlarm(clientIp.c_str(), 2222, "SSH-Decoy");
  }

  // Check Telnet Bait (Port 23)
  WiFiClient telnetClient = telnetBaitServer.available();
  if (telnetClient) {
    String clientIp = telnetClient.remoteIP().toString();
    Serial.printf("[HONEYPOT HIT] Telnet Probe from %s on port 23\n", clientIp.c_str());
    telnetClient.println("TrapWire Embedded Terminal v2.4\r\nLogin: ");
    delay(100);
    telnetClient.stop();
    triggerPhysicalAlarm(clientIp.c_str(), 23, "Telnet-Decoy");
  }

  // Check Modbus SCADA Bait (Port 502)
  WiFiClient modbusClient = modbusBaitServer.available();
  if (modbusClient) {
    String clientIp = modbusClient.remoteIP().toString();
    Serial.printf("[HONEYPOT HIT] SCADA Probe from %s on port 502\n", clientIp.c_str());
    modbusClient.println("MODBUS-TCP-EMULATOR\r\n");
    delay(100);
    modbusClient.stop();
    triggerPhysicalAlarm(clientIp.c_str(), 502, "Modbus-SCADA");
  }
}

void sendHeartbeat() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = String(TRAPWIRE_HOST) + "/api/hardware/heartbeat";
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["node_id"] = NODE_ID;
    doc["hostname"] = "esp32-sensor-node";
    doc["status"] = "ONLINE";
    doc["ip"] = WiFi.localIP().toString();
    doc["services"][0] = "Bait-SSH:2222";
    doc["services"][1] = "Bait-Telnet:23";
    doc["services"][2] = "Bait-Modbus:502";

    String requestBody;
    serializeJson(doc, requestBody);
    http.POST(requestBody);
    http.end();
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  strip.begin();
  strip.setBrightness(120);
  setStrobe(0, 180, 255); // Cyan Boot

  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    renderOled("TRAPWIRE DEFENDER", "CONNECTING TO WI-FI...", "INITIALIZING SENSORS", "STANDBY");
  }

  // Connect to Wi-Fi
  Serial.print("[WIFI] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected! IP: " + WiFi.localIP().toString());
    char ipLine[32];
    snprintf(ipLine, sizeof(ipLine), "IP: %s", WiFi.localIP().toString().c_str());
    renderOled("TRAPWIRE HONEYPOT", "STATUS: ARMED & READY", ipLine, "PORTS: 2222, 23, 502");
  } else {
    Serial.println("\n[WIFI] Running in offline AP mode / USB mode.");
    renderOled("TRAPWIRE DEFENDER", "WI-FI NOT DETECTED", "USB SERIAL ACTIVE", "STANDBY");
  }

  // Start Bait Servers
  sshBaitServer.begin();
  telnetBaitServer.begin();
  modbusBaitServer.begin();

  setStrobe(0, 150, 255); // Cyan Standby
}

void loop() {
  // 1. Listen for network probes
  checkBaitSockets();

  // 2. Alarm Strobe and Buzzer Management
  if (currentState == INTRUSION_DETECTED) {
    unsigned long elapsed = millis() - lastAlarmTime;
    if (elapsed < 12000) { // Alarm active for 12 seconds
      if ((elapsed / 180) % 2 == 0) {
        setStrobe(255, 0, 0); // Flashing Crimson Red
        digitalWrite(PIN_BUZZER, HIGH);
      } else {
        setStrobe(0, 0, 0);
        digitalWrite(PIN_BUZZER, LOW);
      }
    } else {
      // Return to Standby
      currentState = STANDBY;
      digitalWrite(PIN_BUZZER, LOW);
      setStrobe(0, 150, 255); // Cyan
      char ipLine[32];
      snprintf(ipLine, sizeof(ipLine), "IP: %s", WiFi.localIP().toString().c_str());
      renderOled("TRAPWIRE HONEYPOT", "STATUS: ARMED & READY", ipLine, "PORTS: 2222, 23, 502");
    }
  }

  // 3. Periodic Heartbeat every 15s
  if (millis() - lastHeartbeatTime > 15000) {
    lastHeartbeatTime = millis();
    sendHeartbeat();
  }

  delay(10);
}
