/*
 * ============================================================================
 *  TRAPWIRE - ESP32 Physical Threat Alert Node            firmware v1.0
 * ============================================================================
 *  Educational cybersecurity capstone peripheral. When the TRAPWIRE server
 *  detects an attack it sends ONE text line to this board (USB serial at
 *  115200 baud, or Wi-Fi). The board then drives local indicators only:
 *
 *    RED LED   fast-blinks while the siren sounds, then stays ON (latched)
 *              until someone presses the BOOT button or clicks "Silence"
 *              on the SOC dashboard.
 *    BUZZER    15 s siren pattern for critical attacks, 2 short beeps for a
 *              warning/probe, 1 beep when a DPB breach report is filed.
 *    OLED      attacker details: attack type, IP, location, ISP, incident
 *              ID, time, attack counter, DPB acknowledgement number.
 *              Two pages rotate every 3 s.
 *    GREEN LED (optional) ON = armed and idle.
 *
 *  BOOT button (GPIO 0, already on the board):
 *    short press -> silence alarm + clear screen (server is told: ACK)
 *    long press  -> mute / unmute buzzer (LED + OLED keep working)
 *
 *  This firmware never touches a network target; it only lights LEDs, drives
 *  a buzzer, and prints received text to a display. Libraries:
 *    "Adafruit SSD1306" by Adafruit (pulls in "Adafruit GFX").
 *  Board: "ESP32 Dev Module". Wiring: see hardware/README.md
 * ============================================================================
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ----------------------------------------------------------------- options --
#define ENABLE_WIFI      0      // 1 = also accept alerts over Wi-Fi (see README)
#define BUZZER_PASSIVE   0      // 0 = ACTIVE buzzer (beeps on HIGH), 1 = PASSIVE piezo (tone())
#define BUZZER_ON_LEVEL  HIGH   // some 3-pin active buzzers are active-LOW -> set LOW
#define RELAY_ON_LEVEL   HIGH   // relay for an optional 12 V strobe

#if ENABLE_WIFI
  #include <WiFi.h>
  #include <WebServer.h>
  const char* WIFI_SSID = "YOUR_WIFI_NAME";
  const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
  WebServer http(80);
#endif

// -------------------------------------------------------------------- pins --
const int PIN_LED_RED   = 25;
const int PIN_LED_GREEN = 27;   // set to -1 if you don't fit a green LED
const int PIN_BUZZER    = 26;
const int PIN_RELAY     = 33;   // set to -1 if no strobe relay
const int PIN_BUTTON    = 0;    // on-board BOOT button
const int OLED_SDA      = 21;
const int OLED_SCL      = 22;
const uint8_t OLED_ADDR = 0x3C; // some modules are 0x3D

// ------------------------------------------------------------------ timing --
const unsigned long SIREN_MS      = 15000;  // keep equal to SIREN_SECONDS in app/hardware.py
const unsigned long TEST_SIREN_MS = 3000;
const unsigned long HOLD_MS       = 10000;  // warning/report screen time
const unsigned long PAGE_MS       = 3000;   // OLED page rotation
const unsigned long LONG_PRESS_MS = 1500;
const char* FW_VERSION = "1.0";

Adafruit_SSD1306 display(128, 64, &Wire, -1);
bool oledOk = false;

struct Alert {
  bool valid = false;
  char sev = 'C';   // C critical, W warning, R report filed, T self-test
  String type, ip, isp, loc, inc, tm, ack, detail;
  int count = 0;
};

Alert cur, crit;                 // what is on screen / last critical attack
unsigned long curAt = 0;
unsigned long sirenUntil = 0;
unsigned long warnBeepUntil = 0;
bool latched = false;            // red LED stays on until acknowledged
bool muted = false;
int ackCount = 0;

char rxBuf[360];
size_t rxLen = 0;

// =============================================================== helpers ===
void setPin(int pin, int level) { if (pin >= 0) digitalWrite(pin, level); }

String pongString() {
  return String("PONG|TRAPWIRE-ESP32|") + FW_VERSION + "|" + ackCount + "|" + (muted ? "1" : "0");
}

int splitPipe(const String& s, String* out, int maxParts) {   // keeps empty fields
  int n = 0, start = 0;
  while (n < maxParts) {
    int idx = s.indexOf('|', start);
    if (idx < 0) { out[n++] = s.substring(start); break; }
    out[n++] = s.substring(start, idx);
    start = idx + 1;
  }
  return n;
}

bool sirenActive() { return (long)(sirenUntil - millis()) > 0; }

// ---------------------------------------------------------------- buzzer ---
int lastTone = -2;               // force first write
void buzzer(int freq) {          // freq 0 = off; for active buzzer any >0 = on
  if (muted) freq = 0;
  if (freq == lastTone) return;
  lastTone = freq;
#if BUZZER_PASSIVE
  if (freq > 0) tone(PIN_BUZZER, freq); else noTone(PIN_BUZZER);
#else
  digitalWrite(PIN_BUZZER, freq > 0 ? BUZZER_ON_LEVEL : (BUZZER_ON_LEVEL == HIGH ? LOW : HIGH));
#endif
}

// =========================================================== alarm logic ===
void clearAlarm(bool fromButton) {
  latched = false;
  sirenUntil = 0;
  warnBeepUntil = 0;
  buzzer(0);
  setPin(PIN_LED_RED, LOW);
  setPin(PIN_LED_GREEN, HIGH);
  setPin(PIN_RELAY, RELAY_ON_LEVEL == HIGH ? LOW : HIGH);
  cur.valid = false;
  crit.valid = false;
  if (fromButton) {
    ackCount++;
    Serial.print("ACK|BUTTON|");
    Serial.println(ackCount);
  }
}

void onAlert(const Alert& a) {
  cur = a;
  cur.valid = true;
  curAt = millis();
  setPin(PIN_LED_GREEN, LOW);
  if (a.sev == 'C') {
    crit = a;                               // remember for the latched screen
    latched = true;
    sirenUntil = millis() + SIREN_MS;
    setPin(PIN_RELAY, RELAY_ON_LEVEL);
  } else if (a.sev == 'T') {
    sirenUntil = millis() + TEST_SIREN_MS;
  } else {                                  // W (warning/probe) or R (report)
    warnBeepUntil = millis() + (a.sev == 'R' ? 220 : 650);
  }
}

// drive LED + buzzer each loop based on current state
void serviceOutputs() {
  unsigned long now = millis();
  if (sirenActive()) {
    // critical siren: warble buzzer + fast red blink
    bool phase = (now / 250) % 2;
    buzzer(phase ? 2200 : 1400);
    setPin(PIN_LED_RED, phase ? HIGH : LOW);
  } else if ((long)(warnBeepUntil - now) > 0) {
    // short warning/report beep + red on
    bool phase = (now / 120) % 2;
    buzzer(phase ? 1800 : 0);
    setPin(PIN_LED_RED, HIGH);
  } else {
    buzzer(0);
    setPin(PIN_LED_RED, latched ? HIGH : LOW);   // latched = stays on after siren
    if (!latched) setPin(PIN_LED_GREEN, HIGH);
  }
}

// ================================================================= OLED ====
void drawCentered(const String& s, int y, int size) {
  display.setTextSize(size);
  int16_t x1, y1; uint16_t w, h;
  display.getTextBounds(s, 0, y, &x1, &y1, &w, &h);
  display.setCursor((128 - (int)w) / 2, y);
  display.print(s);
}

void drawIdle() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  drawCentered("TRAPWIRE", 14, 2);
  drawCentered("SOC ALERT NODE", 36, 1);
  drawCentered(muted ? "ARMED (muted)" : "ARMED - monitoring", 50, 1);
  display.display();
}

String sevName(char s) {
  switch (s) {
    case 'C': return "!! ATTACK !!";
    case 'W': return "PROBE / WARN";
    case 'R': return "REPORT FILED";
    case 'T': return "SELF TEST";
  }
  return "ALERT";
}

// page 0: who + what. page 1: where + report
void drawAlert(const Alert& a, int page) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  // header bar
  display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setTextSize(1);
  display.setCursor(2, 2);
  display.print(sevName(a.sev));
  String badge = String("#") + a.count;
  display.setCursor(128 - badge.length() * 6 - 2, 2);
  display.print(badge);
  display.setTextColor(SSD1306_WHITE);

  if (page == 0) {
    display.setCursor(0, 16); display.print("Type: "); display.print(a.type);
    display.setCursor(0, 28); display.print("IP  : "); display.print(a.ip);
    display.setCursor(0, 40); display.print("Host: ");
    display.print(a.loc.length() ? a.loc : String("resolving..."));
    display.setCursor(0, 52); display.print("Time: "); display.print(a.tm);
  } else {
    display.setCursor(0, 16); display.print("ISP : "); display.print(a.isp);
    display.setCursor(0, 28); display.print("Inc : "); display.print(a.inc);
    display.setCursor(0, 40);
    if (a.ack.length()) { display.print("DPB : "); display.print(a.ack); }
    else if (a.detail.length()) { display.print("At  : "); display.print(a.detail); }
    else { display.print("Deception engaged"); }
    display.setCursor(0, 52);
    display.print(a.sev == 'C' ? (latched ? "Press BOOT to clear" : "") : "Monitoring...");
  }
  display.display();
}

void serviceDisplay() {
  if (!oledOk) return;
  unsigned long now = millis();
  const Alert* show = nullptr;

  if (cur.valid) {
    bool expired = (cur.sev != 'C') && (now - curAt > HOLD_MS);
    if (!expired) show = &cur;
  }
  if (!show && latched && crit.valid) show = &crit;   // fall back to the attack screen

  if (show) drawAlert(*show, (now / PAGE_MS) % 2);
  else drawIdle();
}

// ============================================================ command in ===
void handleCommand(String line) {
  line.trim();
  if (!line.length()) return;
  String p[11];
  int n = splitPipe(line, p, 11);
  String cmd = p[0]; cmd.toUpperCase();

  if (cmd == "ALERT" && n >= 9) {
    Alert a;
    a.sev    = p[1].length() ? p[1][0] : 'C';
    a.type   = p[2]; a.ip = p[3]; a.isp = p[4]; a.loc = p[5];
    a.inc    = p[6]; a.tm = p[7]; a.count = p[8].toInt();
    a.ack    = (n > 9) ? p[9]  : "";
    a.detail = (n > 10) ? p[10] : "";
    onAlert(a);
  } else if (cmd == "CLEAR") {
    clearAlarm(false);
  } else if (cmd == "MUTE" && n >= 2) {
    muted = (p[1].toInt() != 0);
    if (muted) buzzer(0);
  } else if (cmd == "PING") {
    Serial.println(pongString());
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxLen) { rxBuf[rxLen] = 0; handleCommand(String(rxBuf)); rxLen = 0; }
    } else if (rxLen < sizeof(rxBuf) - 1) {
      rxBuf[rxLen++] = c;
    } else {
      rxLen = 0;   // overflow guard
    }
  }
}

// ============================================================== button =====
void serviceButton() {
  static bool down = false;
  static unsigned long downAt = 0;
  static bool longFired = false;
  bool pressed = (digitalRead(PIN_BUTTON) == LOW);   // active-low

  if (pressed && !down) { down = true; downAt = millis(); longFired = false; }
  else if (pressed && down && !longFired && millis() - downAt > LONG_PRESS_MS) {
    muted = !muted; if (muted) buzzer(0);
    longFired = true;
    Serial.print("LOG|button long press -> muted="); Serial.println(muted ? 1 : 0);
  }
  else if (!pressed && down) {
    down = false;
    if (!longFired) clearAlarm(true);               // short press = acknowledge
  }
}

// ============================================================== Wi-Fi ======
#if ENABLE_WIFI
void handleCmdHttp() {
  String body = http.arg("plain");
  handleCommand(body);
  http.send(200, "text/plain", "OK");
}
void handlePingHttp() { http.send(200, "text/plain", pongString()); }
void setupWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 15000) { delay(300); }
  if (WiFi.status() == WL_CONNECTED) {
    http.on("/cmd", HTTP_POST, handleCmdHttp);
    http.on("/ping", HTTP_GET, handlePingHttp);
    http.begin();
    Serial.print("LOG|wifi ip="); Serial.println(WiFi.localIP());
    if (oledOk) { display.clearDisplay(); drawCentered(WiFi.localIP().toString(), 28, 1); display.display(); delay(1500); }
  } else {
    Serial.println("LOG|wifi connect failed, USB only");
  }
}
#endif

// =============================================================== setup =====
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_RED, OUTPUT);
  if (PIN_LED_GREEN >= 0) pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  if (PIN_RELAY >= 0) pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  buzzer(0);
  setPin(PIN_RELAY, RELAY_ON_LEVEL == HIGH ? LOW : HIGH);

  Wire.begin(OLED_SDA, OLED_SCL);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (oledOk) {
    display.clearDisplay();
    drawCentered("TRAPWIRE", 20, 2);
    drawCentered("alert node v" + String(FW_VERSION), 44, 1);
    display.display();
  }
  // power-on self-check: green on, one short chirp + red flash
  setPin(PIN_LED_GREEN, HIGH);
  setPin(PIN_LED_RED, HIGH); buzzer(1800); delay(150);
  buzzer(0); setPin(PIN_LED_RED, LOW);

#if ENABLE_WIFI
  setupWifi();
#endif

  delay(600);
  if (oledOk) drawIdle();
  Serial.print("READY|TRAPWIRE-ESP32|"); Serial.println(FW_VERSION);
}

void loop() {
  readSerial();
#if ENABLE_WIFI
  http.handleClient();
#endif
  serviceButton();
  serviceOutputs();
  serviceDisplay();
  delay(5);
}
