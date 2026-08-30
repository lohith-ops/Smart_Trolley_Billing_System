import threading
import time
import datetime
import serial
import os
import json
import re
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

app = Flask(__name__, static_folder="web-dashboard", static_url_path="")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for static files
CORS(app)

# ── Authentication & Security Configuration ───────────────────────────────────
JWT_SECRET           = os.environ.get("JWT_SECRET", "smart_trolley_secret_key_2026_jwt_token_secure")
JWT_ALGORITHM        = "HS256"
JWT_EXPIRATION_HOURS = 24
TROLLEY_DEVICE_TOKEN = os.environ.get("TROLLEY_DEVICE_TOKEN", "smart_trolley_hw_token_sec_99")

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# ── Configuration File Persistence ───────────────────────────────────────────
CONFIG_FILE = "config.json"

def load_config():
    defaults = {
        "serialPort": "COM3",
        "upiId": "smartsupermarket@okaxis",
        "storeName": "Smart Supermarket",
        "useCustomQr": False,
        "customQrImage": ""
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

# ── Default Trolleys ──────────────────────────────────────────────────────────
DEFAULT_TROLLEYS = [
    {"_id": "TROLLEY-001", "name": "Smart Trolley 001"},
    {"_id": "TROLLEY-002", "name": "Smart Trolley 002"},
    {"_id": "TROLLEY-003", "name": "Smart Trolley 003"},
]

# ── In-Memory Mock Database Fallback ─────────────────────────────────────────
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

# ── MongoDB Connection ────────────────────────────────────────────────────────
mongo_ok = False
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=1500)
    client.server_info()  # Force connection check
    db = client['smart_trolley']
    products_collection     = db['products']
    carts_collection        = db['carts']
    transactions_collection = db['transactions']
    trolleys_collection     = db['trolleys']
    users_collection        = db['users']
    mongo_ok = True
    print("[DB] Connected to local MongoDB successfully.")
except Exception as e:
    print(f"[DB WARN] MongoDB connection failed: {e}")
    print("[DB WARN] Falling back to IN-MEMORY Mock Database. Changes will not persist after restart.")
    client = MockClient()
    db = client['smart_trolley']
    products_collection     = db['products']
    carts_collection        = db['carts']
    transactions_collection = db['transactions']
    trolleys_collection     = db['trolleys']
    users_collection        = db['users']

    # Seed default products into mock database
    defaults = [
        {"uid": "5C 1E 7E 05", "name": "Rice 1kg",          "price": 60.0,  "category": "Grains", "stock": 45, "shelf": "Aisle A - Shelf 1", "offer": "Buy 1 Get 1 Free"},
        {"uid": "76 E3 33 06", "name": "Sugar 1kg",          "price": 45.0,  "category": "Grains", "stock": 12, "shelf": "Aisle A - Shelf 2", "offer": "No Active Offers"},
        {"uid": "A3 B4 C5 D6", "name": "Whole Wheat Bread",  "price": 25.0,  "category": "Bakery", "stock": 8,  "shelf": "Aisle B - Shelf 1", "offer": "10% Off"},
        {"uid": "11 22 33 44", "name": "Milk (1 Gallon)",    "price": 50.0,  "category": "Dairy",  "stock": 32, "shelf": "Aisle C - Shelf 1", "offer": "No Active Offers"},
        {"uid": "99 88 77 66", "name": "Cheddar Cheese",     "price": 80.0,  "category": "Dairy",  "stock": 15, "shelf": "Aisle C - Shelf 1", "offer": "20% Off"},
        {"uid": "FF EE DD CC", "name": "Free Range Eggs",    "price": 40.0,  "category": "Dairy",  "stock": 24, "shelf": "Aisle C - Shelf 1", "offer": "No Active Offers"},
    ]
    for p in defaults:
        uid_norm = p["uid"].replace(" ", "").upper()
        p["uid_norm"] = uid_norm
        products_collection.data.append(p)

# ── User Accounts & Authentication Setup ─────────────────────────────────────
DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "name":     "System Administrator",
        "role":     "admin",
        "email":    "admin@smarttrolley.local"
    },
    {
        "username": "manager",
        "password": "manager123",
        "name":     "Store Manager",
        "role":     "manager",
        "email":    "manager@smarttrolley.local"
    },
    {
        "username": "cashier",
        "password": "cashier123",
        "name":     "Billing Cashier",
        "role":     "cashier",
        "email":    "cashier@smarttrolley.local"
    },
    {
        "username": "customer",
        "password": "customer123",
        "name":     "Lohith Kumar",
        "role":     "customer",
        "email":    "lohith.k@gmail.com"
    }
]

def init_users():
    """Seed default administrative & staff users on startup and sync existing employees."""
    for u in DEFAULT_USERS:
        existing = users_collection.find_one({"username": u["username"]})
        if not existing:
            users_collection.insert_one({
                "username":      u["username"],
                "password_hash": generate_password_hash(u["password"]),
                "name":          u["name"],
                "role":          u["role"],
                "email":         u["email"],
                "created_at":    time.time(),
                "status":        "Active"
            })
            print(f"[AUTH] Seeded user account: {u['username']} ({u['role']})")

    # Sync existing employees in db['employees'] to users_collection
    try:
        employees_collection = db["employees"]
        for emp in employees_collection.find({}):
            emp_name = (emp.get("name") or "").strip()
            emp_id = (emp.get("id") or "").strip()
            emp_role = (emp.get("role") or "Cashier").strip().lower()
            if emp_role not in ["admin", "manager", "cashier", "customer"]:
                emp_role = "cashier"

            usernames_to_check = []
            if emp.get("username"):
                usernames_to_check.append(emp["username"].lower())
            if emp_name:
                usernames_to_check.append(emp_name.lower().replace(" ", ""))
            if emp_id:
                usernames_to_check.append(emp_id.lower())

            for uname in usernames_to_check:
                if uname and not users_collection.find_one({"username": uname}):
                    default_pw = f"{uname}123"
                    users_collection.insert_one({
                        "username":      uname,
                        "password_hash": generate_password_hash(default_pw),
                        "name":          emp_name or uname,
                        "role":          emp_role,
                        "status":        emp.get("status", "Active"),
                        "created_at":    time.time()
                    })
                    print(f"[AUTH] Auto-synced employee account: {uname} (Role: {emp_role}, Initial PW: {default_pw})")
    except Exception as ex:
        print(f"[AUTH WARN] Error auto-syncing employee accounts: {ex}")

def generate_token(user):
    """Generate signed JWT token valid for JWT_EXPIRATION_HOURS."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "username": user["username"],
        "role":     user.get("role", "cashier"),
        "name":     user.get("name", user["username"]),
        "email":    user.get("email", ""),
        "exp":      now_utc + datetime.timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat":      now_utc
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token_str):
    """Decode and validate a JWT string."""
    try:
        return jwt.decode(token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception as e:
        return None

def require_auth(roles=None, allow_device=False):
    """
    Decorator enforcing token-based authentication and role permissions.
    roles: list of allowed roles (e.g. ['admin', 'manager']), or None for any valid logged-in user.
    allow_device: if True, allows requests signed with X-Trolley-Token or X-API-Key.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check device hardware token if allowed
            if allow_device:
                dev_token = request.headers.get("X-Trolley-Token") or request.headers.get("X-API-Key")
                if dev_token == TROLLEY_DEVICE_TOKEN:
                    return f(*args, **kwargs)

            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return jsonify({"success": False, "message": "Authentication required. Authorization header missing."}), 401
            
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return jsonify({"success": False, "message": "Invalid Authorization header format. Expected 'Bearer <token>'."}), 401
            
            token = parts[1]
            payload = decode_token(token)
            if not payload:
                return jsonify({"success": False, "message": "Invalid or expired session token. Please log in again."}), 401
            
            if roles and payload.get("role") not in roles:
                return jsonify({
                    "success": False, 
                    "message": f"Access denied. Requires one of roles: {', '.join(roles)}. Your role is '{payload.get('role')}'."
                }), 403
            
            request.current_user = payload
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ── Global State (Arduino backward-compat) ────────────────────────────────────
current_mode = "ADD"
global_ser   = None

