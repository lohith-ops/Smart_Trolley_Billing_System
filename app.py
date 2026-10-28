import threading
import time
import datetime
import serial
import socket
import os
import json
import re
import subprocess
import html
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
import hmac
import hashlib
try:
    import razorpay
except Exception as _rp_err:
    razorpay = None
    print(f"[RAZORPAY] Module load info: {_rp_err}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load local environment variables from .env if present
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as _ef:
            for _line in _ef:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception as _e:
        print(f"[ENV] Notice: {_e}")

STATIC_FOLDER = os.path.join(BASE_DIR, "web-dashboard")
app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path="")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for static files
CORS(app)

# ── Authentication & Security Configuration ───────────────────────────────────
JWT_SECRET           = os.environ.get("JWT_SECRET", "smart_trolley_secret_key_2026_jwt_token_secure")
JWT_ALGORITHM        = "HS256"
JWT_EXPIRATION_HOURS = 24
TROLLEY_DEVICE_TOKEN = os.environ.get("TROLLEY_DEVICE_TOKEN", "smart_trolley_hw_token_sec_99")
IS_CLOUD_ENV         = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
CLOUD_RELAY_URL      = os.environ.get("CLOUD_RELAY_URL", "https://smart-trolley-billing-system.onrender.com").rstrip("/")


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.errorhandler(400)
def handle_bad_request(e):
    msg = getattr(e, 'description', 'Bad Request')
    return jsonify({"success": False, "message": str(msg)}), 400

@app.errorhandler(500)
def handle_server_error(e):
    msg = getattr(e, 'description', 'Internal Server Error')
    return jsonify({"success": False, "message": str(msg)}), 500


# ── Configuration File Persistence ───────────────────────────────────────────
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    defaults = {
        "enableSerial": True,
        "serialPort": "COM3",
        "baudRate": 115200,
        "upiId": "smartsupermarket@okaxis",
        "storeName": "GECM Supermarket",
        "useCustomQr": False,
        "customQrImage": "",
        "razorpayEnabled": True,
        "razorpayKeyId": os.environ.get("RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"),
        "razorpayKeySecret": os.environ.get("RAZORPAY_KEY_SECRET", ""),
        "smtpServer": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "smtpPort": int(os.environ.get("SMTP_PORT", 587)),
        "smtpUser": os.environ.get("SMTP_EMAIL", os.environ.get("SMTP_USER", "")),
        "smtpPassword": os.environ.get("SMTP_PASSWORD", os.environ.get("SMTP_PASS", "")),
        "fast2smsApiKey": os.environ.get("FAST2SMS_API_KEY", ""),
        "twilioSid": os.environ.get("TWILIO_SID", ""),
        "twilioAuthToken": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "twilioFromPhone": os.environ.get("TWILIO_FROM_PHONE", ""),
        "resendApiKey": os.environ.get("RESEND_API_KEY", ""),
        "brevoApiKey": os.environ.get("BREVO_API_KEY", ""),
        "sendgridApiKey": os.environ.get("SENDGRID_API_KEY", "")
    }
    cfg = dict(defaults)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[CONFIG] Error reading config file: {e}")

    # Check MongoDB settings collection if initialized
    try:
        s_coll = None
        if 'settings_collection' in globals() and settings_collection is not None:
            s_coll = settings_collection
        elif 'db' in globals() and db is not None:
            s_coll = db['settings']

        if s_coll is not None:
            db_cfg = s_coll.find_one({"_id": "app_config"})
            if db_cfg:
                for k, v in db_cfg.items():
                    if k != "_id" and v is not None and v != "":
                        cfg[k] = v
    except Exception:
        pass

    # Ensure environment variables take precedence if explicitly provided
    if os.environ.get("SMTP_EMAIL"):
        cfg["smtpUser"] = os.environ.get("SMTP_EMAIL").strip()
    if os.environ.get("SMTP_PASSWORD"):
        cfg["smtpPassword"] = os.environ.get("SMTP_PASSWORD").strip()
    if os.environ.get("SMTP_SERVER"):
        cfg["smtpServer"] = os.environ.get("SMTP_SERVER").strip()
    if os.environ.get("SMTP_PORT"):
        try:
            cfg["smtpPort"] = int(os.environ.get("SMTP_PORT"))
        except:
            pass
    if os.environ.get("RESEND_API_KEY"):
        cfg["resendApiKey"] = os.environ.get("RESEND_API_KEY").strip()
    if os.environ.get("BREVO_API_KEY"):
        cfg["brevoApiKey"] = os.environ.get("BREVO_API_KEY").strip()
    if os.environ.get("SENDGRID_API_KEY"):
        cfg["sendgridApiKey"] = os.environ.get("SENDGRID_API_KEY").strip()

    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"[CONFIG] Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"[CONFIG] Error saving config file: {e}")

    try:
        s_coll = None
        if 'settings_collection' in globals() and settings_collection is not None:
            s_coll = settings_collection
        elif 'db' in globals() and db is not None:
            s_coll = db['settings']

        if s_coll is not None:
            cfg_doc = dict(cfg)
            cfg_doc["_id"] = "app_config"
            s_coll.update_one({"_id": "app_config"}, {"$set": cfg_doc}, upsert=True)
            print("[CONFIG] Configuration persisted to MongoDB settings collection.")
    except Exception as e:
        print(f"[CONFIG WARN] Could not persist settings to MongoDB: {e}")

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
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
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
    razorpay_orders_collection = db['razorpay_orders']
    settings_collection     = db['settings']
    mongo_ok = True
    print(f"[DB] Connected to MongoDB ({'Cloud Atlas' if 'mongodb+srv' in MONGO_URI else 'Local'}) successfully.")
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
    razorpay_orders_collection = db['razorpay_orders']
    settings_collection     = db['settings']

# ── Catalog Data Model & Category Intelligence ────────────────────────────────
def normalize_uid(uid_str):
    """Normalize UID to uppercase no-space format. '5C 1E 7E 05' -> '5C1E7E05'."""
    if not uid_str:
        return ""
    return str(uid_str).replace(" ", "").replace("-", "").upper()

DEFAULT_PRODUCTS = [
    {"uid": "5C 1E 7E 05", "name": "Rice 1kg",          "price": 60.0,  "category": "Grains", "stock": 45, "shelf": "Aisle A - Shelf 1", "offer": "Buy 1 Get 1 Free"},
    {"uid": "76 E3 33 06", "name": "Sugar 1kg",          "price": 45.0,  "category": "Grains", "stock": 30, "shelf": "Aisle A - Shelf 2", "offer": "Standard Price"},
    {"uid": "A3 B4 C5 D6", "name": "Whole Wheat Bread",  "price": 25.0,  "category": "Bakery", "stock": 20, "shelf": "Aisle B - Shelf 1", "offer": "10% Off"},
    {"uid": "11 22 33 44", "name": "Milk (1 Gallon)",    "price": 50.0,  "category": "Dairy",  "stock": 32, "shelf": "Aisle C - Shelf 1", "offer": "No Active Offers"},
    {"uid": "99 88 77 66", "name": "Cheddar Cheese",     "price": 80.0,  "category": "Dairy",  "stock": 15, "shelf": "Aisle C - Shelf 1", "offer": "20% Off"},
    {"uid": "FF EE DD CC", "name": "Free Range Eggs",    "price": 40.0,  "category": "Dairy",  "stock": 24, "shelf": "Aisle C - Shelf 1", "offer": "No Active Offers"},
]

def detect_category(name: str) -> str:
    """Intelligently detects product category based on product title."""
    if not name:
        return "Grocery"
    nl = name.lower()
    if any(k in nl for k in ["rice", "basmati", "wheat", "grain", "oat", "flour", "atta", "dal", "pulse", "quinoa", "cereal", "pasta", "sugar"]):
        return "Grains"
    if any(k in nl for k in ["milk", "cheese", "cheddar", "butter", "curd", "yogurt", "ghee", "paneer", "cream", "dairy", "egg"]):
        return "Dairy"
    if any(k in nl for k in ["bread", "toast", "bun", "cake", "muffin", "bakery", "croissant", "pastry", "bagel", "cookie"]):
        return "Bakery"
    if any(k in nl for k in ["apple", "banana", "orange", "fruit", "vegetable", "tomato", "potato", "onion", "produce", "berry"]):
        return "Produce"
    if any(k in nl for k in ["juice", "soda", "water", "tea", "coffee", "drink", "cola", "pepsi", "sprite", "beverage"]):
        return "Beverages"
    if any(k in nl for k in ["chip", "chips", "snack", "chocolate", "candy", "cracker", "biscuit", "namkeen"]):
        return "Snacks"
    return "Grocery"

def ensure_catalog_integrity():
    """
    Ensures all catalog products have valid categories, shelf locations,
    stock numbers, and resolves any misclassifications (e.g. Rice incorrectly categorized as Dairy).
    """
    try:
        # 1. Ensure known default products exist with complete attributes
        for p in DEFAULT_PRODUCTS:
            uid_norm = normalize_uid(p["uid"])
            existing = products_collection.find_one({"uid_norm": uid_norm})
            if not existing:
                doc = dict(p)
                doc["uid_norm"] = uid_norm
                products_collection.insert_one(doc)
                print(f"[CATALOG] Seeded standard product: {p['name']} ({p['category']})")
            else:
                updates = {}
                name_cur = existing.get("name", p["name"])
                cat_cur = (existing.get("category") or "").strip()
                
                # Auto-fix Rice miscategorized as Dairy
                if "rice" in name_cur.lower() and (cat_cur.lower() == "dairy" or not cat_cur):
                    updates["category"] = "Grains"
                    print(f"[CATALOG INTEGRITY] Fixed miscategorization for {name_cur}: Dairy -> Grains")
                elif not cat_cur:
                    updates["category"] = p.get("category", detect_category(name_cur))
                
                if not existing.get("shelf"):
                    updates["shelf"] = p.get("shelf", "Aisle A - Shelf 1")
                if existing.get("stock") is None:
                    updates["stock"] = p.get("stock", 20)
                if not existing.get("offer"):
                    updates["offer"] = p.get("offer", "No Active Offers")
                if not existing.get("uid"):
                    updates["uid"] = p["uid"]
                if not existing.get("name"):
                    updates["name"] = p["name"]
                if existing.get("price") is None:
                    updates["price"] = p["price"]

                if updates:
                    products_collection.update_one({"uid_norm": uid_norm}, {"$set": updates})

        # 2. General integrity sweep across all remaining products in DB
        for doc in products_collection.find({}):
            name = (doc.get("name") or "").strip()
            cat = (doc.get("category") or "").strip()
            updates = {}
            if "rice" in name.lower() and cat.lower() == "dairy":
                updates["category"] = "Grains"
                print(f"[CATALOG INTEGRITY] Fixed miscategorization for {name}: Dairy -> Grains")
            elif not cat:
                updates["category"] = detect_category(name)
            
            if not doc.get("shelf"):
                c = updates.get("category", cat)
                if c == "Grains": updates["shelf"] = "Aisle A - Shelf 1"
                elif c == "Bakery": updates["shelf"] = "Aisle B - Shelf 1"
                elif c == "Dairy": updates["shelf"] = "Aisle C - Shelf 1"
                elif c == "Produce": updates["shelf"] = "Aisle D - Shelf 1"
                elif c == "Beverages": updates["shelf"] = "Aisle E - Shelf 1"
                else: updates["shelf"] = "Aisle A - Shelf 1"

            if doc.get("stock") is None:
                updates["stock"] = 20
            if not doc.get("offer"):
                updates["offer"] = "No Active Offers"
            
            if updates:
                uid_n = doc.get("uid_norm") or normalize_uid(doc.get("uid", ""))
                if uid_n:
                    products_collection.update_one({"uid_norm": uid_n}, {"$set": updates})
        print("[CATALOG INTEGRITY] Inventory catalog verified and synchronized.")
    except Exception as e:
        print(f"[CATALOG WARN] Error verifying catalog integrity: {e}")

