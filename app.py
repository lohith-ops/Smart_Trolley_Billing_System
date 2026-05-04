import json
import threading
import time
import serial
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# State
cart = {
    "items": {},  # UID -> {"name": "...", "price": 0.0, "quantity": 1, "subtotal": 0.0}
    "total": 0.0,
    "unknown_scans": []
}

# Load Dataset
dataset = {}
try:
    with open("dataset.json", "r") as f:
        data = json.load(f)
        for item in data:
            dataset[item["uid"]] = item
except FileNotFoundError:
    print("Warning: dataset.json not found. All UIDs will be unknown.")

# Serial Configuration
SERIAL_PORT = 'COM4'  # Change this to your Arduino's COM port
BAUD_RATE = 9600

def update_cart_total():
    cart["total"] = sum(item["subtotal"] for item in cart["items"].values())

def handle_add(uid):
    if uid in dataset:
        if uid in cart["items"]:
            cart["items"][uid]["quantity"] += 1
            cart["items"][uid]["subtotal"] = cart["items"][uid]["quantity"] * cart["items"][uid]["price"]
        else:
            item_data = dataset[uid]
            cart["items"][uid] = {
                "name": item_data["name"],
                "price": item_data["price"],
                "quantity": 1,
                "subtotal": item_data["price"]
            }
        update_cart_total()
    else:
        if uid not in cart["unknown_scans"]:
            cart["unknown_scans"].append(uid)

def handle_remove(uid):
    if uid in cart["items"]:
        cart["items"][uid]["quantity"] -= 1
        if cart["items"][uid]["quantity"] <= 0:
            del cart["items"][uid]
        else:
            cart["items"][uid]["subtotal"] = cart["items"][uid]["quantity"] * cart["items"][uid]["price"]
        update_cart_total()

def handle_reset():
    cart["items"].clear()
    cart["total"] = 0.0
    cart["unknown_scans"].clear()

def serial_reader_thread():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to Arduino on {SERIAL_PORT}")
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if not line:
                    continue
                
                print(f"Received: {line}")
                
                if line == "RESET":
                    handle_reset()
                elif line.startswith("ADD:"):
                    uid = line.split("ADD:")[1].strip()
                    handle_add(uid)
                elif line.startswith("REMOVE:"):
                    uid = line.split("REMOVE:")[1].strip()
                    handle_remove(uid)
                else:
                    # In case format is just the UID (default fallback)
                    uid = line
                    handle_add(uid)
            time.sleep(0.1)
    except serial.SerialException as e:
        print(f"Serial Error: {e}")
        print("Please check your COM port and make sure no other program is using it.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/bill', methods=['GET'])
def get_bill():
    return jsonify({
        "items": list(cart["items"].values()),
        "total": round(cart["total"], 2),
        "unknown_scans": cart["unknown_scans"]
    })

@app.route('/reset', methods=['POST'])
def reset_cart():
    handle_reset()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    # Start serial reading thread
    serial_thread = threading.Thread(target=serial_reader_thread, daemon=True)
    serial_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