config_data = load_config()
SERIAL_PORT  = config_data.get("serialPort", "COM3")

# ── Trolley Cart Helpers ──────────────────────────────────────────────────────

def _trolley_cart_id(trolley_id: str) -> str:
    """Return the cart document _id for a trolley. Legacy 'cart_1' maps to TROLLEY-001."""
    return trolley_id

def init_trolleys():
    """Seed the trolleys collection and carts for each default trolley on startup."""
    for t in DEFAULT_TROLLEYS:
        tid = t["_id"]
        existing = trolleys_collection.find_one({"_id": tid})
        if not existing:
            trolleys_collection.insert_one({
                "_id":              tid,
                "name":             t["name"],
                "status":           "offline",
                "battery":          0,
                "ip_address":       "",
                "wifi_rssi":        0,
                "last_seen":        0,
                "firmware_version": "2.0",
                "cart_value":       0.0,
                "item_count":       0,
                "current_mode":     "ADD"
            })
        # Ensure cart exists for trolley
        init_cart(tid)

    # Backward-compat: ensure old 'cart_1' still resolves to TROLLEY-001
    # (We now use TROLLEY-001 as _id, but keep a forwarding alias)
    init_cart("TROLLEY-001")

def init_cart(trolley_id: str):
    """Ensure a cart document exists for the given trolley_id."""
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart:
        carts_collection.insert_one({
            "_id":            cart_id,
            "trolley_id":     trolley_id,
            "items":          {},
            "total":          0.0,
            "itemsContained": 0,
            "status":         "ACTIVE",
            "lastActive":     "Just now"
        })
    else:
        # Ensure trolley_id field exists on older documents
        if "trolley_id" not in cart:
            carts_collection.update_one({"_id": cart_id}, {"$set": {"trolley_id": trolley_id}})
        if "status" not in cart:
            carts_collection.update_one({"_id": cart_id}, {"$set": {"status": "ACTIVE"}})

init_trolleys()
init_users()

# ── Static File Routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    full_path = os.path.join(app.static_folder, path)
    if os.path.exists(full_path) and not os.path.isdir(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

# ── Utility ───────────────────────────────────────────────────────────────────

def send_command_to_arduino(cmd):
    """Send command to Arduino over Serial. e.g. LCD:Line1|Line2, BEEP:1"""
    global global_ser
    if global_ser and global_ser.is_open:
        try:
            msg = f"{cmd}\n"
            global_ser.write(msg.encode('utf-8'))
            print(f"[SERIAL OUT] {msg.strip()}")
        except Exception as e:
            print(f"[SERIAL ERROR] {e}")

def normalize_uid(uid_str):
    """Normalize UID to uppercase no-space format. '5C 1E 7E 05' → '5C1E7E05'."""
    return uid_str.replace(' ', '').replace('-', '').upper()

# ── Core Cart Logic (trolley-scoped) ─────────────────────────────────────────

def process_scan(action, uid, trolley_id="TROLLEY-001"):
    """
    Process an RFID scan for a specific trolley.
    Inventory (products_collection) is always global/shared.
    Cart is scoped to trolley_id.
    Returns: (product, total, uid_key)
    """
    uid_key = normalize_uid(uid)

    # Product lookup — try all common formats stored in DB
    product = products_collection.find_one({"uid": uid})
    if not product:
        product = products_collection.find_one({"uid": uid_key})
    if not product:
        spaced = ' '.join(uid_key[i:i+2] for i in range(0, len(uid_key), 2))
        product = products_collection.find_one({"uid": spaced})
    if not product:
        product = products_collection.find_one({"uid_norm": uid_key})

    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart:
        init_cart(trolley_id)
        cart = carts_collection.find_one({"_id": cart_id})
    items = cart.get("items", {}) if cart else {}

    if not product:
        db['feed'].insert_one({
            "actionType":  "UNKNOWN_SCAN",
            "uid":         uid_key,
            "trolley_id":  trolley_id,
            "timestamp":   time.time()
        })
        return None, cart.get("total", 0.0), uid_key

    if action == "ADD":
        current_stock = product.get("stock")
        if current_stock is None:
            current_stock = 20
        if current_stock <= 0:
            db['feed'].insert_one({
                "actionType":   "OUT_OF_STOCK",
                "productName":  product["name"],
                "trolley_id":   trolley_id,
                "timestamp":    time.time()
            })
            return product, cart.get("total", 0.0), "OUT_OF_STOCK"

        # Deduct from global (centralized) inventory
        new_stock = current_stock - 1
        products_collection.update_one({"_id": product["_id"]}, {"$set": {"stock": new_stock}})
        product["stock"] = new_stock

        if uid_key in items:
            items[uid_key]["quantity"] += 1
            items[uid_key]["subtotal"] = items[uid_key]["quantity"] * product["price"]
        else:
            items[uid_key] = {
                "name":     product["name"],
                "price":    product["price"],
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
            # Restore stock in global inventory
            curr_stk = product.get("stock", 0)
            products_collection.update_one({"_id": product["_id"]}, {"$set": {"stock": curr_stk + 1}})
            product["stock"] = curr_stk + 1

    elif action == "REMOVE_ALL":
        if uid_key in items:
            qty_to_restore = items[uid_key]["quantity"]
            del items[uid_key]
            curr_stk = product.get("stock", 0)
            products_collection.update_one({"_id": product["_id"]}, {"$set": {"stock": curr_stk + qty_to_restore}})
            product["stock"] = curr_stk + qty_to_restore

    total = sum(item["subtotal"] for item in items.values())
    items_contained = sum(item["quantity"] for item in items.values())

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {
            "items":          items,
            "total":          total,
            "itemsContained": items_contained,
            "lastActive":     "Just now"
        }
    })

    # Sync cart_value & item_count to trolleys collection
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {
            "cart_value": total,
            "item_count": items_contained
        }
    })

    db['feed'].insert_one({
        "actionType":   "REMOVE" if action in ["REMOVE", "REMOVE_ALL"] else "ADD",
        "productName":  product["name"],
        "productPrice": product["price"],
        "trolley_id":   trolley_id,
        "timestamp":    time.time()
    })

    return product, total, uid_key


