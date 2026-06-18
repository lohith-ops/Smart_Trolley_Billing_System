import threading
import time
import serial
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__, static_folder="web-dashboard", static_url_path="")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for static files
CORS(app)

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['smart_trolley']
products_collection = db['products']
carts_collection = db['carts']
transactions_collection = db['transactions']

# Global State for Arduino Integration (Optional, can be used if Arduino is connected)
current_mode = "ADD"
global_ser = None

# We can keep a "mock" state for testing, but let's persist everything to MongoDB
# Active cart will be stored in carts_collection with id "cart_1"
def init_cart():
    if not carts_collection.find_one({"_id": "cart_1"}):
        carts_collection.insert_one({
            "_id": "cart_1",
            "items": {},
            "total": 0.0,
            "itemsContained": 0,
            "lastActive": "Just now"
        })

init_cart()

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/inventory.html")
def inventory():
    return send_from_directory(app.static_folder, "inventory.html")

@app.route("/api/products", methods=["GET"])
def get_products():
    products = list(products_collection.find({}, {"_id": 0}))
    return jsonify(products)

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    # Calculate revenue from transactions
    pipeline = [{"$group": {"_id": None, "totalRevenue": {"$sum": "$total"}}}]
    rev_result = list(transactions_collection.aggregate(pipeline))
    revenue = rev_result[0]["totalRevenue"] if rev_result else 0.0
    
    # Get scanned items
    items_scanned = transactions_collection.count_documents({})
    
    # Get active carts
    carts = list(carts_collection.find({}))
    active_carts = []
    for c in carts:
        if c.get("itemsContained", 0) > 0:
            active_carts.append({
                "id": c["_id"].split("_")[-1],
                "total": c["total"],
                "itemsContained": c["itemsContained"],
                "lastActive": c["lastActive"]
            })

    # Get recent feed
    feed_cursor = db['feed'].find({}, {"_id": 0}).sort("timestamp", -1).limit(6)
    feed_items = list(feed_cursor)

    return jsonify({
        "revenue": revenue,
        "scannedItems": items_scanned,
        "activeCarts": active_carts,
        "feed": feed_items
    })

def send_command_to_arduino(cmd):
    """Send command to Arduino over Serial.
    Examples: LCD:Line1|Line2, BEEP:1, BEEP:2, BEEP:3
    """
    global global_ser
    if global_ser and global_ser.is_open:
        try:
            msg = f"{cmd}\n"
            global_ser.write(msg.encode('utf-8'))
            print(f"[SERIAL OUT] {msg.strip()}")
        except Exception as e:
            print(f"[SERIAL ERROR] {e}")

def normalize_uid(uid_str):
    """Normalize UID to uppercase no-space format for consistent DB lookup.
    Handles formats like '5C 1E 7E 05', '5c1e7e05', '5C-1E-7E-05'.
    Returns '5C1E7E05'
    """
    return uid_str.replace(' ', '').replace('-', '').upper()

def process_scan(action, uid):
    # Normalize UID once — used as consistent cart key and DB lookup key
    uid_key = normalize_uid(uid)  # e.g. "5C1E7E05"

    # Try lookup in all common formats stored in DB
    product = products_collection.find_one({"uid": uid})
    if not product:
        product = products_collection.find_one({"uid": uid_key})
    if not product:
        spaced = ' '.join(uid_key[i:i+2] for i in range(0, len(uid_key), 2))
        product = products_collection.find_one({"uid": spaced})
    if not product:
        # Try uid_norm field (set by import_products.py)
        product = products_collection.find_one({"uid_norm": uid_key})

    cart = carts_collection.find_one({"_id": "cart_1"})
    items = cart.get("items", {})

    if not product:
        # PUSH UNKNOWN EVENT TO FEED
        db['feed'].insert_one({
            "actionType": "UNKNOWN_SCAN",
            "uid": uid_key,
            "timestamp": time.time()
        })
        return None, cart.get("total", 0.0), uid_key

    # Always use normalized UID as the cart item key for consistency
    if action == "ADD":
        if uid_key in items:
            items[uid_key]["quantity"] += 1
            items[uid_key]["subtotal"] = items[uid_key]["quantity"] * product["price"]
        else:
            items[uid_key] = {
                "name": product["name"],
                "price": product["price"],
                "quantity": 1,
                "subtotal": product["price"]
            }
    elif action == "REMOVE":
        if uid_key in items:
            items[uid_key]["quantity"] -= 1
            if items[uid_key]["quantity"] <= 0:
                del items[uid_key]
            else:
                items[uid_key]["subtotal"] = items[uid_key]["quantity"] * product["price"]

    total = sum(item["subtotal"] for item in items.values())
    items_contained = sum(item["quantity"] for item in items.values())
    
    carts_collection.update_one({"_id": "cart_1"}, {
        "$set": {
            "items": items,
            "total": total,
            "itemsContained": items_contained,
            "lastActive": "Just now"
        }
    })
    
    # Add to feed
    db['feed'].insert_one({
        "actionType": action,
        "productName": product["name"],
        "productPrice": product["price"],
        "timestamp": time.time()
    })
    
    return product, total, uid_key

@app.route("/api/cart/action", methods=["POST"])
def cart_action():
    data = request.json
    action = data.get("action")
    uid = data.get("uid")
    
    product, total, uid_key = process_scan(action, uid)
    if not product:
        return jsonify({"success": False, "message": "Product not found", "uid": uid_key}), 404
        
    cart = carts_collection.find_one({"_id": "cart_1"})
    return jsonify({
        "success": True, 
        "product": {"name": product["name"], "price": product["price"]},
        "action": action,
        "cart": {"total": total, "itemsContained": cart["itemsContained"]}
    })

