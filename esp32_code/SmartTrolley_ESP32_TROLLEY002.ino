/*
 * Smart Trolley Billing System — ESP32 Multi-Trolley Firmware v2.0
 * ================================================================
 * TROLLEY-002 — Flash this file to the FIRST trolley's ESP32.
 *
 * ► To create TROLLEY-002 or TROLLEY-003, open the corresponding
 *   SmartTrolley_ESP32_TROLLEY002.ino / SmartTrolley_ESP32_TROLLEY003.ino
 *   file instead.  The ONLY difference between the three files is the
 *   TROLLEY_ID constant below.
 *
 * ► To add TROLLEY-004, copy this file, change TROLLEY_ID to "TROLLEY-004"
 *   and flash it.  No backend or frontend changes are required.
 *
 * Required Arduino IDE Libraries:
 *   1. MFRC522 (by GithubCommunity)
 *   2. LiquidCrystal_I2C (by Frank de Brabander)
 *   3. ArduinoJson (by Benoit Blanchon) - Version 6 or 7
 *
 * Hardware Connections (ESP32 Dev Board):
 *   - MFRC522 RFID:
 *       VCC  -> 3.3V (DO NOT CONNECT TO 5V!)
 *       GND  -> GND
 *       MISO -> GPIO 19
 *       MOSI -> GPIO 23
 *       SCK  -> GPIO 18
 *       SDA  -> GPIO 5
 *       RST  -> GPIO 4
 *   - I2C LCD Display (16x2):
 *       VCC  -> 5V (from Vin / external 5V power)
 *       GND  -> GND
 *       SDA  -> GPIO 21
 *       SCL  -> GPIO 22
 *   - Push Buttons (Internal Pull-Up enabled):
 *       ADD Button    -> GPIO 13 (other leg to GND)
 *       REMOVE Button -> GPIO 12 (other leg to GND)
 *       RESET Button  -> GPIO 14 (other leg to GND)
 *   - Buzzer:
 *       Positive (+)  -> GPIO 15 (through 220-ohm resistor)
 *       Negative (-)  -> GND
 */

#include <WiFi.h>
#include <esp_wifi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <Wire.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// ══════════════════════════════════════════════════════════════════════════════
// ► TROLLEY IDENTITY — Change ONLY this line when creating a new trolley file
// ══════════════════════════════════════════════════════════════════════════════
const String TROLLEY_ID   = "TROLLEY-002";
const String TROLLEY_NAME = "Smart Trolley 002";
const String FW_VERSION   = "2.0";

// ── Wi-Fi Configuration ────────────────────────────────────────────────────
const char* ssid       = "Redmi 13C 5G";       // Your Wi-Fi SSID
const char* password   = "111111111";           // Your Wi-Fi Password
const String serverIP  = "10.83.19.241";        // Flask server local IP
const int   serverPort = 5000;                  // Flask server port

// ── API Endpoints (all include TROLLEY_ID in JSON body) ─────────────────────
const String BASE_URL     = "http://" + serverIP + ":" + String(serverPort);
const String apiAction    = BASE_URL + "/api/cart/action";
const String apiReset     = BASE_URL + "/api/reset";
const String apiMode      = BASE_URL + "/api/simulator/mode";
const String apiHeartbeat = BASE_URL + "/api/trolley/heartbeat";
const String apiRegister  = BASE_URL + "/api/trolley/register";

// ── Pin Definitions ────────────────────────────────────────────────────────
const int ADD_BTN    = 13;
const int REMOVE_BTN = 12;
const int RESET_BTN  = 14;
const int BUZZER_PIN = 15;

#define SS_PIN   5
#define RST_PIN  4
#define I2C_SDA  21
#define I2C_SCL  22

// ── Global Objects ─────────────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2); // Change to 0x3F if LCD is blank
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ── State Variables ────────────────────────────────────────────────────────
String currentMode    = "ADD";
bool   wifiConnected  = false;

// Heartbeat timing
unsigned long lastHeartbeatTime = 0;
const unsigned long HEARTBEAT_INTERVAL_MS = 15000; // Send heartbeat every 15 s

// Wi-Fi reconnect timing
unsigned long lastWifiCheckTime = 0;
const unsigned long WIFI_CHECK_INTERVAL_MS = 10000;

// Duplicate scan protection
String        lastScannedUID  = "";
unsigned long lastScanTime    = 0;
const unsigned long SCAN_COOLDOWN_MS = 2500; // Block same card within 2.5 s

