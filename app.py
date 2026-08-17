import threading
import time
import datetime
import serial
import os
import json
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

# Configuration File Persistence
CONFIG_FILE = "config.json"

def load_config():
    defaults = {
        "serialPort": "COM3"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
        except Exception as e:
            print(f"[CONFIG] Error reading config file: {e}")
    return defaults

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"[CONFIG] Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"[CONFIG] Error saving config file: {e}")

# In-Memory Mock Database Fallback for development environments without MongoDB
class MockCursor:
    def __init__(self, data):
        self.data = data
    def sort(self, key, direction=-1):
        reverse = (direction == -1)
        self.data.sort(key=lambda x: x.get(key, 0), reverse=reverse)
        return self
    def limit(self, count):
        self.data = self.data[:count]
        return self
    def __iter__(self):
        return iter(self.data)
    def __len__(self):
        return len(self.data)

class MockCollection:
    def __init__(self, data=None):
        self.data = data if data is not None else []
    def find_one(self, filter, projection=None):
        for doc in self.data:
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None
    def find(self, filter=None, projection=None):
        if filter is None:
            filter = {}
        results = []
        for doc in self.data:
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc)
        return MockCursor(results)
    def insert_one(self, document):
        if "_id" not in document:
            document["_id"] = str(len(self.data) + 1)
        self.data.append(document)
        return type('InsertOneResult', (object,), {'inserted_id': document["_id"]})()
    def update_one(self, filter, update, upsert=False):
        doc = self.find_one(filter)
        if not doc:
            if upsert:
                new_doc = {}
                for k, v in filter.items():
                    new_doc[k] = v
                if "$set" in update:
                    for k, v in update["$set"].items():
                        new_doc[k] = v
                self.data.append(new_doc)
                return type('UpdateResult', (object,), {'upserted_id': new_doc.get("_id", "upserted"), 'matched_count': 0, 'modified_count': 1})()
            return type('UpdateResult', (object,), {'upserted_id': None, 'matched_count': 0, 'modified_count': 0})()
        if "$set" in update:
            for k, v in update["$set"].items():
                doc[k] = v
        return type('UpdateResult', (object,), {'upserted_id': None, 'matched_count': 1, 'modified_count': 1})()
    def insert_many(self, documents):
        ids = []
        for document in documents:
            if "_id" not in document:
                document["_id"] = str(len(self.data) + 1)
            self.data.append(document)
            ids.append(document["_id"])
        return type('InsertManyResult', (object,), {'inserted_ids': ids})()
    def delete_one(self, filter):
        doc = self.find_one(filter)
        if doc in self.data:
            self.data.remove(doc)
            return type('DeleteResult', (object,), {'deleted_count': 1})()
        return type('DeleteResult', (object,), {'deleted_count': 0})()
    def delete_many(self, filter):
        if not filter:
            count = len(self.data)
            self.data.clear()
            return type('DeleteResult', (object,), {'deleted_count': count})()
        initial_len = len(self.data)
        to_keep = []
        deleted = 0
        for doc in self.data:
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                deleted += 1
            else:
                to_keep.append(doc)
        self.data = to_keep
        return type('DeleteResult', (object,), {'deleted_count': deleted})()
    def count_documents(self, filter):
        if not filter:
            return len(self.data)
        count = 0
        for doc in self.data:
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count
    def aggregate(self, pipeline):
        total = 0.0
        is_revenue = False
        gte_val = 0
        for stage in pipeline:
            if "$match" in stage:
                timestamp_match = stage["$match"].get("timestamp", {})
                if isinstance(timestamp_match, dict) and "$gte" in timestamp_match:
                    gte_val = timestamp_match["$gte"]
            if "$group" in stage:
                group = stage["$group"]
                if "totalRevenue" in group and "$sum" in group["totalRevenue"]:
                    is_revenue = True
        if is_revenue:
            for doc in self.data:
                if doc.get("timestamp", 0) >= gte_val:
                    total += doc.get("total", 0.0)
            return [{"_id": None, "totalRevenue": total}]
        return []

class MockDatabase:
    def __init__(self):
        self.collections = {}
    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]

class MockClient:
    def __init__(self):
        self.db = MockDatabase()
    def __getitem__(self, name):
        return self.db
    def server_info(self):
        return {"version": "mock"}

