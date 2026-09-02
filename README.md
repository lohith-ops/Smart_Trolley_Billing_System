# Smart Trolley Billing System

An IoT-based retail solution designed to modernize the shopping and checkout experience. The system integrates a physical smart shopping trolley (equipped with an RFID reader, push buttons, status buzzer, and an I2C LCD screen) with a premium, responsive **glassmorphic Web Dashboard** driven by a **Flask/MongoDB backend**.

---

## ⚡ Features
*   **RFID Scans (ADD/REMOVE):** Customers scan items using RFID tags to add them to their digital cart or remove them.
*   **Hardware Mode Switching:** Three push-buttons allow the customer to switch modes between **Add Item**, **Remove Item**, and **Reset Cart**.
*   **Real-time LCD Feedback:** A 16x2 I2C LCD screen on the trolley displays the item name and the running checkout total.
*   **Acoustic Status Alerts:** A 5V buzzer chirps on scans, double-beeps on resetting, and emits warning beep sequences on errors.
*   **Glassmorphic Web UI:** A premium dark-themed dashboard showing today's revenue, active trolleys, item counts, and live transaction streams.
*   **Product Registry:** A dynamically triggered registration interface that prompts the administrator to register new, unrecognized RFID cards directly from the live feed.

---
---

## 🎯 Project Objectives

- Automate the retail billing process using IoT technology.
- Reduce waiting time at traditional checkout counters.
- Allow customers to scan products directly using RFID.
- Display product information and prices on the trolley LCD.
- Calculate the total bill automatically during shopping.
- Provide separate modes for adding and removing products.
- Give audio feedback for successful and incorrect scans.
- Store product and transaction information in MongoDB.
- Connect the physical trolley with a web-based dashboard.
- Provide administrators with real-time shopping information.
- Display active trolley and transaction information.
- Make product registration easier through the web dashboard.
- Detect unrecognized RFID cards.
- Improve accuracy in product billing.
- Reduce manual work for retail staff.
- Provide a simple and responsive user interface.
- Support real-time communication between hardware and backend.
- Improve the overall customer shopping experience.
- Make the checkout process faster and more convenient.
- Demonstrate the practical use of IoT in retail systems.

## 🔧 Hardware Components & Pins
This project is configured for **Arduino Uno / Mega** or compatible microcontrollers.

### 📌 Pin Mapping

| Component | Pin (Arduino) | Target Connection | Notes |
| :--- | :--- | :--- | :--- |
| **MFRC522 RFID** | Pin 10 | SDA (SS) | SPI communication |
| | Pin 13 | SCK | SPI Clock |
| | Pin 11 | MOSI | SPI Master Out |
| | Pin 12 | MISO | SPI Master In |
| | Pin 9 | RST | Reset pin |
| | 3.3V | VCC | **CAUTION: Connect to 3.3V only** |
| | GND | GND | Ground |
| **I2C LCD (16x2)** | Pin A5 | SCL | I2C Clock (Uno) |
| | Pin A4 | SDA | I2C Data (Uno) |
| | 5V | VCC | 5V Power |
| | GND | GND | Ground |
| **Buzzer** | Pin 5 | Positive | Digital Output |
| | GND | Negative | Ground |
| **Add Button** | Pin 3 | Pin 1 | Digital Input (Internal Pull-Up) |
| **Remove Button** | Pin 2 | Pin 1 | Digital Input (Internal Pull-Up) |
| **Reset Button** | Pin 4 | Pin 1 | Digital Input (Internal Pull-Up) |

*Note: For buttons, connect the opposite terminal directly to **GND** (logic uses active-low).*

---

## 📂 Project Structure
```text
SmartTrolleyBillingSystem/
├── app.py                     # Flask web server & background Serial daemon thread
├── import_products.py         # Catalog seed manager (populates/wipes MongoDB)
├── requirements.txt           # Python application dependencies
├── arduino_code/
│   └── SmartTrolley.ino       # Microcontroller C++ firmware
└── web-dashboard/             # Premium Glassmorphic Web App
    ├── index.html             # Dashboard page with statistics & feed stream
    ├── inventory.html         # Inventory inventory tracking page
    ├── styles.css             # Dark-theme layout stylesheet
    └── app.js                 # Frontend AJAX logic & modal controllers
```

---

## ⚙️ Software Installation & Setup

### 1. MongoDB Database Setup
Ensure that MongoDB is running locally on your machine on the default port `27017`.
*   **Windows (Service):**
    ```powershell
    net start MongoDB
    ```

### 2. Python Environment Setup
1.  Navigate into the `SmartTrolleyBillingSystem` directory.
2.  Install the required libraries:
    ```bash
    pip install -r requirements.txt
    ```

### 3. Seed Product Database
Populate your database catalog from the predefined JSON dataset:
*   Import all products:
    ```bash
    python import_products.py
    ```
*   Wipe and clean-import:
    ```bash
    python import_products.py --clear
    ```
*   List all stored products:
    ```bash
    python import_products.py --list
    ```

### 4. Upload Firmware to Arduino
1.  Open the [SmartTrolley.ino](file:///c:/Users/LOHITH/OneDrive/Desktop/MAIN%20PROJECT/SmartTrolleyBillingSystem/arduino_code/SmartTrolley.ino) file inside the Arduino IDE.
2.  Install the following libraries via the Library Manager:
    *   `MFRC522` by Github Community
    *   `LiquidCrystal_I2C` by Frank de Brabander
3.  Connect your Arduino board, select the correct COM port in **Tools -> Port**, and upload the sketch.

### 5. Running the Application
Update the COM port in [app.py](file:///c:/Users/LOHITH/OneDrive/Desktop/MAIN%20PROJECT/SmartTrolleyBillingSystem/app.py) (line 282) to match your Arduino connection port (e.g., `COM3`, `COM4`, `COM5`).

Run the Flask server:
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser to view the real-time dashboard.

---

## 🔌 Serial Communication Protocol

The Arduino firmware and Flask backend communicate over Serial at **9600 Baud** using a simple string-based protocol:

### Arduino ➔ Python (Transmitted on Scans/Presses)
*   `UID:XX XX XX XX` - RFID Card scanned.
*   `MODE:ADD` - Switched to Add Mode.
*   `MODE:REMOVE` - Switched to Remove Mode.
*   `RESET` - Discard the current active trolley bill.

### Python ➔ Arduino (Sent to update hardware)
*   `ITEM:<name>\|TOTAL:<price>` - Updates the I2C LCD display with item name and total amount.
*   `CMD:RESET` - Instructs the Arduino to display "Cart Reset!" and clear local state.