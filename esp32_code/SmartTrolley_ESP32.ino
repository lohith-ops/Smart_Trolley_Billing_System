/*
 * Smart Trolley Billing System — ESP32 Wireless Firmware
 * =======================================================
 * Communicates with the Flask REST API over Wi-Fi.
 * 
 * Required Arduino IDE Libraries:
 *   1. MFRC522 (by GithubCommunity)
 *   2. LiquidCrystal_I2C (by Frank de Brabander)
 *   3. ArduinoJson (by Benoit Blanchon) - IMPORTANT: Install Version 6 or 7
 * 
 * Hardware Connections (NodeMCU ESP32 Pinout):
 *   - MFRC522 RFID:
 *       VCC  -> 3.3V (Do not connect to 5V!)
 *       GND  -> GND
 *       MISO -> GPIO 19
 *       MOSI -> GPIO 23
 *       SCK  -> GPIO 18
 *       SDA  -> GPIO 5
 *       RST  -> GPIO 4
 *   - I2C LCD Display (16x2):
 *       VCC  -> 5V (from Vin or external 5V power)
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
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// ── Wi-Fi Configuration ────────────────────────────────────────────────────
const char* ssid     = "YOUR_WIFI_SSID";     // Enter your Wi-Fi SSID
const char* password = "YOUR_WIFI_PASSWORD"; // Enter your Wi-Fi Password
const String serverIP = "192.168.1.100";     // Enter your Host PC Local IP address
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

// ── Global Objects ─────────────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2); // Change address to 0x3F if LCD stays blank
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ── State Variables ────────────────────────────────────────────────────────
String currentMode = "ADD"; // "ADD" or "REMOVE"
bool isOffline = false;
unsigned long lastPingTime = 0;
const unsigned long PING_INTERVAL_MS = 8000; // Check server health every 8s

// Debounce timings
unsigned long lastDebounceAdd    = 0;
unsigned long lastDebounceRemove = 0;
unsigned long lastDebounceReset  = 0;
const unsigned long DEBOUNCE_MS  = 300;

// ── Audio Indicator Helper Functions ───────────────────────────────────────
void beepOnce() {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(150);
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
  
  String jsonDoc = "{\"mode\":\"" + mode + "\"}";
  int responseCode = http.POST(jsonDoc);
  
  http.end();
}

// ── Initialize Setup ───────────────────────────────────────────────────────
void setup() {
  pinMode(ADD_BTN,    INPUT_PULLUP);
  pinMode(REMOVE_BTN, INPUT_PULLUP);
  pinMode(RESET_BTN,  INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.begin(115200);

  // LCD startup screen
  lcd.init();
  lcd.backlight();
  lcdShow("Smart Trolley", "Wireless ESP32");
  delay(2000);

  // Connect to Wi-Fi
  lcdShow("Connecting to...", ssid);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    lcdShow("WiFi Connected!", WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi Connection Failed!");
    lcdShow("WiFi Error!", "Check SSID/PASS");
  }
  delay(2000);

  // SPI + RFID setup
  SPI.begin();
  mfrc522.PCD_Init();
  
  // Verify MFRC522 self-check
  byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  Serial.print("MFRC522 Version: 0x");
  Serial.println(v, HEX);
  if (v == 0x91 || v == 0x92) {
    lcdShow("RFID Status: OK", "Mode: ADD");
  } else {
    lcdShow("RFID Error!", "Check SPI Wiring");
    delay(2000);
  }
  
  delay(1500);
  lcdShow("Mode: ADD", "Scan card...");
  beepOnce();
}

// ── Main Loop ──────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // ── 1. Wi-Fi Status Check ────────────────────────────────────────────────
  if (WiFi.status() != WL_CONNECTED) {
    if (!isOffline) {
      isOffline = true;
      lcdShow("WiFi Offline", "Reconnecting...");
      beepDouble();
    }
    // Attempt background reconnection
    WiFi.begin(ssid, password);
    delay(1000);
    return;
  }

  // ── 2. Server Ping/Heartbeat Connection Health ───────────────────────────
  if (now - lastPingTime > PING_INTERVAL_MS) {
    lastPingTime = now;
    HTTPClient http;
    http.begin(apiDashboard);
    http.setTimeout(1500); // 1.5s timeout for fast response
    int httpCode = http.GET();
    
    if (httpCode == 200) {
      if (isOffline) {
        isOffline = false;
        lcdShow("Server Online!", "Mode: " + currentMode);
        beepOnce();
        delay(1500);
        lcdShow("Mode: " + currentMode, "Scan card...");
      }
    } else {
      if (!isOffline) {
        isOffline = true;
        lcdShow("Server Offline", "Reconnecting...");
        beepTriple();
      }
    }
    http.end();
  }

  // If server is offline, block inputs until connection is restored
  if (isOffline) {
    delay(500);
    return;
  }

  // ── 3. Button Inputs Debounce Checking ───────────────────────────────────
  if (digitalRead(ADD_BTN) == LOW && (now - lastDebounceAdd > DEBOUNCE_MS)) {
    lastDebounceAdd = now;
    currentMode = "ADD";
    beepOnce();
    lcdShow("Mode: ADD", "Scan card...");
    syncModeWithServer("ADD");
  }

  if (digitalRead(REMOVE_BTN) == LOW && (now - lastDebounceRemove > DEBOUNCE_MS)) {
    lastDebounceRemove = now;
    currentMode = "REMOVE";
    beepOnce();
    lcdShow("Mode: REMOVE", "Scan card...");
    syncModeWithServer("REMOVE");
  }

  if (digitalRead(RESET_BTN) == LOW && (now - lastDebounceReset > DEBOUNCE_MS)) {
    lastDebounceReset = now;
    beepDouble();
    lcdShow("Resetting Cart", "Please wait...");
    
    // Call server reset API
    HTTPClient http;
    http.begin(apiReset);
    int responseCode = http.POST("{}");
    
    if (responseCode == 200) {
      lcdShow("Cart Reset!", "Total: Rs.0.00");
    } else {
      lcdShow("Reset Error!", "Code: " + String(responseCode));
    }
    http.end();
    
    delay(2000);
    currentMode = "ADD";
    lcdShow("Mode: ADD", "Scan card...");
  }

  // ── 4. RFID Card Scanner Reader ──────────────────────────────────────────
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

  Serial.println("RFID Tag Scanned: " + uid);
  lcdShow("Scanning Tag...", uid);

  // Send request to Server
  HTTPClient http;
  http.begin(apiAction);
  http.addHeader("Content-Type", "application/json");

  // Create JSON Payload
  StaticJsonDocument<128> doc;
  doc["action"] = currentMode;
  doc["uid"] = uid;
  String requestPayload;
  serializeJson(doc, requestPayload);

  int httpCode = http.POST(requestPayload);

  if (httpCode == 200) {
    String response = http.getString();
    Serial.println("Response: " + response);

    // Parse Response
    StaticJsonDocument<256> resDoc;
    DeserializationError error = deserializeJson(resDoc, response);

    if (!error) {
      bool success = resDoc["success"];
      if (success) {
        String pName = resDoc["product"]["name"];
        float total  = resDoc["cart"]["total"];
        
        String symbol = (currentMode == "ADD") ? "+" : "-";
        String line1 = symbol + " " + pName;
        String line2 = "Total: Rs." + String(total, 2);
        
        lcdShow(line1, line2);
        beepOnce();
      } else {
        lcdShow("Scan Failed!", "Try Again");
        beepTriple();
      }
    } else {
      lcdShow("JSON Parse Error", "Bad Response");
      beepTriple();
    }
  } 
  else if (httpCode == 404) {
    // Unregistered / Unknown Product scanned
    lcdShow("Unknown Card!", "Check Dashboard");
    beepTriple();
  } 
  else {
    // Other network errors
    lcdShow("Server Error!", "Code: " + String(httpCode));
    beepTriple();
  }

  http.end();

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(2000); // Cooldown delay to prevent double scans of the same card
}