# MongoDB connection
mongo_ok = False
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=1500)
    client.server_info()  # Force connection check
    db = client['smart_trolley']
    products_collection = db['products']
    carts_collection = db['carts']
    transactions_collection = db['transactions']
    mongo_ok = True
    print("[DB] Connected to local MongoDB successfully.")
except Exception as e:
    print(f"[DB WARN] MongoDB connection failed: {e}")
    print("[DB WARN] Falling back to IN-MEMORY Mock Database. Changes will not persist after restart.")
    client = MockClient()
    db = client['smart_trolley']
    products_collection = db['products']
    carts_collection = db['carts']
    transactions_collection = db['transactions']
    
    # Seed default products catalog into mock database
    defaults = [
        {"uid": "5C 1E 7E 05", "name": "Rice 1kg", "price": 60.0, "category": "Grains", "stock": 45, "shelf": "Aisle A - Shelf 1", "offer": "Buy 1 Get 1 Free"},
        {"uid": "76 E3 33 06", "name": "Sugar 1kg", "price": 45.0, "category": "Grains", "stock": 12, "shelf": "Aisle A - Shelf 2", "offer": "No Active Offers"},
        {"uid": "A3 B4 C5 D6", "name": "Whole Wheat Bread", "price": 25.0, "category": "Bakery", "stock": 8, "shelf": "Aisle B - Shelf 1", "offer": "10% Off"},
        {"uid": "11 22 33 44", "name": "Milk (1 Gallon)", "price": 50.0, "category": "Dairy", "stock": 32, "shelf": "Aisle C - Shelf 1", "offer": "No Active Offers"},
        {"uid": "99 88 77 66", "name": "Cheddar Cheese", "price": 80.0, "category": "Dairy", "stock": 15, "shelf": "Aisle C - Shelf 1", "offer": "20% Off"},
        {"uid": "FF EE DD CC", "name": "Free Range Eggs", "price": 40.0, "category": "Dairy", "stock": 24, "shelf": "Aisle C - Shelf 1", "offer": "No Active Offers"}
    ]
    for p in defaults:
        uid_norm = p["uid"].replace(" ", "").upper()
        p["uid_norm"] = uid_norm
        products_collection.data.append(p)

# Global State for Arduino Integration (Optional, can be used if Arduino is connected)
current_mode = "ADD"
global_ser = None

# Load persistent configurations
config_data = load_config()
SERIAL_PORT = config_data.get("serialPort", "COM3")

# We can keep a "mock" state for testing, but let's persist everything to MongoDB
# Active cart will be stored in carts_collection with id "cart_1"
def init_cart():
    cart = carts_collection.find_one({"_id": "cart_1"})
    if not cart:
        carts_collection.insert_one({
            "_id": "cart_1",
            "items": {},
            "total": 0.0,
            "itemsContained": 0,
            "status": "ACTIVE",
            "lastActive": "Just now"
        })
    elif "status" not in cart:
        carts_collection.update_one({"_id": "cart_1"}, {"$set": {"status": "ACTIVE"}})

