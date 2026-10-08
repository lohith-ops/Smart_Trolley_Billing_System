import json
import time
import sys
import urllib.request
import urllib.error
from pymongo import MongoClient

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

BASE_URL = "http://127.0.0.1:5000"

def http_req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(content)
        except:
            return e.code, {"raw": content}

def get_auth_token(username="admin", password="admin123"):
    status, res = http_req("/api/auth/login", method="POST", data={"username": username, "password": password})
    assert status == 200, f"Login failed: {res}"
    return res["token"]

def run_tests():
    print("=" * 65)
    print("RUNNING COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 65)

    token = get_auth_token("admin", "admin123")

    # -------------------------------------------------------------
    # 1. Customer Registration & Trolley Assignment (Mutual Exclusion)
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Customer Registration & Assignment...")
    
    # Clean up test customers if already exist
    client = MongoClient("mongodb://localhost:27017/")
    db = client["smart_trolley"]
    db["customers"].delete_many({"id": {"$in": ["TEST-CUST-A", "TEST-CUST-B"]}})
    db["customers"].delete_many({"phone": {"$in": ["9876500001", "9876500002"]}})

    # Register customer A
    cust_a_data = {
        "customer_id": "TEST-CUST-A",
        "name": "Arjun Sharma",
        "phone": "9876500001",
        "email": "arjun@example.com"
    }
    status, res = http_req("/api/customers", method="POST", data=cust_a_data, token=token)
    print(f"Register Customer A response: {status}, {res.get('message')}")
    assert status in [200, 201]

    # Register customer B
    cust_b_data = {
        "customer_id": "TEST-CUST-B",
        "name": "Priya Patel",
        "phone": "9876500002",
        "email": "priya@example.com"
    }
    status, res = http_req("/api/customers", method="POST", data=cust_b_data, token=token)
    print(f"Register Customer B response: {status}, {res.get('message')}")
    assert status in [200, 201]

    # Register test trolley
    trolley_id = "TROLLEY-001"
    status, res = http_req("/api/trolley/register", method="POST", data={
        "trolley_id": trolley_id,
        "name": "Smart Trolley 001",
        "firmware_version": "2.1",
        "ip_address": "192.168.1.101"
    })
    assert status == 200

    # First unassign if already assigned
    http_req(f"/api/trolleys/{trolley_id}/unassign", method="POST", token=token)

    # Assign TROLLEY-001 to Customer A
    status, res = http_req(f"/api/trolleys/{trolley_id}/assign", method="POST", data={"customer_id": "TEST-CUST-A"}, token=token)
    assert status == 200, f"Failed to assign: {res}"
    print(f"[OK] Successfully assigned {trolley_id} to Arjun Sharma")

    # MUTUAL EXCLUSION CHECK 1: Try to assign the SAME trolley to Customer B
    status, res = http_req(f"/api/trolleys/{trolley_id}/assign", method="POST", data={"customer_id": "TEST-CUST-B"}, token=token)
    assert status == 400, f"Expected 400 mutual exclusion error, got {status}"
    print(f"[OK] Mutual Exclusion Verified: Cannot assign {trolley_id} to second customer: {res.get('message')}")

    # MUTUAL EXCLUSION CHECK 2: Try to assign another trolley to Customer A (who already has TROLLEY-001)
    status, res = http_req("/api/trolleys/TROLLEY-002/assign", method="POST", data={"customer_id": "TEST-CUST-A"}, token=token)
    assert status == 400
    print(f"[OK] Customer Multi-Trolley Prevention Verified: {res.get('message')}")

    # -------------------------------------------------------------
    # 2. Inventory Management Without Any Connected Trolley
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Inventory Management Independently...")
    
    # Fetch all products
    status, products = http_req("/api/products")
    assert status == 200
    print(f"[OK] Fetched {len(products)} products from inventory catalog.")

    # Register/Update a test product
    test_prod = {
        "uid": "B3 4E 8A 19",
        "name": "Organic Almond Milk 1L",
        "price": 145.0,
        "stock": 35,
        "category": "Dairy",
        "shelf": "Aisle B-2",
        "offer": "Buy 2 Get 5% Off"
    }
    status, res = http_req("/api/products/register", method="POST", data=test_prod, token=token)
    assert status == 200
    print("[OK] Successfully registered product in inventory independent of any trolley connection.")

    # -------------------------------------------------------------
    # 3. Product Scanning, Adding, Stock Update & Cart Persistence
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Product Scanning & Cart Building...")

    # Clear cart initially
    http_req("/api/reset", method="POST", data={"trolley_id": trolley_id})

    # Add 2 units of test product
    status, res = http_req("/api/cart/action", method="POST", data={
        "uid": "B3 4E 8A 19",
        "action": "ADD",
        "trolley_id": trolley_id
    })
    assert status == 200
    assert res["cart"]["total"] == 145.0

    status, res = http_req("/api/cart/action", method="POST", data={
        "uid": "B3 4E 8A 19",
        "action": "ADD",
        "trolley_id": trolley_id
    })
    assert status == 200
    cart_total = res["cart"]["total"]
    assert cart_total == 290.0
    print(f"[OK] Scanned 2 units. Cart Total: Rs.{cart_total:.2f}")

    # -------------------------------------------------------------
    # 4. Disconnection / Wi-Fi Drop / ESP32 Restart / Heartbeat Loss Cart Persistence
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Trolley Disconnection & Cart Survival...")

    # Send heartbeat
    status, res = http_req("/api/trolley/heartbeat", method="POST", data={
        "trolley_id": trolley_id,
        "battery": 92,
        "wifi_rssi": -62,
        "ip_address": "192.168.1.101"
    })
    assert status == 200

    # Check trolley detail: should show 24h timestamp and online
    status, t_data = http_req(f"/api/trolleys/{trolley_id}")
    assert status == 200
    print(f"Online status: {t_data.get('status')}")
    print(f"Dual Assignment status: {t_data.get('assignment_status')} -> {t_data.get('assigned_customer_name')}")
    print(f"Accurate 24h Heartbeat timestamp: {t_data.get('last_heartbeat_time_str')}")
    print(f"Relative elapsed: {t_data.get('last_seen_str')}")
    assert ":" in str(t_data.get("last_heartbeat_time_str"))

    # SIMULATE PHYSICAL DISCONNECTION & HEARTBEAT TIMEOUT:
    db["trolleys"].update_one(
        {"_id": trolley_id},
        {"$set": {"last_heartbeat": time.time() - 65, "last_seen": time.time() - 65, "status": "offline"}}
    )

    # Query /api/trolleys which dynamically verifies heartbeat freshness
    status, t_after_disconnect = http_req(f"/api/trolleys/{trolley_id}")
    print(f"Status after physical disconnect / timeout: {t_after_disconnect.get('status')}")
    print(f"Relative elapsed after disconnect: {t_after_disconnect.get('last_seen_str')}")
    assert t_after_disconnect.get("status") in ["offline", "disconnected"]

    # CRITICAL CHECK: CART AND CUSTOMER MUST REMAIN PRESERVED!
    cart_doc = db["carts"].find_one({"_id": trolley_id})
    print(f"Cart in MongoDB after hardware disconnection: Total=Rs.{cart_doc.get('total')}, Items={cart_doc.get('itemsContained')}")
    assert cart_doc.get("total") == 290.0, f"Cart was reset! Expected 290.0, found {cart_doc.get('total')}"
    assert cart_doc.get("itemsContained") == 2

    # SIMULATE ESP32 REBOOT & WI-FI RECONNECTION:
    status, reg_resp = http_req("/api/trolley/register", method="POST", data={
        "trolley_id": trolley_id,
        "name": "Smart Trolley 001",
        "firmware_version": "2.1",
        "ip_address": "192.168.1.101"
    })
    assert status == 200
    print(f"Register response after reboot: cart count={reg_resp['cart']['item_count']}, total={reg_resp['cart']['total_amount']}, customer={reg_resp['customer']['customer_name']}")
    assert reg_resp["cart"]["total_amount"] == 290.0
    assert reg_resp["customer"]["customer_name"] == "Arjun Sharma"

    # Send heartbeat again
    http_req("/api/trolley/heartbeat", method="POST", data={"trolley_id": trolley_id, "battery": 90})

    # Verify trolley is online again
    status, res = http_req(f"/api/trolleys/{trolley_id}")
    assert res.get("status") == "online"
    print("[OK] Cart, customer, and session survived disconnection, reboot and reconnect perfectly!")

    # -------------------------------------------------------------
    # 5. Dashboard Refresh Check
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Dashboard Refresh Data Integrity...")
    status, dash_data = http_req("/api/dashboard")
    assert status == 200
    active_cart = next((c for c in dash_data["activeCarts"] if c.get("trolley_id") == trolley_id), None)
    assert active_cart is not None
    assert active_cart["total"] == 290.0
    assert active_cart["customer_name"] == "Arjun Sharma"
    print(f"[OK] Dashboard refresh verified: Active cart Rs.{active_cart['total']} bound to {active_cart['customer_name']}")

    # -------------------------------------------------------------
    # 6. Complete Checkout & Stock Persistence
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Checkout, Stock Deduction & Trolley Release...")
    
    # Finalize Checkout
    status, checkout_res = http_req("/api/cart/checkout", method="POST", data={
        "trolley_id": trolley_id,
        "paymentMethod": "UPI",
        "paymentReference": "UPI-REF-998811"
    }, token=token)
    assert status == 200
    print(f"[OK] Checkout finalized! Invoice ID: {checkout_res.get('invoiceId')}, Total: Rs.{checkout_res.get('finalTotal')}")

    # Verify transaction in MongoDB has customer details
    txn = db["transactions"].find_one({"invoiceId": checkout_res.get("invoiceId")})
    assert txn is not None
    assert txn.get("customer_name") == "Arjun Sharma"
    assert txn.get("customer_id") == "TEST-CUST-A"
    print(f"[OK] MongoDB Transaction verified with customer metadata: {txn.get('customer_name')} ({txn.get('customer_id')})")

    # Verify stock permanently updated
    prod_after = db["products"].find_one({"uid": "B3 4E 8A 19"})
    assert prod_after["stock"] == 33, f"Expected stock 33, got {prod_after['stock']}"
    print(f"[OK] Inventory stock permanently saved at {prod_after['stock']} units (2 units deducted from initial 35).")

    # Verify trolley is now released to AVAILABLE
    t_released = db["trolleys"].find_one({"_id": trolley_id})
    assert t_released.get("assignment_status") == "AVAILABLE"
    assert t_released.get("assigned_customer_id") is None
    print(f"[OK] Trolley {trolley_id} released back to AVAILABLE status for next shopper.")

    # -------------------------------------------------------------
    # 7. Customer Auto ID, Unassign, and Credentials Verification
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Credentials, Auto-Generated Customer ID & Unassign...")
    # Verify all four credentials
    for user, pwd, expected_role in [
        ("admin", "admin123", "admin"),
        ("manager", "manager123", "manager"),
        ("cashier", "cashier123", "cashier"),
        ("customer", "customer123", "customer")
    ]:
        st, res = http_req("/api/auth/login", method="POST", data={"username": user, "password": pwd})
        assert st == 200, f"Login failed for {user}: {res}"
        assert res.get("user", {}).get("role") == expected_role
        print(f"[OK] Verified credentials for {user} ({expected_role})")

    # Register customer with auto-generated ID using 'mobile' field
    db["customers"].delete_many({"phone": "9876599999"})
    st, res = http_req("/api/customers", method="POST", data={
        "name": "Kiran Rao",
        "mobile": "9876599999",
        "email": "kiran@example.com"
    }, token=token)
    assert st == 201
    auto_cust = res["customer"]
    auto_id = auto_cust["id"]
    assert auto_id.startswith("CUST-")
    print(f"[OK] Auto-generated Customer ID: {auto_id} for Kiran Rao")

    # Ensure TROLLEY-002 is available before test assignment
    t2_id = "TROLLEY-002"
    http_req(f"/api/trolleys/{t2_id}/unassign", method="POST", token=token)
    st, assign_res = http_req(f"/api/trolleys/{t2_id}/assign", method="POST", data={"customer_id": auto_id}, token=token)
    assert st == 200, f"Failed to assign TROLLEY-002: {assign_res}"

    # Verify /api/dashboard displays TROLLEY-002 even with 0 items because customer is assigned!
    st, dash = http_req("/api/dashboard")
    assigned_t2_cart = next((c for c in dash.get("activeCarts", []) if c.get("trolley_id") == t2_id), None)
    assert assigned_t2_cart is not None, "Assigned cart with 0 items must remain visible on dashboard!"
    assert assigned_t2_cart.get("customer_name") == "Kiran Rao"
    print(f"[OK] Dashboard displays zero-item cart when assigned to customer: {assigned_t2_cart.get('customer_name')}")

    # Test explicit unassign endpoint
    st, un_res = http_req(f"/api/trolleys/{t2_id}/unassign", method="POST", token=token)
    assert st == 200
    t2_doc = db["trolleys"].find_one({"_id": t2_id})
    assert t2_doc.get("assignment_status") == "AVAILABLE"
    assert t2_doc.get("assigned_customer_id") is None
    print(f"[OK] Successfully unassigned {t2_id} via API: {un_res.get('message')}")

    # Clean up test records
    db["customers"].delete_many({"id": {"$in": ["TEST-CUST-A", "TEST-CUST-B", auto_id]}})
    db["products"].delete_many({"uid": "B3 4E 8A 19"})

    print("\n" + "=" * 65)
    print("ALL TESTS PASSED SUCCESSFULLY! 100% VERIFIED.")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
