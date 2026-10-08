/*
 * Smart Trolley Billing System — ESP32 Multi-Trolley Firmware v2.0
 * ================================================================
 * TROLLEY-003 — Flash this file to the FIRST trolley's ESP32.
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
 *   4. WiFiManager (by tzapu) - Version 2.0.16-rc.2 or later
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
#include <Preferences.h>
#include <WiFiManager.h>

// ══════════════════════════════════════════════════════════════════════════════
// ► TROLLEY IDENTITY — Change ONLY this line when creating a new trolley file
// ══════════════════════════════════════════════════════════════════════════════
const String TROLLEY_ID   = "TROLLEY-003";
const String TROLLEY_NAME = "Smart Trolley 003";
const String FW_VERSION   = "2.1";

// ── Wi-Fi & Server Configuration (Stored in NVS / Flash) ────────────────────
// Multi-Network Support: Add up to 10 known Wi-Fi networks here!
// The ESP32 scans and connects to whichever network is currently available.
struct KnownNetwork {
  const char* ssid;
  const char* pass;
};

const KnownNetwork knownNetworks[] = {
  { "Yogaraj",              "1234567890" },    // Current active Wi-Fi / Hotspot
  { "Nandini K Y",          "333444455555" },  // Previous hotspot
  { "Redmi 13C 5G",         "111111111" },     // Redmi hotspot
  { "motorolaedge50fusion", "111111111" },     // Motorola hotspot
  // Add more store / lab / home networks below if needed (up to 10):
  // { "Store_WiFi",        "password123" }
};
const int NUM_KNOWN_NETWORKS = sizeof(knownNetworks) / sizeof(knownNetworks[0]);

const char* defaultSSID = "Yogaraj";               // Active Wi-Fi network
const char* defaultPass = "1234567890";            // Active Wi-Fi password
char serverIP[40]       = "10.221.37.241";         // Current Flask server local IP
char serverPort[6]      = "5000";                  // Default Flask server port
Preferences preferences;                           // Non-volatile storage handler
bool shouldSaveConfig = false;

// ── API Endpoints (Dynamic based on serverIP & serverPort) ──────────────────
String BASE_URL     = "http://" + String(serverIP) + ":" + String(serverPort);
String apiAction    = BASE_URL + "/api/cart/action";
String apiReset     = BASE_URL + "/api/reset";
String apiMode      = BASE_URL + "/api/simulator/mode";
String apiHeartbeat = BASE_URL + "/api/trolley/heartbeat";
String apiRegister  = BASE_URL + "/api/trolley/register";

void updateApiEndpoints() {
  BASE_URL     = "http://" + String(serverIP) + ":" + String(serverPort);
  apiAction    = BASE_URL + "/api/cart/action";
  apiReset     = BASE_URL + "/api/reset";
  apiMode      = BASE_URL + "/api/simulator/mode";
  apiHeartbeat = BASE_URL + "/api/trolley/heartbeat";
  apiRegister  = BASE_URL + "/api/trolley/register";
  Serial.println("[CONFIG] API Base URL set to: " + BASE_URL);
}

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
LiquidCrystal_I2C* pLcd = nullptr; // Dynamically created after I2C auto-detection
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
  if (!pLcd) return;
  pLcd->setCursor(0, 0);
  String l1 = line1.substring(0, 16);
  while (l1.length() < 16) l1 += " ";
  pLcd->print(l1);

  pLcd->setCursor(0, 1);
  String l2 = line2.substring(0, 16);
  while (l2.length() < 16) l2 += " ";
  pLcd->print(l2);
}

// ── WiFiManager Callbacks (placed after LCD & Audio helpers) ───────────────
void saveConfigCallback() {
  Serial.println(F("[CONFIG] Settings saved via web portal!"));
  shouldSaveConfig = true;
}

void configModeCallback(WiFiManager *myWiFiManager) {
  Serial.println(F("[WiFiManager] Entered Config Portal Mode"));
  Serial.print(F("[WiFiManager] AP IP: "));
  Serial.println(WiFi.softAPIP());
  Serial.print(F("[WiFiManager] AP SSID: "));
  Serial.println(myWiFiManager->getConfigPortalSSID());
  lcdShow("Setup: Connect!", myWiFiManager->getConfigPortalSSID().substring(0, 16));
  beepDouble();
}

// ── Multi-Network Connection Helpers ────────────────────────────────────────
bool tryConnectToSSID(const char* ssid, const char* pass, int maxWaitSec = 15) {
  if (!ssid || strlen(ssid) == 0) return false;
  Serial.print(F("[WiFi] Connecting to: "));
  Serial.println(ssid);
  lcdShow("Connecting WiFi", String(ssid).substring(0, 16));

  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false); // Crucial for mobile hotspots: prevents sleep disconnections
  WiFi.setTxPower(WIFI_POWER_19_5dBm); // Full transmission power

  // CRITICAL: Set PMF BEFORE WiFi.begin for WPA3 / phone hotspot compatibility
  wifi_config_t conf;
  if (esp_wifi_get_config(WIFI_IF_STA, &conf) == ESP_OK) {
    conf.sta.pmf_cfg.capable = true;
    conf.sta.pmf_cfg.required = false;
    esp_wifi_set_config(WIFI_IF_STA, &conf);
  }

  if (pass && strlen(pass) > 0) {
    WiFi.begin(ssid, pass);
  } else {
    WiFi.begin(ssid);
  }

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < (maxWaitSec * 2)) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n[WiFi] Connected to " + String(ssid) + "! IP: " + WiFi.localIP().toString());
    lcdShow("WiFi Connected!", WiFi.localIP().toString());
    beepOnce();

    // Auto-align server IP subnet with local Wi-Fi subnet (e.g. 10.221.37.x)
    IPAddress myIP = WiFi.localIP();
    IPAddress srv;
    if (srv.fromString(serverIP)) {
      if (myIP[0] != srv[0] || myIP[1] != srv[1] || myIP[2] != srv[2]) {
        Serial.printf("[AUTO-IP] Updating server IP subnet from %s to %d.%d.%d.%d\n", serverIP, myIP[0], myIP[1], myIP[2], srv[3]);
        sprintf(serverIP, "%d.%d.%d.%d", myIP[0], myIP[1], myIP[2], srv[3]);
        updateApiEndpoints();
        preferences.begin("trolley-cfg", false);
        preferences.putString("server_ip", serverIP);
        preferences.end();
      }
    }

    delay(1200);
    return true;
  }
  return false;
}

bool connectToAnySavedNetwork() {
  Serial.println(F("\n[WiFi] Scanning airwaves for known networks..."));
  lcdShow("Checking WiFi...", "Scanning...");

  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);

  int n = WiFi.scanNetworks(false, true); // show_hidden = true for phone hotspots
  Serial.print(F("[WiFi] Nearby networks detected: "));
  Serial.println(n);

  preferences.begin("trolley-cfg", true);
  String savedSSID = preferences.getString("wifi_ssid", defaultSSID);
  String savedPass = preferences.getString("wifi_pass", defaultPass);
  preferences.end();

  // 1. If the saved / active network is detected in the air scan, connect immediately
  if (n > 0 && savedSSID.length() > 0) {
    for (int i = 0; i < n; i++) {
      if (WiFi.SSID(i) == savedSSID) {
        Serial.println("[WiFi] Detected saved network in air: " + savedSSID);
        if (tryConnectToSSID(savedSSID.c_str(), savedPass.c_str(), 15)) {
          return true;
        }
      }
    }
  }

  // 2. Check each known network in the list against scan results
  if (n > 0) {
    for (int j = 0; j < NUM_KNOWN_NETWORKS; j++) {
      const char* candSSID = knownNetworks[j].ssid;
      const char* candPass = knownNetworks[j].pass;
      if (candSSID && strlen(candSSID) > 0) {
        for (int i = 0; i < n; i++) {
          if (WiFi.SSID(i) == candSSID) {
            Serial.println("[WiFi] Detected known network: " + String(candSSID));
            if (tryConnectToSSID(candSSID, candPass, 15)) {
              preferences.begin("trolley-cfg", false);
              preferences.putString("wifi_ssid", candSSID);
              preferences.putString("wifi_pass", candPass);
              preferences.end();
              return true;
            }
          }
        }
      }
    }
  }

  // 3. Fallback: Direct probe connection to saved network
  // (Phone hotspots often suppress broadcast beacons to save battery, but respond to direct probes!)
  if (savedSSID.length() > 0) {
    Serial.println("[WiFi] Direct connection probe to saved network: " + savedSSID);
    if (tryConnectToSSID(savedSSID.c_str(), savedPass.c_str(), 12)) {
      return true;
    }
  }

  // 4. Fallback: Direct probe to other known networks
  for (int j = 0; j < NUM_KNOWN_NETWORKS; j++) {
    const char* candSSID = knownNetworks[j].ssid;
    const char* candPass = knownNetworks[j].pass;
    if (candSSID && strlen(candSSID) > 0 && String(candSSID) != savedSSID) {
      Serial.println("[WiFi] Direct connection probe to: " + String(candSSID));
      if (tryConnectToSSID(candSSID, candPass, 10)) {
        preferences.begin("trolley-cfg", false);
        preferences.putString("wifi_ssid", candSSID);
        preferences.putString("wifi_pass", candPass);
        preferences.end();
        return true;
      }
    }
  }

  return false;
}

// ── Wi-Fi Reconnect (Periodic check) ───────────────────────────────────────
void reconnectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println(F("\n[WiFi] Connection lost — searching for saved networks..."));
  if (connectToAnySavedNetwork()) {
    registerWithServer();
    sendHeartbeat();
    delay(800);
    lcdShow("Mode: " + currentMode, "Scan card...");
  } else {
    wifiConnected = false;
    Serial.println(F("[WiFi] All saved networks currently unreachable."));
    lcdShow("WiFi Offline", "Retrying...");
  }
}

// ── Register Trolley on Server ─────────────────────────────────────────────
void registerWithServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  http.begin(client, apiRegister);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Connection", "close");
  http.setTimeout(5000);

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

  WiFiClient client;
  HTTPClient http;
  http.begin(client, apiHeartbeat);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Connection", "close");
  http.setTimeout(5000);

  int batteryPct = 85;

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
    Serial.println("[HEARTBEAT] Code: " + String(code));
  }
  http.end();
}

// ── Sync Mode with Server ──────────────────────────────────────────────────
void syncModeWithServer(String mode) {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  http.begin(client, apiMode);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Connection", "close");
  http.setTimeout(3000);

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
  addIdleState    = HIGH;
  removeIdleState = HIGH;
  resetIdleState  = HIGH;

  delay(400);
  Serial.println("\n==========================================");
  Serial.println("  Smart Trolley System — " + TROLLEY_ID + "  ");
  Serial.println("==========================================");

  // 1. LCD Init with Auto-I2C Address Detection (0x27 vs 0x3F)
  delay(300); // Allow LCD controller power rails to stabilize
  Wire.begin(I2C_SDA, I2C_SCL);
  delay(100);

  byte lcdAddr = 0;
  // Test 0x27
  Wire.beginTransmission(0x27);
  if (Wire.endTransmission() == 0) {
    lcdAddr = 0x27;
  } else {
    // Test 0x3F
    Wire.beginTransmission(0x3F);
    if (Wire.endTransmission() == 0) {
      lcdAddr = 0x3F;
    } else {
      // Scan standard I2C range (0x20 to 0x3F)
      for (byte a = 0x20; a <= 0x3F; a++) {
        Wire.beginTransmission(a);
        if (Wire.endTransmission() == 0) {
          lcdAddr = a;
          break;
        }
      }
    }
  }

  if (lcdAddr == 0) {
    lcdAddr = 0x27; // Fallback default
    Serial.println(F("[LCD WARNING] No I2C display responding at 0x27 or 0x3F! Check SDA(21), SCL(22), and 5V."));
  } else {
    Serial.print(F("[LCD] Auto-detected I2C display at address: 0x"));
    Serial.println(lcdAddr, HEX);
  }

  pLcd = new LiquidCrystal_I2C(lcdAddr, 16, 2);
  pLcd->init();
  delay(50);
  pLcd->init(); // Dual-init ensures HD44780 controller reliably enters 4-bit mode
  pLcd->backlight();
  pLcd->clear();
  lcdShow(TROLLEY_ID, "Ready to Scan");
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

  // 3. Load Saved Server & Wi-Fi Settings from Flash (Preferences)
  preferences.begin("trolley-cfg", false);
  String storedIP   = preferences.getString("server_ip", "");
  String storedPort = preferences.getString("server_port", "");
  // Check if stored IP has a valid non-empty string and not the obsolete default
  if (storedIP.length() > 0 && storedIP != "10.175.93.241") {
    strncpy(serverIP, storedIP.c_str(), sizeof(serverIP) - 1);
  } else {
    preferences.putString("server_ip", serverIP);
  }
  if (storedPort.length() > 0) {
    strncpy(serverPort, storedPort.c_str(), sizeof(serverPort) - 1);
  } else {
    preferences.putString("server_port", serverPort);
  }
  preferences.end();
  updateApiEndpoints();

  // Check if RESET button is held down at startup (to force Config Portal)
  bool buttonPressed = (digitalRead(RESET_BTN) == LOW);

  // If RESET button is held, clear cached Wi-Fi to force setup portal
  if (buttonPressed) {
    Serial.println(F("[CONFIG] RESET button held at boot! Clearing Wi-Fi cache & opening Setup Portal..."));
    preferences.begin("trolley-cfg", false);
    preferences.remove("wifi_ssid");
    preferences.remove("wifi_pass");
    preferences.end();
    lcdShow("Reset Held", "Opening Setup...");
    beepTriple();
    delay(1000);
  } else {
    Serial.println(F("[WiFi] Auto-connecting to saved Wi-Fi networks..."));
    if (connectToAnySavedNetwork()) {
      registerWithServer();
      sendHeartbeat();
      delay(800);
      lcdShow("Mode: " + currentMode, "Scan card...");
      return; // Fully connected wirelessly! Skip captive portal.
    } else {
      Serial.println(F("\n[WiFi] Saved networks unavailable. Starting Setup Portal..."));
    }
  }

  // 4. Wi-Fi Setup using WiFiManager (On-Demand Captive Portal / Fallback)
  String apName = "Trolley003-Setup";
  Serial.println(F("[WiFi] Launching Setup Access Point: Trolley003-Setup..."));
  lcdShow("Setup: Connect!", apName);
  beepDouble();

  WiFi.disconnect(true);
  delay(150);
  WiFi.mode(WIFI_AP_STA);
  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);



  WiFiManager wm;
  wm.setAPCallback(configModeCallback);
  wm.setSaveConfigCallback(saveConfigCallback);
  wm.setConnectTimeout(30);        // 30s timeout allows mobile hotspots to complete DHCP
  wm.setConfigPortalTimeout(300);  // 5 minutes active portal (plenty of time to configure)

  // Custom parameters for Flask server IP & Port
  WiFiManagerParameter custom_server_ip("server_ip", "Flask Server IP (e.g. 10.221.37.241)", serverIP, 40);
  WiFiManagerParameter custom_server_port("server_port", "Flask Server Port", serverPort, 6);
  wm.addParameter(&custom_server_ip);
  wm.addParameter(&custom_server_port);

  bool portalSuccess = wm.startConfigPortal(apName.c_str());

  // If button was pressed during boot, wait for user to release it to avoid accidental cart reset
  if (buttonPressed) {
    while (digitalRead(RESET_BTN) == LOW) {
      delay(50);
    }
    delay(200);
  }

  // If new credentials / parameters were saved via portal, write them to Flash
  if (shouldSaveConfig) {
    strncpy(serverIP, custom_server_ip.getValue(), sizeof(serverIP) - 1);
    serverIP[sizeof(serverIP) - 1] = '\0';
    strncpy(serverPort, custom_server_port.getValue(), sizeof(serverPort) - 1);
    serverPort[sizeof(serverPort) - 1] = '\0';

    preferences.begin("trolley-cfg", false);
    preferences.putString("server_ip", serverIP);
    preferences.putString("server_port", serverPort);
    preferences.end();
    Serial.println("[CONFIG] Saved new Server IP: " + String(serverIP) + ":" + String(serverPort));
    updateApiEndpoints();
  }

  if (portalSuccess && WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n[WiFi] Connected! IP: " + WiFi.localIP().toString());
    lcdShow("WiFi Connected!", WiFi.localIP().toString());
    beepOnce();
    delay(1500);

    // Save active Wi-Fi credentials to Preferences for ultra-fast boot reconnection
    preferences.begin("trolley-cfg", false);
    if (WiFi.SSID().length() > 0) {
      preferences.putString("wifi_ssid", WiFi.SSID());
      if (WiFi.psk().length() > 0) {
        preferences.putString("wifi_pass", WiFi.psk());
      }
      Serial.println("[CONFIG] Saved Wi-Fi to flash: " + WiFi.SSID());
    }
    preferences.end();

    // Register with server and send first heartbeat
    registerWithServer();
    sendHeartbeat();
  } else {
    wifiConnected = false;
    Serial.println(F("\n[WiFi] Failed/Timeout. Operating in offline/retry mode."));
    lcdShow("WiFi Offline", "Retrying...");
    beepDouble();
  }

  delay(1000);
  lcdShow("Mode: ADD", "Scan card...");
}

// ── Main Loop ──────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // ── 0. Serial Commands (Remote Config from Web Dashboard via USB) ─────────
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.startsWith("WIFI_CFG:")) {
      // Format: WIFI_CFG:ssid|password|serverIP|serverPort
      String payload = line.substring(9);
      int p1 = payload.indexOf('|');
      int p2 = payload.indexOf('|', p1 + 1);
      int p3 = payload.indexOf('|', p2 + 1);

      if (p1 > 0) {
        String newSSID = payload.substring(0, p1);
        String newPass = (p2 > 0) ? payload.substring(p1 + 1, p2) : payload.substring(p1 + 1);
        String newIP   = (p2 > 0 && p3 > 0) ? payload.substring(p2 + 1, p3) : ((p2 > 0) ? payload.substring(p2 + 1) : String(serverIP));
        String newPort = (p3 > 0) ? payload.substring(p3 + 1) : String(serverPort);

        newIP.toCharArray(serverIP, sizeof(serverIP));
        newPort.toCharArray(serverPort, sizeof(serverPort));

        preferences.begin("trolley-cfg", false);
        preferences.putString("server_ip", serverIP);
        preferences.putString("server_port", serverPort);
        preferences.putString("wifi_ssid", newSSID);
        preferences.putString("wifi_pass", newPass);
        preferences.end();
        updateApiEndpoints();

        Serial.println("[WIFI_CFG] Received via USB: SSID=" + newSSID + " Server=" + String(serverIP) + ":" + String(serverPort));
        lcdShow("New WiFi Config!", newSSID.substring(0, 16));
        beepDouble();
        delay(1200);
        lcdShow("Connecting WiFi", "Please wait...");

        if (tryConnectToSSID(newSSID.c_str(), newPass.c_str(), 15)) {
          registerWithServer();
          sendHeartbeat();
        } else {
          wifiConnected = false;
          Serial.println(F("\n[WiFi] Connection failed!"));
          lcdShow("WiFi Failed!", "Check Password");
          beepTriple();
          delay(1500);
        }
        lcdShow("Mode: " + currentMode, "Scan card...");
      }
    }
  }

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
  bool addActive    = (digitalRead(ADD_BTN)    == LOW);
  bool removeActive = (digitalRead(REMOVE_BTN) == LOW);
  bool resetActive  = (digitalRead(RESET_BTN)  == LOW);

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

  // RESET Button: Require intentional 2.5s continuous press to prevent brownouts/glitches from wiping cart
  static unsigned long resetPressStartTime = 0;
  static bool resetHeldTriggered = false;

  if (now > 4000 && resetActive) {
    if (resetPressStartTime == 0) {
      resetPressStartTime = now;
      resetHeldTriggered = false;
    } else if (!resetHeldTriggered && (now - resetPressStartTime >= 2500)) {
      resetHeldTriggered = true;
      Serial.println("[BTN] Intentional 2.5s RESET button hold confirmed!");
      beepDouble();
      lcdShow("Resetting Cart", "Please wait...");

      if (WiFi.status() == WL_CONNECTED) {
        WiFiClient client;
        HTTPClient http;
        http.begin(client, apiReset);
        http.addHeader("Content-Type", "application/json");
        http.addHeader("Connection", "close");
        http.setTimeout(5000);

        StaticJsonDocument<128> doc;
        doc["trolley_id"] = TROLLEY_ID;
        doc["manual"] = true;
        String payload;
        serializeJson(doc, payload);

        int responseCode = http.POST(payload);
        if (responseCode == 200) {
          lcdShow("Cart Reset!", "Total: Rs.0.00");
          beepOnce();
        } else {
          lcdShow("Reset Local", "Err: " + String(responseCode));
        }
        http.end();
      } else {
        lcdShow("Reset Local", "WiFi offline");
      }

      delay(1500);
      currentMode = "ADD";
      lcdShow("Mode: ADD", "Scan card...");
    }
  } else {
    resetPressStartTime = 0;
    resetHeldTriggered = false;
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
  WiFiClient client;
  HTTPClient http;
  http.begin(client, apiAction);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Connection", "close");
  http.setTimeout(5000);

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
    lcdShow("Connection Error", "IP: " + String(serverIP));
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