init_cart()

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    full_path = os.path.join(app.static_folder, path)
    if os.path.exists(full_path) and not os.path.isdir(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/products", methods=["GET"])
def get_products():
    products = list(products_collection.find({}, {"_id": 0}))
    return jsonify(products)

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    # Calculate revenue from transactions today
    now = datetime.datetime.now()
    today_start = datetime.datetime(now.year, now.month, now.day).timestamp()
    pipeline = [
        {"$match": {"timestamp": {"$gte": today_start}}},
        {"$group": {"_id": None, "totalRevenue": {"$sum": "$total"}}}
    ]
    rev_result = list(transactions_collection.aggregate(pipeline))
    revenue = rev_result[0]["totalRevenue"] if rev_result else 0.0
    
    # Calculate total items scanned across all transactions + current cart
    items_scanned = 0
    all_txs = list(transactions_collection.find({}, {"items": 1}))
    for tx in all_txs:
        for item_key, item_val in tx.get("items", {}).items():
            items_scanned += item_val.get("quantity", 0)
    
    cart_1 = carts_collection.find_one({"_id": "cart_1"})
    if cart_1:
        items_scanned += cart_1.get("itemsContained", 0)
    
    # Get active carts
    carts = list(carts_collection.find({}))
    active_carts = []
    for c in carts:
        if c.get("itemsContained", 0) > 0:
            active_carts.append({
                "id": c["_id"].split("_")[-1],
                "total": c["total"],
                "itemsContained": c["itemsContained"],
                "lastActive": c["lastActive"],
                "items": c.get("items", {}),
                "status": c.get("status", "ACTIVE")
            })

    # Get recent feed
    feed_cursor = db['feed'].find({}, {"_id": 0}).sort("timestamp", -1).limit(6)
    feed_items = list(feed_cursor)

    return jsonify({
        "revenue": revenue,
        "scannedItems": items_scanned,
        "activeCarts": active_carts,
        "feed": feed_items,
        "currentMode": current_mode,
        "arduinoConnected": global_ser is not None and global_ser.is_open,
        "serialPort": SERIAL_PORT
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
    if not cart:
        init_cart()
        cart = carts_collection.find_one({"_id": "cart_1"})
    items = cart.get("items", {}) if cart else {}

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
        current_stock = product.get("stock")
        if current_stock is None:
            current_stock = 20
        if current_stock <= 0:
            db['feed'].insert_one({
                "actionType": "OUT_OF_STOCK",
                "productName": product["name"],
                "timestamp": time.time()
            })
            return product, cart.get("total", 0.0), "OUT_OF_STOCK"

        # Reduce stock count in database
        new_stock = current_stock - 1
        products_collection.update_one({"_id": product["_id"]}, {"$set": {"stock": new_stock}})
        product["stock"] = new_stock

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

            # Restore stock count in database
            curr_stk = product.get("stock")
            if curr_stk is None:
                curr_stk = 20
            new_stock = curr_stk + 1
            products_collection.update_one({"_id": product["_id"]}, {"$set": {"stock": new_stock}})
            product["stock"] = new_stock
    elif action == "REMOVE_ALL":
        if uid_key in items:
            qty_to_restore = items[uid_key]["quantity"]
            del items[uid_key]

            # Restore stock count in database
            curr_stk = product.get("stock")
            if curr_stk is None:
                curr_stk = 20
            new_stock = curr_stk + qty_to_restore
            products_collection.update_one({"_id": product["_id"]}, {"$set": {"stock": new_stock}})
            product["stock"] = new_stock

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
        "actionType": "REMOVE" if action in ["REMOVE", "REMOVE_ALL"] else "ADD",
        "productName": product["name"],
        "productPrice": product["price"],
        "timestamp": time.time()
    })
    
    return product, total, uid_key

@app.route("/api/cart/action", methods=["POST"])
def cart_action():
    cart = carts_collection.find_one({"_id": "cart_1"})
    if cart and cart.get("status") == "BILL_GENERATED":
        return jsonify({"success": False, "message": "Cart is locked! Complete payment or cancel bill to modify cart."}), 400

    data = request.json
    action = data.get("action")
    uid = data.get("uid")
    
    product, total, uid_key = process_scan(action, uid)
    if not product:
        send_command_to_arduino("LCD:Unknown Card!|Check Dashboard")
        send_command_to_arduino("BEEP:3")
        return jsonify({"success": False, "message": "Product not found", "uid": uid_key}), 404

    if uid_key == "OUT_OF_STOCK":
        short_pname = product['name'][:16]
        send_command_to_arduino(f"LCD:{short_pname}|OUT OF STOCK!")
        send_command_to_arduino("BEEP:3")
        return jsonify({"success": False, "message": f"'{product['name']}' is Out of Stock!", "stock": 0}), 400
        
    action_symbol = "-" if action in ["REMOVE", "REMOVE_ALL"] else "+"
    short_name = f"{action_symbol} {product['name']}"[:16]
    send_command_to_arduino(f"LCD:{short_name}|Total: Rs.{total:.2f}")
    send_command_to_arduino("BEEP:1")
        
    cart = carts_collection.find_one({"_id": "cart_1"})
    return jsonify({
        "success": True, 
        "product": {"name": product["name"], "price": product["price"], "stock": product.get("stock", 0)},
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
        send_command_to_arduino("LCD:Checked Out!|Total: Rs.0.00")
        send_command_to_arduino("BEEP:2")
        return True, cart["total"], saved_items
    return False, 0.0, {}

def perform_reset():
    """Reset the cart without saving as a transaction (discard all items) and restore item stocks."""
    cart = carts_collection.find_one({"_id": "cart_1"})
    if cart and "items" in cart:
        items = cart.get("items", {})
        for item_key, item_val in items.items():
            qty = item_val.get("quantity", 0)
            if qty > 0:
                p = products_collection.find_one({"uid": item_key})
                if not p:
                    p = products_collection.find_one({"uid_norm": item_key})
                if p:
                    products_collection.update_one(
                        {"_id": p["_id"]},
                        {"$set": {"stock": p.get("stock", 0) + qty}}
                    )

    carts_collection.update_one({"_id": "cart_1"}, {
        "$set": {
            "items": {},
            "total": 0.0,
            "itemsContained": 0,
            "status": "ACTIVE",
            "lastActive": "Reset"
        }
    })
    db['feed'].insert_one({
        "actionType": "RESET",
        "total": cart.get("total", 0.0) if cart else 0.0,
        "timestamp": time.time()
    })
    send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")
    send_command_to_arduino("BEEP:2")
    return True

@app.route("/api/cart/generate-bill", methods=["POST"])
def generate_bill():
    cart = carts_collection.find_one({"_id": "cart_1"})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — scan items first"}), 400
    
    total = cart["total"]
    grand_total = total
    subtotal = grand_total / 1.18
    cgst = subtotal * 0.09
    sgst = subtotal * 0.09
    
    carts_collection.update_one({"_id": "cart_1"}, {
        "$set": {
            "status": "BILL_GENERATED",
            "lastActive": "Bill generated"
        }
    })
    
    send_command_to_arduino(f"LCD:Pay Rs.{grand_total:.2f}|Scan QR to Pay")
    send_command_to_arduino("BEEP:1")
    
    db['feed'].insert_one({
        "actionType": "BILL_GENERATED",
        "total": grand_total,
        "timestamp": time.time()
    })
    
    return jsonify({
        "success": True,
        "subtotal": round(subtotal, 2),
        "cgst": round(cgst, 2),
        "sgst": round(sgst, 2),
        "total": round(grand_total, 2),
        "items": cart["items"]
    })

@app.route("/api/cart/cancel-bill", methods=["POST"])
def cancel_bill():
    cart = carts_collection.find_one({"_id": "cart_1"})
    if not cart:
        return jsonify({"success": False, "message": "Cart not found"}), 404
        
    carts_collection.update_one({"_id": "cart_1"}, {
        "$set": {
            "status": "ACTIVE",
            "lastActive": "Scanning"
        }
    })
    
    total = cart.get("total", 0.0)
    send_command_to_arduino(f"LCD:Bill Cancelled|Total: Rs.{total:.2f}")
    send_command_to_arduino("BEEP:1")
    
    db['feed'].insert_one({
        "actionType": "BILL_CANCELLED",
        "total": total,
        "timestamp": time.time()
    })
    
    return jsonify({"success": True, "message": "Bill cancelled, cart returned to scanning", "total": total})

@app.route("/api/cart/pay", methods=["POST"])
def pay_bill():
    cart = carts_collection.find_one({"_id": "cart_1"})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — scan items first"}), 400
        
    data = request.json or {}
    payment_method = data.get("paymentMethod", "UPI")
    
    saved_items = dict(cart["items"])
    total = cart["total"]
    timestamp = time.time()
    
    transactions_collection.insert_one({
        "items": saved_items,
        "total": total,
        "paymentMethod": payment_method,
        "timestamp": timestamp
    })
    
    carts_collection.update_one({"_id": "cart_1"}, {
        "$set": {
            "items": {},
            "total": 0.0,
            "itemsContained": 0,
            "status": "ACTIVE",
            "lastActive": f"Paid via {payment_method}"
        }
    })
    
    db['feed'].insert_one({
        "actionType": "CHECKOUT",
        "total": total,
        "paymentMethod": payment_method,
        "timestamp": timestamp
    })
    
    send_command_to_arduino("LCD:Checked Out!|Total: Rs.0.00")
    send_command_to_arduino("BEEP:2")
    
    return jsonify({
        "success": True,
        "message": "Payment successful",
        "total": total,
        "items": saved_items,
        "timestamp": timestamp
    })

# Kept for backward compatibility
@app.route("/api/checkout", methods=["POST"])
def checkout():
    return pay_bill()

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
            "uid_norm": uid_norm,
            "stock": int(data.get("stock", 20)),
            "category": data.get("category", "Grocery"),
            "shelf": data.get("shelf", "Aisle A - Shelf 1"),
            "offer": data.get("offer", "No Active Offers")
        }},
        upsert=True
    )
    
    return jsonify({"success": True, "message": f"Registered {name}"})