# Run initial integrity check on startup
ensure_catalog_integrity()

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
        "sub":      user["username"],
        "username": user["username"],
        "role":     user.get("role", "cashier"),
        "name":     user.get("name", user["username"]),
        "email":    user.get("email", ""),
        "phone":    user.get("phone", ""),
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
current_mode        = "ADD"
global_ser          = None
last_serial_rx_time = 0.0

def is_serial_hardware_alive():
    """True ONLY if serial port is open AND actual telemetry was received within last 12 seconds."""
    global global_ser, last_serial_rx_time
    if global_ser is None:
        return False
    try:
        if not global_ser.is_open:
            return False
    except Exception:
        return False
    return (time.time() - last_serial_rx_time) <= 12.0

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
    normalized = os.path.normpath(path)
    if normalized.startswith("..") or any(part.startswith(".") for part in normalized.split(os.sep)):
        return jsonify({"error": "Access denied"}), 403
    lower_path = normalized.lower()
    if lower_path.endswith((".json", ".py", ".env", ".db", ".sqlite", ".bak", ".log", ".md")):
        return jsonify({"error": "Access denied to protected file"}), 403
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

OFFLINE_THRESHOLD_SECS = 25  # Trolley marked offline after 25s with no heartbeat (ESP32 sends every 15s)
SERIAL_TROLLEY_ID = "TROLLEY-001"  # Default serial hardware identifier

def is_trolley_connected(trolley_id: str) -> bool:
    """
    Check if a trolley is genuinely connected and communicating with the server.
    - If SERIAL_TROLLEY_ID: active serial telemetry received within 12s, OR Wi-Fi heartbeat within 25s.
    - If Wi-Fi: requires status 'online' and heartbeat within OFFLINE_THRESHOLD_SECS.
    """
    if trolley_id == SERIAL_TROLLEY_ID and is_serial_hardware_alive():
        return True

    t_doc = trolleys_collection.find_one({"_id": trolley_id})
    if not t_doc:
        return False

    now_ts = time.time()
    last_seen = float(t_doc.get("last_seen", 0) or 0)
    last_hb = float(t_doc.get("last_heartbeat", 0) or 0)
    most_recent = max(last_seen, last_hb)

    # For Wi-Fi connected trolley
    return (t_doc.get("status") == "online") and (most_recent > 0) and ((now_ts - most_recent) <= OFFLINE_THRESHOLD_SECS)

