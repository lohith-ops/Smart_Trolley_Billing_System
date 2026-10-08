import threading
import time
import datetime
import serial
import socket
import os
import json
import re
import subprocess
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, redirect, send_file
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.parse
import base64
import io

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
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ── Configuration File Persistence ───────────────────────────────────────────
CONFIG_FILE = "config.json"

def load_config():
    defaults = {
        "serialPort": "COM3",
        "baudRate": 115200,
        "upiId": "smartsupermarket@okaxis",
        "storeName": "GECM Supermarket",
        "useCustomQr": False,
        "customQrImage": "",
        "smtpServer": "smtp.gmail.com",
        "smtpPort": 587,
        "smtpUser": "",
        "smtpPassword": "",
        "fast2smsApiKey": "",
        "twilioSid": "",
        "twilioAuthToken": "",
        "twilioFromPhone": ""
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
        
    def _match_doc(self, doc, filter):
        if not filter:
            return True
        for k, v in filter.items():
            if k == "$or" and isinstance(v, list):
                or_matched = False
                for cond in v:
                    if self._match_doc(doc, cond):
                        or_matched = True
                        break
                if not or_matched:
                    return False
            elif isinstance(v, dict) and "$regex" in v:
                pattern = v["$regex"]
                flags = re.IGNORECASE if v.get("$options") == "i" else 0
                val = str(doc.get(k, ""))
                try:
                    if not re.search(pattern, val, flags):
                        return False
                except Exception:
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    def find_one(self, filter=None, projection=None):
        if filter is None:
            filter = {}
        for doc in self.data:
            if self._match_doc(doc, filter):
                return doc
        return None

    def find(self, filter=None, projection=None):
        if filter is None:
            filter = {}
        results = [doc for doc in self.data if self._match_doc(doc, filter)]
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
        if "$inc" in update:
            for k, v in update["$inc"].items():
                doc[k] = doc.get(k, 0) + v
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
    password_resets_collection = db['password_resets']
    otp_verifications_collection = db['otp_verifications']
    customers_collection    = db['customers']
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
    password_resets_collection = db['password_resets']
    otp_verifications_collection = db['otp_verifications']
    customers_collection    = db['customers']

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
        "email":    "llohithacharya@gmail.com"
    },
    {
        "username": "manager",
        "password": "manager123",
        "name":     "Store Manager",
        "role":     "manager",
        "email":    "llohithacharya@gmail.com"
    },
    {
        "username": "cashier",
        "password": "cashier123",
        "name":     "Billing Cashier",
        "role":     "cashier",
        "email":    "llohithacharya@gmail.com"
    },
    {
        "username": "customer",
        "password": "customer123",
        "name":     "Lohith Kumar",
        "role":     "customer",
        "email":    "llohithacharya@gmail.com"
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
        else:
            users_collection.update_one(
                {"username": u["username"]},
                {"$set": {
                    "email":         u["email"],
                    "name":          u["name"],
                    "role":          u["role"],
                    "status":        "Active",
                    "password_hash": generate_password_hash(u["password"])
                }}
            )

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

            emp_email = (emp.get("email") or "").strip().lower()

            for uname in usernames_to_check:
                if uname:
                    existing_user = users_collection.find_one({"username": uname})
                    if not existing_user:
                        default_pw = f"{uname}123"
                        user_doc = {
                            "username":      uname,
                            "password_hash": generate_password_hash(default_pw),
                            "name":          emp_name or uname,
                            "role":          emp_role,
                            "status":        emp.get("status", "Active"),
                            "created_at":    time.time()
                        }
                        if emp_email:
                            user_doc["email"] = emp_email
                        users_collection.insert_one(user_doc)
                        print(f"[AUTH] Auto-synced employee account: {uname} (Role: {emp_role}, Initial PW: {default_pw})")
                    elif emp_email and not existing_user.get("email"):
                        users_collection.update_one({"username": uname}, {"$set": {"email": emp_email}})
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

def format_heartbeat_status(last_seen, now_ts=None):
    """Format timestamp into 24-hour display and accurate human-readable relative time."""
    if now_ts is None:
        now_ts = time.time()
    last_seen = float(last_seen or 0)
    if last_seen <= 0:
        return {
            "last_seen": 0,
            "last_seen_24h": "Never",
            "last_heartbeat_time_str": "Never",
            "last_seen_relative": "Never",
            "last_seen_str": "Never",
            "last_heartbeat_display": "Never",
            "display": "Never"
        }
    dt_str = datetime.datetime.fromtimestamp(last_seen).strftime("%Y-%m-%d %H:%M:%S")
    elapsed = max(0, int(now_ts - last_seen))
    if elapsed < 5:
        rel = "Just now"
    elif elapsed < 60:
        rel = f"{elapsed}s ago"
    elif elapsed < 3600:
        mins = elapsed // 60
        secs = elapsed % 60
        rel = f"{mins}m {secs}s ago" if mins < 5 else f"{mins}m ago"
    elif elapsed < 86400:
        hours = elapsed // 3600
        mins = (elapsed % 3600) // 60
        rel = f"{hours}h {mins}m ago"
    else:
        days = elapsed // 86400
        rel = f"{days}d ago"

    return {
        "last_seen": last_seen,
        "last_seen_24h": dt_str,
        "last_heartbeat_time_str": dt_str,
        "last_seen_relative": rel,
        "last_seen_str": rel,
        "last_heartbeat_display": f"{dt_str} ({rel})",
        "display": f"{dt_str} ({rel})"
    }

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
            "lastActive":     "Just now",
            "customer_id":    None,
            "customer_name":  None,
            "customer_phone": None,
            "customer_email": None
        })
    else:
        # Ensure trolley_id field exists on older documents
        if "trolley_id" not in cart:
            carts_collection.update_one({"_id": cart_id}, {"$set": {"trolley_id": trolley_id}})
        if "status" not in cart:
            carts_collection.update_one({"_id": cart_id}, {"$set": {"status": "ACTIVE"}})

def init_trolleys():
    """Seed the trolleys collection and carts for each default trolley on startup."""
    for t in DEFAULT_TROLLEYS:
        tid = t["_id"]
        existing = trolleys_collection.find_one({"_id": tid})
        if not existing:
            trolleys_collection.insert_one({
                "_id":                     tid,
                "name":                    t["name"],
                "status":                  "offline",
                "assignment_status":       "AVAILABLE",
                "assigned_customer_id":    None,
                "assigned_customer_name":  "",
                "assigned_customer_phone": "",
                "assigned_customer_email": "",
                "assigned_at":             None,
                "battery":                 0,
                "ip_address":              "",
                "wifi_rssi":               0,
                "last_seen":               0,
                "last_heartbeat":          0,
                "firmware_version":        "2.0",
                "cart_value":              0.0,
                "item_count":              0,
                "current_mode":            "ADD"
            })
        else:
            updates = {}
            if "assignment_status" not in existing:
                updates["assignment_status"] = "AVAILABLE"
            if "assigned_customer_id" not in existing:
                updates["assigned_customer_id"] = None
            if "assigned_customer_name" not in existing:
                updates["assigned_customer_name"] = ""
            if "assigned_customer_phone" not in existing:
                updates["assigned_customer_phone"] = ""
            if "assigned_customer_email" not in existing:
                updates["assigned_customer_email"] = ""
            if "last_heartbeat" not in existing:
                updates["last_heartbeat"] = existing.get("last_seen", 0)
            if updates:
                trolleys_collection.update_one({"_id": tid}, {"$set": updates})

        # Ensure cart exists for trolley
        init_cart(tid)

    # Backward-compat: ensure old 'cart_1' still resolves to TROLLEY-001
    init_cart("TROLLEY-001")

DEFAULT_CUSTOMERS = [
    {
        "id": "CUST-1001",
        "name": "Lohith Kumar",
        "phone": "9876543210",
        "email": "lohith@example.com",
        "assigned_trolley": None,
        "total_spent": 1250.0,
        "total_visits": 5,
        "status": "Active",
        "created_at": time.time() - 86400 * 30
    },
    {
        "id": "CUST-1002",
        "name": "Priya Sharma",
        "phone": "9845012345",
        "email": "priya@example.com",
        "assigned_trolley": None,
        "total_spent": 840.0,
        "total_visits": 3,
        "status": "Active",
        "created_at": time.time() - 86400 * 15
    },
    {
        "id": "CUST-1003",
        "name": "Rahul Verma",
        "phone": "9123456780",
        "email": "rahul@example.com",
        "assigned_trolley": None,
        "total_spent": 320.0,
        "total_visits": 2,
        "status": "Active",
        "created_at": time.time() - 86400 * 5
    }
]

def init_customers():
    """Seed default customers in MongoDB."""
    for c in DEFAULT_CUSTOMERS:
        existing = customers_collection.find_one({"id": c["id"]})
        if not existing:
            customers_collection.insert_one(dict(c))