@app.route("/api/reset", methods=["POST"])
@app.route("/api/cart/reset", methods=["POST"])
def reset_cart():
    perform_reset()
    return jsonify({"success": True, "message": "Cart has been reset"})

@app.route("/api/products/<uid>", methods=["DELETE"])
def delete_product(uid):
    uid_norm = normalize_uid(uid)
    result = products_collection.delete_one({"uid_norm": uid_norm})
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": "Product deleted successfully"})
    return jsonify({"success": False, "message": "Product not found"}), 404

@app.route("/api/simulator/mode", methods=["POST"])
def set_simulator_mode():
    global current_mode
    data = request.json
    mode = data.get("mode")
    if mode not in ["ADD", "REMOVE"]:
        return jsonify({"success": False, "message": "Invalid mode"}), 400
    current_mode = mode
    # Sync with Arduino if connected
    if current_mode == "ADD":
        send_command_to_arduino("LCD:You Can Now|Add Item")
    else:
        send_command_to_arduino("LCD:You Can Now|Remove Item")
    return jsonify({"success": True, "mode": current_mode})

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    transactions = list(transactions_collection.find({}, {"_id": 0}).sort("timestamp", -1))
    return jsonify(transactions)

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    # Revenue
    pipeline_rev = [{"$group": {"_id": None, "totalRevenue": {"$sum": "$total"}}}]
    rev_res = list(transactions_collection.aggregate(pipeline_rev))
    total_revenue = rev_res[0]["totalRevenue"] if rev_res else 0.0
    
    # Checkouts count
    total_checkouts = transactions_collection.count_documents({})
    
    # Average Order Value
    avg_order_value = total_revenue / total_checkouts if total_checkouts > 0 else 0.0
    
    # Top products (calculate in Python for safety and simplicity)
    product_counts = {}
    product_revenue = {}
    all_tx = list(transactions_collection.find({}))
    for tx in all_tx:
        items = tx.get("items", {})
        for item_key, item_details in items.items():
            name = item_details.get("name", "Unknown Item")
            quantity = item_details.get("quantity", 0)
            subtotal = item_details.get("subtotal", 0.0)
            product_counts[name] = product_counts.get(name, 0) + quantity
            product_revenue[name] = product_revenue.get(name, 0.0) + subtotal
            
    top_products = []
    for name in product_counts:
        top_products.append({
            "name": name,
            "quantity": product_counts[name],
            "revenue": product_revenue[name]
        })
    top_products.sort(key=lambda x: x["quantity"], reverse=True)
    top_products = top_products[:5]
    
    # Sales history timeseries
    timeseries = []
    recent_tx = list(transactions_collection.find({}, {"_id": 0}).sort("timestamp", 1).limit(15))
    for tx in recent_tx:
        timeseries.append({
            "timestamp": tx["timestamp"],
            "total": tx["total"]
        })
        
    return jsonify({
        "totalRevenue": total_revenue,
        "totalCheckouts": total_checkouts,
        "avgOrderValue": avg_order_value,
        "topProducts": top_products,
        "timeseries": timeseries
    })