def perform_checkout(trolley_id="TROLLEY-001"):
    """Checkout a specific trolley's cart and save a transaction."""
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if cart and cart.get("itemsContained", 0) > 0:
        saved_items = dict(cart["items"])
        transactions_collection.insert_one({
            "trolley_id":     trolley_id,
            "items":          cart["items"],
            "total":          cart["total"],
            "paymentMethod":  "Unknown",
            "timestamp":      time.time()
        })
        carts_collection.update_one({"_id": cart_id}, {
            "$set": {
                "items":          {},
                "total":          0.0,
                "itemsContained": 0,
                "status":         "ACTIVE",
                "lastActive":     "Checked out"
            }
        })
        trolleys_collection.update_one({"_id": trolley_id}, {
            "$set": {"cart_value": 0.0, "item_count": 0}
        })
        db['feed'].insert_one({
            "actionType": "CHECKOUT",
            "total":      cart["total"],
            "trolley_id": trolley_id,
            "timestamp":  time.time()
        })
        send_command_to_arduino("LCD:Checked Out!|Total: Rs.0.00")
        send_command_to_arduino("BEEP:2")
        return True, cart["total"], saved_items
    return False, 0.0, {}


def perform_reset(trolley_id="TROLLEY-001"):
    """Reset a trolley's cart without saving as transaction. Restores global stock."""
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if cart and "items" in cart:
        for item_key, item_val in cart.get("items", {}).items():
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

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {
            "items":          {},
            "total":          0.0,
            "itemsContained": 0,
            "status":         "ACTIVE",
            "lastActive":     "Reset"
        }
    })
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {"cart_value": 0.0, "item_count": 0}
    })
    db['feed'].insert_one({
        "actionType": "RESET",
        "total":      cart.get("total", 0.0) if cart else 0.0,
        "trolley_id": trolley_id,
        "timestamp":  time.time()
    })
    send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")
    send_command_to_arduino("BEEP:2")
    return True

# ── Authentication API ────────────────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.json or {}
    raw_user = (data.get("username") or "").strip()
    username = raw_user.lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    # Look up user by username, employee ID, or case-insensitive full name
    user = users_collection.find_one({
        "$or": [
            {"username": username},
            {"id": {"$regex": f"^{re.escape(raw_user)}$", "$options": "i"}},
            {"name": {"$regex": f"^{re.escape(raw_user)}$", "$options": "i"}}
        ]
    })

    # If user not in users_collection, check db['employees']
    if not user:
        emp = db['employees'].find_one({
            "$or": [
                {"username": username},
                {"id": {"$regex": f"^{re.escape(raw_user)}$", "$options": "i"}},
                {"name": {"$regex": f"^{re.escape(raw_user)}$", "$options": "i"}}
            ]
        })
        if emp:
            # Check if there is an account under their ID or username
            emp_user = emp.get("username", emp.get("id", "").lower())
            user = users_collection.find_one({"username": emp_user})

    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"success": False, "message": "Invalid username or password."}), 401

    if user.get("status") == "Inactive":
        return jsonify({"success": False, "message": "Your account has been deactivated. Please contact an administrator."}), 403

    token = generate_token(user)
    
    # Log auth activity
    db['feed'].insert_one({
        "actionType": "USER_LOGIN",
        "username":   username,
        "role":       user.get("role"),
        "timestamp":  time.time()
    })

    return jsonify({
        "success": True,
        "token": token,
        "user": {
            "username": user["username"],
            "name":     user.get("name", user["username"]),
            "role":     user.get("role", "cashier"),
            "email":    user.get("email", "")
        }
    })

@app.route("/api/auth/me", methods=["GET"])
@require_auth()
def auth_me():
    user = users_collection.find_one({"username": request.current_user["username"]}, {"_id": 0, "password_hash": 0})
    if not user:
        return jsonify({"success": True, "user": request.current_user})
    return jsonify({"success": True, "user": user})

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
PHONE_REGEX = re.compile(r'^(\+91[\-\s]?)?[0-9]{10}$')

@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    """Public customer self-registration endpoint (role is locked to customer)."""
    data = request.json or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip()
    phone    = (data.get("phone") or "").strip()

    if not username or not password or not name:
        return jsonify({"success": False, "message": "Username, password, and full name are required."}), 400

    if not USERNAME_REGEX.match(username):
        return jsonify({"success": False, "message": "Username must be 3-30 characters long and contain only letters, numbers, or underscores."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address (e.g. admin@gmail.com)."}), 400

    if phone and not PHONE_REGEX.match(phone):
        return jsonify({"success": False, "message": "Please enter a valid 10-digit phone number."}), 400

    # Check for existing username
    existing = users_collection.find_one({"username": username})
    if existing:
        return jsonify({"success": False, "message": f"Username '{username}' is already taken. Please choose another."}), 400

    # Check for existing email if provided
    if email:
        existing_email = users_collection.find_one({"email": email})
        if existing_email:
            return jsonify({"success": False, "message": f"An account with email '{email}' already exists."}), 400

    # Role is strictly enforced to 'customer'
    new_user = {
        "username":      username,
        "password_hash": generate_password_hash(password),
        "name":          name,
        "role":          "customer",
        "email":         email,
        "phone":         phone,
        "created_at":    time.time(),
        "status":        "Active"
    }

    users_collection.insert_one(new_user)

    # Automatically generate JWT token for instant session login
    token = generate_token(new_user)

    # Activity log
    db['feed'].insert_one({
        "actionType": "CUSTOMER_REGISTER",
        "username":   username,
        "role":       "customer",
        "timestamp":  time.time()
    })

    return jsonify({
        "success": True,
        "message": "Account created successfully!",
        "token": token,
        "user": {
            "username": username,
            "name":     name,
            "role":     "customer",
            "email":    email,
            "phone":    phone
        }
    })

@app.route("/api/auth/register", methods=["POST"])
@require_auth(roles=["admin"])
def auth_register():
    data = request.json or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    name     = (data.get("name") or "").strip()
    role     = (data.get("role") or "cashier").strip().lower()
    email    = (data.get("email") or "").strip()

    if not username or not password or not name:
        return jsonify({"success": False, "message": "Username, password, and full name are required."}), 400

    if not USERNAME_REGEX.match(username):
        return jsonify({"success": False, "message": "Username must be 3-30 characters long and contain only letters, numbers, or underscores."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    if role not in ["admin", "manager", "cashier", "customer"]:
        return jsonify({"success": False, "message": "Invalid role specified."}), 400

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400

    existing = users_collection.find_one({"username": username})
    if existing:
        return jsonify({"success": False, "message": f"User '{username}' already exists."}), 400

    users_collection.insert_one({
        "username":      username,
        "password_hash": generate_password_hash(password),
        "name":          name,
        "role":          role,
        "email":         email,
        "created_at":    time.time(),
        "status":        "Active"
    })

    return jsonify({"success": True, "message": f"User '{username}' ({role}) registered successfully."})

@app.route("/api/auth/users", methods=["GET"])
@require_auth(roles=["admin", "manager"])
def get_auth_users():
    users = list(users_collection.find({}, {"_id": 0, "password_hash": 0}))
    return jsonify(users)

@app.route("/api/auth/users/<username>", methods=["DELETE"])
@require_auth(roles=["admin"])
def delete_auth_user(username):
    username = username.strip().lower()
    if username == "admin":
        return jsonify({"success": False, "message": "Root admin account cannot be deleted."}), 400
    
    result = users_collection.delete_one({"username": username})
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": f"User '{username}' deleted successfully."})
    return jsonify({"success": False, "message": "User not found."}), 404

@app.route("/api/auth/users/<username>/password", methods=["PUT"])
@require_auth(roles=["admin"])
def admin_reset_user_password(username):
    """Admin endpoint to set or reset a password for any user/employee."""
    username = username.strip().lower()
    data = request.json or {}
    new_password = data.get("password") or data.get("new_password") or ""

    if not new_password:
        return jsonify({"success": False, "message": "New password is required."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"success": False, "message": f"User '{username}' not found."}), 404

    users_collection.update_one(
        {"username": username},
        {"$set": {
            "password_hash": generate_password_hash(new_password),
            "updated_at": time.time()
        }}
    )

    db['feed'].insert_one({
        "actionType": "ADMIN_PASSWORD_RESET",
        "target_user": username,
        "reset_by": request.current_user.get("username", "admin"),
        "timestamp": time.time()
    })

    return jsonify({"success": True, "message": f"Password for '{username}' updated successfully."})

@app.route("/api/auth/change-password", methods=["POST"])
@require_auth()
def auth_change_own_password():
    """Endpoint for any logged-in user to change their own password."""
    data = request.json or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Both current password and new password are required."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters long."}), 400

    username = request.current_user["username"]
    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"success": False, "message": "User account not found."}), 404

    if not check_password_hash(user.get("password_hash", ""), current_password):
        return jsonify({"success": False, "message": "Current password is incorrect."}), 400

    users_collection.update_one(
        {"username": username},
        {"$set": {
            "password_hash": generate_password_hash(new_password),
            "updated_at": time.time()
        }}
    )

    db['feed'].insert_one({
        "actionType": "USER_PASSWORD_CHANGE",
        "username": username,
        "timestamp": time.time()
    })

    return jsonify({"success": True, "message": "Your password has been changed successfully."})

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    return jsonify({"success": True, "message": "Logged out successfully."})

