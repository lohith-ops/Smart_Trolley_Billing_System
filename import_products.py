"""
import_products.py — Smart Trolley Product Importer
=====================================================
Imports products into MongoDB from:
  1. A JSON file (dataset.json from SmartTrolley_Python or any path)
  2. Built-in real RFID-scanned items (Rice, Sugar — confirmed UIDs from hardware)

Run:
    python import_products.py                    # import all sources
    python import_products.py --clear            # wipe products first, then import
    python import_products.py --list             # just show what's in DB

Rules:
  - UIDs are normalized (uppercase, no spaces) for matching
  - Existing products (same UID) are UPDATED, not duplicated
  - New products are INSERTED
"""

import json
import os
import sys
import argparse
from pymongo import MongoClient

# ── Config ──────────────────────────────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "smart_trolley"

# Path to the source dataset.json (relative or absolute)
DATASET_PATH = r"C:\Users\LOHITH\OneDrive\Desktop\MAIN PROJECT\SmartTrolley_Python\dataset.json"

# Real RFID-scanned products confirmed from hardware serial output
# Add more here as you scan new RFID cards
# Real RFID-scanned products confirmed from hardware serial output with commercial fields
HARDWARE_PRODUCTS = [
    {"uid": "5C 1E 7E 05", "name": "Rice 1kg", "price": 60.0, "category": "Grains", "stock": 45, "shelf": "Aisle A - Shelf 1", "offer": "Buy 1 Get 1 Free"},
    {"uid": "76 E3 33 06", "name": "Sugar 1kg", "price": 45.0, "category": "Grains", "stock": 12, "shelf": "Aisle A - Shelf 2", "offer": "No Active Offers"},
]

# ── UID Normalizer ───────────────────────────────────────────────────────────
def normalize_uid(uid: str) -> str:
    """Uppercase, no spaces/dashes. '5c 1e 7e 05' → '5C1E7E05'"""
    return uid.replace(" ", "").replace("-", "").upper()