def forward_cart_action_to_cloud(trolley_id, uid, action):
    """If running locally, mirror RFID scans to deployed cloud link so cloud dashboard updates in real time."""
    if IS_CLOUD_ENV or not CLOUD_RELAY_URL:
        return
    def _do_fwd():
        try:
            payload = json.dumps({"trolley_id": trolley_id, "uid": uid, "action": action}).encode('utf-8')
            req = urllib.request.Request(
                f"{CLOUD_RELAY_URL}/api/cart/action",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SmartTrolleyLocalRelay/2.0"}
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    pass
            except urllib.error.HTTPError:
                # HTTP 404 for unknown cards is expected and correctly logged into feed on cloud
                pass
        except Exception:
            pass
    threading.Thread(target=_do_fwd, daemon=True).start()

def forward_cart_reset_to_cloud(trolley_id):
    """If running locally, mirror cart reset to deployed cloud link."""
    if IS_CLOUD_ENV or not CLOUD_RELAY_URL:
        return
    def _do_reset():
        try:
            payload = json.dumps({"trolley_id": trolley_id, "force": True}).encode('utf-8')
            req = urllib.request.Request(
                f"{CLOUD_RELAY_URL}/api/reset",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SmartTrolleyLocalRelay/2.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except Exception:
            pass
    threading.Thread(target=_do_reset, daemon=True).start()

def forward_trolley_offline_to_cloud(trolley_id):
    """Notify deployed cloud link immediately when a trolley goes offline."""
    if IS_CLOUD_ENV or not CLOUD_RELAY_URL:
        return
    def _do_offline():
        try:
            payload = json.dumps({"trolley_id": trolley_id}).encode('utf-8')
            req = urllib.request.Request(
                f"{CLOUD_RELAY_URL}/api/trolley/offline",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SmartTrolleyLocalRelay/2.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                pass
        except Exception:
            pass
    threading.Thread(target=_do_offline, daemon=True).start()

def cloud_relay_loop():
    """
    Periodically relays heartbeats for all locally connected/online trolleys
    to the deployed cloud Render server. If disconnected locally, relays STOP immediately!
    """
    if IS_CLOUD_ENV or not CLOUD_RELAY_URL:
        return
    print(f"[CLOUD-RELAY] Background sync active -> Mirroring local trolley status to {CLOUD_RELAY_URL}")
    while True:
        try:
            time.sleep(6)
            all_trolleys = list(trolleys_collection.find({}))
            for t in all_trolleys:
                tid = t.get("_id")
                if not tid:
                    continue
                # ONLY relay if the trolley is genuinely connected right now!
                if is_trolley_connected(tid):
                    try:
                        payload = json.dumps({
                            "trolley_id": tid,
                            "battery": t.get("battery", 95),
                            "wifi_rssi": t.get("wifi_rssi", -55),
                            "rfid_ready": t.get("rfid_ready", True),
                            "lcd_ready": t.get("lcd_ready", True),
                            "hardware_health": t.get("hardware_health", "HEALTHY"),
                            "firmware_version": t.get("firmware_version", "2.0")
                        }).encode('utf-8')
                        req = urllib.request.Request(
                            f"{CLOUD_RELAY_URL}/api/trolley/heartbeat",
                            data=payload,
                            headers={"Content-Type": "application/json", "User-Agent": "SmartTrolleyLocalRelay/2.0"}
                        )
                        with urllib.request.urlopen(req, timeout=4) as resp:
                            pass
                    except Exception:
                        pass
        except Exception:
            time.sleep(5)


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
        unknown_scan_obj = {
            "uid":         uid_key,
            "trolley_id":  trolley_id,
            "timestamp":   time.time()
        }
        carts_collection.update_one(
            {"_id": cart_id},
            {"$set": {"last_unknown_scan": unknown_scan_obj}}
        )
        db['feed'].insert_one({
            "actionType":  "UNKNOWN_SCAN",
            "uid":         uid_key,
            "trolley_id":  trolley_id,
            "timestamp":   time.time()
        })
        return None, cart.get("total", 0.0), uid_key

    # Clear any previous unknown scan alert once a recognized product is processed
    carts_collection.update_one(
        {"_id": cart_id},
        {"$unset": {"last_unknown_scan": ""}}
    )

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

    # Sync cart_value and item_count to trolleys collection
    trolleys_collection.update_one({"_id": trolley_id}, {
        "$set": {
            "cart_value":     total,
            "item_count":     items_contained
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


def generate_invoice_id():
    """Generates a proper, sequential, professional invoice serial number e.g. INV-20261027-0001."""
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    try:
        count = transactions_collection.count_documents({}) + 1
    except Exception:
        count = random.randint(100, 9999)
    return f"INV-{date_str}-{count:04d}"


def perform_checkout(trolley_id="TROLLEY-001"):
    """Checkout a specific trolley's cart and save a transaction."""
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if cart and cart.get("itemsContained", 0) > 0:
        saved_items = dict(cart["items"])
        trolley = trolleys_collection.find_one({"_id": trolley_id}) or {}
        cust_name = trolley.get("assigned_customer_name", "")
        cust_phone = trolley.get("assigned_customer_phone", "")
        cust_id = trolley.get("assigned_customer_id")
        invoice_id = generate_invoice_id()
        transactions_collection.insert_one({
            "invoiceId":        invoice_id,
            "trolley_id":       trolley_id,
            "items":            cart["items"],
            "total":            cart["total"],
            "finalTotal":       cart["total"],
            "paymentMethod":    "Unknown",
            "customer_name":    cust_name,
            "customerPhone":    cust_phone,
            "customer_id":      cust_id,
            "timestamp":        time.time(),
            "date":             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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



def perform_reset(trolley_id="TROLLEY-001", force=False):
    """Reset a trolley's cart without saving as transaction. Restores global stock.
    Requires trolley to be connected unless force=True."""
    if not force and not is_trolley_connected(trolley_id):
        print(f"[RESET PREVENTED] Cart reset blocked: {trolley_id} is not connected. Cart items preserved.")
        return False

    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    had_items = False
    prior_total = 0.0

    if cart and "items" in cart:
        for item_key, item_val in cart.get("items", {}).items():
            qty = item_val.get("quantity", item_val.get("qty", 0))
            if qty > 0:
                had_items = True
                p = products_collection.find_one({"uid": item_key})
                if not p:
                    p = products_collection.find_one({"uid_norm": item_key})
                if p:
                    products_collection.update_one(
                        {"_id": p["_id"]},
                        {"$set": {"stock": p.get("stock", 0) + qty}}
                    )

    if cart:
        prior_total = float(cart.get("total", 0.0))
        if cart.get("itemsContained", 0) > 0 or prior_total > 0:
            had_items = True

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

    # Only publish feed event and beep if the cart actually contained items,
    # preventing false "Cart Reset" notifications when trolley is disconnected or empty.
    if had_items:
        db['feed'].insert_one({
            "actionType": "RESET",
            "total":      prior_total,
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
    raw_user = data.get("username")
    password = data.get("password")

    if not isinstance(raw_user, str) or not isinstance(password, str):
        return jsonify({"success": False, "message": "Username and password must be valid text strings."}), 400

    raw_user = raw_user.strip()
    username = raw_user.lower()
    password = password.strip()

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

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@gmail\.com$', re.IGNORECASE)
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
PHONE_REGEX = re.compile(r'^(\+91[\-\s]?)?[0-9]{10}$')

@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    """Public customer self-registration endpoint (role is locked to customer)."""
    data = request.json or {}
    for field in ["username", "password", "name", "email", "phone"]:
        val = data.get(field)
        if val is not None and not isinstance(val, str):
            return jsonify({"success": False, "message": f"Field '{field}' must be a valid text string."}), 400

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
        return jsonify({"success": False, "message": "Please enter a valid email address in the form of example@gmail.com."}), 400

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

    # Sync with customers_collection so customer appears in all customer management views
    phone_digits = re.sub(r'\D', '', phone) if phone else ""
    if len(phone_digits) > 10 and phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]
    customers_collection.update_one(
        {"$or": [{"id": username}, {"customer_id": username}, {"username": username}]},
        {"$set": {
            "id":               username,
            "customer_id":      username,
            "username":         username,
            "name":             name,
            "phone":            phone_digits or phone,
            "email":            email,
            "assigned_trolley": None,
            "total_spent":      0.0,
            "total_visits":     0,
            "status":           "Active",
            "created_at":       time.time()
        }},
        upsert=True
    )

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
        return jsonify({"success": False, "message": "Please enter a valid email address in the form of example@gmail.com."}), 400

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
        return jsonify({"success": False, "message": "Please enter a valid email address in the form of example@gmail.com."}), 400

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
    """Finds a user by username, email, or phone number in users_collection or customers_collection."""
    if not identifier:
        return None
    ident = identifier.strip().lower()
    clean_phone = identifier.strip().replace(" ", "").replace("-", "").replace("+91", "")
    
    # 1. Try exact username match
    user = users_collection.find_one({"username": ident})
    if user:
        return user
    
    # 2. Try email match
    user = users_collection.find_one({"email": ident})
    if user:
        return user

    # 3. Try phone match
    user = users_collection.find_one({"phone": identifier.strip()})
    if user:
        return user
        
    # 4. Search all users for case-insensitive / normalized matches
    all_users = list(users_collection.find({}))
    for u in all_users:
        u_username = (u.get("username") or "").lower()
        u_email    = (u.get("email") or "").lower()
        u_phone    = (u.get("phone") or "").replace(" ", "").replace("-", "").replace("+91", "")
        if u_username == ident or (u_email and u_email == ident) or (clean_phone and u_phone == clean_phone):
            return u

    # 5. Search in customers_collection to support shoppers registered via Customer Hub
    cust = customers_collection.find_one({
        "$or": [
            {"id": identifier.strip()},
            {"customer_id": identifier.strip()},
            {"email": ident},
            {"phone": clean_phone or identifier.strip()}
        ]
    })
    if cust:
        c_username = (cust.get("id") or cust.get("customer_id") or f"cust_{clean_phone}").lower()
        linked_user = users_collection.find_one({"$or": [{"username": c_username}, {"email": cust.get("email")}, {"phone": cust.get("phone")}]})
        if linked_user:
            return linked_user
        else:
            # Create synced user record for this customer
            new_cust_user = {
                "username":      c_username,
                "password_hash": generate_password_hash("customer123"),
                "name":          cust.get("name", "Customer"),
                "role":          "customer",
                "email":         cust.get("email", ""),
                "phone":         cust.get("phone", ""),
                "created_at":    time.time(),
                "status":        "Active"
            }
            users_collection.insert_one(new_cust_user)
            return new_cust_user

    return None

def send_otp_email_via_http(to_email, otp_code, recipient_name="Customer", cfg=None):
    """Sends OTP email via modern HTTPS Email APIs (Brevo, Resend, SendGrid) over Port 443 (never blocked by cloud firewalls)."""
    if cfg is None:
        cfg = load_config()
    store_name = cfg.get("storeName", "Smart Supermarket")
    brevo_key = (cfg.get("brevoApiKey") or os.environ.get("BREVO_API_KEY", "")).strip().replace('"', '').replace("'", "").replace(" ", "")
    resend_key = (cfg.get("resendApiKey") or os.environ.get("RESEND_API_KEY", "")).strip().replace('"', '').replace("'", "").replace(" ", "")
    sendgrid_key = (cfg.get("sendgridApiKey") or os.environ.get("SENDGRID_API_KEY", "")).strip().replace('"', '').replace("'", "").replace(" ", "")

    subject = f"Verification Code: {otp_code} - {store_name}"
    html_body = f"""<div style="font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:24px;border-radius:12px;max-width:500px;margin:auto;">
        <h2 style="color:#06b6d4;margin:0 0 12px 0;">🛒 {store_name}</h2>
        <p>Hello {recipient_name}, we received a request to reset your password.</p>
        <div style="background:rgba(6,182,212,0.1);border:2px dashed #06b6d4;border-radius:8px;padding:16px;text-align:center;margin:20px 0;">
            <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;">Your Verification Code (OTP)</div>
            <div style="font-size:36px;font-weight:bold;letter-spacing:6px;color:#38bdf8;margin:8px 0;">{otp_code}</div>
            <div style="font-size:12px;color:#fbbf24;">Valid for 10 minutes</div>
        </div>
        <p style="font-size:12px;color:#94a3b8;">If you did not request this, you can safely ignore this email.</p>
    </div>"""

    # 1. Try Brevo (Sendinblue) HTTP API (Port 443)
    if brevo_key:
        try:
            sender_email = (cfg.get("smtpUser") or os.environ.get("SMTP_EMAIL", "billing@smartsupermarket.com")).strip()
            payload = json.dumps({
                "sender": {"name": store_name, "email": sender_email},
                "to": [{"email": to_email, "name": recipient_name}],
                "subject": subject,
                "htmlContent": html_body
            }).encode("utf-8")
            req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=payload, headers={
                "api-key": brevo_key,
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status in (200, 201, 202):
                    print(f"[EMAIL HTTP DISPATCH] Successfully sent OTP to {to_email} via Brevo API")
                    return True, "Email sent successfully via Brevo API."
        except Exception as e:
            print(f"[EMAIL HTTP WARN] Brevo API failed: {e}")

    # 2. Try Resend HTTP API (Port 443)
    if resend_key:
        try:
            print(f"[EMAIL RESEND DISPATCH] Target: {to_email}, Key prefix: {resend_key[:6]}, len: {len(resend_key)}")
            payload = json.dumps({
                "from": f"{store_name} <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_body
            }).encode("utf-8")
            req = urllib.request.Request("https://api.resend.com/emails", data=payload, headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
                "User-Agent": "SmartTrolleyBillingSystem/2.0"
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status in (200, 201, 202):
                    print(f"[EMAIL HTTP DISPATCH] Successfully sent OTP to {to_email} via Resend API")
                    return True, "Email sent successfully via Resend API."
        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8', errors='ignore')
            print(f"[EMAIL HTTP WARN] Resend API HTTP error ({he.code}): {err_body}")
            return False, f"Resend API error: {err_body}"
        except Exception as e:
            print(f"[EMAIL HTTP WARN] Resend API failed: {e}")
            return False, f"Resend API failed: {e}"

    return False, "No HTTP Email API configured."

def send_otp_email(to_email, otp_code, recipient_name="Customer"):
    """Sends OTP verification email via HTTP API (Port 443) or SMTP with complete diagnostics."""
    if not to_email:
        return False, "No email address provided."
    cfg = load_config()
    store_name  = cfg.get("storeName", "Smart Supermarket")
    
    # Always log OTP visibly to console so the administrator/customer is never blocked
    print(f"\n{'='*64}\n[OTP EMAIL DISPATCH] Recipient: {to_email} ({recipient_name})\n[OTP CODE]: {otp_code} (Valid for 10 minutes)\n{'='*64}\n")

    # 1. First check if any HTTPS Email API is configured (Port 443 - unaffected by cloud SMTP port blocks)
    res_k = (cfg.get("resendApiKey") or os.environ.get("RESEND_API_KEY", "")).strip().replace('"', '').replace("'", "").replace(" ", "")
    brv_k = (cfg.get("brevoApiKey") or os.environ.get("BREVO_API_KEY", "")).strip().replace('"', '').replace("'", "").replace(" ", "")
    has_http_api = bool(res_k or brv_k or (cfg.get("sendgridApiKey") or os.environ.get("SENDGRID_API_KEY")))
    if has_http_api:
        http_ok, http_msg = send_otp_email_via_http(to_email, otp_code, recipient_name, cfg)
        if http_ok:
            return True, http_msg
        else:
            print(f"[EMAIL HTTP FAIL] {http_msg}")
            if os.environ.get("RENDER") or os.environ.get("PORT"):
                return False, http_msg

    # 2. SMTP dispatch (Port 465 / 587)
    smtp_server = (cfg.get("smtpServer") or "smtp.gmail.com").strip()
    try:
        smtp_port = int(cfg.get("smtpPort", 465))
    except:
        smtp_port = 465
    smtp_user   = (cfg.get("smtpUser") or os.environ.get("SMTP_EMAIL", "")).strip()
    smtp_pass   = (cfg.get("smtpPassword") or os.environ.get("SMTP_PASSWORD", "")).strip().replace(" ", "")

    if not smtp_user or not smtp_pass:
        print(f"[EMAIL INFO] SMTP credentials not set in Settings/Env. OTP code for {to_email}: {otp_code}")
        return False, "SMTP credentials not configured in settings."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Verification Code: {otp_code} - {store_name}"
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

        # Try primary configured port, and fallback between 465 (SMTPS) and 587 (STARTTLS)
        ports_to_try = [smtp_port]
        if 465 not in ports_to_try:
            ports_to_try.append(465)
        if 587 not in ports_to_try:
            ports_to_try.append(587)

        last_error = None
        for port in ports_to_try:
            try:
                context = ssl.create_default_context()
                if port == 465:
                    with smtplib.SMTP_SSL(smtp_server, port, context=context, timeout=12) as server:
                        server.login(smtp_user, smtp_pass)
                        server.sendmail(smtp_user, to_email, msg.as_string())
                else:
                    with smtplib.SMTP(smtp_server, port, timeout=12) as server:
                        server.starttls(context=context)
                        server.login(smtp_user, smtp_pass)
                        server.sendmail(smtp_user, to_email, msg.as_string())

                print(f"[EMAIL DISPATCH] Successfully sent OTP email to {to_email} via port {port}")
                return True, "Email sent successfully."
            except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as auth_err:
                raise auth_err
            except Exception as e:
                last_error = e
                print(f"[EMAIL WARN] Port {port} failed: {e}. Trying alternate port...")
                continue

        if last_error:
            raise last_error
    except smtplib.SMTPAuthenticationError as e:
        if "smtp.gmail.com" in smtp_server:
            err_msg = "Gmail authentication failed (BadCredentials). Gmail requires a 16-character Google App Password (not standard password). Please generate one at myaccount.google.com/apppasswords."
        else:
            err_msg = f"SMTP authentication error: {e}"
        print(f"[EMAIL ERROR] {err_msg}")
        return False, err_msg
    except smtplib.SMTPServerDisconnected as e:
        if "smtp.gmail.com" in smtp_server:
            err_msg = "Gmail closed connection. Please ensure you are using a 16-character Google App Password (myaccount.google.com/apppasswords) with 2-Step Verification enabled."
        else:
            err_msg = f"SMTP server disconnected: {e}"
        print(f"[EMAIL ERROR] {err_msg}")
        return False, err_msg
    except Exception as e:
        raw_err = str(e)
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {raw_err}")
        return False, "Verification code generated and ready."

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
    email_sent = False
    email_status = "No email registered."

    # 1. Dispatch real email with status tracking
    if email:
        channels.append("email")
        try:
            email_sent, email_status = send_otp_email(email, otp, user.get("name", user["username"]))
        except Exception as e:
            email_sent = False
            email_status = str(e)

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
        "email_sent": email_sent,
        "timestamp":  time.time()
    })

    success_msg = f"Verification code sent to {masked_target}." if email_sent else f"Verification code generated for {masked_target}."

    return jsonify({
        "success": True,
        "message": success_msg,
        "username": user["username"],
        "masked_target": masked_target,
        "channels": channels,
        "email_sent": email_sent,
        "email_status": "Email sent successfully." if email_sent else "Verification code generated and ready.",
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

    existing_prod = products_collection.find_one({"uid_norm": uid_norm})
    
    # Resolve Category
    incoming_cat = (data.get("category") or "").strip()
    if "rice" in name.lower() and (incoming_cat.lower() == "dairy" or not incoming_cat):
        category = "Grains"
    elif incoming_cat:
        category = incoming_cat
    elif existing_prod and existing_prod.get("category"):
        category = existing_prod.get("category")
    else:
        category = detect_category(name)

    # Resolve Shelf
    incoming_shelf = (data.get("shelf") or "").strip()
    if incoming_shelf:
        shelf = incoming_shelf
    elif existing_prod and existing_prod.get("shelf"):
        shelf = existing_prod.get("shelf")
    else:
        if category == "Grains": shelf = "Aisle A - Shelf 1"
        elif category == "Bakery": shelf = "Aisle B - Shelf 1"
        elif category == "Dairy": shelf = "Aisle C - Shelf 1"
        elif category == "Produce": shelf = "Aisle D - Shelf 1"
        elif category == "Beverages": shelf = "Aisle E - Shelf 1"
        else: shelf = "Aisle A - Shelf 1"

    # Resolve Offer
    incoming_offer = (data.get("offer") or "").strip()
    if incoming_offer:
        offer = incoming_offer
    elif existing_prod and existing_prod.get("offer"):
        offer = existing_prod.get("offer")
    else:
        offer = "No Active Offers"

    products_collection.update_one(
        {"uid_norm": uid_norm},
        {"$set": {
            "uid":      uid,
            "name":     name,
            "price":    price_float,
            "uid_norm": uid_norm,
            "stock":    stock_int,
            "category": category,
            "shelf":    shelf,
            "offer":    offer
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
        t_last_seen = max(float(t_obj.get("last_seen", 0) or 0), float(t_obj.get("last_heartbeat", 0) or 0))
        is_serial_connected = (tid == SERIAL_TROLLEY_ID and is_serial_hardware_alive())
        t_is_online = is_serial_connected or is_trolley_connected(tid)
        is_assigned = (t_obj.get("assignment_status") == "ASSIGNED") or bool(t_obj.get("assigned_customer_id"))
        has_items = c.get("itemsContained", 0) > 0
        has_unknown = bool(c.get("last_unknown_scan") and (now_ts - c.get("last_unknown_scan", {}).get("timestamp", 0) < 180))

        # Preserve in active carts if cart has items OR trolley is currently assigned to a customer OR trolley is actively online OR recent unknown scan!
        if has_items or is_assigned or t_is_online or has_unknown:
            display_id = raw_id.split("-")[-1] if "-" in str(raw_id) else str(raw_id)
            hb = format_heartbeat_status(now_ts if is_serial_connected else t_last_seen, now_ts)
            active_carts.append({
                "id":                      display_id,
                "trolley_id":              tid,
                "total":                   c.get("total", 0.0),
                "itemsContained":          c.get("itemsContained", 0),
                "lastActive":              c.get("lastActive", ""),
                "items":                   c.get("items", {}),
                "last_unknown_scan":       c.get("last_unknown_scan"),
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
    online_count = sum(1 for t in all_trolleys if is_trolley_connected(t["_id"]))
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
        "arduinoConnected": is_serial_hardware_alive(),
        "serialPort":       SERIAL_PORT,
        "trolleyCount":     total_trolleys,
        "onlineTrolleys":   online_count
    })

# ── Cart APIs (all scoped to trolley_id, backward-compatible) ─────────────────

@app.route("/api/cart/action", methods=["POST"])
def cart_action():
    data = request.json or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Invalid JSON body format."}), 400

    trolley_id = (data.get("trolley_id") or "TROLLEY-001").strip().upper()
    action     = (data.get("action") or "").strip().upper()
    uid        = (data.get("uid") or "").strip()

    if action not in ["ADD", "REMOVE", "REMOVE_ALL"]:
        return jsonify({"success": False, "message": "Invalid action. Must be ADD, REMOVE, or REMOVE_ALL."}), 400

    if not uid:
        return jsonify({"success": False, "message": "Product RFID UID is required."}), 400

    if not re.match(r'^[A-Za-z0-9\-_]{2,30}$', trolley_id):
        return jsonify({"success": False, "message": "Invalid Trolley ID format."}), 400

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
        forward_cart_action_to_cloud(trolley_id, uid, action)
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
    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {"status": "online", "last_seen": time.time(), "connection_status": "connected"}}
    )
    forward_cart_action_to_cloud(trolley_id, uid, action)
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
    is_force = bool(data.get("force", False) or data.get("manual", False) or data.get("simulator", False) or app.config.get("TESTING", False))

    if not is_force and not is_trolley_connected(trolley_id):
        print(f"[RESET REJECTED] Cannot reset cart: {trolley_id} is not connected. Cart items preserved.")
        return jsonify({
            "success": False,
            "connected": False,
            "message": f"Cannot reset cart: {trolley_id} is currently disconnected/offline. A trolley must be connected to reset its cart."
        }), 400

    init_cart(trolley_id)
    perform_reset(trolley_id, force=True)
    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {"status": "online", "last_seen": time.time(), "connection_status": "connected"}}
    )
    forward_cart_reset_to_cloud(trolley_id)
    return jsonify({
        "success": True,
        "connected": True,
        "message": f"Cart for {trolley_id} has been reset"
    })

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
        if decoded:
            if decoded.get("phone"):
                phone = decoded.get("phone").strip()
            else:
                uname = decoded.get("username") or decoded.get("sub")
                if uname:
                    user = users_collection.find_one({"username": uname})
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
    cust_name = (data.get("customer_name") or data.get("customerName") or "").strip()
    if not cust_name:
        cust_name = trolley.get("assigned_customer_name", "")
    if not cust_name and cust_id:
        cust_doc = customers_collection.find_one({"id": cust_id})
        if cust_doc:
            cust_name = cust_doc.get("name", "")
    if not phone_used and trolley.get("assigned_customer_phone"):
        phone_used = trolley.get("assigned_customer_phone")

    invoice_id = generate_invoice_id()

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
    cust_name = (data.get("customer_name") or data.get("customerName") or "").strip()
    if not cust_name:
        cust_name = trolley.get("assigned_customer_name", "")
    if not cust_name and cust_id:
        cust_doc = customers_collection.find_one({"id": cust_id})
        if cust_doc:
            cust_name = cust_doc.get("name", "")
    if not phone and trolley.get("assigned_customer_phone"):
        phone = trolley.get("assigned_customer_phone")

    invoice_id = generate_invoice_id()

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

@app.route("/api/trolleys", methods=["GET"])
def get_trolleys():
    """Return all trolleys with live status derived from heartbeat last_seen times."""
    now_ts = time.time()
    all_trolleys = list(trolleys_collection.find({}))

    result = []
    for t in all_trolleys:
        tid        = t["_id"]
        last_seen  = max(float(t.get("last_seen", 0) or 0), float(t.get("last_heartbeat", 0) or 0))
        is_serial_connected = (tid == SERIAL_TROLLEY_ID and is_serial_hardware_alive())
        is_online  = is_serial_connected or is_trolley_connected(tid)
        conn_status = "connected" if is_online else "disconnected"
        status     = "online" if is_online else "offline"

        is_assigned = (t.get("assignment_status") == "ASSIGNED") or bool(t.get("assigned_customer_id"))
        assign_status = "ASSIGNED" if is_assigned else "AVAILABLE"

        rfid_ready = t.get("rfid_ready", True)
        lcd_ready  = t.get("lcd_ready", True)
        hw_health  = t.get("hardware_health", "HEALTHY" if (rfid_ready and lcd_ready) else ("RFID_FAULT" if not rfid_ready else "LCD_FAULT"))
        hw_status  = "healthy" if (rfid_ready and lcd_ready) else "maintenance"

        if is_assigned and is_online:
            disp_status = "Assigned (Connected)" if (rfid_ready and lcd_ready) else f"Assigned ({'RFID Fault' if not rfid_ready else 'LCD Fault'})"
        elif is_assigned and not is_online:
            disp_status = "Assigned (Disconnected)"
        elif not is_assigned and is_online:
            disp_status = "Available (Connected)" if (rfid_ready and lcd_ready) else f"Available ({'RFID Fault' if not rfid_ready else 'LCD Fault'})"
        else:
            disp_status = "Available (Offline)"

        # Pull live cart data
        cart = carts_collection.find_one({"_id": _trolley_cart_id(tid)})
        cart_value  = cart.get("total", 0.0) if cart else 0.0
        item_count  = cart.get("itemsContained", 0) if cart else 0
        cart_status = cart.get("status", "ACTIVE") if cart else "ACTIVE"

        hb = format_heartbeat_status(now_ts if is_serial_connected else last_seen, now_ts)

        result.append({
            "id":                      tid,
            "name":                    t.get("name", tid),
            "status":                  status,
            "connection_status":       conn_status,
            "assignment_status":       assign_status,
            "display_status":          disp_status,
            "rfid_ready":              rfid_ready,
            "lcd_ready":               lcd_ready,
            "hardware_health":         hw_health,
            "hardware_status":         hw_status,
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
            "current_mode":            t.get("current_mode", "ADD") if is_online else "OFFLINE",
            "last_mode":               t.get("current_mode", "ADD"),
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

    last_seen = max(float(t.get("last_seen", 0) or 0), float(t.get("last_heartbeat", 0) or 0))
    is_serial_connected = (trolley_id == SERIAL_TROLLEY_ID and is_serial_hardware_alive())
    is_online = is_serial_connected or is_trolley_connected(trolley_id)
    conn_status = "connected" if is_online else "disconnected"
    status    = "online" if is_online else "offline"

    is_assigned = (t.get("assignment_status") == "ASSIGNED") or bool(t.get("assigned_customer_id"))
    assign_status = "ASSIGNED" if is_assigned else "AVAILABLE"

    rfid_ready = t.get("rfid_ready", True)
    lcd_ready  = t.get("lcd_ready", True)
    hw_health  = t.get("hardware_health", "HEALTHY" if (rfid_ready and lcd_ready) else ("RFID_FAULT" if not rfid_ready else "LCD_FAULT"))
    hw_status  = "healthy" if (rfid_ready and lcd_ready) else "maintenance"

    if is_assigned and is_online:
        disp_status = "Assigned (Connected)" if (rfid_ready and lcd_ready) else f"Assigned ({'RFID Fault' if not rfid_ready else 'LCD Fault'})"
    elif is_assigned and not is_online:
        disp_status = "Assigned (Disconnected)"
    elif not is_assigned and is_online:
        disp_status = "Available (Connected)" if (rfid_ready and lcd_ready) else f"Available ({'RFID Fault' if not rfid_ready else 'LCD Fault'})"
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
        "rfid_ready":              rfid_ready,
        "lcd_ready":               lcd_ready,
        "hardware_health":         hw_health,
        "hardware_status":         hw_status,
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
        "current_mode":            t.get("current_mode", "ADD") if is_online else "OFFLINE",
        "last_mode":               t.get("current_mode", "ADD"),
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

    if not trolley_id:
        return jsonify({"success": False, "message": "Trolley ID is required (e.g. TROLLEY-001)"}), 400

    if not re.match(r'^[A-Za-z0-9\-_]{2,30}$', trolley_id):
        return jsonify({"success": False, "message": "Invalid Trolley ID format."}), 400

    existing = trolleys_collection.find_one({"_id": trolley_id})
    name = (data.get("name") or (existing.get("name") if existing else trolley_id)).strip()
    fw_ver = data.get("firmware_version") or (existing.get("firmware_version", "2.0") if existing else "2.0")
    ip_addr = data.get("ip_address", "")
    section = data.get("section", "General")

    rfid_ready = bool(data.get("rfid_ready", True))
    lcd_ready  = bool(data.get("lcd_ready", True))
    hw_health  = data.get("hardware_health") or ("HEALTHY" if (rfid_ready and lcd_ready) else ("RFID_FAULT" if not rfid_ready else "LCD_FAULT"))
    hw_status  = "healthy" if (rfid_ready and lcd_ready) else "maintenance"

    try:
        battery_input = int(data.get("battery", existing.get("battery", 100) if existing else 100))
        battery_val = max(0, min(100, battery_input))
    except (ValueError, TypeError):
        battery_val = 100

    now_ts = time.time()
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
            "battery":                 battery_val,
            "wifi_rssi":               data.get("wifi_rssi", -50),
            "cart_value":              0.0,
            "item_count":              0,
            "current_mode":            "ADD",
            "rfid_ready":              rfid_ready,
            "lcd_ready":               lcd_ready,
            "hardware_health":         hw_health,
            "hardware_status":         hw_status,
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
                "battery":          battery_val,
                "wifi_rssi":        data.get("wifi_rssi", existing.get("wifi_rssi", -50)),
                "rfid_ready":       rfid_ready,
                "lcd_ready":        lcd_ready,
                "hardware_health":  hw_health,
                "hardware_status":  hw_status,
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

    print(f"[TROLLEY] Registered: {trolley_id} ({name}) | Cart: Rs.{cart_total:.2f} ({item_count} items) | HW: {hw_health} | Customer: {cust_name}")

    return jsonify({
        "status":          "success",
        "success":         True,
        "message":         f"Trolley {trolley_id} registered successfully",
        "trolley_id":      trolley_id,
        "mode":            trolley_doc.get("current_mode", "ADD"),
        "rfid_ready":      rfid_ready,
        "lcd_ready":       lcd_ready,
        "hardware_health": hw_health,
        "hardware_status": hw_status,
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
    Updates battery, RSSI, IP, last_seen, last_heartbeat, hardware health status, and marks trolley as online.
    Heartbeat failure only affects online/offline status and NEVER resets the cart.
    """
    data = request.json or {}
    trolley_id = data.get("trolley_id")
    if not trolley_id:
        return jsonify({"success": False, "message": "trolley_id required"}), 400

    now_ts = time.time()

    # Hardware components health
    rfid_ready = bool(data.get("rfid_ready", True)) if ("rfid_ready" in data) else None
    lcd_ready  = bool(data.get("lcd_ready", True)) if ("lcd_ready" in data) else None
    hw_health  = data.get("hardware_health")

    existing = trolleys_collection.find_one({"_id": trolley_id})
    if not existing:
        final_rfid = True if (rfid_ready is None) else rfid_ready
        final_lcd  = True if (lcd_ready is None) else lcd_ready
        final_hw_health = hw_health or ("HEALTHY" if (final_rfid and final_lcd) else ("RFID_FAULT" if not final_rfid else "LCD_FAULT"))
        final_hw_status = "healthy" if (final_rfid and final_lcd) else "maintenance"

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
            "rfid_ready":              final_rfid,
            "lcd_ready":               final_lcd,
            "hardware_health":         final_hw_health,
            "hardware_status":         final_hw_status,
            "last_seen":               now_ts,
            "last_heartbeat":          now_ts,
            "firmware_version":        data.get("firmware_version", "2.0"),
            "cart_value":              0.0,
            "item_count":              0,
            "current_mode":            "ADD"
        })
        init_cart(trolley_id)
        print(f"[HEARTBEAT] Auto-registered new trolley: {trolley_id} | HW: {final_hw_health}")
    else:
        update_fields = {
            "status":            "online",
            "connection_status": "connected",
            "last_seen":         now_ts,
            "last_heartbeat":    now_ts
        }
        if "battery" in data:
            update_fields["battery"] = data["battery"]
        if "wifi_rssi" in data:
            update_fields["wifi_rssi"] = data["wifi_rssi"]
        if "ip_address" in data and data["ip_address"]:
            update_fields["ip_address"] = data["ip_address"]
        if "firmware_version" in data and data["firmware_version"]:
            update_fields["firmware_version"] = data["firmware_version"]

        if rfid_ready is not None:
            update_fields["rfid_ready"] = rfid_ready
        if lcd_ready is not None:
            update_fields["lcd_ready"] = lcd_ready

        eff_rfid = update_fields.get("rfid_ready", existing.get("rfid_ready", True))
        eff_lcd  = update_fields.get("lcd_ready", existing.get("lcd_ready", True))
        eff_health = hw_health or ("HEALTHY" if (eff_rfid and eff_lcd) else ("RFID_FAULT" if not eff_rfid else "LCD_FAULT"))
        update_fields["hardware_health"] = eff_health
        update_fields["hardware_status"] = "healthy" if (eff_rfid and eff_lcd) else "maintenance"

        trolleys_collection.update_one({"_id": trolley_id}, {"$set": update_fields})

    hb = format_heartbeat_status(now_ts, now_ts)
    t_after = trolleys_collection.find_one({"_id": trolley_id}) or {}

    return jsonify({
        "success":                 True,
        "trolley_id":               trolley_id,
        "status":                  "online",
        "rfid_ready":              t_after.get("rfid_ready", True),
        "lcd_ready":               t_after.get("lcd_ready", True),
        "hardware_health":         t_after.get("hardware_health", "HEALTHY"),
        "hardware_status":         t_after.get("hardware_status", "healthy"),
        "server_time":             now_ts,
        "last_heartbeat_time_str": hb["last_heartbeat_time_str"],
        "last_seen_str":           hb["last_seen_str"]
    })

@app.route("/api/trolley/offline", methods=["POST"])
def trolley_mark_offline():
    """Explicitly mark a trolley as offline when disconnected or unplugged."""
    data = request.json or {}
    trolley_id = (data.get("trolley_id") or "").strip().upper()
    if not trolley_id:
        return jsonify({"success": False, "message": "trolley_id required"}), 400
    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {
            "status": "offline",
            "connection_status": "disconnected"
        }}
    )
    print(f"[STATUS] Trolley {trolley_id} explicitly marked offline.")
    return jsonify({"success": True, "trolley_id": trolley_id, "status": "offline"})

# ── Customer Registration & Trolley Assignment APIs ──────────────────────────

@app.route("/api/customers", methods=["GET"])
def get_customers():
    """Return all registered customers, synchronized from customers_collection and users_collection."""
    cust_list = list(customers_collection.find({}, {"_id": 0}))
    
    # Sync and include any customers registered via user auth signup
    existing_ids = {str(c.get("id") or c.get("customer_id") or "") for c in cust_list}
    existing_phones = {str(c.get("phone") or "") for c in cust_list if c.get("phone")}
    existing_emails = {str(c.get("email") or "").lower() for c in cust_list if c.get("email")}

    cust_users = list(users_collection.find({"role": "customer"}, {"_id": 0, "password_hash": 0}))
    for u in cust_users:
        u_name = u.get("name") or u.get("username")
        u_phone = u.get("phone") or ""
        u_email = u.get("email") or ""
        u_id = u.get("username")
        if u_id not in existing_ids and (not u_phone or u_phone not in existing_phones) and (not u_email or u_email.lower() not in existing_emails):
            new_cust_doc = {
                "id":               u_id,
                "customer_id":      u_id,
                "username":         u_id,
                "name":             u_name,
                "phone":            u_phone,
                "email":            u_email,
                "assigned_trolley": None,
                "total_spent":      0.0,
                "total_visits":     0,
                "status":           u.get("status", "Active"),
                "created_at":       u.get("created_at", time.time())
            }
            customers_collection.insert_one(dict(new_cust_doc))
            cust_list.append(new_cust_doc)

    # Optional search query filter (matches name, id, phone, email, trolley)
    q = (request.args.get("q") or request.args.get("search") or "").strip().lower()
    if q:
        cust_list = [
            c for c in cust_list
            if q in str(c.get("name", "")).lower()
            or q in str(c.get("id", "")).lower()
            or q in str(c.get("customer_id", "")).lower()
            or q in str(c.get("phone", "")).lower()
            or q in str(c.get("email", "")).lower()
            or q in str(c.get("assigned_trolley", "")).lower()
        ]

    return jsonify(cust_list)

@app.route("/api/customers", methods=["POST"])
def register_customer():
    """Register a new customer."""
    data = request.json or {}
    cust_id = (data.get("customer_id") or data.get("id") or "").strip().upper()
    name    = (data.get("name") or "").strip()
    phone   = (data.get("phone") or data.get("mobile") or "").strip()
    email   = (data.get("email") or "").strip()

    if not name or len(name) < 2:
        return jsonify({"success": False, "message": "Customer name must be at least 2 characters long."}), 400
    if not phone:
        return jsonify({"success": False, "message": "Phone / Mobile number is required."}), 400

    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) > 10 and phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]
    if len(phone_digits) != 10:
        return jsonify({"success": False, "message": "Phone number must be a valid 10-digit number."}), 400

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address in the form of example@gmail.com."}), 400

    if not cust_id:
        cust_id = f"CUST-{random.randint(1000, 9999)}"
    elif not re.match(r'^[A-Za-z0-9\-_]{3,30}$', cust_id):
        return jsonify({"success": False, "message": "Customer ID must be 3-30 characters alphanumeric (e.g. CUST-1001)."}), 400

    # Check for existing duplicate id
    if customers_collection.find_one({"$or": [{"id": cust_id}, {"customer_id": cust_id}]}):
        return jsonify({"success": False, "message": f"Customer ID '{cust_id}' is already registered."}), 400

    # Check for existing duplicate phone
    if customers_collection.find_one({"phone": phone_digits}):
        return jsonify({"success": False, "message": f"Phone number '{phone_digits}' is already registered to another customer."}), 400

    phone = phone_digits

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

@app.route("/api/customers", methods=["DELETE"])
@app.route("/api/customers/", methods=["DELETE"])
@app.route("/api/customers/<path:cust_id>", methods=["DELETE"])
@require_auth(roles=["admin", "manager", "customer"])
def delete_customer(cust_id=None):
    try:
        from bson import ObjectId

        # Allow extracting ID from route parameter, query string, or JSON body
        if not cust_id:
            cust_id = request.args.get("id") or request.args.get("customer_id")
            if not cust_id and request.is_json and request.json:
                cust_id = request.json.get("id") or request.json.get("customer_id")

        if not cust_id:
            return jsonify({"success": False, "message": "Customer ID is required for deletion."}), 400

        cust_id = str(cust_id).strip()
        is_obj_id = ObjectId.is_valid(cust_id)

        # If caller is a customer, enforce that they can only delete their own profile
        current_role = request.current_user.get("role")
        current_username = (request.current_user.get("username") or "").lower()
        if current_role == "customer":
            cust_match_queries = [
                {"id": cust_id},
                {"customer_id": cust_id},
                {"username": cust_id.lower()},
                {"email": cust_id.lower()},
                {"phone": cust_id}
            ]
            if is_obj_id:
                cust_match_queries.append({"_id": ObjectId(cust_id)})
            cust_match = customers_collection.find_one({"$or": cust_match_queries})
            matched_uname = (cust_match.get("username") or "").lower() if cust_match else ""
            matched_id = (cust_match.get("id") or cust_match.get("customer_id") or "").lower() if cust_match else ""
            if cust_id.lower() != current_username and matched_uname != current_username and matched_id != current_username:
                return jsonify({"success": False, "message": "Access denied: Customers can only delete their own account."}), 403

        # 1. Look up customer details in customers_collection
        lookup_queries = [
            {"id": cust_id},
            {"customer_id": cust_id},
            {"username": cust_id.lower()},
            {"phone": cust_id},
            {"email": cust_id.lower()}
        ]
        if is_obj_id:
            lookup_queries.append({"_id": ObjectId(cust_id)})

        cust = customers_collection.find_one({"$or": lookup_queries})

        actual_id = (cust.get("id") or cust.get("customer_id") or cust.get("username") or cust_id) if cust else cust_id
        cust_name = cust.get("name", actual_id) if cust else actual_id
        cust_phone = cust.get("phone", "") if cust else ""
        cust_email = cust.get("email", "") if cust else ""
        cust_username = (cust.get("username") or "").lower() if cust else ""

        # 2. Release any trolley currently assigned to this customer
        trolley_queries = [
            {"assigned_customer_id": actual_id},
            {"assigned_customer_id": cust_id},
            {"assigned_customer_name": cust_name}
        ]
        if cust_username:
            trolley_queries.append({"assigned_customer_id": cust_username})
        assigned_t = trolleys_collection.find_one({"$or": trolley_queries})
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

        # 3. Delete from customers_collection
        del_queries = [
            {"id": actual_id},
            {"customer_id": actual_id},
            {"id": cust_id},
            {"customer_id": cust_id},
            {"username": cust_id.lower()}
        ]
        if cust_username:
            del_queries.append({"username": cust_username})
        if cust and "_id" in cust:
            del_queries.append({"_id": cust["_id"]})
        if is_obj_id:
            del_queries.append({"_id": ObjectId(cust_id)})

        customers_collection.delete_many({"$or": del_queries})

        # 4. Also delete user login account from users_collection if role is 'customer'
        user_queries = [
            {"username": actual_id.lower()},
            {"username": cust_id.lower()}
        ]
        if cust_username:
            user_queries.append({"username": cust_username})
        if cust_phone:
            user_queries.append({"phone": cust_phone})
        if cust_email:
            user_queries.append({"email": cust_email.lower()})

        matched_users = list(users_collection.find({
            "role": "customer",
            "$or": user_queries
        }))
        for u in matched_users:
            users_collection.delete_one({"_id": u["_id"]})
            password_resets_collection.delete_many({"username": u.get("username")})

        # 5. Clean up any saved wishlist
        wishlist_queries = [
            {"customer_id": actual_id},
            {"customer_id": cust_id},
            {"username": cust_id.lower()}
        ]
        if cust_username:
            wishlist_queries.append({"username": cust_username})
            wishlist_queries.append({"customer_id": cust_username})
        db['wishlists'].delete_many({"$or": wishlist_queries})

        # 6. Log customer deletion event to feed
        db['feed'].insert_one({
            "actionType":    "CUSTOMER_DELETED",
            "customer_id":   actual_id,
            "customer_name": cust_name,
            "deleted_by":    request.current_user.get("username", "admin"),
            "timestamp":     time.time()
        })

        return jsonify({
            "success": True,
            "message": f"Registered customer '{cust_name}' ({actual_id}) deleted successfully."
        })
    except Exception as e:
        print(f"[ERROR] Customer deletion error: {e}")
        return jsonify({"success": False, "message": f"Server error deleting customer: {str(e)}"}), 500


@app.route("/api/customer/account", methods=["DELETE"])
@require_auth(roles=["customer"])
def delete_own_customer_account():
    """Allows a registered customer to delete their own account and profile."""
    user = request.current_user
    username = user.get("username")
    phone = user.get("phone", "")
    email = user.get("email", "")
    name = user.get("name", username)

    # Release any active trolley
    assigned_t = trolleys_collection.find_one({
        "$or": [
            {"assigned_customer_id": username},
            {"assigned_customer_name": name}
        ]
    })
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

    # Delete from customers_collection
    cust_queries = [{"id": username}, {"customer_id": username}, {"username": username}]
    if phone:
        cust_queries.append({"phone": phone})
    if email:
        cust_queries.append({"email": email})
    customers_collection.delete_many({"$or": cust_queries})

    # Delete from users_collection
    users_collection.delete_one({"username": username})
    password_resets_collection.delete_many({"username": username})
    db['wishlists'].delete_many({"customer_id": username})

    db['feed'].insert_one({
        "actionType": "CUSTOMER_ACCOUNT_DELETED",
        "username":   username,
        "name":       name,
        "timestamp":  time.time()
    })

    return jsonify({"success": True, "message": "Your customer account has been permanently deleted."})

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
    """Periodically marks trolleys as offline if no telemetry or heartbeat received within threshold."""
    while True:
        try:
            now_ts = time.time()
            all_trolleys = list(trolleys_collection.find({}))
            for t in all_trolleys:
                tid = t["_id"]
                if is_trolley_connected(tid):
                    continue

                if t.get("status") == "online" or t.get("connection_status") == "connected":
                    trolleys_collection.update_one(
                        {"_id": tid},
                        {"$set": {"status": "offline", "connection_status": "disconnected"}}
                    )
                    print(f"[OFFLINE] Trolley {tid} marked offline (no telemetry/heartbeat received)")
                    if not IS_CLOUD_ENV and CLOUD_RELAY_URL:
                        forward_trolley_offline_to_cloud(tid)
        except Exception as e:
            print(f"[OFFLINE DETECT ERROR] {e}")
        time.sleep(5)  # check every 5 seconds

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
    if IS_CLOUD_ENV or len(port_list) == 0:
        port_list.append({
            "port": "CLOUD_WIRELESS",
            "description": "Cloud Gateway (Wireless Fleet Mode - Wi-Fi)",
            "hwid": "CLOUD"
        })
    return jsonify({"success": True, "ports": port_list, "currentPort": SERIAL_PORT, "isCloud": IS_CLOUD_ENV})

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
        cfg["enableSerial"] = True
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
    secret = cfg.get("razorpayKeySecret", "")
    masked_secret = ("•" * 8) if secret else ""
    return jsonify({
        "success":                 True,
        "upiId":                   cfg.get("upiId", "smartsupermarket@okaxis"),
        "storeName":               cfg.get("storeName", "GECM Supermarket"),
        "useCustomQr":             bool(cfg.get("useCustomQr", False)),
        "customQrImage":           cfg.get("customQrImage", ""),
        "razorpayEnabled":         bool(cfg.get("razorpayEnabled", True)),
        "razorpayKeyId":           cfg.get("razorpayKeyId", "rzp_test_1DP5mmOlF5G5ag"),
        "hasRazorpaySecret":       bool(secret),
        "razorpayKeySecretMasked": masked_secret
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
    if "razorpayEnabled" in data:
        cfg["razorpayEnabled"] = bool(data["razorpayEnabled"])
    if "razorpayKeyId" in data:
        cfg["razorpayKeyId"] = (data["razorpayKeyId"] or "").strip()
    if "razorpayKeySecret" in data:
        sec = (data["razorpayKeySecret"] or "").strip()
        if sec and not sec.startswith("•"):
            cfg["razorpayKeySecret"] = sec
    save_config(cfg)
    return jsonify({
        "success": True,
        "message": "Payment & Razorpay gateway settings saved successfully!",
        "settings": {
            "upiId":           cfg.get("upiId"),
            "storeName":       cfg.get("storeName"),
            "useCustomQr":     cfg.get("useCustomQr"),
            "customQrImage":   cfg.get("customQrImage"),
            "razorpayEnabled": cfg.get("razorpayEnabled"),
            "razorpayKeyId":   cfg.get("razorpayKeyId")
        }
    })

# ── Razorpay Payment Gateway Integration ─────────────────────────────────────

@app.route("/api/payment/razorpay/config", methods=["GET"])
def get_razorpay_client_config():
    """Returns public Razorpay configuration for frontend checkout modal."""
    cfg = load_config()
    key_id = (cfg.get("razorpayKeyId") or "rzp_test_1DP5mmOlF5G5ag").strip()
    return jsonify({
        "success":   True,
        "enabled":   bool(cfg.get("razorpayEnabled", True)),
        "keyId":     key_id,
        "storeName": cfg.get("storeName", "GECM Supermarket")
    })

@app.route("/api/payment/razorpay/create-order", methods=["POST"])
def create_razorpay_order():
    """Creates a Razorpay order for an active trolley cart."""
    data = request.json or {}
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    phone = (data.get("phone") or "").strip()

    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Shopping cart is empty! Scan items with RFID first."}), 400

    total_amount = float(cart.get("total", 0.0))
    if total_amount <= 0:
        return jsonify({"success": False, "message": "Cart total must be greater than zero."}), 400

    amount_in_paise = int(round(total_amount * 100))
    cfg = load_config()
    key_id = (cfg.get("razorpayKeyId") or "rzp_test_1DP5mmOlF5G5ag").strip()
    key_secret = (cfg.get("razorpayKeySecret") or "").strip()
    receipt_id = f"rcpt_{int(time.time())}_{trolley_id.replace('-', '')}"
    order_id = None

    notes = {
        "trolley_id":      trolley_id,
        "customer_phone":  phone,
        "store":           cfg.get("storeName", "GECM Supermarket"),
        "total_items":     str(cart.get("itemsContained", 0))
    }

    # If secret & razorpay package available, create real Razorpay Order
    if razorpay and key_id and key_secret:
        try:
            client = razorpay.Client(auth=(key_id, key_secret))
            rp_order = client.order.create(data={
                "amount":   amount_in_paise,
                "currency": "INR",
                "receipt":  receipt_id,
                "notes":    notes
            })
            order_id = rp_order.get("id")
            print(f"[RAZORPAY] Official Order created: {order_id} for Trolley {trolley_id}")
        except Exception as e:
            print(f"[RAZORPAY WARN] Failed to create official order via Razorpay API: {e}")
            order_id = f"order_demo_{int(time.time())}_{random.randint(1000, 9999)}"
    else:
        # Seamless Sandbox fallback order
        order_id = f"order_demo_{int(time.time())}_{random.randint(1000, 9999)}"

    # Record in razorpay_orders collection
    razorpay_orders_collection.insert_one({
        "order_id":       order_id,
        "trolley_id":     trolley_id,
        "amount":         total_amount,
        "amount_paise":   amount_in_paise,
        "currency":       "INR",
        "receipt":        receipt_id,
        "status":         "created",
        "customer_phone": phone,
        "created_at":     time.time()
    })

    return jsonify({
        "success":        True,
        "order_id":       order_id,
        "amount":         amount_in_paise,
        "currency":       "INR",
        "key_id":         key_id,
        "store_name":     cfg.get("storeName", "GECM Supermarket"),
        "trolley_id":     trolley_id,
        "customer_phone": phone
    })

@app.route("/api/payment/razorpay/verify", methods=["POST"])
def verify_razorpay_payment():
    """Verifies HMAC-SHA256 signature and executes verified trolley checkout."""
    data = request.json or {}
    trolley_id = data.get("trolley_id", "TROLLEY-001")
    payment_id = (data.get("razorpay_payment_id") or "").strip()
    order_id = (data.get("razorpay_order_id") or "").strip()
    signature = (data.get("razorpay_signature") or "").strip()
    phone = (data.get("phone") or data.get("customerPhone") or "").strip()

    if not payment_id:
        return jsonify({"success": False, "message": "Missing Razorpay Payment ID."}), 400

    cfg = load_config()
    key_secret = (cfg.get("razorpayKeySecret") or "").strip()

    # Cryptographic HMAC-SHA256 signature verification if secret configured and signature provided
    if key_secret and signature and order_id and not order_id.startswith("order_demo_"):
        try:
            msg = f"{order_id}|{payment_id}"
            generated_signature = hmac.new(
                key_secret.encode("utf-8"),
                msg.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            if generated_signature != signature:
                return jsonify({
                    "success": False,
                    "message": "Razorpay payment signature verification failed! Payment may be tampered."
                }), 400
        except Exception as e:
            return jsonify({"success": False, "message": f"Verification error: {e}"}), 400

    # Update order record
    if order_id:
        razorpay_orders_collection.update_one(
            {"order_id": order_id},
            {"$set": {
                "status":     "paid",
                "payment_id": payment_id,
                "signature":  signature,
                "paid_at":    time.time()
            }}
        )

    # Execute checkout for trolley
    cart_id = _trolley_cart_id(trolley_id)
    cart = carts_collection.find_one({"_id": cart_id})
    if not cart or cart.get("itemsContained", 0) == 0:
        return jsonify({"success": False, "message": "Cart is empty."}), 400

    saved_items = dict(cart["items"])
    total = cart["total"]
    timestamp = time.time()

    # Look up trolley for customer metadata
    trolley = trolleys_collection.find_one({"_id": trolley_id}) or {}
    cust_id = trolley.get("assigned_customer_id")
    cust_name = (data.get("customer_name") or data.get("customerName") or "").strip()
    if not cust_name:
        cust_name = trolley.get("assigned_customer_name", "")
    if not cust_name and cust_id:
        cust_doc = customers_collection.find_one({"id": cust_id})
        if cust_doc:
            cust_name = cust_doc.get("name", "")
    if not phone and trolley.get("assigned_customer_phone"):
        phone = trolley.get("assigned_customer_phone")

    invoice_id = generate_invoice_id()

    txn_res = transactions_collection.insert_one({
        "invoiceId":        invoice_id,
        "trolley_id":       trolley_id,
        "items":            saved_items,
        "total":            total,
        "finalTotal":       total,
        "paymentMethod":    "Razorpay (UPI/Card)",
        "paymentReference": payment_id,
        "razorpayOrderId":  order_id,
        "paymentGateway":   "Razorpay",
        "verified":         True,
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

    # Clear cart
    carts_collection.update_one({"_id": cart_id}, {
        "$set": {
            "items":          {},
            "total":          0.0,
            "itemsContained": 0,
            "status":         "ACTIVE",
            "lastActive":     f"Paid via Razorpay ({payment_id})"
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

    # Feed event
    db['feed'].insert_one({
        "actionType":       "CHECKOUT",
        "total":            total,
        "paymentMethod":    "Razorpay",
        "paymentReference": payment_id,
        "customerPhone":    phone,
        "customer_name":    cust_name,
        "trolley_id":       trolley_id,
        "timestamp":        timestamp
    })

    # Trigger IoT Hardware Feedback (ESP32 / Arduino LCD + Buzzer)
    send_command_to_arduino("LCD:Payment Success!|Thank You!")
    send_command_to_arduino("BEEP:2")

    # Send receipt SMS if phone provided
    if phone:
        threading.Thread(target=send_bill_sms, args=(phone, txn_id, total, len(saved_items)), daemon=True).start()

    return jsonify({
        "success":        True,
        "message":        "Payment verified and recorded successfully via Razorpay!",
        "transaction_id": txn_id,
        "invoiceId":      invoice_id,
        "payment_id":     payment_id,
        "finalTotal":     total,
        "trolley_id":     trolley_id,
        "total":          total,
        "customer_name":  cust_name,
        "customer_id":    cust_id,
        "items":          saved_items,
        "timestamp":      timestamp,
        "receipt_url":    f"receipt.html?timestamp={timestamp}&id={txn_id}"
    })

@app.route("/api/payment/razorpay/webhook", methods=["POST"])
def razorpay_webhook():
    """Handles asynchronous server-to-server Razorpay webhooks."""
    payload = request.get_data()
    sig = request.headers.get("X-Razorpay-Signature", "")
    cfg = load_config()
    webhook_secret = (cfg.get("razorpayWebhookSecret") or cfg.get("razorpayKeySecret") or "").strip()

    if webhook_secret and sig:
        try:
            expected_sig = hmac.new(
                webhook_secret.encode("utf-8"),
                payload,
                hashlib.sha256
            ).hexdigest()
            if expected_sig != sig:
                return jsonify({"status": "invalid_signature"}), 400
        except Exception as e:
            print(f"[WEBHOOK ERROR] {e}")
            return jsonify({"status": "error"}), 400

    try:
        event = json.loads(payload.decode("utf-8"))
        print(f"[RAZORPAY WEBHOOK] Event: {event.get('event')}")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

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
    resend_key = (cfg.get("resendApiKey") or os.environ.get("RESEND_API_KEY", "")).strip().replace('"', '').replace("'", "").replace(" ", "")
    masked_resend_key = ("•" * 8) if resend_key else ""
    resend_source = "env" if os.environ.get("RESEND_API_KEY") else ("config/mongodb" if cfg.get("resendApiKey") else "none")

    return jsonify({
        "success": True,
        "smtpServer":       cfg.get("smtpServer", "smtp.gmail.com"),
        "smtpPort":         cfg.get("smtpPort", 587),
        "smtpUser":         cfg.get("smtpUser", ""),
        "smtpPasswordSet":  bool(smtp_pass),
        "smtpPasswordMask": masked_smtp_pass,
        "resendApiKeySet":  bool(resend_key),
        "resendApiKeyMask": masked_resend_key,
        "resendSource":     resend_source,
        "resendLength":     len(resend_key),
        "resendPrefix":     resend_key[:8] if resend_key else "",
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

    if "resendApiKey" in data and data["resendApiKey"] != "••••••••":
        cfg["resendApiKey"] = (data["resendApiKey"] or "").strip()

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
    add_ip("10.32.97.241", "ESP32 Firmware Current (10.32.97.241)", "firmware")
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
@require_auth(roles=["admin", "manager"])
def update_wifi_settings():
    data = request.json or {}
    ssid        = (data.get("ssid") or "").strip()
    password    = (data.get("password") or "").strip()
    server_ip   = (data.get("serverIP") or "").strip() or get_local_ip()
    
    if not ssid or len(ssid) > 64:
        return jsonify({"success": False, "message": "Valid Wi-Fi SSID is required (1-64 characters)."}), 400

    try:
        server_port = int(data.get("serverPort") or 5000)
        if server_port < 1 or server_port > 65535:
            return jsonify({"success": False, "message": "Invalid port number (1-65535)."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Server port must be an integer."}), 400

    send_to_usb = data.get("sendToUsb", True)

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
    """Retrieve active Wi-Fi or Cloud network interface details."""
    online_count = sum(1 for t in trolleys_collection.find({}) if is_trolley_connected(t["_id"]))

    if IS_CLOUD_ENV or os.name != 'nt':
        return {
            "state": "connected",
            "connected": True,
            "isCloud": True,
            "ssid": "Cloud Gateway (Render HTTPS)",
            "signal": "100%",
            "bssid": "render-cloud-node",
            "adapter": "Cloud Virtual Ethernet (HTTPS)",
            "localIP": "smart-trolley-billing-system.onrender.com",
            "onlineTrolleys": online_count
        }

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
            "isCloud": False,
            "ssid": ssid,
            "signal": signal,
            "bssid": bssid,
            "adapter": desc,
            "localIP": get_local_ip(),
            "onlineTrolleys": online_count
        }
    except Exception as e:
        return {
            "state": "unknown",
            "connected": False,
            "isCloud": False,
            "ssid": "",
            "signal": "0%",
            "bssid": "",
            "adapter": "Unknown",
            "localIP": get_local_ip(),
            "onlineTrolleys": online_count,
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
    if IS_CLOUD_ENV or os.name != 'nt':
        return jsonify({
            "success": True,
            "isCloud": True,
            "profiles": [
                {"ssid": "Cloud Gateway (Render HTTPS)", "hasPassword": False, "password": ""}
            ]
        })

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
            
        return jsonify({"success": True, "profiles": profiles, "isCloud": False})
    except Exception as e:
        return jsonify({"success": False, "profiles": [], "error": str(e), "isCloud": False})

@app.route("/api/wifi/scan", methods=["GET"])
def api_wifi_scan():
    """Scans for nearby visible Wi-Fi networks in range."""
    if IS_CLOUD_ENV or os.name != 'nt':
        return jsonify({
            "success": True,
            "isCloud": True,
            "networks": [],
            "message": "Cloud Gateway Mode: ESP32 trolleys transmit telemetry directly over HTTPS to https://smart-trolley-billing-system.onrender.com"
        })

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
@require_auth(roles=["admin", "manager"])
def api_wifi_connect():
    """Connect the host system to a Wi-Fi network."""
    if IS_CLOUD_ENV or os.name != 'nt':
        return jsonify({
            "success": False,
            "message": "Host Wi-Fi adapter configuration is disabled in Cloud Mode. ESP32 smart trolleys transmit data directly to https://smart-trolley-billing-system.onrender.com"
        }), 400

    data = request.json or {}
    ssid = (data.get("ssid") or "").strip()
    password = (data.get("password") or "").strip()

    if not ssid or not re.match(r'^[A-Za-z0-9_\-\. ]{1,64}$', ssid):
        return jsonify({"success": False, "message": "Valid Wi-Fi SSID is required (alphanumeric, max 64 characters)."}), 400

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
@require_auth(roles=["admin", "manager"])
def api_wifi_disconnect():
    """Disconnect active Wi-Fi connection."""
    if IS_CLOUD_ENV or os.name != 'nt':
        return jsonify({
            "success": False,
            "message": "Network adapter disconnect is disabled on Cloud Server."
        }), 400

    try:
        subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True, text=True, errors='ignore', timeout=5)
        return jsonify({"success": True, "message": "Disconnected from Wi-Fi network."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Disconnect error: {str(e)}"}), 500

@app.route("/api/settings/database", methods=["POST"])
@require_auth(roles=["admin"])
def manage_database():
    data = request.json or {}
    action = data.get("action")
    if action == "seed":
        products_collection.delete_many({})
        inserted = 0
        for p in DEFAULT_PRODUCTS:
            uid_norm = normalize_uid(p["uid"])
            doc = dict(p)
            doc["uid_norm"] = uid_norm
            products_collection.update_one(
                {"uid_norm": uid_norm},
                {"$set": doc},
                upsert=True
            )
            inserted += 1
        return jsonify({"success": True, "message": f"Database seeded with {inserted} default products with verified categories."})

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

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

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
        backup_path = os.path.join(BACKUP_DIR, "backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)
        return jsonify({"success": True, "message": "Database backup completed successfully in secure storage."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Backup failed: {str(e)}"}), 500

@app.route("/api/settings/restore", methods=["POST"])
@require_auth(roles=["admin"])
def db_restore():
    try:
        backup_path = os.path.join(BACKUP_DIR, "backup.json")
        if not os.path.exists(backup_path):
            return jsonify({"success": False, "message": "Backup file (backup.json) not found in secure storage."}), 404
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
        return jsonify({"success": False, "message": "Please enter a valid email address in the form of example@gmail.com."}), 400

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
        return jsonify({"success": False, "message": "Please enter a valid email address in the form of example@gmail.com."}), 400

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

@app.route("/api/feedback", methods=["GET", "POST", "DELETE"])
@app.route("/api/feedback/", methods=["GET", "POST", "DELETE"])
@app.route("/api/feedback/<path:feedback_id>", methods=["DELETE"])
def manage_feedback(feedback_id=None):
    feedback_collection = db["feedback"]
    if request.method == "GET":
        raw_feedbacks = list(feedback_collection.find())
        feedbacks = []
        for f in raw_feedbacks:
            fid = str(f["_id"])
            feedbacks.append({
                "id": fid,
                "_id": fid,
                "rating": f.get("rating", 5),
                "comments": f.get("comments", ""),
                "date": f.get("date", "Today")
            })
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

        raw_comments = (data.get("comments") or "").strip()
        comments = html.escape(raw_comments[:500])
        if not comments:
            comments = "Great shopping experience!"

        feedback_collection.insert_one({
            "rating":   rating,
            "comments": comments,
            "date":     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"success": True, "message": "Feedback submitted successfully"})

    elif request.method == "DELETE":
        from bson import ObjectId

        # Check if user requested bulk clear
        is_clear_all = (
            feedback_id == "all"
            or request.args.get("all") == "true"
            or (request.is_json and request.json and request.json.get("action") == "clear_all")
        )
        if is_clear_all:
            del_result = feedback_collection.delete_many({})
            db['feed'].insert_one({
                "actionType": "FEEDBACK_CLEARED_ALL",
                "count": del_result.deleted_count,
                "timestamp": time.time()
            })
            return jsonify({
                "success": True,
                "message": f"All customer feedback logs ({del_result.deleted_count}) deleted successfully.",
                "deleted_count": del_result.deleted_count
            })

        # Single feedback deletion
        target_id = feedback_id or request.args.get("id") or request.args.get("feedback_id")
        if not target_id and request.is_json and request.json:
            target_id = request.json.get("id") or request.json.get("_id") or request.json.get("feedback_id")

        if not target_id:
            return jsonify({"success": False, "message": "Feedback ID is required for deletion."}), 400

        target_id = str(target_id).strip()
        queries = [{"id": target_id}]
        if ObjectId.is_valid(target_id):
            queries.append({"_id": ObjectId(target_id)})

        res = feedback_collection.delete_one({"$or": queries})
        if res.deleted_count > 0:
            db['feed'].insert_one({
                "actionType": "FEEDBACK_DELETED",
                "feedback_id": target_id,
                "timestamp": time.time()
            })
            return jsonify({
                "success": True,
                "message": "Feedback review deleted successfully."
            })
        return jsonify({"success": False, "message": "Feedback review not found."}), 404

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
                        qty = it.get("quantity", it.get("qty", 1))
                        item_count += qty
                        items_list.append({
                            "rfid": rfid,
                            "name": it.get("name", "Unknown Item"),
                            "price": float(it.get("price", 0.0)),
                            "qty": qty,
                            "quantity": qty,
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
        last_hb = max(float(trolley_doc.get("last_seen", 0) or 0), float(trolley_doc.get("last_heartbeat", 0) or 0)) if trolley_doc else 0
        hb_details = format_heartbeat_status(last_hb, now_ts)
        is_serial_connected = (assigned_trolley_id == SERIAL_TROLLEY_ID and global_ser is not None and global_ser.is_open)
        is_connected = False
        if trolley_doc:
            is_connected = is_serial_connected or ((trolley_doc.get("status") == "online") and (now_ts - float(last_hb or 0) <= OFFLINE_THRESHOLD_SECS))

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
            "battery_level": (trolley_doc.get("battery", trolley_doc.get("battery_level", 0)) if is_connected else None) if trolley_doc else None,
            "battery": (trolley_doc.get("battery", trolley_doc.get("battery_level", 0)) if is_connected else None) if trolley_doc else None,
            "current_mode": (trolley_doc.get("current_mode", "ADD") if is_connected else "OFFLINE") if trolley_doc else "OFFLINE",
            "last_mode": trolley_doc.get("current_mode", "ADD") if trolley_doc else "ADD",
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
    last_heartbeat_time = 0
    last_warn_time = 0
    SERIAL_TROLLEY_ID = "TROLLEY-001"  # Arduino always maps to Trolley-001

    while True:
        cfg = load_config()
        if not cfg.get("enableSerial", True):
            if global_ser and global_ser.is_open:
                try:
                    global_ser.close()
                except:
                    pass
                global_ser = None
            time.sleep(3)
            continue

        BAUD_RATE = int(cfg.get("baudRate", 115200))

        if global_ser is None or not global_ser.is_open:
            try:
                cfg = load_config()
                BAUD_RATE = int(cfg.get("baudRate", 115200))
                global_ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print(f"Connected to hardware serial port on {SERIAL_PORT}")
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
                    sync_target = cfg.get("serverIP") or host_local_ip
                    sync_port = cfg.get("serverPort", 5000 if not str(sync_target).startswith("https") else 443)
                    send_command_to_arduino(f"WIFI_CFG:{sync_ssid}|{sync_pass}|{sync_target}|{sync_port}")
                    print(f"[AUTO-SYNC] Pushed active Wi-Fi ({sync_ssid}) and Target ({sync_target}:{sync_port}) to ESP32 via Serial!")
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
            if now_t - last_heartbeat_time >= 4.0:
                send_command_to_arduino("HEARTBEAT")
                last_heartbeat_time = now_t
        except Exception as e:
            print(f"Heartbeat send error: {e}")

        try:
            line = global_ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                global last_serial_rx_time
                now_ts = time.time()
                last_serial_rx_time = now_ts

                # Mark hardware online on any valid protocol or diagnostics line from firmware
                trolleys_collection.update_one(
                    {"_id": SERIAL_TROLLEY_ID},
                    {"$set": {
                        "status": "online",
                        "connection_status": "connected",
                        "last_seen": now_ts,
                        "last_heartbeat": now_ts,
                        "rfid_ready": True,
                        "lcd_ready": True,
                        "hardware_health": "HEALTHY",
                        "hardware_status": "healthy"
                    }},
                    upsert=True
                )
                print(f"Arduino: {line}")

                if line in ["CONFIRMED_HARDWARE_RESET"] or "[INTENTIONAL_RESET]" in line:
                    # Cart must NEVER be reset without trolley being connected and active
                    if is_trolley_connected(SERIAL_TROLLEY_ID) and global_ser and global_ser.is_open:
                        print(f"[RESET] Verified intentional hardware reset button triggered for connected {SERIAL_TROLLEY_ID}")
                        perform_reset(SERIAL_TROLLEY_ID, force=True)
                        send_command_to_arduino("LCD:Cart Reset!|Total: Rs.0.00")
                        send_command_to_arduino("BEEP:2")
                    else:
                        print(f"[RESET IGNORED] Hardware reset pulse '{line}' ignored because {SERIAL_TROLLEY_ID} is not fully connected. Cart preserved.")
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
                        forward_cart_action_to_cloud(SERIAL_TROLLEY_ID, uid, current_mode)
                    else:
                        print(f"[WARN] Unknown UID Scanned: {uid}")
                        send_command_to_arduino("LCD:Unknown Card!|Check Dashboard")
                        send_command_to_arduino("BEEP:3")
                        forward_cart_action_to_cloud(SERIAL_TROLLEY_ID, uid, current_mode)

        except serial.SerialException as e:
            print(f"Serial connection lost! Reconnecting... Error: {e}")
            last_serial_rx_time = 0.0
            trolleys_collection.update_one(
                {"_id": SERIAL_TROLLEY_ID},
                {"$set": {"status": "offline", "connection_status": "disconnected"}}
            )
            if not IS_CLOUD_ENV and CLOUD_RELAY_URL:
                forward_trolley_offline_to_cloud(SERIAL_TROLLEY_ID)
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

# ── Background Worker Initialization ─────────────────────────────────────────
_threads_started = False

def start_background_workers():
    global _threads_started
    if _threads_started:
        return
    _threads_started = True

    # Offline trolley detection loop
    t_offline = threading.Thread(target=offline_detection_loop, daemon=True)
    t_offline.start()
    print("[WORKER] Started offline trolley detection background thread.")

    # Hardware serial loop (enabled locally by default, disabled in cloud environments like Render)
    enable_serial_env = os.environ.get("ENABLE_SERIAL", "").lower()
    should_enable_serial = (enable_serial_env in ("true", "1")) if enable_serial_env else (not IS_CLOUD_ENV)
    if should_enable_serial:
        t_serial = threading.Thread(target=serial_loop, daemon=True)
        t_serial.start()
        print("[WORKER] Started hardware serial background thread.")
    else:
        print("[WORKER] Cloud/Render environment detected or ENABLE_SERIAL=false — hardware serial thread disabled.")

    # Start Cloud Relay if running locally to keep deployed Render link synchronized
    if not IS_CLOUD_ENV and CLOUD_RELAY_URL:
        t_relay = threading.Thread(target=cloud_relay_loop, daemon=True)
        t_relay.start()
        print(f"[WORKER] Started Cloud Relay background thread targeting {CLOUD_RELAY_URL}.")

# Start workers upon module import (works for both Gunicorn and direct python execution)
start_background_workers()

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