# ── Products API ──────────────────────────────────────────────────────────────

@app.route("/api/products", methods=["GET"])
def get_products():
    products = list(products_collection.find({}, {"_id": 0}))
    return jsonify(products)

@app.route("/api/products/register", methods=["POST"])
@require_auth(roles=["admin", "manager"])
def register_product():
    data = request.json or {}
    uid = (data.get("uid") or "").strip()
    name = (data.get("name") or "").strip()
    price = data.get("price")
    stock = data.get("stock", 20)

    if not uid or not name or price is None:
        return jsonify({"success": False, "message": "RFID UID, Product Name, and Price are required."}), 400

    if len(name) < 2:
        return jsonify({"success": False, "message": "Product name must be at least 2 characters long."}), 400

    try:
        price_float = float(price)
        if price_float <= 0:
            return jsonify({"success": False, "message": "Price must be greater than Rs. 0.00."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Price must be a valid positive number."}), 400

    try:
        stock_int = int(stock)
        if stock_int < 0:
            return jsonify({"success": False, "message": "Stock quantity cannot be negative."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Stock must be a valid integer."}), 400

    uid_norm = normalize_uid(uid)
    if len(uid_norm) < 4:
        return jsonify({"success": False, "message": "Invalid RFID UID format (must have at least 4 hex characters)."}), 400

    products_collection.update_one(
        {"uid_norm": uid_norm},
        {"$set": {
            "uid":      uid,
            "name":     name,
            "price":    price_float,
            "uid_norm": uid_norm,
            "stock":    stock_int,
            "category": data.get("category", "Grocery"),
            "shelf":    data.get("shelf", "Aisle A - Shelf 1"),
            "offer":    data.get("offer", "No Active Offers")
        }},
        upsert=True
    )
    db['feed'].insert_one({
        "actionType":   "PRODUCT_REGISTERED",
        "productName":  name,
        "productPrice": price_float,
        "uid":          uid,
        "timestamp":    time.time()
    })
    print(f"[PRODUCT] Registered: {name} (Rs.{price_float}) -> {uid_norm} (Stock: {stock_int})")
    return jsonify({"success": True, "message": f"Product '{name}' saved successfully."})

@app.route("/api/products/<uid>", methods=["DELETE"])
@require_auth(roles=["admin", "manager"])
def delete_product(uid):
    uid_norm = normalize_uid(uid)
    result = products_collection.delete_one({"uid_norm": uid_norm})
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": "Product deleted successfully"})
    return jsonify({"success": False, "message": "Product not found"}), 404

# ── Dashboard API ─────────────────────────────────────────────────────────────

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    now = datetime.datetime.now()
    today_start = datetime.datetime(now.year, now.month, now.day).timestamp()
    pipeline = [
        {"$match": {"timestamp": {"$gte": today_start}}},
        {"$group": {"_id": None, "totalRevenue": {"$sum": "$total"}}}
    ]
    rev_result = list(transactions_collection.aggregate(pipeline))
    revenue = rev_result[0]["totalRevenue"] if rev_result else 0.0

    # Items scanned (all transactions + all live carts)
    items_scanned = 0
    all_txs = list(transactions_collection.find({}, {"items": 1}))
    for tx in all_txs:
        for item_key, item_val in tx.get("items", {}).items():
            items_scanned += item_val.get("quantity", 0)

    all_carts = list(carts_collection.find({}))
    for c in all_carts:
        items_scanned += c.get("itemsContained", 0)

    # Active carts
    active_carts = []
    for c in all_carts:
        if c.get("itemsContained", 0) > 0:
            raw_id = c["_id"]
            # Provide a short display id: last segment after '-' or full id
            display_id = raw_id.split("-")[-1] if "-" in str(raw_id) else str(raw_id)
            active_carts.append({
                "id":             display_id,
                "trolley_id":     c.get("trolley_id", raw_id),
                "total":          c["total"],
                "itemsContained": c["itemsContained"],
                "lastActive":     c.get("lastActive", ""),
                "items":          c.get("items", {}),
                "status":         c.get("status", "ACTIVE")
            })

    # Trolley summary
    all_trolleys = list(trolleys_collection.find({}))
    online_count = sum(1 for t in all_trolleys if t.get("status") == "online")
    total_trolleys = len(all_trolleys)

    # Feed (most recent 6 events)
    feed_cursor = db['feed'].find({}, {"_id": 0}).sort("timestamp", -1).limit(6)
    feed_items = list(feed_cursor)

    return jsonify({
        "revenue":          revenue,
        "scannedItems":     items_scanned,
        "activeCarts":      active_carts,
        "feed":             feed_items,
        "currentMode":      current_mode,
        "arduinoConnected": global_ser is not None and global_ser.is_open,
        "serialPort":       SERIAL_PORT,
        "trolleyCount":     total_trolleys,
        "onlineTrolleys":   online_count
    })

# ── Cart APIs (all scoped to trolley_id, backward-compatible) ─────────────────

@app.route("/api/cart/action", methods=["POST"])
def cart_action():
    data = request.json
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    action     = data.get("action")
    uid        = data.get("uid")

    # Ensure cart and trolley exist
    init_cart(trolley_id)

    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if cart and cart.get("status") == "BILL_GENERATED":
        return jsonify({"success": False, "message": "Cart is locked! Complete payment or cancel bill to modify cart."}), 400

    product, total, uid_key = process_scan(action, uid, trolley_id)
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

    cart = carts_collection.find_one({"_id": cart_id})
    return jsonify({
        "success":   True,
        "product":   {"name": product["name"], "price": product["price"], "stock": product.get("stock", 0)},
        "action":    action,
        "trolley_id": trolley_id,
        "cart":      {"total": total, "itemsContained": cart["itemsContained"]}
    })

@app.route("/api/reset", methods=["POST"])
@app.route("/api/cart/reset", methods=["POST"])
def reset_cart():
    data = request.json or {}
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    init_cart(trolley_id)
    perform_reset(trolley_id)
    return jsonify({"success": True, "message": f"Cart for {trolley_id} has been reset"})

@app.route("/api/cart/generate-bill", methods=["POST"])
def generate_bill():
    data = request.json or {}
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — scan items first"}), 400

    total       = cart["total"]
    grand_total = total
    subtotal    = grand_total / 1.18
    cgst        = subtotal * 0.09
    sgst        = subtotal * 0.09

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {"status": "BILL_GENERATED", "lastActive": "Bill generated"}
    })
    send_command_to_arduino(f"LCD:Pay Rs.{grand_total:.2f}|Scan QR to Pay")
    send_command_to_arduino("BEEP:1")
    db['feed'].insert_one({
        "actionType": "BILL_GENERATED",
        "total":      grand_total,
        "trolley_id": trolley_id,
        "timestamp":  time.time()
    })

    return jsonify({
        "success":    True,
        "trolley_id": trolley_id,
        "subtotal":   round(subtotal, 2),
        "cgst":       round(cgst, 2),
        "sgst":       round(sgst, 2),
        "total":      round(grand_total, 2),
        "items":      cart["items"]
    })

@app.route("/api/cart/cancel-bill", methods=["POST"])
def cancel_bill():
    data = request.json or {}
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart:
        return jsonify({"success": False, "message": "Cart not found"}), 404

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {"status": "ACTIVE", "lastActive": "Scanning"}
    })
    total = cart.get("total", 0.0)
    send_command_to_arduino(f"LCD:Bill Cancelled|Total: Rs.{total:.2f}")
    send_command_to_arduino("BEEP:1")
    db['feed'].insert_one({
        "actionType": "BILL_CANCELLED",
        "total":      total,
        "trolley_id": trolley_id,
        "timestamp":  time.time()
    })
    return jsonify({"success": True, "message": "Bill cancelled, cart returned to scanning", "total": total})