# ── Upsert Logic ─────────────────────────────────────────────────────────────
def upsert_product(collection, product: dict) -> str:
    """Insert or update a product by UID. Returns 'inserted' or 'updated'."""
    uid_norm = normalize_uid(product["uid"])
    
    # Predefined fields for standard products if not provided in JSON
    category = product.get("category")
    if not category:
        name_lower = product["name"].lower()
        if "bread" in name_lower: category = "Bakery"
        elif "milk" in name_lower: category = "Dairy"
        elif "cheese" in name_lower: category = "Dairy"
        elif "eggs" in name_lower: category = "Dairy"
        elif "apple" in name_lower or "fruit" in name_lower: category = "Produce"
        else: category = "Grocery"
        
    stock = product.get("stock")
    if stock is None:
        name_lower = product["name"].lower()
        if "bread" in name_lower: stock = 8
        elif "milk" in name_lower: stock = 32
        elif "cheese" in name_lower: stock = 15
        elif "eggs" in name_lower: stock = 24
        else: stock = 25

    shelf = product.get("shelf")
    if not shelf:
        name_lower = product["name"].lower()
        if "bread" in name_lower: shelf = "Aisle B - Shelf 1"
        elif "milk" in name_lower or "cheese" in name_lower or "eggs" in name_lower: shelf = "Aisle C - Shelf 1"
        else: shelf = "Aisle D - Shelf 3"

    offer = product.get("offer")
    if not offer:
        name_lower = product["name"].lower()
        if "bread" in name_lower: offer = "10% Off"
        elif "cheese" in name_lower: offer = "20% Off"
        else: offer = "No Active Offers"

    doc = {
        "uid":   product["uid"],
        "name":  product["name"],
        "price": float(product["price"]),
        "uid_norm": uid_norm,
        "stock": int(stock),
        "shelf": shelf,
        "category": category,
        "offer": offer
    }
    result = collection.update_one(
        {"uid_norm": uid_norm},          # match by normalized UID
        {"$set": doc},
        upsert=True
    )
    return "inserted" if result.upserted_id else "updated"

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Smart Trolley Product Importer")
    parser.add_argument("--clear", action="store_true", help="Clear all products before importing")
    parser.add_argument("--list",  action="store_true", help="List current products in DB and exit")
    parser.add_argument("--file",  type=str, default=DATASET_PATH, help="Path to dataset JSON file")
    args = parser.parse_args()

    # Connect
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        client.server_info()  # test connection
    except Exception as e:
        print(f"[ERR] Cannot connect to MongoDB at {MONGO_URI}")
        print(f"    Error: {e}")
        print("    -> Make sure MongoDB is running: net start MongoDB")
        sys.exit(1)

    db = client[DB_NAME]
    col = db["products"]

    # ── List mode ──────────────────────────────────────────────────────────
    if args.list:
        products = list(col.find({}, {"_id": 0, "uid_norm": 0}))
        if not products:
            print("[WARN] No products in database.")
        else:
            print(f"\n{'UID':<16}  {'Name':<30}  {'Price':>8}")
            print("-" * 58)
            for p in products:
                print(f"{p['uid']:<16}  {p['name']:<30}  {p['price']:>8.2f}")
            print(f"\nTotal: {len(products)} product(s)")
        return

    # ── Clear mode ─────────────────────────────────────────────────────────
    if args.clear:
        count = col.count_documents({})
        col.delete_many({})
        print(f"[CLEAR] Cleared {count} existing product(s) from database.")

    inserted = 0
    updated  = 0
    errors   = 0

    # ── Import from JSON file ──────────────────────────────────────────────
    json_path = args.file
    if os.path.exists(json_path):
        print(f"\n[LOAD] Loading from: {json_path}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                file_products = json.load(f)
            print(f"    Found {len(file_products)} product(s) in file.")
            for p in file_products:
                if "uid" not in p or "name" not in p or "price" not in p:
                    print(f"    [WARN] Skipping invalid entry: {p}")
                    errors += 1
                    continue
                action = upsert_product(col, p)
                print(f"    {'[OK] Inserted' if action == 'inserted' else '[UPDATE] Updated ':11}  {p['uid']:<16}  {p['name']}")
                if action == "inserted": inserted += 1
                else: updated += 1
        except json.JSONDecodeError as e:
            print(f"    [ERR] JSON parse error: {e}")
        except Exception as e:
            print(f"    [ERR] Error reading file: {e}")
    else:
        print(f"\n[WARN] JSON file not found: {json_path}")
        print("    Skipping file import. Use --file <path> to specify a different path.")

    # -- Import hardware-confirmed RFID products ----------------------------
    print(f"\n[HW] Importing hardware-confirmed RFID products ({len(HARDWARE_PRODUCTS)} items)...")
    for p in HARDWARE_PRODUCTS:
        action = upsert_product(col, p)
        print(f"    {'[OK] Inserted' if action == 'inserted' else '[UPDATE] Updated ':11}  {p['uid']:<16}  {p['name']}")
        if action == "inserted": inserted += 1
        else: updated += 1

    # ── Seed Employees & Feedback ────────────────────────────────────────────
    print("\n[SEED] Seeding Employee Directory...")
    employees_col = db["employees"]
    if args.clear:
        employees_col.delete_many({})
    
    default_employees = [
        {"id": "E001", "name": "Rohit Sharma", "role": "Admin", "shift": "Morning (08:00 AM - 04:00 PM)", "status": "Active"},
        {"id": "E002", "name": "Ananya Sen", "role": "Manager", "shift": "Evening (04:00 PM - 12:00 AM)", "status": "Active"},
        {"id": "E003", "name": "Vikram Malhotra", "role": "Cashier", "shift": "Morning (08:00 AM - 04:00 PM)", "status": "Active"},
        {"id": "E004", "name": "Priya Nair", "role": "Inventory Staff", "shift": "Night (12:00 AM - 08:00 AM)", "status": "Active"}
    ]
    for emp in default_employees:
        employees_col.update_one({"id": emp["id"]}, {"$set": emp}, upsert=True)
    print(f"    Seeded {len(default_employees)} employee records.")

    print("\n[SEED] Seeding Customer Feedback Logs...")
    feedback_col = db["feedback"]
    if args.clear:
        feedback_col.delete_many({})
    
    default_feedback = [
        {"rating": 5, "comments": "Fastest checkout experience ever! Loving the RFID trolley.", "date": "Just now"},
        {"rating": 4, "comments": "Very clean dashboard and responsive, but we need more trolleys.", "date": "Yesterday"},
        {"rating": 5, "comments": "No queue at billing is a huge relief.", "date": "2 days ago"}
    ]
    if feedback_col.count_documents({}) == 0:
        feedback_col.insert_many(default_feedback)
    print(f"    Seeded default customer feedback.")

    # ── Summary ────────────────────────────────────────────────────────────
    total = col.count_documents({})
    print(f"\n{'-'*45}")
    print(f"  [OK] Inserted : {inserted}")
    print(f"  [UPDATE] Updated  : {updated}")
    print(f"  [ERROR] Errors   : {errors}")
    print(f"  [DB] Total in DB : {total} product(s)")
    print(f"{'-'*45}\n")

    # Show final state
    print("Current product catalog:")
    print(f"  {'UID':<16}  {'Name':<30}  {'Price':>8}  {'Stock':<6}  {'Category':<10}")
    print(f"  {'-'*16}  {'-'*30}  {'-'*8}  {'-'*6}  {'-'*10}")
    for p in col.find({}, {"_id": 0, "uid_norm": 0}).sort("name", 1):
        print(f"  {p['uid']:<16}  {p['name']:<30}  {p['price']:>8.2f}  {p.get('stock', 0):<6}  {p.get('category', ''):<10}")

if __name__ == "__main__":
    main()