def perform_checkout():
    cart = carts_collection.find_one({"_id": "cart_1"})
    if cart and cart.get("itemsContained", 0) > 0:
        saved_items = dict(cart["items"])   # snapshot before clearing
        transactions_collection.insert_one({
            "items": cart["items"],
            "total": cart["total"],
            "timestamp": time.time()
        })
        carts_collection.update_one({"_id": "cart_1"}, {
            "$set": {
                "items": {},
                "total": 0.0,
                "itemsContained": 0,
                "lastActive": "Checked out"
            }
        })
        db['feed'].insert_one({
            "actionType": "CHECKOUT",
            "total": cart["total"],
            "timestamp": time.time()
        })
        return True, cart["total"], saved_items
    return False, 0.0, {}

def perform_reset():
    """Reset the cart without saving as a transaction (discard all items)."""
    cart = carts_collection.find_one({"_id": "cart_1"})
    carts_collection.update_one({"_id": "cart_1"}, {
        "$set": {
            "items": {},
            "total": 0.0,
            "itemsContained": 0,
            "lastActive": "Reset"
        }
    })
    db['feed'].insert_one({
        "actionType": "RESET",
        "total": cart.get("total", 0.0) if cart else 0.0,
        "timestamp": time.time()
    })
    return True

@app.route("/api/checkout", methods=["POST"])
def checkout():
    success, total, items = perform_checkout()
    if success:
        return jsonify({"success": True, "total": total, "items": items})
    return jsonify({"success": False, "message": "Cart is empty — scan items first"})

@app.route("/api/products/register", methods=["POST"])
def register_product():
    data = request.json
    uid = data.get("uid")
    name = data.get("name")
    price = data.get("price")
    
    if not uid or not name or price is None:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
        
    try:
        price_float = float(price)
    except ValueError:
        return jsonify({"success": False, "message": "Price must be a number"}), 400
        
    uid_norm = normalize_uid(uid)
    
    products_collection.update_one(
        {"uid_norm": uid_norm},
        {"$set": {
            "uid": uid,
            "name": name,
            "price": price_float,
            "uid_norm": uid_norm
        }},
        upsert=True
    )
    
    return jsonify({"success": True, "message": f"Registered {name}"})

@app.route("/api/reset", methods=["POST"])
def reset_cart():
    perform_reset()
    return jsonify({"success": True, "message": "Cart has been reset"})

def serial_loop():
    global global_ser, current_mode
    SERIAL_PORT = 'COM4'  # You can change this if your Arduino moves to COM3, COM5, etc.
    BAUD_RATE = 9600
    
    while True:
        # Reconnection Logic
        if global_ser is None or not global_ser.is_open:
            try:
                global_ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print(f"Connected to Arduino on {SERIAL_PORT}")
            except Exception as e:
                print(f"Waiting for Arduino on {SERIAL_PORT}... (Please check your connection or close Serial Monitor)")
                time.sleep(3)
                continue

        try:
            line = global_ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"Arduino: {line}")

                # ── Button state diagnostic (every 3s from Arduino) ──────────
                if line.startswith("BTN_STATE:"):
                    # Format: BTN_STATE: ADD=1 REMOVE=1 RESET=1  (1=not pressed, 0=pressed)
                    if "RESET=0" in line:
                        print("[BTN] ✅ Reset button IS being pressed — triggering reset")
                        perform_reset()
                        send_command_to_arduino("LCD:Cart Reset!|Rs.0")
                        send_command_to_arduino("BEEP:2")

                # ── Reset — catch ALL possible formats Arduino might send ─────
                elif (line == "RESET"
                      or line.upper() == "RESET"
                      or line.startswith("Reset")
                      or "Bill cleared" in line):
                    print("[RESET] Hardware reset button triggered")
                    perform_reset()
                    send_command_to_arduino("LCD:Cart Reset!|Rs.0")

                elif line == "MODE:ADD":
                    current_mode = "ADD"
                    print("[Mode] Switched to ADD")
                    send_command_to_arduino("LCD:You Can Now|Add Item")
                elif line == "MODE:REMOVE":
                    current_mode = "REMOVE"
                    print("[Mode] Switched to REMOVE")
                    send_command_to_arduino("LCD:You Can Now|Remove Item")
                elif line.startswith("SCAN:"):
                    uid = line.split("SCAN:")[1].strip()
                    product, total, uid_key = process_scan(current_mode, uid)
                    if product:
                        action_text = "Added" if current_mode == "ADD" else "Removed"
                        short_name = product["name"][:16]
                        send_command_to_arduino(f"LCD:{short_name}|{action_text} Rs.{total:.2f}")
                        send_command_to_arduino("BEEP:1")
                    else:
                        print(f"[WARN] Unknown UID Scanned: {uid}")
                        send_command_to_arduino("LCD:Unknown Card!|Check Dashboard")
                        send_command_to_arduino("BEEP:3")
        except serial.SerialException as e:
            print(f"Serial connection lost! Reconnecting... Error: {e}")
            if global_ser:
                global_ser.close()
            global_ser = None
            time.sleep(2)
        except Exception as e:
            print(f"Serial Logic Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    t = threading.Thread(target=serial_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