@app.route("/api/settings/ports", methods=["GET"])
def get_available_ports():
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    port_list = []
    for p in ports:
        port_list.append({
            "port": p.device,
            "description": p.description,
            "hwid": p.hwid
        })
    return jsonify({
        "success": True,
        "ports": port_list,
        "currentPort": SERIAL_PORT
    })

@app.route("/api/settings/update", methods=["POST"])
def update_settings():
    global SERIAL_PORT, global_ser
    data = request.json
    new_port = data.get("serialPort")
    
    if new_port:
        SERIAL_PORT = new_port.strip().upper()
        # Save settings config
        cfg = load_config()
        cfg["serialPort"] = SERIAL_PORT
        save_config(cfg)
        # Close existing connection to force reconnect loop to try the port immediately
        if global_ser:
            try:
                global_ser.close()
            except:
                pass
            global_ser = None
        print(f"Serial port set to {SERIAL_PORT}. Reconnecting...")
            
    return jsonify({
        "success": True, 
        "serialPort": SERIAL_PORT,
        "arduinoConnected": global_ser is not None and global_ser.is_open
    })

@app.route("/api/settings/database", methods=["POST"])
def manage_database():
    action = request.json.get("action")
    if action == "seed":
        products_collection.delete_many({})
        defaults = [
            {"uid": "5C 1E 7E 05", "name": "Rice 1kg", "price": 60.0},
            {"uid": "76 E3 33 06", "name": "Sugar 1kg", "price": 45.0},
            {"uid": "A3 B4 C5 D6", "name": "Whole Wheat Bread", "price": 25.0},
            {"uid": "11 22 33 44", "name": "Milk (1 Gallon)", "price": 50.0},
            {"uid": "99 88 77 66", "name": "Cheddar Cheese", "price": 80.0},
            {"uid": "FF EE DD CC", "name": "Free Range Eggs", "price": 40.0}
        ]
        inserted = 0
        for p in defaults:
            uid_norm = normalize_uid(p["uid"])
            products_collection.update_one(
                {"uid_norm": uid_norm},
                {"$set": {
                    "uid": p["uid"],
                    "name": p["name"],
                    "price": float(p["price"]),
                    "uid_norm": uid_norm
                }},
                upsert=True
            )
            inserted += 1
        return jsonify({"success": True, "message": f"Database seeded with {inserted} default products."})
        
    elif action == "clear_transactions":
        transactions_collection.delete_many({})
        db['feed'].delete_many({})
        carts_collection.update_one({"_id": "cart_1"}, {
            "$set": {
                "items": {},
                "total": 0.0,
                "itemsContained": 0,
                "lastActive": "Cleared"
            }
        })
        return jsonify({"success": True, "message": "Transaction logs and feed have been cleared."})
        
    return jsonify({"success": False, "message": "Invalid database action"}), 400

