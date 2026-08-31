/*
 * Smart Trolley Billing System — Arduino Firmware (Universal & Fail-Safe)
 * =======================================================================
 * Supported Serial Protocol:
 *   Arduino → Python:
 *     "UID:XX XX XX XX"   — RFID card scanned (uppercase hex, space-separated)
 *     "MODE:ADD"          — Add button pressed
 *     "MODE:REMOVE"       — Remove button pressed
 *     "RESET"             — Reset button pressed
 *
 *   Python → Arduino:
 *     "LCD:Line1|Line2"   — Show 2-line text on LCD
 *     "BEEP:<count>"      — Beep buzzer
 *
 * Pins: ADD=3, REMOVE=2, RESET=4, BUZZER=5, SS=10, RST=9
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <MFRC522.h>
#include <SPI.h>

// ── LCD Setup (0x27 or 0x3F) ──────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ── Pin Definitions ────────────────────────────────────────────────────────
const int ADD_BTN    = 3;
const int REMOVE_BTN = 2;
const int RESET_BTN  = 4;
const int BUZZER_PIN = 5;

#define SS_PIN  10
#define RST_PIN  9
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ── State Variables ────────────────────────────────────────────────────────
String currentMode = "ADD";
unsigned long lastHeartbeatTime = 0;
unsigned long lastDiagTime = 0;

// Auto-detected idle pin states (determines unpressed logic)
int addIdleState    = HIGH;
int removeIdleState = HIGH;
int resetIdleState  = HIGH;

// Debounce timing
unsigned long lastDebounceAdd    = 0;
unsigned long lastDebounceRemove = 0;
unsigned long lastDebounceReset  = 0;
const unsigned long DEBOUNCE_MS  = 250;

// ── Helpers ────────────────────────────────────────────────────────────────
void beepOnce() {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(100);
  digitalWrite(BUZZER_PIN, LOW);
}

void beepDouble() {
  beepOnce();
  delay(80);
  beepOnce();
}

void lcdShow(String line1, String line2 = "") {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  if (line2.length() > 0) {
    lcd.setCursor(0, 1);
    lcd.print(line2.substring(0, 16));
  }
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  // Try internal pullup first
  pinMode(ADD_BTN,    INPUT_PULLUP);
  pinMode(REMOVE_BTN, INPUT_PULLUP);
  pinMode(RESET_BTN,  INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.begin(9600);

  // Read initial unpressed pin states
  delay(50);
  addIdleState    = digitalRead(ADD_BTN);
  removeIdleState = digitalRead(REMOVE_BTN);
  resetIdleState  = digitalRead(RESET_BTN);

  // LCD init
  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcdShow("Smart Trolley", "System Starting");
  beepOnce();
  delay(1000);

  // SPI + RFID
  SPI.begin();
  mfrc522.PCD_Init();
  mfrc522.PCD_SetAntennaGain(mfrc522.RxGain_max);

  lcdShow("Mode: ADD", "Scan card...");
  lastHeartbeatTime = millis();
}

// ── Main Loop ──────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // ── 1. SERIAL COMMANDS FROM PYTHON ───────────────────────────────────────
  if (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();

    if (msg.length() > 0) {
      lastHeartbeatTime = millis();
    }

    if (msg.startsWith("LCD:")) {
      int sep = msg.indexOf('|');
      if (sep != -1) {
        lcdShow(msg.substring(4, sep), msg.substring(sep + 1));
      } else {
        lcdShow(msg.substring(4));
      }
    }
    else if (msg.startsWith("BEEP:")) {
      int count = msg.substring(5).toInt();
      for (int i = 0; i < count; i++) {
        if (i > 0) delay(80);
        beepOnce();
      }
    }
    else if (msg == "CMD:RESET") {
      lcdShow("Cart Reset!", "Total: Rs.0.00");
      delay(1200);
      lcdShow("Mode: " + currentMode, "Scan card...");
    }
  }

  // ── 2. DIAGNOSTIC PRINTING (Every 2 seconds) ─────────────────────────────
  if (now - lastDiagTime > 2000) {
    lastDiagTime = now;
    Serial.print("[BTN DIAG] ADD(D3)=");
    Serial.print(digitalRead(ADD_BTN));
    Serial.print(" | REMOVE(D2)=");
    Serial.print(digitalRead(REMOVE_BTN));
    Serial.print(" | RESET(D4)=");
    Serial.println(digitalRead(RESET_BTN));
  }

  // ── 3. UNIVERSAL DUAL-POLARITY BUTTON DETECTION ──────────────────────────
  // Triggers when pin state changes from idle state (works with GND or 5V wiring)
  bool addActive    = (digitalRead(ADD_BTN) != addIdleState);
  bool removeActive = (digitalRead(REMOVE_BTN) != removeIdleState);
  bool resetActive  = (digitalRead(RESET_BTN) != resetIdleState);

  // ADD Button Pressed
  if (addActive && (now - lastDebounceAdd > DEBOUNCE_MS)) {
    lastDebounceAdd = now;
    currentMode = "ADD";
    Serial.println("MODE:ADD");
    beepOnce();
    lcdShow("Mode: ADD", "Scan card...");
  }

  // REMOVE Button Pressed
  if (removeActive && (now - lastDebounceRemove > DEBOUNCE_MS)) {
    lastDebounceRemove = now;
    currentMode = "REMOVE";
    Serial.println("MODE:REMOVE");
    beepOnce();
    lcdShow("Mode: REMOVE", "Scan card...");
  }

  // RESET Button Pressed
  if (resetActive && (now - lastDebounceReset > DEBOUNCE_MS)) {
    lastDebounceReset = now;
    Serial.println("RESET");
    beepDouble();
    lcdShow("Cart Reset!", "Total: Rs.0.00");
    delay(1200);
    lcdShow("Mode: ADD", "Scan card...");
    currentMode = "ADD";
  }

  // ── 4. RFID SCAN ─────────────────────────────────────────────────────────
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial())   return;

  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (i > 0) uid += " ";
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  Serial.println("UID:" + uid);
  lcdShow("Scanning...", uid.substring(0, 16));
  beepOnce();

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1200);
}