@app.route("/api/cart/pay", methods=["POST"])
def pay_bill():
    data = request.json or {}
    trolley_id     = data.get("trolley_id", "TROLLEY-001")
    payment_method = data.get("paymentMethod", "UPI")

    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — scan items first"}), 400

    saved_items = dict(cart["items"])
    total       = cart["total"]
    timestamp   = time.time()

    transactions_collection.insert_one({
        "trolley_id":    trolley_id,
        "items":         saved_items,
        "total":         total,
        "paymentMethod": payment_method,
        "timestamp":     timestamp
    })

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {
            "items":          {},
            "total":          0.0,
            "itemsContained": 0,
            "status":         "ACTIVE",
            "lastActive":     f"Paid via {payment_method}"
        }
    })
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {"cart_value": 0.0, "item_count": 0}
    })
    db['feed'].insert_one({
        "actionType":    "CHECKOUT",
        "total":         total,
        "paymentMethod": payment_method,
        "trolley_id":    trolley_id,
        "timestamp":     timestamp
    })
    send_command_to_arduino("LCD:Checked Out!|Total: Rs.0.00")
    send_command_to_arduino("BEEP:2")

    return jsonify({
        "success":   True,
        "message":   "Payment successful",
        "trolley_id": trolley_id,
        "total":     total,
        "items":     saved_items,
        "timestamp": timestamp
    })

# Backward-compat alias
@app.route("/api/checkout", methods=["POST"])
def checkout():
    return pay_bill()

# ── Simulator Mode API ────────────────────────────────────────────────────────

@app.route("/api/simulator/mode", methods=["POST"])
def set_simulator_mode():
    global current_mode
    data = request.json
    mode = data.get("mode")
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    if mode not in ["ADD", "REMOVE"]:
        return jsonify({"success": False, "message": "Invalid mode"}), 400
    current_mode = mode
    # Update mode in trolley doc
    trolleys_collection.update_one({"_id": trolley_id}, {"$set": {"current_mode": mode}})
    if current_mode == "ADD":
        send_command_to_arduino("LCD:You Can Now|Add Item")
    else:
        send_command_to_arduino("LCD:You Can Now|Remove Item")
    return jsonify({"success": True, "mode": current_mode, "trolley_id": trolley_id})

# ── Trolley Registry APIs ─────────────────────────────────────────────────────

OFFLINE_THRESHOLD_SECS = 45  # Trolley marked offline after this many seconds with no heartbeat

@app.route("/api/trolleys", methods=["GET"])
def get_trolleys():
    """Return all trolleys with live status derived from heartbeat last_seen times."""
    now_ts = time.time()
    all_trolleys = list(trolleys_collection.find({}))

    result = []
    for t in all_trolleys:
        tid        = t["_id"]
        last_seen  = t.get("last_seen", 0)
        is_online  = (last_seen > 0) and ((now_ts - last_seen) < OFFLINE_THRESHOLD_SECS)
        status     = "online" if is_online else "offline"

        # Pull live cart data
        cart = carts_collection.find_one({"_id": _trolley_cart_id(tid)})
        cart_value  = cart.get("total", 0.0) if cart else 0.0
        item_count  = cart.get("itemsContained", 0) if cart else 0
        cart_status = cart.get("status", "ACTIVE") if cart else "ACTIVE"

        last_seen_str = "Never"
        if last_seen > 0:
            elapsed = int(now_ts - last_seen)
            if elapsed < 60:
                last_seen_str = f"{elapsed}s ago"
            elif elapsed < 3600:
                last_seen_str = f"{elapsed // 60}m ago"
            else:
                last_seen_str = f"{elapsed // 3600}h ago"

        result.append({
            "id":               tid,
            "name":             t.get("name", tid),
            "status":           status,
            "battery":          t.get("battery", 0),
            "ip_address":       t.get("ip_address", ""),
            "wifi_rssi":        t.get("wifi_rssi", 0),
            "last_seen":        last_seen,
            "last_seen_str":    last_seen_str,
            "firmware_version": t.get("firmware_version", ""),
            "cart_value":       cart_value,
            "item_count":       item_count,
            "cart_status":      cart_status,
            "current_mode":     t.get("current_mode", "ADD"),
            # Legacy fields kept for backward compatibility with old trolleys.js
            "customer":         t.get("customer", "None"),
            "items":            item_count,
            "total":            cart_value,
            "latency":          t.get("latency", 0)
        })

    return jsonify(result)

@app.route("/api/trolleys/<trolley_id>", methods=["GET"])
def get_trolley_detail(trolley_id):
    """Return full detail for a single trolley including its current cart."""
    now_ts = time.time()
    t = trolleys_collection.find_one({"_id": trolley_id})
    if not t:
        return jsonify({"success": False, "message": f"Trolley {trolley_id} not found"}), 404

    last_seen = t.get("last_seen", 0)
    is_online = (last_seen > 0) and ((now_ts - last_seen) < OFFLINE_THRESHOLD_SECS)
    status    = "online" if is_online else "offline"

    cart = carts_collection.find_one({"_id": _trolley_cart_id(trolley_id)})
    cart_data = {}
    if cart:
        cart_data = {
            "items":          cart.get("items", {}),
            "total":          cart.get("total", 0.0),
            "itemsContained": cart.get("itemsContained", 0),
            "status":         cart.get("status", "ACTIVE"),
            "lastActive":     cart.get("lastActive", "")
        }

    last_seen_str = "Never"
    if last_seen > 0:
        elapsed = int(now_ts - last_seen)
        if elapsed < 60:
            last_seen_str = f"{elapsed}s ago"
        elif elapsed < 3600:
            last_seen_str = f"{elapsed // 60}m ago"
        else:
            last_seen_str = f"{elapsed // 3600}h ago"

    return jsonify({
        "success":          True,
        "id":               trolley_id,
        "name":             t.get("name", trolley_id),
        "status":           status,
        "battery":          t.get("battery", 0),
        "ip_address":       t.get("ip_address", ""),
        "wifi_rssi":        t.get("wifi_rssi", 0),
        "last_seen":        last_seen,
        "last_seen_str":    last_seen_str,
        "firmware_version": t.get("firmware_version", ""),
        "current_mode":     t.get("current_mode", "ADD"),
        "cart":             cart_data
    })