// Button idle states (auto-detected on boot)
int addIdleState    = HIGH;
int removeIdleState = HIGH;
int resetIdleState  = HIGH;

// Button debounce
unsigned long lastDebounceAdd    = 0;
unsigned long lastDebounceRemove = 0;
unsigned long lastDebounceReset  = 0;
const unsigned long DEBOUNCE_MS  = 250;

// ── Audio Helpers ──────────────────────────────────────────────────────────
void beepOnce() {
  digitalWrite(BUZZER_PIN, HIGH); delay(120); digitalWrite(BUZZER_PIN, LOW);
}
void beepDouble() {
  beepOnce(); delay(80); beepOnce();
}
void beepTriple() {
  beepOnce(); delay(80); beepOnce(); delay(80); beepOnce();
}

// ── LCD Helper ─────────────────────────────────────────────────────────────
void lcdShow(String line1, String line2 = "") {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  if (line2.length() > 0) {
    lcd.setCursor(0, 1);
    lcd.print(line2.substring(0, 16));
  }
}

// ── Wi-Fi Reconnect ────────────────────────────────────────────────────────
void reconnectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("[WiFi] Connection lost — attempting reconnect...");
  lcdShow("WiFi: Reconnect", "Please wait...");

  WiFi.disconnect();
  delay(500);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n[WiFi] Reconnected! IP: " + WiFi.localIP().toString());
    lcdShow("WiFi Reconnected", WiFi.localIP().toString());
    beepOnce();
    delay(1200);
    lcdShow("Mode: " + currentMode, "Scan card...");
  } else {
    wifiConnected = false;
    Serial.println("\n[WiFi] Reconnect failed. Will retry later.");
    lcdShow("WiFi Failed", "Retrying soon...");
    delay(1000);
    lcdShow("Mode: " + currentMode, "Scan card...");
  }
}

// ── Register Trolley on Server ─────────────────────────────────────────────
void registerWithServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(apiRegister);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  StaticJsonDocument<200> doc;
  doc["trolley_id"]       = TROLLEY_ID;
  doc["name"]             = TROLLEY_NAME;
  doc["firmware_version"] = FW_VERSION;
  doc["ip_address"]       = WiFi.localIP().toString();
  String payload;
  serializeJson(doc, payload);

  int code = http.POST(payload);
  Serial.println("[REGISTER] Server response code: " + String(code));
  http.end();
}

// ── Send Heartbeat ─────────────────────────────────────────────────────────
void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(apiHeartbeat);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  // Estimate battery from supply voltage (simple linear approximation)
  // On a real system, wire a voltage divider to an ADC pin
  int batteryPct = 85; // Placeholder — replace with analogRead-based reading

  StaticJsonDocument<200> doc;
  doc["trolley_id"]       = TROLLEY_ID;
  doc["battery"]          = batteryPct;
  doc["wifi_rssi"]        = WiFi.RSSI();
  doc["ip_address"]       = WiFi.localIP().toString();
  doc["firmware_version"] = FW_VERSION;
  String payload;
  serializeJson(doc, payload);

  int code = http.POST(payload);
  if (code == 200) {
    Serial.println("[HEARTBEAT] OK — Battery: " + String(batteryPct) + "%, RSSI: " + String(WiFi.RSSI()) + " dBm");
  } else {
    Serial.println("[HEARTBEAT] Failed, code: " + String(code));
  }
  http.end();
}

