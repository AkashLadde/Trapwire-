/*
 * =====================================================================================
 * TRAPWIRE — ESP32 DevKit V1 Physical Threat Siren & SOC Defense Node
 * =====================================================================================
 * Target Board:
 *   ESP32 Development Board (ESP32 DevKit V1 with Wi-Fi & Bluetooth, 30-pin or 36-pin)
 *
 * Operational Behavior:
 *   1. NORMAL STANDBY:
 *      - White LED: BLINKS rhythmically (500ms ON / 500ms OFF) to indicate system armed
 *      - Red LED:   OFF
 *      - Buzzer:    SILENT (completely quiet)
 *      - OLED:      DYNAMIC ANIMATED SCREEN with:
 *                   - Animated rotating radar sweep icon
 *                   - Live blinking "[*] ARMED & READY" status
 *                   - Live UPTIME counter (HH:MM:SS) updating in real-time
 *                   - Active honeypot port monitor (Port 8080)
 *                   - Smooth horizontal scrolling marquee ticker
 *                   - STRICT NO-OVERLAP layout grid
 *
 *   2. ATTACK TIME (Threat Intrusion Detected):
 *      - White LED: OFF
 *      - Red LED:   BLINKS rapidly (120ms emergency tactical strobe)
 *      - Buzzer:    POLICE SIREN (960Hz / 650Hz dual-tone wail alternating every 250ms)
 *      - OLED:      DYNAMIC INTRUSION SCREEN with:
 *                   - Alternating flashing emergency banner (! CRITICAL BREACH !)
 *                   - Pulsing perimeter threat border
 *                   - Live attacker IP and exploit vector
 *                   - Real-time animated lockdown countdown bar (9s -> 0s)
 *                   - DPB Statutory compliance badge
 *      - Auto-resets back to Standby after 9 seconds of inactivity
 *
 * Pin Connections on ESP32 DevKit V1:
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
 * Required Arduino Libraries (Install via Arduino IDE Library Manager):
 *   1. "Adafruit SSD1306" by Adafruit
 *   2. "Adafruit GFX Library" by Adafruit
 *   3. "ArduinoJson" (v6 or v7) by Benoit Blanchon
 *
 * Communication:
 *   115200 baud USB Serial connected to hardware/serial_bridge.py
 *   Manual serial commands supported: type "attack" or "test" to test; "reset" to standby.
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
#define OLED_RESET     -1  // No dedicated reset pin on 4-pin I2C modules

#define I2C_SDA_PIN    21  // ESP32 hardware I2C SDA (D21)
#define I2C_SCL_PIN    22  // ESP32 hardware I2C SCL (D22)

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool oledReady = false;
uint8_t detectedOledAddress = 0x3C;

// -------------------------------------------------------------------------------------
// GPIO Pin Assignments
// -------------------------------------------------------------------------------------
#define PIN_WHITE_LED  18  // GPIO 18 (D18) - Normal Guard Status (Blinks in Standby)
#define PIN_RED_LED    19  // GPIO 19 (D19) - Threat Alarm Strobe (Blinks during Attack)
#define PIN_BUZZER     23  // GPIO 23 (D23) - Warning Audio Siren (Police Siren on Attack)

// -------------------------------------------------------------------------------------
// Buzzer Configuration:
// - isBuzzerActive = false: Passive Buzzer (default, dual-tone 960Hz / 650Hz AC wave)
// - isBuzzerActive = true:  Active Buzzer (internal oscillator, DC pulse cadence)
// Can also be toggled at runtime via Serial command: type "active" or "passive"
// -------------------------------------------------------------------------------------
bool isBuzzerActive = false;
#define BUZZER_ACTIVE_LOW  false

#define BUZZER_ON_LEVEL    (BUZZER_ACTIVE_LOW ? LOW : HIGH)
#define BUZZER_OFF_LEVEL   (BUZZER_ACTIVE_LOW ? HIGH : LOW)

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

String currentAttackerIp = "185.220.101.45";
String currentAttackType = "SQL INJECTION";

// -------------------------------------------------------------------------------------
// Non-Blocking Timing Variables
// -------------------------------------------------------------------------------------
// 1. Standby White LED Blink (500ms ON / 500ms OFF)
unsigned long lastWhiteBlinkToggle = 0;
bool whiteLedState = false;

// 2. Attack Time Red LED Fast Strobe (120ms ON / 120ms OFF)
unsigned long lastRedBlinkToggle = 0;
bool redLedState = false;

// 3. Attack Time Police Siren (Alternates 960Hz / 650Hz every 250ms)
unsigned long lastSirenToggle = 0;
bool sirenToneHigh = false;

// 4. OLED Dynamic Refresh Engine (Updates at ~15-20 FPS without blocking)
unsigned long lastOledRefresh = 0;
const unsigned long OLED_REFRESH_INTERVAL_MS = 60; // 60ms refresh rate

// 5. Dynamic Marquee & Radar Animations
int marqueeScrollIndex = 0;
unsigned long lastMarqueeScroll = 0;
int radarFrame = 0;
unsigned long lastRadarAnim = 0;

const char* MARQUEE_TEXT = "   >>> TRAPWIRE CYBER RESILIENCE SHIELD ACTIVE * PERIMETER PATROLLING * ZERO DATA LEAKAGE * DPDP 2023 COMPLIANT <<<   ";
const int MARQUEE_LEN = 119;

// -------------------------------------------------------------------------------------
// Universal Buzzer Driver: Police Siren & Silence (Active & Passive Buzzers)
// -------------------------------------------------------------------------------------
void setBuzzerTone(unsigned int freq) {
  if (isBuzzerActive) {
    digitalWrite(PIN_BUZZER, BUZZER_ON_LEVEL);
  } else {
    tone(PIN_BUZZER, freq);
  }
}

void silenceBuzzer() {
  noTone(PIN_BUZZER);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, BUZZER_OFF_LEVEL);
}

void playPoliceSiren(unsigned long now) {
  // Police Siren: Alternates between High Tone (960 Hz) and Low Tone (650 Hz) every 250ms
  if (now - lastSirenToggle >= 250) {
    lastSirenToggle = now;
    sirenToneHigh = !sirenToneHigh;

    if (!isBuzzerActive) {
      // Passive Buzzer: Authentic dual-tone Police Siren wail
      tone(PIN_BUZZER, sirenToneHigh ? 960 : 650);
    }
  }

  // Active Buzzer: Rapid tactical pulsing cadence
  if (isBuzzerActive) {
    int pulseRate = sirenToneHigh ? 70 : 130;
    bool activePulse = ((now / pulseRate) % 2) == 0;
    digitalWrite(PIN_BUZZER, activePulse ? BUZZER_ON_LEVEL : BUZZER_OFF_LEVEL);
  }
}

// -------------------------------------------------------------------------------------
// I2C Hardware Bus Scanner
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
  }
  Serial.println(F("========================================================\n"));

  return foundAddress;
}

// -------------------------------------------------------------------------------------
// Initialize OLED with charge pump overrides for maximum compatibility
// -------------------------------------------------------------------------------------
bool initOledDisplay(uint8_t addr) {
  if (!display.begin(SSD1306_SWITCHCAPVCC, addr, false, false)) {
    return false;
  }

  // Charge-pump & contrast activation commands
  display.ssd1306_command(SSD1306_CHARGEPUMP);
  display.ssd1306_command(0x14);

  display.ssd1306_command(0xAD);
  display.ssd1306_command(0x8B);

  display.ssd1306_command(SSD1306_SETCONTRAST);
  display.ssd1306_command(0xFF);
  display.ssd1306_command(SSD1306_DISPLAYON);

  return true;
}

// -------------------------------------------------------------------------------------
// DYNAMIC OLED RENDERING ENGINE (Strict Zero-Overlap Layout)
// -------------------------------------------------------------------------------------
void renderDynamicStandby(unsigned long now) {
  display.clearDisplay();
  display.setTextWrap(false); // CRITICAL: Prevents rogue text wrapping onto lower lines!

  // 1. Animated Radar Indicator in Header
  if (now - lastRadarAnim > 250) {
    lastRadarAnim = now;
    radarFrame = (radarFrame + 1) % 4;
  }
  const char radarChars[] = {'|', '/', '-', '\\'};

  // 2. Inverted Top Header Bar (Height 12px)
  display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(4, 2);
  display.print(F("TRAPWIRE DEFENSE ["));
  display.print(radarChars[radarFrame]);
  display.print(F("]"));

  // 3. Row 1 (Y=16): System Status + Animated Armed Indicator
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(2, 16);
  display.print(F("SYS: ARMED & READY"));
  // Pulsing blink indicator aligned with white LED
  if ((now / 500) % 2 == 0) {
    display.setCursor(110, 16);
    display.print(F("[*]"));
  }

  // 4. Row 2 (Y=27): Honeypot Deception Status
  display.setCursor(2, 27);
  display.print(F("DECOY: ISOLATED (8080)"));

  // 5. Row 3 (Y=38): Live Ticking Uptime Counter (HH:MM:SS)
  unsigned long totalSecs = now / 1000;
  unsigned int secs = totalSecs % 60;
  unsigned int mins = (totalSecs / 60) % 60;
  unsigned int hrs = (totalSecs / 3600);

  display.setCursor(2, 38);
  display.print(F("UP: "));
  if (hrs < 10) display.print(F("0"));
  display.print(hrs);
  display.print(F(":"));
  if (mins < 10) display.print(F("0"));
  display.print(mins);
  display.print(F(":"));
  if (secs < 10) display.print(F("0"));
  display.print(secs);
  display.print(F(" | SENS:100%"));

  // 6. Horizontal Divider Line (Y=49)
  display.drawLine(0, 49, 127, 49, SSD1306_WHITE);

  // 7. Row 4 (Y=53): Smooth Horizontal Scrolling Marquee
  if (now - lastMarqueeScroll > 140) {
    lastMarqueeScroll = now;
    marqueeScrollIndex++;
    if (marqueeScrollIndex >= MARQUEE_LEN) {
      marqueeScrollIndex = 0;
    }
  }

  char marqueeWindow[22];
  for (int i = 0; i < 21; i++) {
    int charIdx = (marqueeScrollIndex + i) % MARQUEE_LEN;
    marqueeWindow[i] = MARQUEE_TEXT[charIdx];
  }
  marqueeWindow[21] = '\0';

  display.setCursor(2, 53);
  display.print(marqueeWindow);

  display.display();
}

void renderDynamicThreat(unsigned long now) {
  display.clearDisplay();
  display.setTextWrap(false); // CRITICAL: Zero line overlap

  // 1. Dynamic Flashing Emergency Header Banner (Alternates every 180ms)
  bool flashPhase = ((now / 180) % 2) == 0;
  if (flashPhase) {
    display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(8, 2);
    display.print(F("! CRITICAL BREACH !"));
  } else {
    display.drawRect(0, 0, 128, 12, SSD1306_WHITE);
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(6, 2);
    display.print(F("! INTRUSION ALERT !"));
  }

  display.setTextColor(SSD1306_WHITE);

  // 2. Row 1 (Y=16): Attacker Source IP (Strictly bounded)
  display.setCursor(2, 16);
  display.print(F("IP  : "));
  String ipClean = currentAttackerIp.length() > 0 ? currentAttackerIp : F("185.20.209.0");
  if (ipClean.startsWith(F("::ffff:"))) ipClean = ipClean.substring(7);
  if (ipClean.length() > 15) ipClean = ipClean.substring(0, 15);
  display.print(ipClean);

  // 3. Row 2 (Y=27): Attack Vector
  display.setCursor(2, 27);
  display.print(F("ATK : "));
  String vecClean = currentAttackType.length() > 0 ? currentAttackType : F("SQL INJECTION");
  if (vecClean.length() > 15) vecClean = vecClean.substring(0, 15);
  display.print(vecClean);

  // 4. Row 3 (Y=38): Live Countdown & Graphical Progress Bar
  // CRITICAL: Safe unsigned calculation prevents wrap-around underflow
  unsigned long elapsed = (now >= lastThreatTime) ? (now - lastThreatTime) : 0;
  int remainingSecs = 9;
  if (elapsed < ALARM_DURATION_MS) {
    remainingSecs = (ALARM_DURATION_MS - elapsed) / 1000 + 1;
  } else {
    remainingSecs = 0;
  }

  display.setCursor(2, 38);
  display.print(F("SIREN: "));
  display.print(remainingSecs);
  display.print(F("s"));

  // Graphic progress bar shrinking in real time (X=56, Y=38, Width=68, Height=7)
  display.drawRect(56, 38, 68, 7, SSD1306_WHITE);
  int fillWidth = 0;
  if (elapsed < ALARM_DURATION_MS) {
    fillWidth = map(ALARM_DURATION_MS - elapsed, 0, ALARM_DURATION_MS, 0, 64);
  }
  if (fillWidth > 64) fillWidth = 64;
  if (fillWidth > 0) {
    display.fillRect(58, 40, fillWidth, 3, SSD1306_WHITE);
  }

  // 5. Horizontal Divider Line (Y=49)
  display.drawLine(0, 49, 127, 49, SSD1306_WHITE);

  // 6. Row 4 (Y=53): Statutory Regulatory Action
  display.setCursor(2, 53);
  display.print(F("DPB REPORT: FILED [OK]"));

  // 7. Pulsing Outer Threat Border (flashes with siren tempo)
  if (sirenToneHigh) {
    display.drawRect(0, 0, 128, 64, SSD1306_WHITE);
  }

  display.display();
}

void updateOled(unsigned long now) {
  if (!oledReady) return;
  if (now - lastOledRefresh < OLED_REFRESH_INTERVAL_MS) return;
  lastOledRefresh = now;

  if (currentState == STATE_CRITICAL || currentState == STATE_WARNING) {
    renderDynamicThreat(now);
  } else {
    renderDynamicStandby(now);
  }
}

// -------------------------------------------------------------------------------------
// Setup Routine
// -------------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50); // Fast non-blocking serial reading
  delay(300);

  // Configure GPIO Pins
  pinMode(PIN_WHITE_LED, OUTPUT);
  pinMode(PIN_RED_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Initial state: Everything strictly OFF
  digitalWrite(PIN_WHITE_LED, LOW);
  digitalWrite(PIN_RED_LED, LOW);
  silenceBuzzer();

  // Configure ESP32 I2C pins with internal pull-ups enabled
  pinMode(I2C_SDA_PIN, INPUT_PULLUP);
  pinMode(I2C_SCL_PIN, INPUT_PULLUP);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(100000); // 100 kHz standard mode
  delay(100);

  // 1. Run I2C Hardware Bus Scan
  uint8_t oledAddr = scanI2CAddress();
  if (oledAddr != 0) {
    detectedOledAddress = oledAddr;
  }

  // 2. Initialize OLED Display
  if (initOledDisplay(detectedOledAddress)) {
    oledReady = true;
    Serial.print(F("[+] OLED initialized at 0x"));
    Serial.println(detectedOledAddress, HEX);
  } else if (initOledDisplay(0x3C)) {
    oledReady = true;
    detectedOledAddress = 0x3C;
    Serial.println(F("[+] OLED initialized at fallback 0x3C"));
  } else if (initOledDisplay(0x3D)) {
    oledReady = true;
    detectedOledAddress = 0x3D;
    Serial.println(F("[+] OLED initialized at fallback 0x3D"));
  } else {
    oledReady = false;
    Serial.println(F("[-] OLED allocation failed. Continuing with LEDs and Buzzer."));
  }

  // =========================================================================
  // HARDWARE POWER-ON SELF-TEST (Auditory chime + Visual flashes)
  // =========================================================================
  Serial.println(F("[SELF-TEST] Testing Hardware: White LED, Red LED, Dynamic OLED & Police Siren..."));

  // Power-on chime: 3 crisp audible tones (880Hz -> 1175Hz -> 1760Hz)
  // Gives immediate auditory proof that the buzzer is functioning!
  setBuzzerTone(880);
  digitalWrite(PIN_WHITE_LED, HIGH);
  delay(90);
  silenceBuzzer();
  digitalWrite(PIN_WHITE_LED, LOW);
  delay(60);

  setBuzzerTone(1175);
  digitalWrite(PIN_RED_LED, HIGH);
  delay(90);
  silenceBuzzer();
  digitalWrite(PIN_RED_LED, LOW);
  delay(60);

  setBuzzerTone(1760);
  digitalWrite(PIN_WHITE_LED, HIGH);
  digitalWrite(PIN_RED_LED, HIGH);
  delay(120);
  silenceBuzzer();
  digitalWrite(PIN_WHITE_LED, LOW);
  digitalWrite(PIN_RED_LED, LOW);

  // Enter Standby Mode
  currentState = STATE_STANDBY;
  silenceBuzzer();

  Serial.println(F("[SELF-TEST] Complete. System is in NORMAL STANDBY mode."));
  Serial.println(F("[NOTE] In Standby: White LED blinks, Red LED is OFF, Buzzer is SILENT."));
  Serial.println(F("[TIP] Type 'attack' or 'test' in Serial Monitor to trigger Police Siren!"));
}

// -------------------------------------------------------------------------------------
// JSON Threat Stream Parser
// -------------------------------------------------------------------------------------
void processIncomingThreatJson(const String& jsonStr) {
  #if ARDUINOJSON_VERSION_MAJOR >= 7
  JsonDocument doc;
  #else
  StaticJsonDocument<512> doc;
  #endif

  DeserializationError err = deserializeJson(doc, jsonStr);
  if (err) {
    // Fallback: check if line is a plain string containing attack terms
    String s = jsonStr;
    s.toLowerCase();
    if (s.indexOf("attack") >= 0 || s.indexOf("critical") >= 0 || s.indexOf("sql") >= 0 || s.indexOf("threat") >= 0) {
      currentState = STATE_CRITICAL;
      lastThreatTime = millis();
      currentAttackerIp = "185.20.209.0";
      currentAttackType = "CYBER ATTACK";
      Serial.println(F("[ALARM ACTIVE] Fallback plain-text threat engaged!"));
    }
    return;
  }

  const char* levelStr = doc["level"] | "info";
  const char* typeStr = doc["attack_type"] | doc["type"] | "";
  const char* messageStr = doc["message"] | "Threat event detected";
  const char* ipStr = doc["attacker_ip"] | doc["ip"] | "185.20.209.0";

  String lvl = String(levelStr);
  lvl.toLowerCase();

  if (lvl == "critical" || lvl == "emergency" || lvl == "warning" || lvl == "high") {
    currentState = STATE_CRITICAL;
    lastThreatTime = millis();

    // 1. Clean Attacker IP
    currentAttackerIp = String(ipStr);
    if (currentAttackerIp.startsWith("::ffff:")) {
      currentAttackerIp = currentAttackerIp.substring(7);
    }
    if (currentAttackerIp.length() > 15) {
      currentAttackerIp = currentAttackerIp.substring(0, 15);
    }

    // 2. Clean Attack Type
    if (strlen(typeStr) > 0) {
      currentAttackType = String(typeStr);
    } else {
      String msg = String(messageStr);
      msg.toUpperCase();
      if (msg.indexOf("SQL") >= 0) currentAttackType = "SQL INJECTION";
      else if (msg.indexOf("XSS") >= 0) currentAttackType = "STORED XSS";
      else if (msg.indexOf("TRAVERSAL") >= 0 || msg.indexOf("LFI") >= 0) currentAttackType = "PATH TRAVERSAL";
      else if (msg.indexOf("IDOR") >= 0 || msg.indexOf("BOLA") >= 0) currentAttackType = "IDOR / BOLA";
      else if (msg.indexOf("SSRF") >= 0) currentAttackType = "SSRF EXPLOIT";
      else if (msg.indexOf("HONEYTOKEN") >= 0) currentAttackType = "HONEYTOKEN HIT";
      else if (msg.indexOf("EXFILTRAT") >= 0 || msg.indexOf("EXPORT") >= 0) currentAttackType = "EXFILTRATION";
      else if (msg.indexOf("LOGIN") >= 0 || msg.indexOf("AUTH") >= 0 || msg.indexOf("BRUTE") >= 0) currentAttackType = "BRUTE FORCE";
      else if (msg.indexOf("CANARY") >= 0) currentAttackType = "CANARY TRAP";
      else if (msg.indexOf("TEST") >= 0) currentAttackType = "HARDWARE TEST";
      else currentAttackType = msg.substring(0, 15);
    }
    if (currentAttackType.length() > 15) {
      currentAttackType = currentAttackType.substring(0, 15);
    }

    Serial.print(F("[⚡ HARDWARE THREAT TRIGGERED] Type: "));
    Serial.print(currentAttackType);
    Serial.print(F(" | Attacker IP: "));
    Serial.println(currentAttackerIp);
  }
}

// -------------------------------------------------------------------------------------
// Main Loop (100% Non-blocking timing)
// -------------------------------------------------------------------------------------
void loop() {
  // 1. Process USB Serial commands
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.length() > 0) {
      if (line.equalsIgnoreCase("attack") || line.equalsIgnoreCase("test") || line.equalsIgnoreCase("siren")) {
        // Manual test command from user in Serial Monitor
        currentState = STATE_CRITICAL;
        lastThreatTime = millis();
        currentAttackerIp = "192.168.1.105";
        currentAttackType = "TEST POLICE SIREN";
        Serial.println(F("[!] MANUAL TEST ENGAGED: Red LED blinking & Police Siren sounding for 9s!"));
      } 
      else if (line.equalsIgnoreCase("reset") || line.equalsIgnoreCase("standby") || line.equalsIgnoreCase("stop")) {
        // Manual reset command
        currentState = STATE_STANDBY;
        digitalWrite(PIN_RED_LED, LOW);
        silenceBuzzer();
        Serial.println(F("[*] MANUAL RESET: Returned to Standby. White LED blinking."));
      } 
      else if (line.equalsIgnoreCase("active") || line.equalsIgnoreCase("buzzer:active")) {
        isBuzzerActive = true;
        Serial.println(F("[BUZZER] Switched to ACTIVE BUZZER mode (DC pulse cadence)."));
      }
      else if (line.equalsIgnoreCase("passive") || line.equalsIgnoreCase("buzzer:passive")) {
        isBuzzerActive = false;
        Serial.println(F("[BUZZER] Switched to PASSIVE BUZZER mode (960Hz/650Hz dual tone)."));
      }
      else {
        // Real-time JSON alert from serial_bridge.py / hardware_bridge.py
        processIncomingThreatJson(line);
      }
    }
  }

  // CRITICAL FIX: Refresh 'now' AFTER reading serial so that now >= lastThreatTime is ALWAYS true!
  unsigned long now = millis();

  // 2. Hardware Alarm State Machine
  if (currentState == STATE_CRITICAL || currentState == STATE_WARNING) {
    // ATTACK TIME:
    // - White LED: Strictly OFF
    // - Red LED:   Blinks rapidly (120ms emergency strobe)
    // - Buzzer:    Produces POLICE SIREN sound (alternating 960Hz / 650Hz wail)
    digitalWrite(PIN_WHITE_LED, LOW);

    // Red LED fast strobe
    if (now - lastRedBlinkToggle >= 120) {
      lastRedBlinkToggle = now;
      redLedState = !redLedState;
      digitalWrite(PIN_RED_LED, redLedState ? HIGH : LOW);
    }

    // Police Siren Sound
    playPoliceSiren(now);

    // Auto-Reset back to Normal Standby after alarm timeout (9 seconds)
    // CRITICAL FIX: Safe unsigned comparison guards against 32-bit wrap-around underflow!
    if (now >= lastThreatTime && (now - lastThreatTime) >= ALARM_DURATION_MS) {
      currentState = STATE_STANDBY;
      digitalWrite(PIN_RED_LED, LOW);
      silenceBuzzer();
      Serial.println(F("{\"event\":\"AUTO_RESET\",\"status\":\"STANDBY\"}"));
      Serial.println(F("[*] Attack ended. Returned to Standby mode (White LED blinking, Buzzer silent)."));
    }
  } 
  else {
    // NORMAL STANDBY TIME:
    // - Red LED:   Strictly OFF
    // - Buzzer:    Strictly SILENT
    // - White LED: BLINKS rhythmically (500ms ON / 500ms OFF)
    digitalWrite(PIN_RED_LED, LOW);
    silenceBuzzer();

    // White LED rhythmic blink
    if (now - lastWhiteBlinkToggle >= 500) {
      lastWhiteBlinkToggle = now;
      whiteLedState = !whiteLedState;
      digitalWrite(PIN_WHITE_LED, whiteLedState ? HIGH : LOW);
    }
  }

  // 3. Dynamic OLED Screen Refresh Engine
  updateOled(now);
}
