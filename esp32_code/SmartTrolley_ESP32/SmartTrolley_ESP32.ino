/*
 * Smart Trolley Billing System — ESP32 Wireless Firmware (Robust & Non-Blocking)
 * ==============================================================================
 * Communicates with the Flask REST API over Wi-Fi.
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
 *       ADD Button    -> GPIO 13 (Connect other leg to GND)
 *       REMOVE Button -> GPIO 12 (Connect other leg to GND)
 *       RESET Button  -> GPIO 14 (Connect other leg to GND)
 *   - Buzzer:
 *       Positive (+) -> GPIO 15 (Connect through 220-ohm resistor)
 *       Negative (-) -> GND
 */

#include <WiFi.h>
#include <esp_wifi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <Wire.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// ── Wi-Fi Configuration ────────────────────────────────────────────────────
const char* ssid     = "Redmi 13C 5G";       // Matches your Hotspot SSID exactly
const char* password = "111111111";          // Change to your Wi-Fi Password
const String serverIP = "10.135.126.241";    // Your PC's Local IP address on hotspot
const int serverPort = 5000;                 // Flask Server Port

// API Endpoints
const String apiAction    = "http://" + serverIP + ":" + String(serverPort) + "/api/cart/action";
const String apiReset     = "http://" + serverIP + ":" + String(serverPort) + "/api/reset";
const String apiMode      = "http://" + serverIP + ":" + String(serverPort) + "/api/simulator/mode";
const String apiDashboard = "http://" + serverIP + ":" + String(serverPort) + "/api/dashboard";

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
LiquidCrystal_I2C lcd(0x27, 16, 2); // Change address to 0x3F if LCD screen is blank
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ── State Variables ────────────────────────────────────────────────────────
String currentMode = "ADD"; // "ADD" or "REMOVE"
bool wifiConnected = false;
unsigned long lastPingTime = 0;
const unsigned long PING_INTERVAL_MS = 10000; // Ping server every 10s

// Debounce timings
unsigned long lastDebounceAdd    = 0;
unsigned long lastDebounceRemove = 0;
unsigned long lastDebounceReset  = 0;
const unsigned long DEBOUNCE_MS  = 300;

// ── Audio Indicator Helper Functions ───────────────────────────────────────
void beepOnce() {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(120);
  digitalWrite(BUZZER_PIN, LOW);
}

void beepDouble() {
  beepOnce();
  delay(80);
  beepOnce();
}

void beepTriple() {
  beepOnce();
  delay(80);
  beepOnce();
  delay(80);
  beepOnce();
}

// ── LCD Output Helper ──────────────────────────────────────────────────────
void lcdShow(String line1, String line2 = "") {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  if (line2.length() > 0) {
    lcd.setCursor(0, 1);
    lcd.print(line2.substring(0, 16));
  }
}

// ── Sync Mode to Web Simulator ─────────────────────────────────────────────
void syncModeWithServer(String mode) {
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  http.begin(apiMode);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2000);
  
  String jsonDoc = "{\"mode\":\"" + mode + "\"}";
  http.POST(jsonDoc);
  http.end();
}

// ── Initialize Setup ───────────────────────────────────────────────────────
void setup() {
  // Config Pin Modes with Internal Pull-Ups
  pinMode(ADD_BTN,    INPUT_PULLUP);
  pinMode(REMOVE_BTN, INPUT_PULLUP);
  pinMode(RESET_BTN,  INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.begin(115200);
  delay(500);
  Serial.println("\n==========================================");
  Serial.println("   Smart Trolley System — ESP32 Starting  ");
  Serial.println("==========================================");

  // 1. Initialize I2C Bus & LCD
  Wire.begin(I2C_SDA, I2C_SCL);
  lcd.init();
  lcd.backlight();
  lcdShow("Smart Trolley", "Wireless ESP32");
  beepOnce();
  delay(1500);

  // 2. Initialize SPI & MFRC522 RFID Reader
  SPI.begin(18, 19, 23, 5); // SCK=18, MISO=19, MOSI=23, SS=5
  mfrc522.PCD_Init();
  mfrc522.PCD_SetAntennaGain(mfrc522.RxGain_max); // Set max gain for reliable card reading
  
  byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  Serial.print("[RFID] MFRC522 Version: 0x");
  Serial.println(v, HEX);
  if (v == 0x91 || v == 0x92) {
    Serial.println("[RFID] Reader initialized successfully!");
    lcdShow("RFID Status: OK", "Mode: ADD");
  } else {
    Serial.println("[RFID WARNING] Unknown RFID chip or wiring issue! Check 3.3V power.");
    lcdShow("RFID Check Wire", "Power must be 3V3");
    delay(2000);
  }

  // 3. Connect to Wi-Fi Network
  WiFi.mode(WIFI_STA);
  wifi_country_t country = {
    .cc = "IN",
    .schan = 1,
    .nchan = 13,
    .policy = WIFI_COUNTRY_POLICY_AUTO
  };
  esp_wifi_set_country(&country);
  WiFi.disconnect();
  delay(100);

  Serial.println("[WiFi] Scanning nearby 2.4GHz networks...");
  lcdShow("Scanning WiFi..", "Please wait");
  int n = WiFi.scanNetworks();
  Serial.print("[WiFi Scan] Found ");
  Serial.print(n);
  Serial.println(" networks:");
  bool targetFound = false;
  for (int i = 0; i < n; ++i) {
    String foundSSID = WiFi.SSID(i);
    int rssi = WiFi.RSSI(i);
    Serial.print("   ");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.print(foundSSID);
    Serial.print(" (");
    Serial.print(rssi);
    Serial.println(" dBm)");
    if (foundSSID == ssid) {
      targetFound = true;
    }
  }

  if (!targetFound) {
    Serial.println("[WiFi WARNING] Target SSID '" + String(ssid) + "' was NOT found in 2.4GHz scan!");
    Serial.println("[HINT] If using a phone hotspot, change AP Band from 5.0 GHz to 2.4 GHz in Hotspot Settings!");
  }

  Serial.print("[WiFi] Connecting to: ");
  Serial.println(ssid);
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
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
    lcdShow("WiFi Connected!", WiFi.localIP().toString());
    beepOnce();
  } else {
    wifiConnected = false;
    Serial.println("\n[WiFi] Connection failed! Operating in standalone/retry mode.");
    lcdShow("WiFi Offline", "Mode: ADD");
    beepDouble();
  }
  
  delay(1500);
  lcdShow("Mode: ADD", "Scan card...");
}