# ── Auxiliary Web Overhaul APIs ──────────────────────────────────────────────

@app.route("/api/employees", methods=["GET", "POST"])
def manage_employees():
    employees_collection = db["employees"]
    if request.method == "GET":
        emps = list(employees_collection.find({}, {"_id": 0}))
        return jsonify(emps)
    elif request.method == "POST":
        data = request.json
        emp_id = data.get("id")
        if not emp_id:
            return jsonify({"success": False, "message": "Employee ID required"}), 400
        employees_collection.update_one(
            {"id": emp_id},
            {"$set": {
                "id": emp_id,
                "name": data.get("name", "Unknown Name"),
                "role": data.get("role", "Staff"),
                "shift": data.get("shift", "Morning"),
                "status": data.get("status", "Active")
            }},
            upsert=True
        )
        return jsonify({"success": True, "message": "Employee saved successfully"})

@app.route("/api/employees/<emp_id>", methods=["DELETE"])
def delete_employee(emp_id):
    employees_collection = db["employees"]
    result = employees_collection.delete_one({"id": emp_id})
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": "Employee deleted"})
    return jsonify({"success": False, "message": "Employee not found"}), 404

@app.route("/api/feedback", methods=["GET", "POST"])
def manage_feedback():
    feedback_collection = db["feedback"]
    if request.method == "GET":
        feedbacks = list(feedback_collection.find({}, {"_id": 0}))
        ratings = [f.get("rating", 5) for f in feedbacks]
        avg_rating = sum(ratings) / len(ratings) if ratings else 5.0
        return jsonify({
            "feedbacks": feedbacks,
            "averageRating": round(avg_rating, 1),
            "totalResponses": len(feedbacks)
        })
    elif request.method == "POST":
        data = request.json
        rating = data.get("rating", 5)
        comments = data.get("comments", "")
        feedback_collection.insert_one({
            "rating": int(rating),
            "comments": comments,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"success": True, "message": "Feedback submitted successfully"})