@app.route("/api/trolleys/<trolley_id>/cart", methods=["GET"])
def get_trolley_cart(trolley_id):
    """Return only the cart for a specific trolley."""
    init_cart(trolley_id)
    cart = carts_collection.find_one({"_id": _trolley_cart_id(trolley_id)})
    if not cart:
        return jsonify({"success": False, "message": "Cart not found"}), 404
    return jsonify({
        "success":        True,
        "trolley_id":     trolley_id,
        "items":          cart.get("items", {}),
        "total":          cart.get("total", 0.0),
        "itemsContained": cart.get("itemsContained", 0),
        "status":         cart.get("status", "ACTIVE"),
        "lastActive":     cart.get("lastActive", "")
    })

@app.route("/api/trolleys", methods=["POST"])
@app.route("/api/trolley/register", methods=["POST"])
def register_trolley():
    """Register or update a trolley in the registry. Can be called from Web UI or ESP32."""
    data = request.json or {}
    trolley_id = (data.get("trolley_id") or data.get("id") or "").strip().upper()
    name = (data.get("name") or trolley_id).strip()
    fw_ver = data.get("firmware_version", "2.0")
    ip_addr = data.get("ip_address", "")
    section = data.get("section", "General")

    if not trolley_id:
        return jsonify({"success": False, "message": "Trolley ID is required (e.g. TROLLEY-004)"}), 400

    now_ts = time.time()
    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {
            "_id":              trolley_id,
            "name":             name,
            "firmware_version": fw_ver,
            "ip_address":       ip_addr,
            "section":          section,
            "status":           data.get("status", "offline"),
            "battery":          data.get("battery", 100),
            "wifi_rssi":        data.get("wifi_rssi", -50),
            "cart_value":       0.0,
            "item_count":       0,
            "current_mode":     "ADD",
            "last_seen":        now_ts if data.get("status") == "online" else 0
        }},
        upsert=True
    )
    init_cart(trolley_id)
    print(f"[TROLLEY] Registered: {trolley_id} ({name})")
    return jsonify({"success": True, "message": f"Trolley {trolley_id} ({name}) registered successfully!"})

@app.route("/api/trolleys/<trolley_id>", methods=["DELETE"])
@require_auth(roles=["admin", "manager"])
def delete_trolley(trolley_id):
    """Decommission / remove a trolley from the fleet."""
    trolley_id = trolley_id.strip().upper()
    res = trolleys_collection.delete_one({"_id": trolley_id})
    carts_collection.delete_one({"_id": _trolley_cart_id(trolley_id)})
    if res.deleted_count > 0:
        return jsonify({"success": True, "message": f"Trolley {trolley_id} removed from fleet."})
    return jsonify({"success": False, "message": f"Trolley {trolley_id} not found."}), 404

@app.route("/api/trolley/heartbeat", methods=["POST"])
def trolley_heartbeat():
    """
    Periodic heartbeat from ESP32.
    Updates battery, RSSI, IP, last_seen, and marks trolley as online.
    """
    data = request.json or {}
    trolley_id = data.get("trolley_id")
    if not trolley_id:
        return jsonify({"success": False, "message": "trolley_id required"}), 400

    now_ts = time.time()

    # Auto-register unknown trolleys on first heartbeat
    existing = trolleys_collection.find_one({"_id": trolley_id})
    if not existing:
        trolleys_collection.insert_one({
            "_id":              trolley_id,
            "name":             data.get("name", trolley_id),
            "status":           "online",
            "battery":          data.get("battery", 0),
            "ip_address":       data.get("ip_address", ""),
            "wifi_rssi":        data.get("wifi_rssi", 0),
            "last_seen":        now_ts,
            "firmware_version": data.get("firmware_version", "2.0"),
            "cart_value":       0.0,
            "item_count":       0,
            "current_mode":     "ADD"
        })
        init_cart(trolley_id)
        print(f"[HEARTBEAT] Auto-registered new trolley: {trolley_id}")
    else:
        trolleys_collection.update_one({"_id": trolley_id}, {
            "$set": {
                "status":    "online",
                "battery":   data.get("battery", existing.get("battery", 0)),
                "ip_address":data.get("ip_address", existing.get("ip_address", "")),
                "wifi_rssi": data.get("wifi_rssi", existing.get("wifi_rssi", 0)),
                "last_seen": now_ts,
                "firmware_version": data.get("firmware_version", existing.get("firmware_version", "2.0"))
            }
        })

    print(f"[HEARTBEAT] {trolley_id} | Battery: {data.get('battery', 0)}% | RSSI: {data.get('wifi_rssi', 0)} dBm | IP: {data.get('ip_address', '')}")
    return jsonify({
        "success":   True,
        "trolley_id": trolley_id,
        "server_time": now_ts
    })

# ── Background: Offline Detection Thread ─────────────────────────────────────

def offline_detection_loop():
    """Periodically marks trolleys as offline if no heartbeat received for > OFFLINE_THRESHOLD_SECS."""
    while True:
        try:
            now_ts = time.time()
            all_trolleys = list(trolleys_collection.find({}))
            for t in all_trolleys:
                last_seen = t.get("last_seen", 0)
                current_status = t.get("status", "offline")
                if last_seen > 0 and current_status == "online":
                    if (now_ts - last_seen) > OFFLINE_THRESHOLD_SECS:
                        trolleys_collection.update_one({"_id": t["_id"]}, {"$set": {"status": "offline"}})
                        print(f"[OFFLINE] Trolley {t['_id']} marked offline (no heartbeat for >{OFFLINE_THRESHOLD_SECS}s)")
        except Exception as e:
            print(f"[OFFLINE DETECT ERROR] {e}")
        time.sleep(15)  # check every 15 seconds

# ── Transactions & Analytics APIs ────────────────────────────────────────────

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    trolley_filter = request.args.get("trolley_id")
    query = {}
    if trolley_filter:
        query["trolley_id"] = trolley_filter
    transactions = list(transactions_collection.find(query, {"_id": 0}).sort("timestamp", -1))
    return jsonify(transactions)

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    pipeline_rev = [{"$group": {"_id": None, "totalRevenue": {"$sum": "$total"}}}]
    rev_res = list(transactions_collection.aggregate(pipeline_rev))
    total_revenue = rev_res[0]["totalRevenue"] if rev_res else 0.0

    total_checkouts   = transactions_collection.count_documents({})
    avg_order_value   = total_revenue / total_checkouts if total_checkouts > 0 else 0.0

    product_counts  = {}
    product_revenue = {}
    all_tx = list(transactions_collection.find({}))
    for tx in all_tx:
        for item_key, item_details in tx.get("items", {}).items():
            name     = item_details.get("name", "Unknown Item")
            quantity = item_details.get("quantity", 0)
            subtotal = item_details.get("subtotal", 0.0)
            product_counts[name]  = product_counts.get(name, 0) + quantity
            product_revenue[name] = product_revenue.get(name, 0.0) + subtotal

    top_products = [
        {"name": n, "quantity": product_counts[n], "revenue": product_revenue[n]}
        for n in product_counts
    ]
    top_products.sort(key=lambda x: x["quantity"], reverse=True)
    top_products = top_products[:5]

    timeseries  = []
    recent_tx = list(transactions_collection.find({}, {"_id": 0}).sort("timestamp", 1).limit(15))
    for tx in recent_tx:
        timeseries.append({"timestamp": tx["timestamp"], "total": tx["total"]})

    return jsonify({
        "totalRevenue":   total_revenue,
        "totalCheckouts": total_checkouts,
        "avgOrderValue":  avg_order_value,
        "topProducts":    top_products,
        "timeseries":     timeseries
    })