// ── Main Loop ──────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // ── 1. Non-Blocking Wi-Fi Status & Health Check ─────────────────────────
  if (now - lastPingTime > PING_INTERVAL_MS) {
    lastPingTime = now;
    if (WiFi.status() != WL_CONNECTED) {
      wifiConnected = false;
      Serial.println("[WiFi] Reconnecting in background...");
      WiFi.disconnect();
      WiFi.reconnect();
    } else {
      wifiConnected = true;
    }
  }

  // ── 2. Button Inputs (Always active, non-blocking) ───────────────────────
  static unsigned long lastBtnDiag = 0;
  if (now - lastBtnDiag > 3000) {
    lastBtnDiag = now;
    Serial.print("[BTN DIAGNOSTIC] ADD(GPIO13)=");
    Serial.print(digitalRead(ADD_BTN));
    Serial.print(" | REMOVE(GPIO12)=");
    Serial.print(digitalRead(REMOVE_BTN));
    Serial.print(" | RESET(GPIO14)=");
    Serial.println(digitalRead(RESET_BTN));
  }

  if (digitalRead(ADD_BTN) == LOW && (now - lastDebounceAdd > DEBOUNCE_MS)) {
    lastDebounceAdd = now;
    currentMode = "ADD";
    Serial.println("[BTN] ADD button pressed");
    beepOnce();
    lcdShow("Mode: ADD", "Scan card...");
    syncModeWithServer("ADD");
  }

  if (digitalRead(REMOVE_BTN) == LOW && (now - lastDebounceRemove > DEBOUNCE_MS)) {
    lastDebounceRemove = now;
    currentMode = "REMOVE";
    Serial.println("[BTN] REMOVE button pressed");
    beepOnce();
    lcdShow("Mode: REMOVE", "Scan card...");
    syncModeWithServer("REMOVE");
  }

  if (digitalRead(RESET_BTN) == LOW && (now - lastDebounceReset > DEBOUNCE_MS)) {
    lastDebounceReset = now;
    Serial.println("[BTN] RESET button pressed");
    beepDouble();
    lcdShow("Resetting Cart", "Please wait...");
    
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(apiReset);
      http.setTimeout(2000);
      int responseCode = http.POST("{}");
      if (responseCode == 200) {
        lcdShow("Cart Reset!", "Total: Rs.0.00");
      } else {
        lcdShow("Reset Local", "Total: Rs.0.00");
      }
      http.end();
    } else {
      lcdShow("Reset Local", "Total: Rs.0.00");
    }
    
    delay(1500);
    currentMode = "ADD";
    lcdShow("Mode: ADD", "Scan card...");
  }

  // ── 3. RFID Card Reader (Always active, non-blocking) ────────────────────
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Format Tag UID to "XX XX XX XX" Hex string
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (i > 0) uid += " ";
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  Serial.println("[RFID] Scanned Tag UID: " + uid);
  lcdShow("Scanning Tag...", uid);
  beepOnce();

  // If Wi-Fi is disconnected, show scanned UID on LCD so user knows RFID hardware is working!
  if (WiFi.status() != WL_CONNECTED) {
    lcdShow("Tag: " + uid, "WiFi Disconnected");
    beepDouble();
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(1500);
    lcdShow("Mode: " + currentMode, "Scan card...");
    return;
  }

  // Send request to Flask REST API Server
  HTTPClient http;
  http.begin(apiAction);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000); // 3s HTTP timeout

  // Create JSON Payload
  StaticJsonDocument<128> doc;
  doc["action"] = currentMode;
  doc["uid"] = uid;
  String requestPayload;
  serializeJson(doc, requestPayload);

  int httpCode = http.POST(requestPayload);

  if (httpCode == 200) {
    String response = http.getString();
    Serial.println("[API] Server Response: " + response);

    StaticJsonDocument<256> resDoc;
    DeserializationError error = deserializeJson(resDoc, response);

    if (!error && resDoc["success"].as<bool>()) {
      String pName = resDoc["product"]["name"].as<String>();
      float total  = resDoc["cart"]["total"].as<float>();
      
      String symbol = (currentMode == "ADD") ? "+" : "-";
      String line1 = symbol + " " + pName;
      String line2 = "Total: Rs." + String(total, 2);
      
      lcdShow(line1, line2);
      beepOnce();
    } else {
      lcdShow("Scan Error!", "Try Again");
      beepTriple();
    }
  } 
  else if (httpCode == 404) {
    // Unregistered / Unknown Product scanned
    Serial.println("[API] Unknown Card Scanned: " + uid);
    lcdShow("Unknown Card!", "Check Dashboard");
    beepTriple();
  } 
  else {
    // Other network errors
    Serial.println("[API Error] Code: " + String(httpCode));
    lcdShow("Server Error!", "Code: " + String(httpCode));
    beepTriple();
  }

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1500); // Cooldown delay to prevent rapid double-scanning of the same card
}