@app.route("/api/trolleys", methods=["GET"])
def get_trolleys():
    cart_1 = carts_collection.find_one({"_id": "cart_1"})
    trolley_1_total = cart_1.get("total", 0.0) if cart_1 else 0.0
    trolley_1_items = cart_1.get("itemsContained", 0) if cart_1 else 0
    trolley_1_status = "Active" if (global_ser is not None and global_ser.is_open) else "Idle"
    if trolley_1_items > 0:
        trolley_1_status = "Active"
        
    trolleys = [
        {
            "id": "Trolley-01",
            "status": trolley_1_status,
            "customer": "Lohith Kumar",
            "items": trolley_1_items,
            "total": trolley_1_total,
            "battery": 86,
            "latency": 42 if trolley_1_status == "Active" else 0
        },
        {
            "id": "Trolley-02",
            "status": "Idle",
            "customer": "Jane Smith",
            "items": 0,
            "total": 0.0,
            "battery": 92,
            "latency": 0
        },
        {
            "id": "Trolley-03",
            "status": "Offline",
            "customer": "None",
            "items": 0,
            "total": 0.0,
            "battery": 15,
            "latency": 0
        },
        {
            "id": "Trolley-04",
            "status": "Active",
            "customer": "Amit Patel",
            "items": 3,
            "total": 145.0,
            "battery": 74,
            "latency": 68
        }
    ]
    return jsonify(trolleys)