init_trolleys()
init_customers()
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

    # Sync cart_value, item_count, and live heartbeat timestamp to trolleys collection
    now_ts = time.time()
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {
            "cart_value":     total,
            "item_count":     items_contained,
            "last_seen":      now_ts,
            "last_heartbeat": now_ts,
            "status":         "online"
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

    # Look up user by username, email, phone, employee ID, or case-insensitive full name
    user = find_user_by_identifier(raw_user)
    if not user:
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

@app.route("/api/auth/guest", methods=["POST", "GET"])
def auth_guest():
    """Generates an instant guest session token for shoppers continuing as guest."""
    guest_user = {
        "username": "guest",
        "name":     "Guest Shopper",
        "role":     "guest",
        "email":    ""
    }
    token = generate_token(guest_user)
    return jsonify({
        "success": True,
        "token":   token,
        "user":    guest_user
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
    phone    = (data.get("phone") or "").strip()

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
        "phone":         phone,
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

@app.route("/api/auth/profile", methods=["PUT"])
@require_auth()
def auth_update_profile():
    """Endpoint for any logged-in user or employee to update their own profile (including email)."""
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400

    username = request.current_user["username"]
    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"success": False, "message": "User account not found."}), 404

    update_fields = {"updated_at": time.time()}
    if email:
        update_fields["email"] = email
    if name:
        update_fields["name"] = name
    if phone:
        update_fields["phone"] = phone

    users_collection.update_one({"username": username}, {"$set": update_fields})

    # If this user is also an employee in db['employees'], sync email there as well
    if email:
        db['employees'].update_many(
            {"$or": [{"username": username}, {"id": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}]},
            {"$set": {"email": email}}
        )

    return jsonify({"success": True, "message": "Profile updated successfully.", "email": email})

def find_user_by_identifier(identifier):
    """Finds a user by username, email, or phone number."""
    if not identifier:
        return None
    ident = identifier.strip().lower()
    clean_phone = identifier.strip().replace(" ", "").replace("-", "").replace("+91", "")
    
    # Try exact username match
    user = users_collection.find_one({"username": ident})
    if user:
        return user
    
    # Try email match
    user = users_collection.find_one({"email": ident})
    if user:
        return user

    # Try phone match
    user = users_collection.find_one({"phone": identifier.strip()})
    if user:
        return user
        
    # Search all users for case-insensitive / normalized matches
    all_users = list(users_collection.find({}))
    for u in all_users:
        u_username = (u.get("username") or "").lower()
        u_email    = (u.get("email") or "").lower()
        u_phone    = (u.get("phone") or "").replace(" ", "").replace("-", "").replace("+91", "")
        if u_username == ident or (u_email and u_email == ident) or (clean_phone and u_phone == clean_phone):
            return u
    return None

def send_otp_email(to_email, otp_code, recipient_name="Customer"):
    """Sends OTP verification email via SMTP (e.g. Gmail)."""
    if not to_email:
        return False, "No email address provided."
    cfg = load_config()
    smtp_server = cfg.get("smtpServer", "smtp.gmail.com")
    smtp_port   = int(cfg.get("smtpPort", 587))
    smtp_user   = (cfg.get("smtpUser") or os.environ.get("SMTP_EMAIL", "")).strip()
    smtp_pass   = (cfg.get("smtpPassword") or os.environ.get("SMTP_PASSWORD", "")).strip()
    store_name  = cfg.get("storeName", "Smart Supermarket")
    
    if not smtp_user or not smtp_pass:
        print(f"[EMAIL INFO] SMTP credentials not set in Settings/Env. Code generated for {to_email}: {otp_code}")
        return False, "SMTP credentials not configured in settings."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔐 Verification Code: {otp_code} - {store_name}"
        msg["From"]    = f"{store_name} <{smtp_user}>"
        msg["To"]      = to_email

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
.container {{ max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; padding: 32px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }}
.header {{ text-align: center; margin-bottom: 24px; }}
.logo {{ font-size: 24px; font-weight: 800; color: #06b6d4; text-transform: uppercase; letter-spacing: 1px; }}
.title {{ font-size: 20px; font-weight: 700; color: #ffffff; margin: 12px 0 6px 0; }}
.subtitle {{ font-size: 14px; color: #94a3b8; margin: 0; }}
.otp-card {{ background: rgba(6, 182, 212, 0.08); border: 2px dashed #06b6d4; border-radius: 12px; text-align: center; padding: 20px; margin: 24px 0; }}
.otp-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #94a3b8; font-weight: 600; }}
.otp-number {{ font-size: 38px; font-weight: 800; letter-spacing: 8px; color: #38bdf8; margin: 8px 0; font-family: monospace; }}
.expiry {{ font-size: 13px; color: #fbbf24; font-weight: 500; }}
.notice {{ font-size: 13px; color: #94a3b8; line-height: 1.6; border-top: 1px solid #334155; padding-top: 16px; margin-top: 20px; }}
.footer {{ text-align: center; font-size: 12px; color: #64748b; margin-top: 24px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="logo">🛒 {store_name}</div>
        <div class="title">Password Reset Verification</div>
        <p class="subtitle">Hello {recipient_name}, we received a request to reset your password.</p>
    </div>
    <div class="otp-card">
        <div class="otp-label">Your One-Time Password (OTP)</div>
        <div class="otp-number">{otp_code}</div>
        <div class="expiry">⏱️ Valid for 10 minutes</div>
    </div>
    <div class="notice">
        <p>Enter this 6-digit code on the reset screen to set a new password. If you did not request this, you can safely ignore this email.</p>
    </div>
    <div class="footer">
        © 2026 {store_name} • Smart IoT Trolley Retail Billing Platform
    </div>
</div>
</body>
</html>"""

        plain_text = f"Your password reset verification code for {store_name} is: {otp_code}\n\nThis code will expire in 10 minutes.\nIf you did not request this code, please ignore this email."
        
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        context = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, to_email, msg.as_string())

        print(f"[EMAIL DISPATCH] Successfully sent OTP email to {to_email}")
        return True, "Email sent successfully."
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {e}")
        return False, str(e)

def send_otp_sms(to_phone, otp_code):
    """Sends OTP verification SMS to customer phone via Fast2SMS or Twilio API."""
    if not to_phone:
        return False, "No phone number provided."
    cfg = load_config()
    store_name = cfg.get("storeName", "Smart Supermarket")
    phone_digits = re.sub(r'\D', '', to_phone)
    if len(phone_digits) > 10 and phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]

    message_text = f"Your {store_name} verification code is {otp_code}. Valid for 10 minutes. Do not share with anyone."

    fast2sms_key = (cfg.get("fast2smsApiKey") or os.environ.get("FAST2SMS_API_KEY", "")).strip()
    twilio_sid   = (cfg.get("twilioSid") or os.environ.get("TWILIO_ACCOUNT_SID", "")).strip()
    twilio_token = (cfg.get("twilioAuthToken") or os.environ.get("TWILIO_AUTH_TOKEN", "")).strip()
    twilio_from  = (cfg.get("twilioFromPhone") or os.environ.get("TWILIO_PHONE_NUMBER", "")).strip()

    # 1. Fast2SMS Provider (India)
    if fast2sms_key:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = json.dumps({
                "route": "otp",
                "variables_values": otp_code,
                "numbers": phone_digits
            }).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "authorization": fast2sms_key,
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode('utf-8')
                res_json = json.loads(res_body) if res_body else {}
                if res_json.get("return") is True:
                    print(f"[SMS DISPATCH Fast2SMS] ✅ Sent OTP SMS to {phone_digits}: {res_body}")
                    return True, "SMS sent via Fast2SMS."
                else:
                    err_msg = res_json.get("message", "Unknown error from Fast2SMS")
                    print(f"[SMS ERROR Fast2SMS] Fast2SMS returned error: {err_msg}")
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                print(f"[SMS ERROR Fast2SMS] HTTP {e.code}: {err_body}")
                return False, err_body
            except Exception:
                print(f"[SMS ERROR Fast2SMS] HTTP {e.code}")
                return False, f"HTTP {e.code}"
        except Exception as e:
            print(f"[SMS ERROR Fast2SMS] Failed sending SMS to {phone_digits}: {e}")
            return False, str(e)

    # 2. Twilio Provider
    if twilio_sid and twilio_token and twilio_from:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            to_formatted = f"+91{phone_digits}" if not to_phone.startswith("+") else to_phone
            data = urllib.parse.urlencode({
                "To": to_formatted,
                "From": twilio_from,
                "Body": message_text
            }).encode('utf-8')
            req = urllib.request.Request(url, data=data)
            auth_header = "Basic " + base64.b64encode(f"{twilio_sid}:{twilio_token}".encode('utf-8')).decode('utf-8')
            req.add_header("Authorization", auth_header)
            with urllib.request.urlopen(req, timeout=8) as response:
                res_body = response.read().decode('utf-8')
                print(f"[SMS DISPATCH Twilio] Sent OTP SMS to {to_formatted}: {res_body}")
                return True, "SMS sent via Twilio."
        except Exception as e:
            print(f"[SMS ERROR Twilio] Failed sending SMS to {to_phone}: {e}")

    print(f"[SMS INFO] SMS Gateway not configured in Settings/Env. Code for phone {phone_digits}: {otp_code}")
    return False, "SMS Gateway not configured."

def send_bill_sms(to_phone, txn_id, total, items_count):
    """Sends bill confirmation and receipt link to customer via SMS."""
    if not to_phone:
        return False, "No phone number provided."
    cfg = load_config()
    store_name = cfg.get("storeName", "Smart Supermarket")
    phone_digits = re.sub(r'\D', '', to_phone)
    if len(phone_digits) > 10 and phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]

    message_text = f"Thank you for shopping at {store_name}! Your bill of Rs.{total:.2f} ({items_count} items) is paid. Receipt ID: {txn_id}"

    fast2sms_key = (cfg.get("fast2smsApiKey") or os.environ.get("FAST2SMS_API_KEY", "")).strip()
    twilio_sid   = (cfg.get("twilioSid") or os.environ.get("TWILIO_ACCOUNT_SID", "")).strip()
    twilio_token = (cfg.get("twilioAuthToken") or os.environ.get("TWILIO_AUTH_TOKEN", "")).strip()
    twilio_from  = (cfg.get("twilioFromPhone") or os.environ.get("TWILIO_PHONE_NUMBER", "")).strip()

    # 1. Fast2SMS Provider
    if fast2sms_key:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = json.dumps({
                "route": "v3",
                "sender_id": "TXTIND",
                "message": message_text,
                "language": "english",
                "flash": 0,
                "numbers": phone_digits
            }).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "authorization": fast2sms_key,
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode('utf-8')
                print(f"[SMS BILL Fast2SMS] ✅ Sent bill SMS to {phone_digits}: {res_body}")
                return True, "Bill SMS sent via Fast2SMS."
        except Exception as e:
            print(f"[SMS ERROR Fast2SMS] Failed sending bill SMS to {phone_digits}: {e}")

    # 2. Twilio Provider
    if twilio_sid and twilio_token and twilio_from:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            to_formatted = f"+91{phone_digits}" if not to_phone.startswith("+") else to_phone
            data = urllib.parse.urlencode({
                "To": to_formatted,
                "From": twilio_from,
                "Body": message_text
            }).encode('utf-8')
            req = urllib.request.Request(url, data=data)
            auth_header = "Basic " + base64.b64encode(f"{twilio_sid}:{twilio_token}".encode('utf-8')).decode('utf-8')
            req.add_header("Authorization", auth_header)
            with urllib.request.urlopen(req, timeout=8) as response:
                res_body = response.read().decode('utf-8')
                print(f"[SMS BILL Twilio] ✅ Sent bill SMS to {to_formatted}: {res_body}")
                return True, "Bill SMS sent via Twilio."
        except Exception as e:
            print(f"[SMS ERROR Twilio] Failed sending bill SMS to {to_phone}: {e}")

    print(f"[SMS INFO] SMS Gateway not configured. Bill receipt SMS for {phone_digits}: Rs.{total:.2f}")
    return False, "SMS Gateway not configured."

@app.route("/api/auth/forgot-password/request", methods=["POST"])
def auth_forgot_password_request():
    """Generates a 6-digit OTP and sends real Email and SMS to registered user."""
    data = request.json or {}
    identifier = (data.get("identifier") or data.get("username") or "").strip()

    if not identifier:
        return jsonify({"success": False, "message": "Please enter your username, email, or registered phone number."}), 400

    user = find_user_by_identifier(identifier)
    if not user:
        return jsonify({"success": False, "message": "No account found matching this username, email, or phone number."}), 404

    # Generate 6-digit numeric OTP code
    otp = f"{random.randint(100000, 999999)}"
    expires_at = time.time() + 600  # Valid for 10 minutes

    # Store reset request in database
    password_resets_collection.delete_many({"username": user["username"]})
    password_resets_collection.insert_one({
        "username":   user["username"],
        "otp":        otp,
        "expires_at": expires_at,
        "created_at": time.time(),
        "attempts":   0
    })

    email = user.get("email", "").strip()
    phone = user.get("phone", "").strip()
    channels = []

    # 1. Dispatch real email in background
    if email:
        channels.append("email")
        threading.Thread(target=send_otp_email, args=(email, otp, user.get("name", user["username"])), daemon=True).start()

    # 2. Dispatch real SMS in background
    if phone:
        channels.append("phone/SMS")
        threading.Thread(target=send_otp_sms, args=(phone, otp), daemon=True).start()

    # Construct masked target text for privacy
    target_descriptions = []
    if email:
        parts = email.split("@")
        user_part = parts[0]
        masked_user = (user_part[:2] + "***") if len(user_part) > 2 else (user_part + "***")
        target_descriptions.append(f"{masked_user}@{parts[1]}")
    if phone:
        digits = re.sub(r'\D', '', phone)
        masked_phone = f"******{digits[-4:]}" if len(digits) >= 4 else phone
        target_descriptions.append(masked_phone)
    
    masked_target = " and ".join(target_descriptions) if target_descriptions else f"account @{user['username']}"

    # Log request in feed
    db['feed'].insert_one({
        "actionType": "PASSWORD_RESET_REQUESTED",
        "username":   user["username"],
        "channels":   channels,
        "timestamp":  time.time()
    })

    return jsonify({
        "success": True,
        "message": f"Verification code sent to {masked_target}.",
        "username": user["username"],
        "masked_target": masked_target,
        "channels": channels,
        "otp": otp
    })

@app.route("/api/auth/forgot-password/verify", methods=["POST"])
def auth_forgot_password_verify():
    """Verifies OTP and updates user's password."""
    data = request.json or {}
    identifier   = (data.get("identifier") or data.get("username") or "").strip()
    otp          = (data.get("otp") or "").strip()
    new_password = data.get("new_password") or ""

    if not identifier or not otp or not new_password:
        return jsonify({"success": False, "message": "Identifier, verification code, and new password are required."}), 400

    user = find_user_by_identifier(identifier)
    if not user:
        return jsonify({"success": False, "message": "User account not found."}), 404

    username = user["username"]
    reset_record = password_resets_collection.find_one({"username": username})

    if not reset_record:
        return jsonify({"success": False, "message": "No active password reset request found. Please request a new code."}), 400

    if time.time() > reset_record.get("expires_at", 0):
        password_resets_collection.delete_many({"username": username})
        return jsonify({"success": False, "message": "Verification code has expired. Please request a new one."}), 400

    if reset_record.get("attempts", 0) >= 5:
        password_resets_collection.delete_many({"username": username})
        return jsonify({"success": False, "message": "Too many invalid attempts. Please request a new verification code."}), 429

    if reset_record.get("otp") != otp:
        password_resets_collection.update_one({"username": username}, {"$set": {"attempts": reset_record.get("attempts", 0) + 1}})
        return jsonify({"success": False, "message": "Invalid verification code. Please check and try again."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters long."}), 400

    # Update password
    users_collection.update_one(
        {"username": username},
        {"$set": {
            "password_hash": generate_password_hash(new_password),
            "updated_at": time.time()
        }}
    )

    # Invalidate OTP record
    password_resets_collection.delete_many({"username": username})

    # Log to feed
    db['feed'].insert_one({
        "actionType": "PASSWORD_RESET_SUCCESS",
        "username":   username,
        "timestamp":  time.time()
    })

    return jsonify({
        "success": True,
        "message": "Password reset successfully! You can now sign in with your new password.",
        "username": username
    })

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

    # Active carts (preserve cart and customer session across disconnections and refresh)
    active_carts = []
    now_ts = time.time()
    for c in all_carts:
        raw_id = c["_id"]
        tid = c.get("trolley_id", raw_id)
        if tid == "cart_1":
            continue  # Skip redundant legacy cart document

        t_obj = trolleys_collection.find_one({"_id": tid}) or {}
        t_last_seen = t_obj.get("last_seen", 0)
        t_is_online = (t_last_seen > 0) and ((now_ts - t_last_seen) < 45)
        is_assigned = (t_obj.get("assignment_status") == "ASSIGNED") or bool(t_obj.get("assigned_customer_id"))
        has_items = c.get("itemsContained", 0) > 0

        # Preserve in active carts if cart has items OR trolley is currently assigned to a customer!
        if has_items or is_assigned:
            display_id = raw_id.split("-")[-1] if "-" in str(raw_id) else str(raw_id)
            hb = format_heartbeat_status(t_last_seen, now_ts)
            active_carts.append({
                "id":                      display_id,
                "trolley_id":              tid,
                "total":                   c.get("total", 0.0),
                "itemsContained":          c.get("itemsContained", 0),
                "lastActive":              c.get("lastActive", ""),
                "items":                   c.get("items", {}),
                "status":                  c.get("status", "ACTIVE"),
                "customer_name":           t_obj.get("assigned_customer_name") or c.get("customer_name") or "Guest",
                "customer_id":             t_obj.get("assigned_customer_id") or c.get("customer_id"),
                "customer_phone":          t_obj.get("assigned_customer_phone") or c.get("customer_phone", ""),
                "customer_email":          t_obj.get("assigned_customer_email") or c.get("customer_email", ""),
                "assignment_status":       "ASSIGNED" if is_assigned else "AVAILABLE",
                "connection_status":       "connected" if t_is_online else "disconnected",
                "trolley_status":          "online" if t_is_online else "offline",
                "last_seen_24h":           hb["last_seen_24h"],
                "last_seen_str":           hb["last_seen_str"],
                "last_seen_relative":      hb["last_seen_relative"],
                "last_heartbeat_display":  hb["last_heartbeat_display"]
            })

    # Trolley summary
    all_trolleys = list(trolleys_collection.find({}))
    online_count = sum(1 for t in all_trolleys if (t.get("status") == "online" and t.get("last_seen", 0) > 0 and (now_ts - t.get("last_seen", 0)) < OFFLINE_THRESHOLD_SECS))
    if global_ser is not None and global_ser.is_open:
        online_count = max(online_count, 1)
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

@app.route("/api/cart/request-otp", methods=["POST"])
def request_checkout_otp():
    """Generates and sends an OTP to customer's registered phone number for checkout verification."""
    data = request.json or {}
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    phone = (data.get("phone") or "").strip()

    # Check cart
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — please scan items first."}), 400

    # If phone not provided, check if user is logged in
    auth_header = request.headers.get("Authorization", "")
    if not phone and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        decoded = decode_token(token)
        if decoded and decoded.get("sub"):
            user = users_collection.find_one({"username": decoded["sub"]})
            if user:
                phone = user.get("phone", "").strip()

    if not phone:
        return jsonify({"success": False, "message": "Please enter a valid registered phone number."}), 400

    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) > 10 and phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]
    if len(phone_digits) != 10:
        return jsonify({"success": False, "message": "Phone number must be a valid 10-digit number."}), 400

    # Generate 6-digit numeric OTP
    otp = f"{random.randint(100000, 999999)}"
    expires_at = time.time() + 600  # 10 minutes

    # Store OTP in database
    otp_verifications_collection.delete_many({"trolley_id": trolley_id})
    otp_verifications_collection.insert_one({
        "trolley_id": trolley_id,
        "phone":      phone_digits,
        "otp":        otp,
        "expires_at": expires_at,
        "created_at": time.time(),
        "attempts":   0
    })

    # Dispatch SMS in background
    threading.Thread(target=send_otp_sms, args=(phone_digits, otp), daemon=True).start()

    masked_phone = f"******{phone_digits[-4:]}" if len(phone_digits) >= 4 else phone_digits

    return jsonify({
        "success":      True,
        "message":      f"Verification code sent to {masked_phone}.",
        "trolley_id":   trolley_id,
        "masked_phone": masked_phone,
        "otp":          otp  # Demo mode fallback
    })

@app.route("/api/cart/verify-and-pay", methods=["POST"])
def verify_and_pay():
    """Verifies OTP sent to customer's phone and executes payment/checkout."""
    data = request.json or {}
    trolley_id     = data.get("trolley_id", "TROLLEY-001")
    otp            = (data.get("otp") or "").strip()
    payment_method = data.get("paymentMethod", "UPI")
    phone          = (data.get("phone") or "").strip()

    # Look up OTP record
    otp_record = otp_verifications_collection.find_one({"trolley_id": trolley_id})
    if not otp_record:
        return jsonify({"success": False, "message": "No active OTP request found for this trolley. Please click 'Send OTP' first."}), 400

    if time.time() > otp_record.get("expires_at", 0):
        otp_verifications_collection.delete_many({"trolley_id": trolley_id})
        return jsonify({"success": False, "message": "Verification code has expired. Please request a new OTP."}), 400

    if otp_record.get("attempts", 0) >= 5:
        otp_verifications_collection.delete_many({"trolley_id": trolley_id})
        return jsonify({"success": False, "message": "Too many invalid attempts. Please request a new verification code."}), 429

    if otp_record.get("otp") != otp:
        otp_verifications_collection.update_one({"trolley_id": trolley_id}, {"$set": {"attempts": otp_record.get("attempts", 0) + 1}})
        return jsonify({"success": False, "message": "Invalid OTP code. Please check and try again."}), 400

    # OTP is verified! Proceed to checkout
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — scan items first"}), 400

    saved_items = dict(cart["items"])
    total       = cart["total"]
    timestamp   = time.time()
    phone_used  = phone or otp_record.get("phone", "")

    # Look up trolley for customer metadata
    trolley = trolleys_collection.find_one({"_id": trolley_id}) or {}
    cust_id = trolley.get("assigned_customer_id")
    cust_name = trolley.get("assigned_customer_name", "")
    if not phone_used and trolley.get("assigned_customer_phone"):
        phone_used = trolley.get("assigned_customer_phone")

    invoice_id = f"INV-{int(timestamp)}-{random.randint(1000, 9999)}"

    txn_res = transactions_collection.insert_one({
        "invoiceId":        invoice_id,
        "trolley_id":       trolley_id,
        "items":            saved_items,
        "total":            total,
        "finalTotal":       total,
        "paymentMethod":    payment_method,
        "customerPhone":    phone_used,
        "customer_id":      cust_id,
        "customer_name":    cust_name,
        "timestamp":        timestamp,
        "date":             datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    })
    txn_id = str(txn_res.inserted_id)

    # Update customer record if registered
    if cust_id:
        customers_collection.update_one(
            {"id": cust_id},
            {
                "$inc": {"total_spent": total, "total_visits": 1},
                "$set": {"last_visit": timestamp, "assigned_trolley": None}
            }
        )

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {
            "items":          {},
            "total":          0.0,
            "itemsContained": 0,
            "status":         "ACTIVE",
            "lastActive":     f"Paid via {payment_method} (Verified)"
        }
    })
    # Release trolley to AVAILABLE
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {
            "cart_value":              0.0,
            "item_count":              0,
            "assignment_status":       "AVAILABLE",
            "assigned_customer_id":    None,
            "assigned_customer_name":  "",
            "assigned_customer_phone": "",
            "assigned_at":             None
        }
    })
    db['feed'].insert_one({
        "actionType":    "CHECKOUT",
        "total":         total,
        "paymentMethod": payment_method,
        "customerPhone": phone_used,
        "customer_name": cust_name,
        "trolley_id":    trolley_id,
        "timestamp":     timestamp
    })
    send_command_to_arduino("LCD:Checked Out!|Total: Rs.0.00")
    send_command_to_arduino("BEEP:2")

    # Invalidate verified OTP
    otp_verifications_collection.delete_many({"trolley_id": trolley_id})

    # Dispatch Bill receipt SMS
    if phone_used:
        threading.Thread(target=send_bill_sms, args=(phone_used, txn_id, total, len(saved_items)), daemon=True).start()

    return jsonify({
        "success":        True,
        "message":        "OTP verified and payment successful!",
        "transaction_id": txn_id,
        "invoiceId":      invoice_id,
        "finalTotal":     total,
        "trolley_id":     trolley_id,
        "total":          total,
        "customer_name":  cust_name,
        "customer_id":    cust_id,
        "items":          saved_items,
        "timestamp":      timestamp
    })

@app.route("/api/cart/pay", methods=["POST"])
@app.route("/api/cart/checkout", methods=["POST"])
@app.route("/api/checkout", methods=["POST"])
def pay_bill():
    data = request.json or {}
    trolley_id     = data.get("trolley_id", "TROLLEY-001")
    payment_method = data.get("paymentMethod", "UPI")
    phone          = (data.get("phone") or data.get("customerPhone") or "").strip()

    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty — scan items first"}), 400

    saved_items = dict(cart["items"])
    total       = cart["total"]
    timestamp   = time.time()

    # Look up trolley for customer metadata
    trolley = trolleys_collection.find_one({"_id": trolley_id}) or {}
    cust_id = trolley.get("assigned_customer_id")
    cust_name = trolley.get("assigned_customer_name", "")
    if not phone and trolley.get("assigned_customer_phone"):
        phone = trolley.get("assigned_customer_phone")

    invoice_id = f"INV-{int(timestamp)}-{random.randint(1000, 9999)}"

    txn_res = transactions_collection.insert_one({
        "invoiceId":        invoice_id,
        "trolley_id":       trolley_id,
        "items":            saved_items,
        "total":            total,
        "finalTotal":       total,
        "paymentMethod":    payment_method,
        "paymentReference": data.get("paymentReference", ""),
        "customerPhone":    phone,
        "customer_id":      cust_id,
        "customer_name":    cust_name,
        "timestamp":        timestamp,
        "date":             datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    })
    txn_id = str(txn_res.inserted_id)

    # Update customer record if registered
    if cust_id:
        customers_collection.update_one(
            {"id": cust_id},
            {
                "$inc": {"total_spent": total, "total_visits": 1},
                "$set": {"last_visit": timestamp, "assigned_trolley": None}
            }
        )

    carts_collection.update_one({"_id": cart_id}, {
        "$set": {
            "items":          {},
            "total":          0.0,
            "itemsContained": 0,
            "status":         "ACTIVE",
            "lastActive":     f"Paid via {payment_method}"
        }
    })
    # Release trolley to AVAILABLE
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {
            "cart_value":              0.0,
            "item_count":              0,
            "assignment_status":       "AVAILABLE",
            "assigned_customer_id":    None,
            "assigned_customer_name":  "",
            "assigned_customer_phone": "",
            "assigned_at":             None
        }
    })
    db['feed'].insert_one({
        "actionType":    "CHECKOUT",
        "total":         total,
        "paymentMethod": payment_method,
        "customerPhone": phone,
        "customer_name": cust_name,
        "trolley_id":    trolley_id,
        "timestamp":     timestamp
    })
    send_command_to_arduino("LCD:Checked Out!|Total: Rs.0.00")
    send_command_to_arduino("BEEP:2")

    # Send receipt SMS if phone provided
    if phone:
        threading.Thread(target=send_bill_sms, args=(phone, txn_id, total, len(saved_items)), daemon=True).start()

    return jsonify({
        "success":        True,
        "message":        "Payment successful",
        "transaction_id": txn_id,
        "invoiceId":      invoice_id,
        "finalTotal":     total,
        "trolley_id":     trolley_id,
        "total":          total,
        "customer_name":  cust_name,
        "customer_id":    cust_id,
        "items":          saved_items,
        "timestamp":      timestamp
    })

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
        conn_status = "connected" if is_online else "disconnected"
        status     = "online" if is_online else "offline"

        is_assigned = (t.get("assignment_status") == "ASSIGNED") or bool(t.get("assigned_customer_id"))
        assign_status = "ASSIGNED" if is_assigned else "AVAILABLE"

        if is_assigned and is_online:
            disp_status = "Assigned (Connected)"
        elif is_assigned and not is_online:
            disp_status = "Assigned (Disconnected)"
        elif not is_assigned and is_online:
            disp_status = "Available (Connected)"
        else:
            disp_status = "Available (Offline)"

        # Pull live cart data
        cart = carts_collection.find_one({"_id": _trolley_cart_id(tid)})
        cart_value  = cart.get("total", 0.0) if cart else 0.0
        item_count  = cart.get("itemsContained", 0) if cart else 0
        cart_status = cart.get("status", "ACTIVE") if cart else "ACTIVE"

        hb = format_heartbeat_status(last_seen, now_ts)

        result.append({
            "id":                      tid,
            "name":                    t.get("name", tid),
            "status":                  status,
            "connection_status":       conn_status,
            "assignment_status":       assign_status,
            "display_status":          disp_status,
            "assigned_customer_id":    t.get("assigned_customer_id"),
            "assigned_customer_name":  t.get("assigned_customer_name", ""),
            "assigned_customer_phone": t.get("assigned_customer_phone", ""),
            "assigned_customer_email": t.get("assigned_customer_email", ""),
            "assigned_at":             t.get("assigned_at"),
            "battery":                 t.get("battery", 0),
            "ip_address":              t.get("ip_address", ""),
            "wifi_rssi":               t.get("wifi_rssi", 0),
            "last_seen":               last_seen,
            "last_heartbeat":          t.get("last_heartbeat", last_seen),
            "last_heartbeat_time_str": hb["last_heartbeat_time_str"],
            "last_seen_24h":           hb["last_seen_24h"],
            "last_seen_str":           hb["last_seen_str"],
            "last_seen_relative":      hb["last_seen_relative"],
            "last_heartbeat_display":  hb["last_heartbeat_display"],
            "firmware_version":        t.get("firmware_version", ""),
            "cart_value":              cart_value,
            "item_count":              item_count,
            "cart_status":             cart_status,
            "current_mode":            t.get("current_mode", "ADD"),
            # Legacy fields kept for backward compatibility with old trolleys.js
            "customer":                t.get("assigned_customer_name") or t.get("customer", "None"),
            "items":                   item_count,
            "total":                   cart_value,
            "latency":                 t.get("latency", 0)
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
    conn_status = "connected" if is_online else "disconnected"
    status    = "online" if is_online else "offline"

    is_assigned = (t.get("assignment_status") == "ASSIGNED") or bool(t.get("assigned_customer_id"))
    assign_status = "ASSIGNED" if is_assigned else "AVAILABLE"

    if is_assigned and is_online:
        disp_status = "Assigned (Connected)"
    elif is_assigned and not is_online:
        disp_status = "Assigned (Disconnected)"
    elif not is_assigned and is_online:
        disp_status = "Available (Connected)"
    else:
        disp_status = "Available (Offline)"

    cart = carts_collection.find_one({"_id": _trolley_cart_id(trolley_id)})
    cart_data = {}
    if cart:
        cart_data = {
            "items":          cart.get("items", {}),
            "total":          cart.get("total", 0.0),
            "itemsContained": cart.get("itemsContained", 0),
            "status":         cart.get("status", "ACTIVE"),
            "lastActive":     cart.get("lastActive", ""),
            "customer_id":    cart.get("customer_id") or t.get("assigned_customer_id"),
            "customer_name":  cart.get("customer_name") or t.get("assigned_customer_name"),
            "customer_phone": cart.get("customer_phone") or t.get("assigned_customer_phone")
        }

    hb = format_heartbeat_status(last_seen, now_ts)

    return jsonify({
        "success":                 True,
        "id":                      trolley_id,
        "name":                    t.get("name", trolley_id),
        "status":                  status,
        "connection_status":       conn_status,
        "assignment_status":       assign_status,
        "display_status":          disp_status,
        "assigned_customer_id":    t.get("assigned_customer_id"),
        "assigned_customer_name":  t.get("assigned_customer_name", ""),
        "assigned_customer_phone": t.get("assigned_customer_phone", ""),
        "assigned_customer_email": t.get("assigned_customer_email", ""),
        "assigned_at":             t.get("assigned_at"),
        "battery":                 t.get("battery", 0),
        "ip_address":              t.get("ip_address", ""),
        "wifi_rssi":               t.get("wifi_rssi", 0),
        "last_seen":               last_seen,
        "last_heartbeat":          t.get("last_heartbeat", last_seen),
        "last_heartbeat_time_str": hb["last_heartbeat_time_str"],
        "last_seen_24h":           hb["last_seen_24h"],
        "last_seen_str":           hb["last_seen_str"],
        "last_seen_relative":      hb["last_seen_relative"],
        "last_heartbeat_display":  hb["last_heartbeat_display"],
        "firmware_version":        t.get("firmware_version", ""),
        "current_mode":            t.get("current_mode", "ADD"),
        "cart":                    cart_data
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
    """Register or update a trolley in the registry. Preserves active cart and customer session."""
    data = request.json or {}
    trolley_id = (data.get("trolley_id") or data.get("id") or "").strip().upper()
    name = (data.get("name") or trolley_id).strip()
    fw_ver = data.get("firmware_version", "2.0")
    ip_addr = data.get("ip_address", "")
    section = data.get("section", "General")

    if not trolley_id:
        return jsonify({"success": False, "message": "Trolley ID is required (e.g. TROLLEY-001)"}), 400

    now_ts = time.time()
    existing = trolleys_collection.find_one({"_id": trolley_id})
    if not existing:
        trolleys_collection.insert_one({
            "_id":                     trolley_id,
            "name":                    name,
            "firmware_version":        fw_ver,
            "ip_address":              ip_addr,
            "section":                 section,
            "status":                  data.get("status", "online"),
            "assignment_status":       "AVAILABLE",
            "assigned_customer_id":    None,
            "assigned_customer_name":  "",
            "assigned_customer_phone": "",
            "assigned_at":             None,
            "battery":                 data.get("battery", 100),
            "wifi_rssi":               data.get("wifi_rssi", -50),
            "cart_value":              0.0,
            "item_count":              0,
            "current_mode":            "ADD",
            "last_seen":               now_ts,
            "last_heartbeat":          now_ts
        })
    else:
        # DO NOT wipe existing cart, items, or customer assignment!
        trolleys_collection.update_one(
            {"_id": trolley_id},
            {"$set": {
                "name":             name if name != trolley_id else existing.get("name", trolley_id),
                "firmware_version": fw_ver,
                "ip_address":       ip_addr or existing.get("ip_address", ""),
                "section":          section,
                "status":           data.get("status", "online"),
                "battery":          data.get("battery", existing.get("battery", 100)),
                "wifi_rssi":        data.get("wifi_rssi", existing.get("wifi_rssi", -50)),
                "last_seen":        now_ts,
                "last_heartbeat":   now_ts
            }}
        )

    init_cart(trolley_id)
    cart = carts_collection.find_one({"_id": _trolley_cart_id(trolley_id)}) or {}
    trolley_doc = trolleys_collection.find_one({"_id": trolley_id}) or {}

    cust_name = trolley_doc.get("assigned_customer_name") or "Guest"
    cust_id = trolley_doc.get("assigned_customer_id")
    cart_total = cart.get("total", 0.0)
    item_count = cart.get("itemsContained", 0)

    # Sync cart totals in trolley doc
    trolleys_collection.update_one({"_id": trolley_id}, {"$set": {"cart_value": cart_total, "item_count": item_count}})

    print(f"[TROLLEY] Registered: {trolley_id} ({name}) | Cart: Rs.{cart_total:.2f} ({item_count} items) | Customer: {cust_name}")

    return jsonify({
        "status":     "success",
        "success":    True,
        "message":    f"Trolley {trolley_id} registered successfully",
        "trolley_id": trolley_id,
        "mode":       trolley_doc.get("current_mode", "ADD"),
        "cart": {
            "item_count":   item_count,
            "total_amount": cart_total
        },
        "customer": {
            "customer_id":   cust_id,
            "customer_name": cust_name
        }
    })

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
    Updates battery, RSSI, IP, last_seen, last_heartbeat, and marks trolley as online.
    Heartbeat failure only affects online/offline status and NEVER resets the cart.
    """
    data = request.json or {}
    trolley_id = data.get("trolley_id")
    if not trolley_id:
        return jsonify({"success": False, "message": "trolley_id required"}), 400

    now_ts = time.time()

    existing = trolleys_collection.find_one({"_id": trolley_id})
    if not existing:
        trolleys_collection.insert_one({
            "_id":                     trolley_id,
            "name":                    data.get("name", trolley_id),
            "status":                  "online",
            "assignment_status":       "AVAILABLE",
            "assigned_customer_id":    None,
            "assigned_customer_name":  "",
            "assigned_customer_phone": "",
            "assigned_at":             None,
            "battery":                 data.get("battery", 0),
            "ip_address":              data.get("ip_address", ""),
            "wifi_rssi":               data.get("wifi_rssi", 0),
            "last_seen":               now_ts,
            "last_heartbeat":          now_ts,
            "firmware_version":        data.get("firmware_version", "2.0"),
            "cart_value":              0.0,
            "item_count":              0,
            "current_mode":            "ADD"
        })
        init_cart(trolley_id)
        print(f"[HEARTBEAT] Auto-registered new trolley: {trolley_id}")
    else:
        update_fields = {
            "status":         "online",
            "last_seen":      now_ts,
            "last_heartbeat": now_ts
        }
        if "battery" in data:
            update_fields["battery"] = data["battery"]
        if "wifi_rssi" in data:
            update_fields["wifi_rssi"] = data["wifi_rssi"]
        if "ip_address" in data and data["ip_address"]:
            update_fields["ip_address"] = data["ip_address"]
        if "firmware_version" in data and data["firmware_version"]:
            update_fields["firmware_version"] = data["firmware_version"]

        trolleys_collection.update_one({"_id": trolley_id}, {"$set": update_fields})

    hb = format_heartbeat_status(now_ts, now_ts)
    return jsonify({
        "success":                 True,
        "trolley_id":               trolley_id,
        "status":                  "online",
        "server_time":             now_ts,
        "last_heartbeat_time_str": hb["last_heartbeat_time_str"],
        "last_seen_str":           hb["last_seen_str"]
    })

# ── Customer Registration & Trolley Assignment APIs ──────────────────────────

@app.route("/api/customers", methods=["GET"])
def get_customers():
    """Return all registered customers."""
    cust_list = list(customers_collection.find({}, {"_id": 0}))
    return jsonify(cust_list)

@app.route("/api/customers", methods=["POST"])
def register_customer():
    """Register a new customer."""
    data = request.json or {}
    cust_id = (data.get("customer_id") or data.get("id") or "").strip().upper()
    name    = (data.get("name") or "").strip()
    phone   = (data.get("phone") or data.get("mobile") or "").strip()
    email   = (data.get("email") or "").strip()

    if not name:
        return jsonify({"success": False, "message": "Customer name is required"}), 400
    if not phone:
        return jsonify({"success": False, "message": "Phone / Mobile number is required"}), 400

    if not cust_id:
        cust_id = f"CUST-{random.randint(1000, 9999)}"

    # Check for existing duplicate id
    if customers_collection.find_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]}):
        return jsonify({"success": False, "message": f"Customer ID '{cust_id}' is already registered."}), 400

    # Check for existing duplicate phone
    if customers_collection.find_one({"phone": phone}):
        return jsonify({"success": False, "message": f"Phone number '{phone}' is already registered to another customer."}), 400

    cust_doc = {
        "id":               cust_id,
        "customer_id":      cust_id,
        "name":             name,
        "phone":            phone,
        "email":            email,
        "assigned_trolley": None,
        "total_spent":      0.0,
        "total_visits":     0,
        "status":           "Active",
        "created_at":       time.time()
    }
    customers_collection.insert_one(cust_doc)
    doc_copy = dict(cust_doc)
    doc_copy.pop("_id", None)
    return jsonify({"success": True, "message": "Customer registered successfully", "customer": doc_copy}), 201

@app.route("/api/customers/<cust_id>", methods=["GET"])
def get_customer_detail(cust_id):
    cust_id = cust_id.strip()
    cust = customers_collection.find_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]}, {"_id": 0})
    if not cust:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    return jsonify({"success": True, "customer": cust})

@app.route("/api/customers/<cust_id>", methods=["PUT"])
@require_auth(roles=["admin", "manager"])
def update_customer(cust_id):
    cust_id = cust_id.strip()
    data = request.json or {}
    updates = {}
    for k in ["name", "phone", "email", "status"]:
        if k in data:
            updates[k] = data[k]
    if updates:
        res = customers_collection.update_one(
            {"$or": [{"id": cust_id}, {"customer_id": cust_id}]},
            {"$set": updates}
        )
        if res.matched_count == 0:
            return jsonify({"success": False, "message": "Customer not found"}), 404
    return jsonify({"success": True, "message": "Customer updated successfully"})

@app.route("/api/customers/<cust_id>", methods=["DELETE"])
@require_auth(roles=["admin", "manager"])
def delete_customer(cust_id):
    cust_id = cust_id.strip()
    # If customer is currently assigned to a trolley, release the trolley
    assigned_t = trolleys_collection.find_one({"assigned_customer_id": cust_id})
    if assigned_t:
        trolleys_collection.update_one(
            {"_id": assigned_t["_id"]},
            {"$set": {
                "assignment_status":       "AVAILABLE",
                "assigned_customer_id":    None,
                "assigned_customer_name":  "",
                "assigned_customer_phone": "",
                "assigned_at":             None
            }}
        )
    customers_collection.delete_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]})
    return jsonify({"success": True, "message": "Customer deleted successfully"})

@app.route("/api/trolleys/<trolley_id>/assign", methods=["POST"])
def assign_trolley_to_customer(trolley_id):
    """Assign an active trolley to a customer with mutual exclusion."""
    trolley_id = trolley_id.strip().upper()
    data = request.json or {}
    cust_id = (data.get("customer_id") or data.get("id") or "").strip()

    if not cust_id:
        return jsonify({"success": False, "message": "Customer ID is required for trolley assignment"}), 400

    trolley = trolleys_collection.find_one({"_id": trolley_id})
    if not trolley:
        return jsonify({"success": False, "message": f"Trolley {trolley_id} not found"}), 404

    # MUTUAL EXCLUSION CHECK 1: Trolley already assigned to another customer
    if trolley.get("assignment_status") == "ASSIGNED" and trolley.get("assigned_customer_id") != cust_id:
        assigned_to = trolley.get("assigned_customer_name") or trolley.get("assigned_customer_id")
        return jsonify({
            "success": False,
            "message": f"Trolley {trolley_id} is already assigned to customer '{assigned_to}'."
        }), 400

    if cust_id.lower() == "guest":
        actual_cust_id = "guest"
        cust_name = "Guest Shopper"
        cust_phone = ""
        cust_email = ""
    else:
        customer = customers_collection.find_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]})
        if not customer:
            return jsonify({"success": False, "message": f"Customer '{cust_id}' not found. Please register customer first."}), 404

        actual_cust_id = customer.get("id") or cust_id
        cust_name = customer.get("name", "")
        cust_phone = customer.get("phone", "")
        cust_email = customer.get("email", "")

        # MUTUAL EXCLUSION CHECK 2: Customer already has another trolley assigned
        other_trolley = trolleys_collection.find_one({
            "assigned_customer_id": actual_cust_id,
            "_id": {"$ne": trolley_id}
        })
        if other_trolley:
            return jsonify({
                "success": False,
                "message": f"Customer '{customer.get('name')}' is already assigned to {other_trolley['_id']}. Please release that trolley first."
            }), 400

    now_ts = time.time()
    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {
            "assignment_status":       "ASSIGNED",
            "assigned_customer_id":    actual_cust_id,
            "assigned_customer_name":  cust_name,
            "assigned_customer_phone": cust_phone,
            "assigned_customer_email": cust_email,
            "assigned_at":             now_ts
        }}
    )

    if actual_cust_id != "guest":
        customers_collection.update_one(
            {"$or": [{"id": actual_cust_id}, {"customer_id": actual_cust_id}]},
            {"$set": {"assigned_trolley": trolley_id}}
        )

    # Persist customer metadata to carts_collection
    cart_id = _trolley_cart_id(trolley_id)
    carts_collection.update_one(
        {"_id": cart_id},
        {"$set": {
            "customer_id":             actual_cust_id,
            "customer_name":           cust_name,
            "customer_phone":          cust_phone,
            "customer_email":          cust_email,
            "assignment_status":       "ASSIGNED"
        }},
        upsert=True
    )

    print(f"[ASSIGNMENT] {trolley_id} assigned to {cust_name} ({actual_cust_id})")

    return jsonify({
        "success": True,
        "message": f"Trolley {trolley_id} assigned to {cust_name}.",
        "trolley_id": trolley_id,
        "customer": {
            "id":    actual_cust_id,
            "name":  cust_name,
            "phone": cust_phone,
            "email": cust_email
        }
    })

@app.route("/api/trolleys/<trolley_id>/unassign", methods=["POST"])
def unassign_trolley(trolley_id):
    """Release a trolley from customer assignment back to AVAILABLE."""
    trolley_id = trolley_id.strip().upper()
    trolley = trolleys_collection.find_one({"_id": trolley_id})
    if not trolley:
        return jsonify({"success": False, "message": f"Trolley {trolley_id} not found"}), 404

    cust_id = trolley.get("assigned_customer_id")
    if cust_id:
        customers_collection.update_one(
            {"$or": [{"id": cust_id}, {"customer_id": cust_id}]},
            {"$set": {"assigned_trolley": None}}
        )

    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {
            "assignment_status":       "AVAILABLE",
            "assigned_customer_id":    None,
            "assigned_customer_name":  "",
            "assigned_customer_phone": "",
            "assigned_customer_email": "",
            "assigned_at":             None
        }}
    )

    cart_id = _trolley_cart_id(trolley_id)
    carts_collection.update_one(
        {"_id": cart_id},
        {"$set": {
            "customer_id":             None,
            "customer_name":           "",
            "customer_phone":          "",
            "customer_email":          "",
            "assignment_status":       "AVAILABLE"
        }}
    )

    print(f"[UNASSIGNMENT] {trolley_id} released to AVAILABLE status")
    return jsonify({"success": True, "message": f"Trolley {trolley_id} is now AVAILABLE."})

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
    customer_filter = request.args.get("customer_id")
    phone_filter = request.args.get("phone")
    query = {}
    if trolley_filter:
        query["trolley_id"] = trolley_filter
    if customer_filter:
        query["$or"] = [{"customer_id": customer_filter}, {"customerPhone": customer_filter}]
    elif phone_filter:
        query["customerPhone"] = phone_filter
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
        "storeName":     cfg.get("storeName", "GECM Supermarket"),
        "useCustomQr":   bool(cfg.get("useCustomQr", False)),
        "customQrImage": cfg.get("customQrImage", "")
    })

@app.route("/api/payment/qr", methods=["GET"])
def get_payment_qr():
    """Generates official high-contrast NPCI UPI QR code image."""
    amount = request.args.get("amount", "0.00")
    cfg = load_config()
    upi_id = (cfg.get("upiId") or "9353180038@ybl").strip()
    store_name = (cfg.get("storeName") or "GECM Supermarket").strip()

    upi_url = f"upi://pay?pa={upi_id}&pn={urllib.parse.quote(store_name)}&am={amount}&cu=INR&tn=SmartTrolleyBill"

    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

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

@app.route("/api/settings/notifications", methods=["GET"])
@require_auth(roles=["admin", "manager"])
def get_notification_settings():
    cfg = load_config()
    smtp_pass = cfg.get("smtpPassword", "")
    masked_smtp_pass = ("•" * 8) if smtp_pass else ""
    fast2sms_key = cfg.get("fast2smsApiKey", "")
    masked_sms_key = ("•" * 8) if fast2sms_key else ""
    twilio_token = cfg.get("twilioAuthToken", "")
    masked_twilio_token = ("•" * 8) if twilio_token else ""

    return jsonify({
        "success": True,
        "smtpServer":       cfg.get("smtpServer", "smtp.gmail.com"),
        "smtpPort":         cfg.get("smtpPort", 587),
        "smtpUser":         cfg.get("smtpUser", ""),
        "smtpPasswordSet":  bool(smtp_pass),
        "smtpPasswordMask": masked_smtp_pass,
        "fast2smsApiKeySet": bool(fast2sms_key),
        "fast2smsApiKeyMask": masked_sms_key,
        "twilioSid":        cfg.get("twilioSid", ""),
        "twilioAuthTokenSet": bool(twilio_token),
        "twilioAuthTokenMask": masked_twilio_token,
        "twilioFromPhone":  cfg.get("twilioFromPhone", "")
    })

@app.route("/api/settings/notifications", methods=["POST"])
@require_auth(roles=["admin", "manager"])
def update_notification_settings():
    data = request.json or {}
    cfg = load_config()

    if "smtpServer" in data:
        cfg["smtpServer"] = (data["smtpServer"] or "smtp.gmail.com").strip()
    if "smtpPort" in data:
        try:
            cfg["smtpPort"] = int(data["smtpPort"])
        except:
            cfg["smtpPort"] = 587
    if "smtpUser" in data:
        cfg["smtpUser"] = (data["smtpUser"] or "").strip()
    if "smtpPassword" in data and data["smtpPassword"] != "••••••••":
        cfg["smtpPassword"] = (data["smtpPassword"] or "").strip()

    if "fast2smsApiKey" in data and data["fast2smsApiKey"] != "••••••••":
        cfg["fast2smsApiKey"] = (data["fast2smsApiKey"] or "").strip()
    if "twilioSid" in data:
        cfg["twilioSid"] = (data["twilioSid"] or "").strip()
    if "twilioAuthToken" in data and data["twilioAuthToken"] != "••••••••":
        cfg["twilioAuthToken"] = (data["twilioAuthToken"] or "").strip()
    if "twilioFromPhone" in data:
        cfg["twilioFromPhone"] = (data["twilioFromPhone"] or "").strip()

    save_config(cfg)
    return jsonify({
        "success": True,
        "message": "Email & SMS notification gateway settings saved successfully!"
    })

@app.route("/api/settings/notifications/test", methods=["POST"])
@require_auth(roles=["admin", "manager"])
def test_notification_dispatch():
    data = request.json or {}
    test_type = data.get("type", "email") # "email" or "sms"
    target    = (data.get("target") or "").strip()

    if not target:
        return jsonify({"success": False, "message": "Target email address or phone number is required."}), 400

    test_otp = f"{random.randint(100000, 999999)}"

    if test_type == "email":
        ok, msg = send_otp_email(target, test_otp, "Store Admin")
        if ok:
            return jsonify({"success": True, "message": f"Test email sent successfully to {target} with code {test_otp}."})
        return jsonify({"success": False, "message": f"Email sending failed: {msg}"}), 500
    elif test_type == "sms":
        ok, msg = send_otp_sms(target, test_otp)
        if ok:
            return jsonify({"success": True, "message": f"Test SMS sent successfully to {target} with code {test_otp}."})
        return jsonify({"success": False, "message": f"SMS sending failed: {msg}"}), 500

    return jsonify({"success": False, "message": "Invalid notification test type."}), 400

# ── Trolley Wi-Fi Configuration API ──────────────────────────────────────────

def get_local_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def get_all_known_ips(cfg, current_ip):
    """Compile a list of all saved, active, and known IP addresses for Wi-Fi setup."""
    saved_ips = []
    seen = set()

    def add_ip(ip_val, label_str, category_str, is_active=False):
        if not ip_val or ip_val in seen:
            return
        seen.add(ip_val)
        saved_ips.append({
            "ip": ip_val,
            "label": label_str,
            "category": category_str,
            "isActive": is_active
        })

    # 1. Current Live Host IP
    add_ip(current_ip, f"Live Active Wi-Fi IP ({current_ip}) [Recommended]", "live", True)

    # 2. Configured IP in config.json
    cfg_ip = cfg.get("serverIP")
    if cfg_ip:
        add_ip(cfg_ip, f"Configured in config.json ({cfg_ip})", "config")

    # 3. All network interfaces from hostname
    try:
        import socket
        for iface_ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not iface_ip.startswith("127."):
                add_ip(iface_ip, f"Network Adapter IP ({iface_ip})", "adapter")
    except Exception:
        pass

    # 4. Known Firmware IPs
    add_ip("10.221.37.241", "ESP32 Firmware Default (10.221.37.241)", "firmware")
    add_ip("10.175.93.241", "ESP32 NVS Fallback (10.175.93.241)", "firmware")
    add_ip("192.168.1.101", "Trolley 001 Lab Static IP (192.168.1.101)", "static")
    add_ip("192.168.1.104", "Trolley 002 Lab Static IP (192.168.1.104)", "static")

    # 5. Custom saved historical IPs from config
    for custom in cfg.get("savedIPs", []):
        add_ip(custom, f"Custom Saved IP ({custom})", "custom")

    # 6. Localhost
    add_ip("127.0.0.1", "Localhost Loopback (127.0.0.1)", "loopback")

    return saved_ips

def get_known_wifi_networks():
    """List of known Wi-Fi networks from firmware and hotspot profiles."""
    return [
        {"ssid": "Redmi 13C 5G", "pass": "111111111", "label": "Active Hotspot (Redmi 13C 5G)"},
        {"ssid": "Yogaraj", "pass": "1234567890", "label": "ESP32 Default Wi-Fi (Yogaraj)"},
        {"ssid": "Nandini K Y", "pass": "333444455555", "label": "Saved Hotspot (Nandini K Y)"},
        {"ssid": "motorolaedge50fusion", "pass": "111111111", "label": "Saved Hotspot (motorolaedge50fusion)"},
        {"ssid": "OnePlus Nord CE 2 Lite 5G", "pass": "8970868217", "label": "Config Stored Wi-Fi"}
    ]

@app.route("/api/settings/wifi", methods=["GET"])
def get_wifi_settings():
    cfg = load_config()
    current_ip = get_local_ip()
    saved_ips = get_all_known_ips(cfg, current_ip)
    known_nets = get_known_wifi_networks()
    return jsonify({
        "ssid":            cfg.get("wifiSSID", "Redmi 13C 5G"),
        "password":        cfg.get("wifiPassword", "111111111"),
        "serverIP":        cfg.get("serverIP", current_ip),
        "localIP":         current_ip,
        "savedIPs":        saved_ips,
        "knownNetworks":   known_nets,
        "serverPort":      cfg.get("serverPort", 5000),
        "serialConnected": bool(global_ser and global_ser.is_open),
        "serialPort":      SERIAL_PORT
    })

@app.route("/api/settings/wifi", methods=["POST"])
def update_wifi_settings():
    data = request.json or {}
    ssid        = (data.get("ssid") or "").strip()
    password    = (data.get("password") or "").strip()
    server_ip   = (data.get("serverIP") or "").strip() or get_local_ip()
    server_port = int(data.get("serverPort") or 5000)
    send_to_usb = data.get("sendToUsb", True)

    if not ssid:
        return jsonify({"success": False, "message": "Wi-Fi SSID is required."}), 400

    cfg = load_config()
    cfg["wifiSSID"]     = ssid
    cfg["wifiPassword"] = password
    cfg["serverIP"]     = server_ip
    cfg["serverPort"]   = server_port

    # Persist in savedIPs list if new
    saved_list = cfg.get("savedIPs", [])
    if server_ip and server_ip not in saved_list:
        saved_list.append(server_ip)
        cfg["savedIPs"] = saved_list

    save_config(cfg)

    usb_sent = False
    if send_to_usb and global_ser and global_ser.is_open:
        cmd = f"WIFI_CFG:{ssid}|{password}|{server_ip}|{server_port}"
        send_command_to_arduino(cmd)
        usb_sent = True

    msg = "Wi-Fi settings saved successfully."
    if usb_sent:
        msg += " Pushed to Trolley via USB (COM3)!"
    else:
        msg += " (Trolley USB not connected, settings saved for wireless trolleys)."

    return jsonify({
        "success": True,
        "message": msg,
        "usbSent": usb_sent,
        "serverIP": server_ip,
        "serverPort": server_port
    })

# ---------------------------------------------------------------------------
# Wi-Fi Networks Management & Connection Assistant
# ---------------------------------------------------------------------------

def get_wifi_interface_status():
    """Retrieve active Wi-Fi interface details on Windows."""
    try:
        res = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], capture_output=True, text=True, errors='ignore', timeout=5)
        state_m = re.search(r'^\s*State\s*:\s*(.+)$', res.stdout, re.M)
        ssid_m = re.search(r'^\s*SSID\s*:\s*(.+)$', res.stdout, re.M)
        signal_m = re.search(r'^\s*Signal\s*:\s*(.+)$', res.stdout, re.M)
        bssid_m = re.search(r'^\s*AP BSSID\s*:\s*(.+)$', res.stdout, re.M)
        desc_m = re.search(r'^\s*Description\s*:\s*(.+)$', res.stdout, re.M)
        state = state_m.group(1).strip() if state_m else "disconnected"
        ssid = ssid_m.group(1).strip() if ssid_m else ""
        signal = signal_m.group(1).strip() if signal_m else "0%"
        bssid = bssid_m.group(1).strip() if bssid_m else ""
        desc = desc_m.group(1).strip() if desc_m else "Wi-Fi Adapter"
        return {
            "state": state,
            "connected": state.lower() == "connected",
            "ssid": ssid,
            "signal": signal,
            "bssid": bssid,
            "adapter": desc,
            "localIP": get_local_ip()
        }
    except Exception as e:
        return {
            "state": "unknown",
            "connected": False,
            "ssid": "",
            "signal": "0%",
            "bssid": "",
            "adapter": "Unknown",
            "localIP": get_local_ip(),
            "error": str(e)
        }

@app.route("/api/wifi/status", methods=["GET"])
def api_wifi_status():
    status = get_wifi_interface_status()
    cfg = load_config()
    status["configuredSSID"] = cfg.get("wifiSSID", "")
    status["configuredServerIP"] = cfg.get("serverIP", status["localIP"])
    status["serverPort"] = cfg.get("serverPort", 5000)
    return jsonify(status)

@app.route("/api/wifi/saved-profiles", methods=["GET"])
def api_wifi_saved_profiles():
    """Returns saved Windows Wi-Fi profiles and their known passwords."""
    try:
        res = subprocess.run(['netsh', 'wlan', 'show', 'profiles'], capture_output=True, text=True, errors='ignore', timeout=5)
        names = [p.strip() for p in re.findall(r'All User Profile\s*:\s*(.+)', res.stdout)]
        
        from concurrent.futures import ThreadPoolExecutor
        def fetch_key(name):
            try:
                p_res = subprocess.run(['netsh', 'wlan', 'show', 'profile', f'name={name}', 'key=clear'], capture_output=True, text=True, errors='ignore', timeout=3)
                km = re.search(r'Key Content\s*:\s*(.+)', p_res.stdout)
                pwd = km.group(1).strip() if km else ''
                return {"ssid": name, "hasPassword": bool(pwd), "password": pwd}
            except Exception:
                return {"ssid": name, "hasPassword": False, "password": ""}

        with ThreadPoolExecutor(max_workers=8) as ex:
            profiles = list(ex.map(fetch_key, names[:25]))
            
        return jsonify({"success": True, "profiles": profiles})
    except Exception as e:
        return jsonify({"success": False, "profiles": [], "error": str(e)})

@app.route("/api/wifi/scan", methods=["GET"])
def api_wifi_scan():
    """Scans for nearby visible Wi-Fi networks in range."""
    try:
        status = get_wifi_interface_status()
        current_ssid = status.get("ssid", "")

        res = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], capture_output=True, text=True, errors='ignore', timeout=8)
        blocks = re.split(r'\nSSID\s+\d+\s+:\s*', res.stdout)
        networks = []
        seen = set()

        for b in blocks[1:]:
            lines = b.split('\n')
            ssid = lines[0].strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)

            auth = re.search(r'Authentication\s*:\s*(.+)', b)
            signal = re.search(r'Signal\s*:\s*(\d+)%', b)
            band = re.search(r'Band\s*:\s*(.+)', b)
            bssid = re.search(r'BSSID\s+\d+\s*:\s*([0-9a-fA-F:]+)', b)

            # Check if profile exists and get clear key
            p_res = subprocess.run(['netsh', 'wlan', 'show', 'profile', f'name={ssid}', 'key=clear'], capture_output=True, text=True, errors='ignore', timeout=2)
            km = re.search(r'Key Content\s*:\s*(.+)', p_res.stdout)
            has_profile = 'All User Profile' in p_res.stdout or 'User Profile' in p_res.stdout
            pwd = km.group(1).strip() if km else ''

            networks.append({
                "ssid": ssid,
                "auth": auth.group(1).strip() if auth else "WPA2-Personal",
                "signal": int(signal.group(1)) if signal else 50,
                "band": band.group(1).strip() if band else "2.4 GHz",
                "bssid": bssid.group(1).strip() if bssid else "",
                "isCurrent": (ssid.lower() == current_ssid.lower()),
                "hasSavedProfile": has_profile,
                "password": pwd
            })

        # Sort by active first, then signal strength descending
        networks.sort(key=lambda x: (not x["isCurrent"], -x["signal"]))

        return jsonify({
            "success": True,
            "currentSSID": current_ssid,
            "connected": status.get("connected", False),
            "networks": networks
        })
    except Exception as e:
        return jsonify({"success": False, "networks": [], "error": str(e)}), 500

@app.route("/api/wifi/connect", methods=["POST"])
def api_wifi_connect():
    """Connect the host system to a Wi-Fi network."""
    data = request.json or {}
    ssid = (data.get("ssid") or "").strip()
    password = (data.get("password") or "").strip()

    if not ssid:
        return jsonify({"success": False, "message": "SSID is required."}), 400

    try:
        # Check if Windows already has a profile for this SSID
        p_check = subprocess.run(['netsh', 'wlan', 'show', 'profile', f'name={ssid}'], capture_output=True, text=True, errors='ignore', timeout=3)
        profile_exists = "All User Profile" in p_check.stdout or "User Profile" in p_check.stdout

        if not profile_exists and password:
            # Create a WPA2 profile XML and add it
            import tempfile
            xml_content = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""
            temp_xml = os.path.join(tempfile.gettempdir(), f"wifi_prof_{int(time.time())}.xml")
            with open(temp_xml, "w", encoding="utf-8") as f:
                f.write(xml_content)
            try:
                subprocess.run(['netsh', 'wlan', 'add', 'profile', f'filename={temp_xml}', 'user=all'], capture_output=True, text=True, errors='ignore', timeout=5)
            finally:
                if os.path.exists(temp_xml):
                    try: os.remove(temp_xml)
                    except Exception: pass

        # Initiate connection
        cmd = ['netsh', 'wlan', 'connect', f'name={ssid}']
        c_res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore', timeout=8)
        
        # Give Windows a brief moment to associate and acquire IP
        time.sleep(2.5)
        new_status = get_wifi_interface_status()
        new_ip = get_local_ip()

        # Also update config.json with this SSID and new IP
        cfg = load_config()
        cfg["wifiSSID"] = ssid
        if password:
            cfg["wifiPassword"] = password
        cfg["serverIP"] = new_ip
        save_config(cfg)

        return jsonify({
            "success": True,
            "message": f"Connection command issued to '{ssid}'.",
            "connected": new_status.get("connected", False),
            "currentSSID": new_status.get("ssid", ssid),
            "signal": new_status.get("signal", "0%"),
            "localIP": new_ip
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Connection error: {str(e)}"}), 500

@app.route("/api/wifi/disconnect", methods=["POST"])
def api_wifi_disconnect():
    """Disconnect active Wi-Fi connection."""
    try:
        subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True, text=True, errors='ignore', timeout=5)
        return jsonify({"success": True, "message": "Disconnected from Wi-Fi network."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Disconnect error: {str(e)}"}), 500

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
    email = (data.get("email") or "").strip().lower()

    if not emp_id or not name:
        return jsonify({"success": False, "message": "Employee ID and Full Name are required."}), 400

    if len(name) < 2:
        return jsonify({"success": False, "message": "Employee name must be at least 2 characters long."}), 400

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address (e.g. employee@smarttrolley.com)."}), 400

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
            "email":    email,
            "role":     role,
            "shift":    shift,
            "status":   status
        }},
        upsert=True
    )

    # If a password is provided (or when creating a new employee), sync with users_collection
    user_role = role.lower()
    if user_role not in ["admin", "manager", "cashier", "customer"]:
        user_role = "cashier"

    user_update_fields = {
        "username":      username,
        "name":          name,
        "role":          user_role,
        "status":        status,
        "email":         email,
        "updated_at":    time.time()
    }

    if password:
        user_update_fields["password_hash"] = generate_password_hash(password)
        users_collection.update_one(
            {"username": username},
            {"$set": user_update_fields},
            upsert=True
        )
    else:
        existing_user = users_collection.find_one({"username": username})
        if not existing_user:
            default_pw = f"{username}123"
            new_user_doc = {
                "username":      username,
                "password_hash": generate_password_hash(default_pw),
                "name":          name,
                "role":          user_role,
                "status":        status,
                "email":         email,
                "created_at":    time.time()
            }
            users_collection.insert_one(new_user_doc)
        else:
            users_collection.update_one(
                {"username": username},
                {"$set": user_update_fields}
            )

    return jsonify({"success": True, "message": f"Employee {name} ({emp_id}) saved successfully."})

@app.route("/api/employees/<emp_id>/email", methods=["PUT"])
@require_auth(roles=["admin", "manager"])
def update_employee_email(emp_id):
    """Admin/Manager endpoint to update an employee's registered email address."""
    emp_id = (emp_id or "").strip().upper()
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address (e.g. employee@smarttrolley.com)."}), 400

    employees_collection = db["employees"]
    emp = employees_collection.find_one({"id": emp_id})
    if not emp:
        return jsonify({"success": False, "message": f"Employee '{emp_id}' not found."}), 404

    employees_collection.update_one(
        {"id": emp_id},
        {"$set": {"email": email}}
    )

    # Sync to users_collection for this employee
    target_username = emp.get("username", emp_id.lower()).lower()
    users_collection.update_many(
        {"$or": [
            {"username": target_username},
            {"username": emp_id.lower()}
        ]},
        {"$set": {"email": email, "updated_at": time.time()}}
    )

    db['feed'].insert_one({
        "actionType": "EMPLOYEE_EMAIL_UPDATE",
        "employee_id": emp_id,
        "email": email,
        "updated_by": request.current_user.get("username", "admin"),
        "timestamp": time.time()
    })

    return jsonify({"success": True, "message": f"Email for employee {emp.get('name', emp_id)} ({emp_id}) updated successfully.", "email": email})

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

# ── Customer Portal API ───────────────────────────────────────────────────────

@app.route("/api/customer/profile", methods=["GET"])
def get_customer_profile():
    """Return dynamic customer profile, live assigned trolley, cart contents, and recent receipts."""
    cust_id = request.args.get("customer_id") or request.args.get("id")
    phone = request.args.get("phone")

    # If auth header provided, attempt JWT decode
    auth_header = request.headers.get("Authorization", "")
    if not cust_id and not phone and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_phone = payload.get("phone")
            user_email = payload.get("email")
            user_role = payload.get("role")
            if user_role == "guest":
                cust_id = "guest"
            elif user_phone:
                phone = user_phone
            elif user_email:
                cust_match = customers_collection.find_one({"email": user_email})
                if cust_match:
                    cust_id = cust_match.get("id")
        except Exception:
            pass

    # GUEST PROFILE HANDLING
    if (cust_id and cust_id.strip().lower() == "guest") or request.args.get("is_guest") == "true":
        req_trolley = request.args.get("trolley_id")
        trolley_doc = None
        if req_trolley:
            trolley_doc = trolleys_collection.find_one({"_id": req_trolley.strip().upper()})
        if not trolley_doc:
            trolley_doc = trolleys_collection.find_one({"assigned_customer_id": "guest"})

        assigned_trolley_id = trolley_doc["_id"] if trolley_doc else None
        active_trolley_data = None

        if assigned_trolley_id:
            cart_doc = carts_collection.find_one({"_id": _trolley_cart_id(assigned_trolley_id)})
            now_ts = time.time()
            last_hb = trolley_doc.get("last_seen", trolley_doc.get("last_heartbeat", 0)) if trolley_doc else 0
            hb_details = format_heartbeat_status(last_hb, now_ts)
            is_connected = False
            if trolley_doc:
                is_connected = (trolley_doc.get("status") == "online") and (now_ts - float(last_hb or 0) <= OFFLINE_THRESHOLD_SECS)

            items_list = []
            cart_total = 0.0
            item_count = 0
            if cart_doc:
                cart_total = float(cart_doc.get("total", 0.0))
                raw_items = cart_doc.get("items", {})
                if isinstance(raw_items, dict):
                    for rfid, it in raw_items.items():
                        qty = it.get("qty", 1)
                        item_count += qty
                        items_list.append({
                            "rfid": rfid,
                            "name": it.get("name", "Unknown Item"),
                            "price": float(it.get("price", 0.0)),
                            "qty": qty,
                            "total": float(it.get("price", 0.0)) * qty,
                            "shelf": it.get("shelf", "Aisle A"),
                            "offer": it.get("offer", "Standard Price")
                        })

            active_trolley_data = {
                "trolley_id": assigned_trolley_id,
                "is_connected": is_connected,
                "current_mode": trolley_doc.get("current_mode", "ADD"),
                "total": cart_total,
                "items_count": item_count,
                "items": items_list,
                "heartbeat": hb_details
            }

        return jsonify({
            "customer": {
                "id": "GUEST",
                "customer_id": "GUEST",
                "name": "Guest Shopper",
                "phone": "",
                "email": "",
                "tier": "Guest Access",
                "points": 0,
                "total_spent": 0.0,
                "total_visits": 1,
                "assigned_trolley": assigned_trolley_id,
                "status": "Guest",
                "wishlist": [],
                "is_guest": True
            },
            "active_trolley": active_trolley_data,
            "recent_transactions": []
        })

    customer = None
    if cust_id:
        customer = customers_collection.find_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]})
    elif phone:
        customer = customers_collection.find_one({"phone": phone})

    if not customer:
        customer = customers_collection.find_one({})
        if not customer:
            init_customers()
            customer = customers_collection.find_one({})

    actual_cust_id = customer.get("id") or customer.get("customer_id", "CUST-1001")
    actual_phone = customer.get("phone", "")
    actual_name = customer.get("name", "Valued Customer")
    actual_email = customer.get("email", "")

    # Calculate real Tier and Points
    total_spent = float(customer.get("total_spent", 0.0))
    total_visits = int(customer.get("total_visits", 0))

    if total_spent >= 5000:
        tier = "Platinum VIP"
    elif total_spent >= 1500:
        tier = "Gold Member"
    elif total_spent >= 500:
        tier = "Silver Member"
    else:
        tier = "Bronze Member"

    points = int(total_spent // 10) + (total_visits * 15)

    # Wishlist from customer doc or defaults
    wishlist = customer.get("wishlist")
    if wishlist is None:
        wishlist = [
            {"name": "Rice 1kg", "price": 60.0, "category": "Grains", "shelf": "Aisle A - Shelf 1", "offer": "Buy 1 Get 1 Free"},
            {"name": "Sugar 1kg", "price": 45.0, "category": "Grains", "shelf": "Aisle A - Shelf 2", "offer": "Standard Price"}
        ]
        customers_collection.update_one(
            {"$or": [{"id": actual_cust_id}, {"customer_id": actual_cust_id}]},
            {"$set": {"wishlist": wishlist}}
        )

    # Active Trolley details if customer currently has an assigned trolley
    assigned_trolley_id = customer.get("assigned_trolley")
    active_trolley_data = None

    if assigned_trolley_id:
        trolley_doc = trolleys_collection.find_one({"_id": assigned_trolley_id})
        cart_doc = carts_collection.find_one({"_id": _trolley_cart_id(assigned_trolley_id)})
        
        now_ts = time.time()
        last_hb = trolley_doc.get("last_seen", trolley_doc.get("last_heartbeat", 0)) if trolley_doc else 0
        hb_details = format_heartbeat_status(last_hb, now_ts)
        is_connected = False
        if trolley_doc:
            is_connected = (trolley_doc.get("status") == "online") and (now_ts - float(last_hb or 0) <= OFFLINE_THRESHOLD_SECS)

        cart_items_list = []
        cart_total = 0.0
        item_count = 0
        cart_status = "ACTIVE"
        if cart_doc:
            cart_total = float(cart_doc.get("total", 0.0))
            cart_status = cart_doc.get("status", "ACTIVE")
            items_dict = cart_doc.get("items", {})
            for uid, item in items_dict.items():
                qty = item.get("quantity", item.get("qty", 1))
                price = float(item.get("price", 0.0))
                cart_items_list.append({
                    "uid": uid,
                    "name": item.get("name", "Unknown Item"),
                    "price": price,
                    "quantity": qty,
                    "subtotal": round(price * qty, 2),
                    "offer": item.get("offer", "Standard Price")
                })
                item_count += qty

        active_trolley_data = {
            "trolley_id": assigned_trolley_id,
            "trolley_name": trolley_doc.get("name", assigned_trolley_id) if trolley_doc else assigned_trolley_id,
            "is_connected": is_connected,
            "status_label": "🟢 Connected (Hardware Online)" if is_connected else "🟡 Disconnected (Cart Preserved in DB)",
            "last_seen_str": hb_details.get("last_seen_str", "N/A"),
            "last_heartbeat_time_str": hb_details.get("last_heartbeat_time_str", "N/A"),
            "battery_level": trolley_doc.get("battery_level", 85) if trolley_doc else 85,
            "current_mode": trolley_doc.get("current_mode", "ADD") if trolley_doc else "ADD",
            "cart_status": cart_status,
            "items": cart_items_list,
            "items_count": item_count,
            "subtotal": cart_total,
            "gst": round(cart_total * 0.18, 2),
            "grand_total": round(cart_total * 1.18, 2)
        }

    # Fetch customer's real transaction history
    tx_query = {"$or": [{"customer_id": actual_cust_id}, {"customerPhone": actual_phone}]}
    tx_list = list(transactions_collection.find(tx_query, {"_id": 0}).sort("timestamp", -1).limit(20))
    # Fallback to all transactions if none matched (e.g. initial demo)
    if not tx_list:
        tx_list = list(transactions_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(10))

    return jsonify({
        "success": True,
        "customer": {
            "id": actual_cust_id,
            "customer_id": actual_cust_id,
            "memberId": actual_cust_id,
            "name": actual_name,
            "email": actual_email,
            "phone": actual_phone,
            "tier": tier,
            "points": points,
            "total_spent": total_spent,
            "total_visits": total_visits,
            "assigned_trolley": assigned_trolley_id,
            "status": customer.get("status", "Active"),
            "wishlist": wishlist,
            "savedAddresses": [
                "123, 4th Cross, Green Glen Layout, Bangalore - 560103",
                "Office: Tech Park Phase 2, Outer Ring Road, Bangalore"
            ]
        },
        "active_trolley": active_trolley_data,
        "recent_transactions": tx_list
    })

@app.route("/api/customer/wishlist", methods=["POST", "DELETE"])
def update_customer_wishlist():
    cust_id = request.args.get("customer_id") or request.args.get("id")
    if not cust_id:
        cust = customers_collection.find_one({})
        cust_id = cust["id"] if cust else "CUST-1001"

    customer = customers_collection.find_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]})
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404

    wishlist = list(customer.get("wishlist", []))

    if request.method == "POST":
        data = request.json or {}
        item_name = data.get("name", "").strip()
        price = float(data.get("price", 0.0))
        category = data.get("category", "General")
        shelf = data.get("shelf", "General Aisle")
        offer = data.get("offer", "Standard Price")

        if not item_name:
            return jsonify({"success": False, "message": "Item name is required"}), 400

        if any(w.get("name", "").lower() == item_name.lower() for w in wishlist):
            return jsonify({"success": True, "message": "Item already in wishlist", "wishlist": wishlist})

        wishlist.append({
            "name": item_name,
            "price": price,
            "category": category,
            "shelf": shelf,
            "offer": offer
        })
        customers_collection.update_one({"_id": customer["_id"]}, {"$set": {"wishlist": wishlist}})
        return jsonify({"success": True, "message": f"Added '{item_name}' to wishlist", "wishlist": wishlist})

    elif request.method == "DELETE":
        data = request.json or {}
        item_name = (data.get("name") or request.args.get("name") or "").strip().lower()
        if not item_name:
            return jsonify({"success": False, "message": "Item name is required to remove"}), 400

        wishlist = [w for w in wishlist if w.get("name", "").lower() != item_name]
        customers_collection.update_one({"_id": customer["_id"]}, {"$set": {"wishlist": wishlist}})
        return jsonify({"success": True, "message": "Removed from wishlist", "wishlist": wishlist})

# ── Arduino Serial Loop (backward-compatible, targets TROLLEY-001) ────────────

def serial_loop():
    global global_ser, current_mode, SERIAL_PORT
    cfg = load_config()
    BAUD_RATE = int(cfg.get("baudRate", 115200))
    last_heartbeat_time = 0
    last_warn_time = 0
    SERIAL_TROLLEY_ID = "TROLLEY-001"  # Arduino always maps to Trolley-001

    while True:
        if global_ser is None or not global_ser.is_open:
            try:
                cfg = load_config()
                BAUD_RATE = int(cfg.get("baudRate", 115200))
                global_ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print(f"Connected to hardware on {SERIAL_PORT}")
                last_warn_time = 0
                try:
                    s_tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s_tmp.connect(('8.8.8.8', 80))
                    host_local_ip = s_tmp.getsockname()[0]
                    s_tmp.close()
                    time.sleep(1.0)
                    cfg = load_config()
                    sync_ssid = cfg.get("wifiSSID", "Yogaraj")
                    sync_pass = cfg.get("wifiPassword", "1234567890")
                    sync_port = cfg.get("serverPort", 5000)
                    send_command_to_arduino(f"WIFI_CFG:{sync_ssid}|{sync_pass}|{host_local_ip}|{sync_port}")
                    print(f"[AUTO-SYNC] Automatically pushed active Wi-Fi ({sync_ssid}) and Host IP ({host_local_ip}:{sync_port}) to ESP32 via Serial!")
                except Exception as ex_ip:
                    print(f"[AUTO-SYNC WARN] {ex_ip}")
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

                if line in ["CONFIRMED_HARDWARE_RESET"] or "[INTENTIONAL_RESET]" in line:
                    print("[RESET] Verified intentional hardware reset button triggered (held for >2.5s)")
                    perform_reset(SERIAL_TROLLEY_ID)
                    send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")
                    send_command_to_arduino("BEEP:2")
                elif line in ["HARDWARE_BTN_RESET", "CMD:RESET"]:
                    print(f"[RESET IGNORED] Transient reset pulse '{line}' received on startup/disconnect. Ignored to preserve cart.")

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