# ── Settings APIs ─────────────────────────────────────────────────────────────

@app.route("/api/settings/ports", methods=["GET"])
def get_available_ports():
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    port_list = [{"port": p.device, "description": p.description, "hwid": p.hwid} for p in ports]
    return jsonify({"success": True, "ports": port_list, "currentPort": SERIAL_PORT})

@app.route("/api/settings/update", methods=["POST"])
@require_auth(roles=["admin"])
def update_settings():
    global SERIAL_PORT, global_ser
    data = request.json
    new_port = data.get("serialPort")

    if new_port:
        SERIAL_PORT = new_port.strip().upper()
        cfg = load_config()
        cfg["serialPort"] = SERIAL_PORT
        save_config(cfg)
        if global_ser:
            try:
                global_ser.close()
            except:
                pass
            global_ser = None
        print(f"Serial port set to {SERIAL_PORT}. Reconnecting...")

    return jsonify({
        "success":        True,
        "serialPort":     SERIAL_PORT,
        "arduinoConnected": global_ser is not None and global_ser.is_open
    })

@app.route("/api/settings/payment", methods=["GET"])
def get_payment_settings():
    cfg = load_config()
    return jsonify({
        "success":       True,
        "upiId":         cfg.get("upiId", "smartsupermarket@okaxis"),
        "storeName":     cfg.get("storeName", "Smart Supermarket"),
        "useCustomQr":   bool(cfg.get("useCustomQr", False)),
        "customQrImage": cfg.get("customQrImage", "")
    })

@app.route("/api/settings/payment", methods=["POST"])
@require_auth(roles=["admin", "manager"])
def update_payment_settings():
    data = request.json or {}
    cfg = load_config()
    if "upiId" in data:
        cfg["upiId"] = (data["upiId"] or "").strip()
    if "storeName" in data:
        cfg["storeName"] = (data["storeName"] or "").strip()
    if "useCustomQr" in data:
        cfg["useCustomQr"] = bool(data["useCustomQr"])
    if "customQrImage" in data:
        cfg["customQrImage"] = data["customQrImage"]
    save_config(cfg)
    return jsonify({
        "success": True,
        "message": "Payment & UPI settings saved successfully!",
        "settings": {
            "upiId":         cfg.get("upiId"),
            "storeName":     cfg.get("storeName"),
            "useCustomQr":   cfg.get("useCustomQr"),
            "customQrImage": cfg.get("customQrImage")
        }
    })

@app.route("/api/settings/database", methods=["POST"])
@require_auth(roles=["admin"])
def manage_database():
    action = request.json.get("action")
    if action == "seed":
        products_collection.delete_many({})
        defaults = [
            {"uid": "5C 1E 7E 05", "name": "Rice 1kg",         "price": 60.0},
            {"uid": "76 E3 33 06", "name": "Sugar 1kg",         "price": 45.0},
            {"uid": "A3 B4 C5 D6", "name": "Whole Wheat Bread", "price": 25.0},
            {"uid": "11 22 33 44", "name": "Milk (1 Gallon)",   "price": 50.0},
            {"uid": "99 88 77 66", "name": "Cheddar Cheese",    "price": 80.0},
            {"uid": "FF EE DD CC", "name": "Free Range Eggs",   "price": 40.0},
        ]
        inserted = 0
        for p in defaults:
            uid_norm = normalize_uid(p["uid"])
            products_collection.update_one(
                {"uid_norm": uid_norm},
                {"$set": {"uid": p["uid"], "name": p["name"], "price": float(p["price"]), "uid_norm": uid_norm}},
                upsert=True
            )
            inserted += 1
        return jsonify({"success": True, "message": f"Database seeded with {inserted} default products."})

    elif action == "clear_transactions":
        transactions_collection.delete_many({})
        db['feed'].delete_many({})
        # Reset all trolley carts
        for t in DEFAULT_TROLLEYS:
            carts_collection.update_one({"_id": t["_id"]}, {
                "$set": {"items": {}, "total": 0.0, "itemsContained": 0, "lastActive": "Cleared"}
            })
        return jsonify({"success": True, "message": "Transaction logs, feed and all carts cleared."})

    return jsonify({"success": False, "message": "Invalid database action"}), 400

@app.route("/api/settings/backup", methods=["POST"])
@require_auth(roles=["admin"])
def db_backup():
    try:
        backup_data = {
            "products":     list(products_collection.find({}, {"_id": 0})),
            "transactions": list(transactions_collection.find({}, {"_id": 0})),
            "employees":    list(db["employees"].find({}, {"_id": 0})),
            "feedback":     list(db["feedback"].find({}, {"_id": 0}))
        }
        backup_path = os.path.join(app.static_folder, "backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)
        return jsonify({"success": True, "message": "Database backup completed successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Backup failed: {str(e)}"}), 500

@app.route("/api/settings/restore", methods=["POST"])
@require_auth(roles=["admin"])
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

# ── Employee & Feedback APIs ──────────────────────────────────────────────────

@app.route("/api/employees", methods=["GET"])
def get_employees():
    employees_collection = db["employees"]
    emps = list(employees_collection.find({}, {"_id": 0}))
    return jsonify(emps)

@app.route("/api/employees", methods=["POST"])
@require_auth(roles=["admin", "manager"])
def save_employee():
    employees_collection = db["employees"]
    data = request.json or {}
    emp_id = (data.get("id") or "").strip().upper()
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "Cashier").strip()
    shift = data.get("shift", "Morning (08:00 AM - 04:00 PM)")
    status = data.get("status", "Active")
    password = data.get("password") or ""
    username = (data.get("username") or emp_id.lower()).strip().lower()

    if not emp_id or not name:
        return jsonify({"success": False, "message": "Employee ID and Full Name are required."}), 400

    if len(name) < 2:
        return jsonify({"success": False, "message": "Employee name must be at least 2 characters long."}), 400

    if role.lower() not in ["admin", "manager", "cashier"]:
        return jsonify({"success": False, "message": "Role must be Admin, Manager, or Cashier."}), 400

    if password and len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    employees_collection.update_one(
        {"id": emp_id},
        {"$set": {
            "id":       emp_id,
            "username": username,
            "name":     name,
            "role":     role,
            "shift":    shift,
            "status":   status
        }},
        upsert=True
    )

    # If a password is provided (or when creating a new employee), sync with users_collection
    if password:
        user_role = role.lower()
        users_collection.update_one(
            {"username": username},
            {"$set": {
                "username":      username,
                "password_hash": generate_password_hash(password),
                "name":          name,
                "role":          user_role,
                "status":        status,
                "updated_at":    time.time()
            }},
            upsert=True
        )

    return jsonify({"success": True, "message": f"Employee {name} ({emp_id}) saved successfully."})