@app.route("/api/customer/profile", methods=["GET"])
def get_customer_profile():
    transactions = list(transactions_collection.find({}, {"_id": 0}))
    points = sum(int(tx.get("total", 0) // 10) for tx in transactions)
    
    return jsonify({
        "memberId": "MEM-872910",
        "name": "Lohith Kumar",
        "email": "lohith.k@gmail.com",
        "phone": "+91 98765 43210",
        "tier": "Gold Member",
        "points": points + 150,
        "savedAddresses": [
            "123, 4th Cross, Green Glen Layout, Bangalore - 560103",
            "Office: Tech Park Phase 2, Outer Ring Road, Bangalore"
        ],
        "wishlist": [
            {"name": "Rice 1kg", "price": 60.0, "category": "Grains"},
            {"name": "Sugar 1kg", "price": 45.0, "category": "Grains"}
        ]
    })

@app.route("/api/settings/backup", methods=["POST"])
def db_backup():
    try:
        backup_data = {
            "products": list(products_collection.find({}, {"_id": 0})),
            "transactions": list(transactions_collection.find({}, {"_id": 0})),
            "employees": list(db["employees"].find({}, {"_id": 0})),
            "feedback": list(db["feedback"].find({}, {"_id": 0}))
        }
        backup_path = os.path.join(app.static_folder, "backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)
        return jsonify({"success": True, "message": "Database backup completed successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Backup failed: {str(e)}"}), 500
        
@app.route("/api/settings/restore", methods=["POST"])
def db_restore():
    try:
        backup_path = os.path.join(app.static_folder, "backup.json")
        if not os.path.exists(backup_path):
            return jsonify({"success": False, "message": "Backup file (backup.json) not found."}), 404
            
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
            
        if "products" in backup_data and backup_data["products"]:
            products_collection.delete_many({})
            products_collection.insert_many(backup_data["products"])
        if "transactions" in backup_data and backup_data["transactions"]:
            transactions_collection.delete_many({})
            transactions_collection.insert_many(backup_data["transactions"])
        if "employees" in backup_data and backup_data["employees"]:
            db["employees"].delete_many({})
            db["employees"].insert_many(backup_data["employees"])
        if "feedback" in backup_data and backup_data["feedback"]:
            db["feedback"].delete_many({})
            db["feedback"].insert_many(backup_data["feedback"])
            
        return jsonify({"success": True, "message": "Database restored successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Restore failed: {str(e)}"}), 500

def serial_loop():
    global global_ser, current_mode, SERIAL_PORT
    BAUD_RATE = 9600
    last_heartbeat_time = 0
    last_warn_time = 0
    
    while True:
        # Reconnection Logic
        if global_ser is None or not global_ser.is_open:
            try:
                global_ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print(f"Connected to hardware on {SERIAL_PORT}")
                last_warn_time = 0  # Reset warning rate limiter
            except Exception as e:
                # Try auto-detecting connected serial device if configured port fails
                try:
                    import serial.tools.list_ports
                    avail_ports = serial.tools.list_ports.comports()
                    if avail_ports:
                        for p in avail_ports:
                            if p.device != SERIAL_PORT:
                                try:
                                    test_ser = serial.Serial(p.device, BAUD_RATE, timeout=1)
                                    global_ser = test_ser
                                    SERIAL_PORT = p.device
                                    cfg = load_config()
                                    cfg["serialPort"] = SERIAL_PORT
                                    save_config(cfg)
                                    print(f"[AUTO-DETECT] Successfully auto-connected to hardware on {SERIAL_PORT} ({p.description})")
                                    last_warn_time = 0
                                    break
                                except Exception:
                                    pass
                except Exception:
                    pass

                if global_ser is None or not global_ser.is_open:
                    now_t = time.time()
                    if now_t - last_warn_time > 15:
                        print(f"Waiting for hardware on {SERIAL_PORT}... (Please check your connection or close Serial Monitor)")
                        last_warn_time = now_t
                    time.sleep(3)
                    continue

        # Send heartbeat
        try:
            now_t = time.time()
            if now_t - last_heartbeat_time >= 5.0:
                send_command_to_arduino("HEARTBEAT")
                last_heartbeat_time = now_t
        except Exception as e:
            print(f"Heartbeat send error: {e}")

        try:
            line = global_ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"Arduino: {line}")

                # ── Button state diagnostic (every 2s from Arduino) ──────────
                if line.startswith("BTN_STATE:") or line.startswith("[BTN DIAG"):
                    if "RESET=0" in line or "RESET=0" in line:
                        print("[BTN] ✅ Reset button IS being pressed — triggering reset")
                        perform_reset()
                        send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")
                        send_command_to_arduino("BEEP:2")

                # ── Reset — catch ALL possible formats Arduino might send ─────
                elif (line == "RESET"
                      or line.upper() == "RESET"
                      or line.startswith("Reset")
                      or "BTN] RESET" in line
                      or "Bill cleared" in line):
                    print("[RESET] Hardware reset button triggered")
                    perform_reset()
                    send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")

                elif line == "MODE:ADD" or "BTN] ADD" in line:
                    current_mode = "ADD"
                    print("[Mode] Switched to ADD")
                    send_command_to_arduino("LCD:You Can Now|Add Item")
                elif line == "MODE:REMOVE" or "BTN] REMOVE" in line:
                    current_mode = "REMOVE"
                    print("[Mode] Switched to REMOVE")
                    send_command_to_arduino("LCD:You Can Now|Remove Item")
                elif line.startswith("SCAN:") or line.startswith("UID:"):
                    prefix = "SCAN:" if line.startswith("SCAN:") else "UID:"
                    uid = line.split(prefix)[1].strip()
                    cart = carts_collection.find_one({"_id": "cart_1"})
                    if cart and cart.get("status") == "BILL_GENERATED":
                        print("[SCAN] Blocked: Cart is locked in BILL_GENERATED state.")
                        send_command_to_arduino("LCD:Cart Locked!|Pay or Cancel Bill")
                        send_command_to_arduino("BEEP:3")
                        continue
                    product, total, uid_key = process_scan(current_mode, uid)
                    if uid_key == "OUT_OF_STOCK" and product:
                        print(f"[WARN] Out of Stock: {product['name']}")
                        short_pname = product['name'][:16]
                        send_command_to_arduino(f"LCD:{short_pname}|OUT OF STOCK!")
                        send_command_to_arduino("BEEP:3")
                    elif product:
                        action_symbol = "+" if current_mode == "ADD" else "-"
                        short_name = f"{action_symbol} {product['name']}"[:16]
                        send_command_to_arduino(f"LCD:{short_name}|Total: Rs.{total:.2f}")
                        send_command_to_arduino("BEEP:1")
                    else:
                        print(f"[WARN] Unknown UID Scanned: {uid}")
                        send_command_to_arduino("LCD:Unknown Card!|Check Dashboard")
                        send_command_to_arduino("BEEP:3")
        except serial.SerialException as e:
            print(f"Serial connection lost! Reconnecting... Error: {e}")
            if global_ser:
                try:
                    global_ser.close()
                except:
                    pass
            global_ser = None
            time.sleep(2)
        except Exception as e:
            print(f"Serial Logic Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    t = threading.Thread(target=serial_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
