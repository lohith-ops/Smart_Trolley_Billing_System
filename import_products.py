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
HARDWARE_PRODUCTS = [
    {"uid": "5C 1E 7E 05", "name": "Rice 1kg",   "price": 60.0},
    {"uid": "76 E3 33 06", "name": "Sugar 1kg",  "price": 45.0},
]

# ── UID Normalizer ───────────────────────────────────────────────────────────
def normalize_uid(uid: str) -> str:
    """Uppercase, no spaces/dashes. '5c 1e 7e 05' → '5C1E7E05'"""
    return uid.replace(" ", "").replace("-", "").upper()

# ── Upsert Logic ─────────────────────────────────────────────────────────────
def upsert_product(collection, product: dict) -> str:
    """Insert or update a product by UID. Returns 'inserted' or 'updated'."""
    uid_norm = normalize_uid(product["uid"])
    doc = {
        "uid":   product["uid"],         # keep original format for display
        "name":  product["name"],
        "price": float(product["price"]),
        "uid_norm": uid_norm             # normalized for fast lookup
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
    print(f"  {'UID':<16}  {'Name':<30}  {'Price':>8}")
    print(f"  {'-'*16}  {'-'*30}  {'-'*8}")
    for p in col.find({}, {"_id": 0, "uid_norm": 0}).sort("name", 1):
        print(f"  {p['uid']:<16}  {p['name']:<30}  {p['price']:>8.2f}")

if __name__ == "__main__":
    main()