@app.route("/api/employees/<emp_id>/password", methods=["PUT"])
@require_auth(roles=["admin"])
def reset_employee_password(emp_id):
    """Admin endpoint to reset an employee's password by their employee ID."""
    data = request.json or {}
    new_password = data.get("password") or data.get("new_password") or ""

    if not new_password:
        return jsonify({"success": False, "message": "New password is required."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    employees_collection = db["employees"]
    emp = employees_collection.find_one({"id": emp_id})
    target_username = emp.get("username", emp_id.lower()) if emp else emp_id.lower()
    name = emp.get("name", target_username) if emp else target_username
    role = (emp.get("role", "cashier") if emp else "cashier").lower()
    if role not in ["admin", "manager", "cashier"]:
        role = "cashier"

    new_hash = generate_password_hash(new_password)

    # Collect all possible identifier aliases for this employee
    aliases = [emp_id.lower(), target_username.lower()]
    if emp and emp.get("name"):
        aliases.append(emp["name"].lower().replace(" ", ""))

    # Update ALL matched user accounts in users_collection so old password is completely invalidated
    update_filter = {
        "$or": [
            {"username": {"$in": aliases}},
            {"id": emp_id},
            {"name": name}
        ]
    }

    result = users_collection.update_many(
        update_filter,
        {"$set": {
            "password_hash": new_hash,
            "role": role,
            "status": "Active",
            "updated_at": time.time()
        }}
    )

    # If no existing document matched, insert a canonical user document
    if result.matched_count == 0:
        users_collection.insert_one({
            "username": target_username,
            "password_hash": new_hash,
            "name": name,
            "role": role,
            "status": "Active",
            "created_at": time.time()
        })

    db['feed'].insert_one({
        "actionType": "EMPLOYEE_PASSWORD_RESET",
        "employee_id": emp_id,
        "username": target_username,
        "reset_by": request.current_user.get("username", "admin"),
        "timestamp": time.time()
    })

    return jsonify({"success": True, "message": f"Password for {name} ({target_username}) updated successfully."})

@app.route("/api/employees/<emp_id>", methods=["DELETE"])
@require_auth(roles=["admin", "manager"])
def delete_employee(emp_id):
    employees_collection = db["employees"]
    emp = employees_collection.find_one({"id": emp_id})
    if emp and "username" in emp:
        users_collection.delete_one({"username": emp["username"]})
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
            "feedbacks":      feedbacks,
            "averageRating":  round(avg_rating, 1),
            "totalResponses": len(feedbacks)
        })
    elif request.method == "POST":
        data = request.json or {}
        try:
            rating = int(data.get("rating", 5))
            if rating < 1 or rating > 5:
                return jsonify({"success": False, "message": "Rating must be between 1 and 5 stars."}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Rating must be a valid number between 1 and 5."}), 400

        comments = (data.get("comments") or "").strip()
        if not comments:
            comments = "Great shopping experience!"

        feedback_collection.insert_one({
            "rating":   rating,
            "comments": comments,
            "date":     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"success": True, "message": "Feedback submitted successfully"})
        return jsonify({"success": True, "message": "Feedback submitted successfully"})

# ── Customer Portal API ───────────────────────────────────────────────────────

@app.route("/api/customer/profile", methods=["GET"])
def get_customer_profile():
    transactions = list(transactions_collection.find({}, {"_id": 0}))
    points = sum(int(tx.get("total", 0) // 10) for tx in transactions)
    return jsonify({
        "memberId":  "MEM-872910",
        "name":      "Lohith Kumar",
        "email":     "lohith.k@gmail.com",
        "phone":     "+91 98765 43210",
        "tier":      "Gold Member",
        "points":    points + 150,
        "savedAddresses": [
            "123, 4th Cross, Green Glen Layout, Bangalore - 560103",
            "Office: Tech Park Phase 2, Outer Ring Road, Bangalore"
        ],
        "wishlist": [
            {"name": "Rice 1kg",  "price": 60.0, "category": "Grains"},
            {"name": "Sugar 1kg", "price": 45.0, "category": "Grains"}
        ]
    })

# ── Arduino Serial Loop (backward-compatible, targets TROLLEY-001) ────────────

def serial_loop():
    global global_ser, current_mode, SERIAL_PORT
    BAUD_RATE = 9600
    last_heartbeat_time = 0
    last_warn_time = 0
    SERIAL_TROLLEY_ID = "TROLLEY-001"  # Arduino always maps to Trolley-001

    while True:
        if global_ser is None or not global_ser.is_open:
            try:
                global_ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print(f"Connected to hardware on {SERIAL_PORT}")
                last_warn_time = 0
            except Exception as e:
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
                        print(f"Waiting for hardware on {SERIAL_PORT}... (Please check connection or close Serial Monitor)")
                        last_warn_time = now_t
                    time.sleep(3)
                    continue

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

                if line.startswith("BTN_STATE:") or line.startswith("[BTN DIAG"):
                    if "RESET=0" in line:
                        print("[BTN] ✅ Reset button IS being pressed — triggering reset")
                        perform_reset(SERIAL_TROLLEY_ID)
                        send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")
                        send_command_to_arduino("BEEP:2")

                elif (line == "RESET"
                      or line.upper() == "RESET"
                      or line.startswith("Reset")
                      or "BTN] RESET" in line
                      or "Bill cleared" in line):
                    print("[RESET] Hardware reset button triggered")
                    perform_reset(SERIAL_TROLLEY_ID)
                    send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")

                elif line == "MODE:ADD" or "BTN] ADD" in line:
                    current_mode = "ADD"
                    trolleys_collection.update_one({"_id": SERIAL_TROLLEY_ID}, {"$set": {"current_mode": "ADD"}})
                    print("[Mode] Switched to ADD")
                    send_command_to_arduino("LCD:You Can Now|Add Item")

                elif line == "MODE:REMOVE" or "BTN] REMOVE" in line:
                    current_mode = "REMOVE"
                    trolleys_collection.update_one({"_id": SERIAL_TROLLEY_ID}, {"$set": {"current_mode": "REMOVE"}})
                    print("[Mode] Switched to REMOVE")
                    send_command_to_arduino("LCD:You Can Now|Remove Item")

                elif line.startswith("SCAN:") or line.startswith("UID:"):
                    prefix = "SCAN:" if line.startswith("SCAN:") else "UID:"
                    uid = line.split(prefix)[1].strip()
                    cart = carts_collection.find_one({"_id": _trolley_cart_id(SERIAL_TROLLEY_ID)})
                    if cart and cart.get("status") == "BILL_GENERATED":
                        print("[SCAN] Blocked: Cart is locked in BILL_GENERATED state.")
                        send_command_to_arduino("LCD:Cart Locked!|Pay or Cancel Bill")
                        send_command_to_arduino("BEEP:3")
                        continue
                    product, total, uid_key = process_scan(current_mode, uid, SERIAL_TROLLEY_ID)
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

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Start background threads
    t_serial  = threading.Thread(target=serial_loop,           daemon=True)
    t_offline = threading.Thread(target=offline_detection_loop, daemon=True)
    t_serial.start()
    t_offline.start()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
