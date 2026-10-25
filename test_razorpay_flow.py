"""
Test Suite for Razorpay Payment Gateway Integration in Smart Trolley Billing System.
Verifies config retrieval, order creation, signature verification, cart clearance,
and receipt generation.
"""

import sys
import json
import time
import hmac
import hashlib

def run_tests():
    from app import app, carts_collection, products_collection, trolleys_collection, transactions_collection, razorpay_orders_collection

    client = app.test_client()

    print("\n--- 1. Testing GET /api/payment/razorpay/config ---")
    res = client.get("/api/payment/razorpay/config")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    cfg = res.get_json()
    assert cfg.get("success") is True
    assert "keyId" in cfg
    print(f"PASS: Razorpay config retrieved. Key ID: {cfg.get('keyId')}")

    print("\n--- 2. Setting up active cart for TROLLEY-001 ---")
    trolley_id = "TROLLEY-001"
    # Seed a cart with an item
    carts_collection.update_one(
        {"_id": trolley_id},
        {"$set": {
            "items": {
                "5C1E7E05": {
                    "name": "Rice 1kg",
                    "price": 60.0,
                    "quantity": 2,
                    "subtotal": 120.0
                }
            },
            "total": 120.0,
            "itemsContained": 2,
            "status": "ACTIVE"
        }},
        upsert=True
    )
    trolleys_collection.update_one(
        {"_id": trolley_id},
        {"$set": {
            "cart_value": 120.0,
            "item_count": 2,
            "assignment_status": "ASSIGNED",
            "assigned_customer_name": "Test Customer",
            "assigned_customer_phone": "9876543210"
        }},
        upsert=True
    )
    print("PASS: Cart seeded with total Rs. 120.00")

    print("\n--- 3. Testing POST /api/payment/razorpay/create-order ---")
    order_res = client.post("/api/payment/razorpay/create-order", json={
        "trolley_id": trolley_id,
        "phone": "9876543210"
    })
    assert order_res.status_code == 200, f"Expected 200, got {order_res.status_code}: {order_res.get_data(as_text=True)}"
    order_data = order_res.get_json()
    assert order_data.get("success") is True
    assert order_data.get("amount") == 12000, f"Expected 12000 paise, got {order_data.get('amount')}"
    order_id = order_data.get("order_id")
    assert order_id is not None
    print(f"PASS: Razorpay order created successfully! Order ID: {order_id}, Amount: {order_data.get('amount')} paise")

    print("\n--- 4. Testing POST /api/payment/razorpay/verify ---")
    payment_id = f"pay_test_{int(time.time())}"
    from app import load_config
    cfg = load_config()
    key_secret = (cfg.get("razorpayKeySecret") or "").strip()
    if key_secret:
        valid_sig = hmac.new(
            key_secret.encode('utf-8'),
            f"{order_id}|{payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    else:
        valid_sig = "mock_test_signature"

    verify_res = client.post("/api/payment/razorpay/verify", json={
        "trolley_id": trolley_id,
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": order_id,
        "razorpay_signature": valid_sig,
        "phone": "9876543210"
    })
    assert verify_res.status_code == 200, f"Expected 200, got {verify_res.status_code}: {verify_res.get_data(as_text=True)}"
    verify_data = verify_res.get_json()
    assert verify_data.get("success") is True
    assert verify_data.get("payment_id") == payment_id
    assert verify_data.get("invoiceId") is not None
    txn_id = verify_data.get("transaction_id")
    print(f"PASS: Payment verified! Invoice ID: {verify_data.get('invoiceId')}, Txn ID: {txn_id}")

    print("\n--- 5. Verifying Cart is Cleared & Trolley Released ---")
    cart_after = carts_collection.find_one({"_id": trolley_id})
    assert cart_after.get("total") == 0.0, "Cart total was not reset to 0"
    assert cart_after.get("itemsContained") == 0, "Cart item count was not reset to 0"
    print("PASS: Cart successfully reset.")

    trolley_after = trolleys_collection.find_one({"_id": trolley_id})
    assert trolley_after.get("assignment_status") == "AVAILABLE", f"Expected AVAILABLE, got {trolley_after.get('assignment_status')}"
    print("PASS: Trolley status returned to AVAILABLE.")

    print("\n--- 6. Verifying Transaction Record in Database ---")
    tx_doc = transactions_collection.find_one({"invoiceId": verify_data.get("invoiceId")})
    assert tx_doc is not None, "Transaction not found in DB"
    assert tx_doc.get("paymentMethod") == "Razorpay (UPI/Card)"
    assert tx_doc.get("paymentReference") == payment_id
    assert tx_doc.get("verified") is True
    print(f"PASS: Transaction record verified with reference: {tx_doc.get('paymentReference')}")

    print("\n--- 7. Testing Empty Cart Edge Case ---")
    empty_order_res = client.post("/api/payment/razorpay/create-order", json={"trolley_id": trolley_id})
    assert empty_order_res.status_code == 400
    print("PASS: Empty cart correctly rejected with 400 Bad Request.")

    print("\n" + "="*50)
    print("ALL RAZORPAY INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_tests()
