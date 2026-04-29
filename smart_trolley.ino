/****************************************************
 * Code Designed By : Rahul Jadhav Youtube Channel
 * Bugs Fixed By    : Claude (Anthropic)
 *
 * FIXES APPLIED:
 * 1. item_list[] populated with example items
 * 2. Loop uses number_of_item instead of sizeof()
 * 3. Buttons changed to INPUT_PULLUP (prevents floating pin glitch)
 * 4. Button logic inverted to match INPUT_PULLUP (LOW = pressed)
 ****************************************************/

/******************RFID Connection:*********************

RFID PIN    ARDUINO PIN
SDA         10
SCK         13
MOSI        11
MISO        12
GND         GND
RST         9
3.3v        3.3v
 ******************************************************/

/***** LCD Connection ***********************************
LCD PIN   ARDUINO PIN
SCL       SCL (Arduino Last pin)
SDA       SDA (Arduino Second last pin)
VCC       5v
GND       GND
 ******************************************************/

/***** Buzzer Connection ***********************************
Buzzer PIN   ARDUINO PIN
Positive     5
GND          GND
 *****************************************************/

/***** Button Connection ***********************************
Button PIN       ARDUINO PIN
Remove_Button    2
Add_button       3
Reset_button     4
VCC              5v
GND              GND
 *****************************************************/

#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);
const int remove_button = 2;
const int add_button    = 3;
const int reset_button  = 4;
const int buzzer_Pin    = 5;
#define SS_PIN  10
#define RST_PIN  9
MFRC522 mfrc522(SS_PIN, RST_PIN);

struct item
{
  String item_name;
  String item_number;  // RFID UID in uppercase HEX, e.g. "A1 B2 C3 D4"
  int    item_price;
};

// ---------------------------------------------------------------
// FIX 1: Fill in your items.
// HOW TO GET YOUR UID: Open Serial Monitor, scan each card,
// copy the "UID tag : XX XX XX XX" value (without leading space).
// Replace the placeholder UIDs below with your actual values.
// ---------------------------------------------------------------
const int number_of_item = 4;
const item item_list[number_of_item] =
{
  // Item Name        Item RFID UID (UPPERCASE)    Price (Rs)
  {"Rice 1kg",        "A1 B2 C3 D4",               60},
  {"Sugar 1kg",       "E5 F6 G7 H8",               45},
  {"Chips Pack",      "I9 J0 K1 L2",               20},
 
};

int bill_amount       = 0;
int remove_buttonState = 0;
int add_buttonState    = 0;
int reset_buttonState  = 0;
int add_item_flag     = 1;   // Default: ADD mode
int remove_item_flag  = 0;

void setup()
{
  // FIX 3: Use INPUT_PULLUP so floating pins don't trigger buttons randomly
  pinMode(remove_button, INPUT_PULLUP);
  pinMode(reset_button,  INPUT_PULLUP);
  pinMode(add_button,    INPUT_PULLUP);
  pinMode(buzzer_Pin,    OUTPUT);

  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  Serial.println("Approximate your card to the reader...");
  Serial.println();

  digitalWrite(buzzer_Pin, LOW);

  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Smart Trolley");
  lcd.setCursor(0, 1);
  lcd.print("Billing System");
  delay(2000);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Start Purchasing");
  lcd.setCursor(0, 1);
  lcd.print("Your Item");
  delay(100);
  Serial.println("RFID Reader ready");
}

void loop()
{
  // FIX 4: Read LOW (not HIGH) because INPUT_PULLUP is LOW when pressed
  remove_buttonState = digitalRead(remove_button);
  add_buttonState    = digitalRead(add_button);
  reset_buttonState  = digitalRead(reset_button);

  if (remove_buttonState == LOW)
  {
    add_item_flag    = 0;
    remove_item_flag = 1;
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("You Can Now");
    lcd.setCursor(0, 1);
    lcd.print("Remove Your Item");
    delay(2000);
  }
  else if (add_buttonState == LOW)
  {
    add_item_flag    = 1;
    remove_item_flag = 0;
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("You Can Now");
    lcd.setCursor(0, 1);
    lcd.print("Add Your Item");
    delay(2000);
  }
  else if (reset_buttonState == LOW)
  {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Resetting");
    lcd.setCursor(0, 1);
    lcd.print("Trolley Data");
    delay(2000);

    bill_amount      = 0;
    add_item_flag    = 1;   // Go back to ADD mode after reset
    remove_item_flag = 0;

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Start Purchasing");
    lcd.setCursor(0, 1);
    lcd.print("Your Item");
    delay(2000);
  }

  // Look for new cards
  if (!mfrc522.PICC_IsNewCardPresent())
  {
    return;
  }

  // Select one of the cards
  if (!mfrc522.PICC_ReadCardSerial())
  {
    return;
  }

  // Read UID and print to Serial Monitor
  Serial.print("UID tag :");
  String content = "";
  for (byte i = 0; i < mfrc522.uid.size; i++)
  {
    Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(mfrc522.uid.uidByte[i], HEX);
    content.concat(String(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " "));
    content.concat(String(mfrc522.uid.uidByte[i], HEX));
  }
  Serial.println();
  content.toUpperCase();

  bool item_found = false;
  Serial.print("Parsed content : [");
  Serial.print(content.substring(1));
  Serial.println("]");

  // FIX 2: Use number_of_item instead of sizeof(item_list)
  for (int i = 0; i < number_of_item; i++)
  {
    if (content.substring(1) == item_list[i].item_number)
    {
      item_found = true;

      if (add_item_flag == 1)
      {
        bill_amount += item_list[i].item_price;

        Serial.println("Added: "      + item_list[i].item_name);
        Serial.print("Item Price: ");  Serial.println(item_list[i].item_price);
        Serial.print("Total Bill: ");  Serial.println(bill_amount);

        digitalWrite(buzzer_Pin, HIGH);
        delay(500);
        digitalWrite(buzzer_Pin, LOW);

        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print(item_list[i].item_name);
        lcd.setCursor(0, 1);
        lcd.print("Added: " + String(item_list[i].item_price) + " Rs");
        delay(2000);
      }
      else if (remove_item_flag == 1)
      {
        if (bill_amount > 0)
        {
          bill_amount -= item_list[i].item_price;
          if (bill_amount < 0) bill_amount = 0;  // Safety clamp

          Serial.println("Removed: "    + item_list[i].item_name);
          Serial.print("Item Price: ");  Serial.println(item_list[i].item_price);
          Serial.print("Total Bill: ");  Serial.println(bill_amount);

          digitalWrite(buzzer_Pin, HIGH);
          delay(500);
          digitalWrite(buzzer_Pin, LOW);

          lcd.clear();
          lcd.setCursor(0, 0);
          lcd.print(item_list[i].item_name);
          lcd.setCursor(0, 1);
          lcd.print("Removed");
          delay(2000);
        }
        else
        {
          lcd.clear();
          lcd.setCursor(0, 0);
          lcd.print("Trolley Is");
          lcd.setCursor(0, 1);
          lcd.print("Already Empty!");
          delay(2000);
        }
      }
      break;  // Stop searching once item is matched
    }
  }

  // If card scanned but not in list
  if (!item_found)
  {
    Serial.println("Unknown card scanned.");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Unknown Item!");
    lcd.setCursor(0, 1);
    lcd.print("Not in List");
    delay(2000);
  }

  // Always show total bill after scan
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Total Billing");
  lcd.setCursor(0, 1);
  lcd.print(String(bill_amount) + " Rs");
  delay(2000);
}