// ── Sync Mode with Server ──────────────────────────────────────────────────
void syncModeWithServer(String mode) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(apiMode);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2000);

  StaticJsonDocument<128> doc;
  doc["mode"]       = mode;
  doc["trolley_id"] = TROLLEY_ID;
  String payload;
  serializeJson(doc, payload);
  http.POST(payload);
  http.end();
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  pinMode(ADD_BTN,    INPUT_PULLUP);
  pinMode(REMOVE_BTN, INPUT_PULLUP);
  pinMode(RESET_BTN,  INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.begin(115200);
  delay(100);
  addIdleState    = digitalRead(ADD_BTN);
  removeIdleState = digitalRead(REMOVE_BTN);
  resetIdleState  = digitalRead(RESET_BTN);

  delay(400);
  Serial.println("\n==========================================");
  Serial.println("  Smart Trolley System — " + TROLLEY_ID + "  ");
  Serial.println("==========================================");

  // 1. LCD Init
  Wire.begin(I2C_SDA, I2C_SCL);
  lcd.init();
  lcd.backlight();
  lcdShow(TROLLEY_ID, "Starting v" + FW_VERSION);
  beepOnce();
  delay(1500);

  // 2. RFID Init
  SPI.begin(18, 19, 23, 5);
  mfrc522.PCD_Init();
  mfrc522.PCD_SetAntennaGain(mfrc522.RxGain_max);
  byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  Serial.print("[RFID] MFRC522 Version: 0x");
  Serial.println(v, HEX);
  if (v == 0x91 || v == 0x92) {
    Serial.println("[RFID] Reader initialized successfully!");
    lcdShow("RFID Status: OK", "Mode: ADD");
  } else {
    Serial.println("[RFID WARNING] Check 3.3V power and wiring!");
    lcdShow("RFID Check Wire", "Power must be 3V3");
    delay(2000);
  }

  // 3. Wi-Fi Connect
  WiFi.mode(WIFI_STA);
  wifi_country_t country = { .cc = "IN", .schan = 1, .nchan = 13, .policy = WIFI_COUNTRY_POLICY_AUTO };
  esp_wifi_set_country(&country);
  WiFi.disconnect();
  delay(100);

  Serial.println("[WiFi] Scanning networks...");
  lcdShow("Scanning WiFi..", "Please wait");
  int n = WiFi.scanNetworks();
  Serial.print("[WiFi Scan] Found "); Serial.print(n); Serial.println(" networks:");
  bool targetFound = false;
  for (int i = 0; i < n; ++i) {
    String foundSSID = WiFi.SSID(i);
    Serial.print("   "); Serial.print(i + 1); Serial.print(": ");
    Serial.print(foundSSID); Serial.print(" ("); Serial.print(WiFi.RSSI(i)); Serial.println(" dBm)");
    if (foundSSID == ssid) targetFound = true;
  }
  if (!targetFound) {
    Serial.println("[WiFi WARNING] SSID '" + String(ssid) + "' not found! Ensure 2.4GHz AP.");
  }

  Serial.print("[WiFi] Connecting to: "); Serial.println(ssid);
  lcdShow("Connecting WiFi", ssid);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n[WiFi] Connected! IP: " + WiFi.localIP().toString());
    lcdShow("WiFi Connected!", WiFi.localIP().toString());
    beepOnce();
    delay(1500);
    // Register with server and send first heartbeat
    registerWithServer();
    sendHeartbeat();
  } else {
    wifiConnected = false;
    Serial.println("\n[WiFi] Failed. Operating in offline/retry mode.");
    lcdShow("WiFi Offline", "Retrying...");
    beepDouble();
  }

  delay(1000);
  lcdShow("Mode: ADD", "Scan card...");
}

