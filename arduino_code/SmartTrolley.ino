/*
 * Smart Trolley Billing System — Arduino Firmware
 * ================================================
 * Matches the Python backend protocol in app.py
 *
 * Serial Protocol:
 *   Arduino → Python:
 *     "UID:XX XX XX XX"   — RFID card scanned (uppercase hex, space-separated)
 *     "MODE:ADD"          — Add button pressed
 *     "MODE:REMOVE"       — Remove button pressed
 *     "RESET"             — Reset button pressed
 *
 *   Python → Arduino (LCD display):
 *     "ITEM:<name>|TOTAL:<price>\n"  — Show item and total on LCD
 *     "CMD:RESET\n"                  — Clear LCD, show "Cart Reset"
 *
 * LCD I2C Address: 0x27 (try 0x3F if display is blank)
 * Pins: ADD=3, REMOVE=2, RESET=4, BUZZER=5, SS=10, RST=9
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <MFRC522.h>
#include <SPI.h>

// ── LCD Setup (change 0x27 to 0x3F if display stays blank) ────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ── Pin Definitions ────────────────────────────────────────────────────────
const int ADD_BTN    = 3;
const int REMOVE_BTN = 2;
const int RESET_BTN  = 4;
const int BUZZER_PIN = 5;

// ── RFID Setup ─────────────────────────────────────────────────────────────
#define SS_PIN  10
#define RST_PIN  9
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ── State ──────────────────────────────────────────────────────────────────
String currentMode = "ADD";

// ── Debounce ───────────────────────────────────────────────────────────────
unsigned long lastDebounceAdd    = 0;
unsigned long lastDebounceRemove = 0;
unsigned long lastDebounceReset  = 0;
const unsigned long DEBOUNCE_MS  = 300;

// ── Helpers ────────────────────────────────────────────────────────────────
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

/** Print a 2-line message on the LCD, padding/truncating to 16 chars each. */
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
  pinMode(ADD_BTN,    INPUT_PULLUP);
  pinMode(REMOVE_BTN, INPUT_PULLUP);
  pinMode(RESET_BTN,  INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);

  Serial.begin(9600);

  // LCD init
  lcd.init();
  lcd.backlight();
  lcdShow("Smart Trolley", "System Ready");
  delay(2000);
  lcd.clear();

  // SPI + RFID
  SPI.begin();
  mfrc522.PCD_Init();

  // RC522 self-check — report to Python
  byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  Serial.print("RC522 Firmware : 0x");
  Serial.println(v, HEX);
  if (v == 0x91 || v == 0x92) {
    Serial.println("RC522 Status   : OK");
    lcdShow("RFID Ready", "Scan a card");
  } else {
    Serial.println("RC522 Status   : ERROR — check SPI wiring and 3.3V power");
    lcdShow("RFID Error", "Check wiring!");
    delay(3000);
    lcdShow("Mode: ADD", "Scan card...");
  }

  lcdShow("Mode: ADD", "Scan card...");
}

// ── Main Loop ──────────────────────────────────────────────────────────────
void loop() {

  // ── 1. BUTTON HANDLING (with debounce) ──────────────────────────────────
  unsigned long now = millis();

  if (digitalRead(ADD_BTN) == LOW && (now - lastDebounceAdd > DEBOUNCE_MS)) {
    lastDebounceAdd = now;
    currentMode = "ADD";
    Serial.println("MODE:ADD");
    beepOnce();
    lcdShow("Mode: ADD", "Scan card...");
  }

  if (digitalRead(REMOVE_BTN) == LOW && (now - lastDebounceRemove > DEBOUNCE_MS)) {
    lastDebounceRemove = now;
    currentMode = "REMOVE";
    Serial.println("MODE:REMOVE");
    beepOnce();
    lcdShow("Mode: REMOVE", "Scan card...");
  }

  if (digitalRead(RESET_BTN) == LOW && (now - lastDebounceReset > DEBOUNCE_MS)) {
    lastDebounceReset = now;
    Serial.println("RESET");
    beepDouble();
    lcdShow("Cart Reset!", "Total: Rs.0.00");
    delay(1500);
    lcdShow("Mode: ADD", "Scan card...");
    currentMode = "ADD";
  }

  // ── 2. RECEIVE FROM PYTHON (LCD display & Buzzer commands) ───────────────
  // MUST be before RFID block — RFID uses early return which would block this.
  if (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();

    if (msg.startsWith("LCD:")) {
      // Format: LCD:Line1|Line2 or LCD:SingleLine
      int sep = msg.indexOf('|');
      if (sep != -1) {
        String line1 = msg.substring(4, sep);
        String line2 = msg.substring(sep + 1);
        lcdShow(line1, line2);
      } else {
        lcdShow(msg.substring(4));
      }
    }
    else if (msg.startsWith("BEEP:")) {
      int count = msg.substring(5).toInt();
      for (int i = 0; i < count; i++) {
        if (i > 0) delay(100);
        beepOnce();
      }
    }
    else if (msg.startsWith("ITEM:")) {
      // Legacy Format: ITEM:<name>|TOTAL:<price>
      int sep = msg.indexOf('|');
      if (sep != -1) {
        String itemName  = msg.substring(5, sep);
        String totalStr  = msg.substring(sep + 7);
        lcdShow(itemName, "Total: Rs." + totalStr);
      }
    }
    else if (msg == "CMD:RESET") {
      lcdShow("Cart Reset!", "Total: Rs.0.00");
      delay(1200);
      lcdShow("Mode: " + currentMode, "Scan card...");
    }
  }

  // ── 3. RFID SCAN ─────────────────────────────────────────────────────────
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial())   return;

  // Build UID string: "XX XX XX XX" (uppercase hex, space-separated)
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (i > 0) uid += " ";
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  // Send UID to Python
  Serial.println("UID:" + uid);

  // Show scanning feedback on LCD immediately
  lcdShow("Scanning...", uid.substring(0, 16));

  beepOnce();

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}