// ── Main Loop ──────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // ── 1. Wi-Fi Health Check & Reconnect ────────────────────────────────────
  if (now - lastWifiCheckTime > WIFI_CHECK_INTERVAL_MS) {
    lastWifiCheckTime = now;
    if (WiFi.status() != WL_CONNECTED) {
      wifiConnected = false;
      reconnectWiFi();
    } else {
      wifiConnected = true;
    }
  }

  // ── 2. Periodic Heartbeat ─────────────────────────────────────────────────
  if (now - lastHeartbeatTime > HEARTBEAT_INTERVAL_MS) {
    lastHeartbeatTime = now;
    sendHeartbeat();
  }

  // ── 3. Button Diagnostic (every 2s) ──────────────────────────────────────
  static unsigned long lastBtnDiag = 0;
  if (now - lastBtnDiag > 2000) {
    lastBtnDiag = now;
    Serial.print("[BTN DIAG] ADD(GPIO13)="); Serial.print(digitalRead(ADD_BTN));
    Serial.print(" | REMOVE(GPIO12)="); Serial.print(digitalRead(REMOVE_BTN));
    Serial.print(" | RESET(GPIO14)="); Serial.println(digitalRead(RESET_BTN));
  }

  // ── 4. Button Inputs ──────────────────────────────────────────────────────
  bool addActive    = (digitalRead(ADD_BTN)    != addIdleState);
  bool removeActive = (digitalRead(REMOVE_BTN) != removeIdleState);
  bool resetActive  = (digitalRead(RESET_BTN)  != resetIdleState);

  if (addActive && (now - lastDebounceAdd > DEBOUNCE_MS)) {
    lastDebounceAdd = now;
    currentMode = "ADD";
    Serial.println("[BTN] ADD button pressed");
    beepOnce();
    lcdShow("Mode: ADD", "Scan card...");
    syncModeWithServer("ADD");
  }

  if (removeActive && (now - lastDebounceRemove > DEBOUNCE_MS)) {
    lastDebounceRemove = now;
    currentMode = "REMOVE";
    Serial.println("[BTN] REMOVE button pressed");
    beepOnce();
    lcdShow("Mode: REMOVE", "Scan card...");
    syncModeWithServer("REMOVE");
  }

  if (resetActive && (now - lastDebounceReset > DEBOUNCE_MS)) {
    lastDebounceReset = now;
    Serial.println("[BTN] RESET button pressed");
    beepDouble();
    lcdShow("Resetting Cart", "Please wait...");

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(apiReset);
      http.addHeader("Content-Type", "application/json");
      http.setTimeout(3000);

      StaticJsonDocument<128> doc;
      doc["trolley_id"] = TROLLEY_ID;
      String payload;
      serializeJson(doc, payload);

      int responseCode = http.POST(payload);
      if (responseCode == 200) {
        lcdShow("Cart Reset!", "Total: Rs.0.00");
        beepOnce();
      } else {
        lcdShow("Reset Local", "Total: Rs.0.00");
      }
      http.end();
    } else {
      lcdShow("Reset Local", "WiFi offline");
    }

    delay(1500);
    currentMode = "ADD";
    lcdShow("Mode: ADD", "Scan card...");
  }

  // ── 5. RFID Card Reader ───────────────────────────────────────────────────
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Format UID as "XX XX XX XX"
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (i > 0) uid += " ";
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  // ── Duplicate scan protection ─────────────────────────────────────────────
  if (uid == lastScannedUID && (now - lastScanTime) < SCAN_COOLDOWN_MS) {
    Serial.println("[RFID] Duplicate scan blocked for UID: " + uid);
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    return;
  }
  lastScannedUID = uid;
  lastScanTime   = now;

  Serial.println("[RFID] Scanned Tag UID: " + uid + " (" + TROLLEY_ID + ")");
  lcdShow("Scanning Tag...", uid);
  beepOnce();

  // Handle offline mode
  if (WiFi.status() != WL_CONNECTED) {
    lcdShow("Tag: " + uid, "WiFi Offline");
    beepDouble();
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(1500);
    lcdShow("Mode: " + currentMode, "Scan card...");
    return;
  }

  // ── Send scan request to Flask ────────────────────────────────────────────
  HTTPClient http;
  http.begin(apiAction);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  StaticJsonDocument<200> doc;
  doc["trolley_id"] = TROLLEY_ID;
  doc["action"]     = currentMode;
  doc["uid"]        = uid;
  String requestPayload;
  serializeJson(doc, requestPayload);

  int httpCode = http.POST(requestPayload);

  if (httpCode == 200) {
    String response = http.getString();
    Serial.println("[API] Response: " + response);

    StaticJsonDocument<256> resDoc;
    DeserializationError error = deserializeJson(resDoc, response);

    if (!error && resDoc["success"].as<bool>()) {
      String pName  = resDoc["product"]["name"].as<String>();
      float  total  = resDoc["cart"]["total"].as<float>();
      String symbol = (currentMode == "ADD") ? "+" : "-";
      lcdShow(symbol + " " + pName, "Total: Rs." + String(total, 2));
      beepOnce();
    } else {
      lcdShow("Scan Error!", "Try Again");
      beepTriple();
    }
  } else if (httpCode == 404) {
    Serial.println("[API] Unknown card: " + uid);
    lcdShow("Unknown Card!", "Check Dashboard");
    beepTriple();
  } else if (httpCode == 400) {
    Serial.println("[API] Cart locked (HTTP 400)");
    lcdShow("Cart Locked!", "Pay/Cancel Bill");
    beepTriple();
  } else if (httpCode < 0) {
    Serial.println("[API Error] Connection failed, code: " + String(httpCode));
    lcdShow("Connection Error", "Check Server IP");
    beepTriple();
  } else {
    Serial.println("[API Error] HTTP " + String(httpCode));
    lcdShow("Server Error!", "Code: " + String(httpCode));
    beepTriple();
  }

  http.end();
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1200); // Post-scan cooldown
}

