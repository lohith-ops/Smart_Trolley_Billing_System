"""
Verification script for Smart Trolley Authentication & RBAC
"""
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(r"c:\Users\LOHITH\OneDrive\Desktop\MAIN PROJECT\SmartTrolleyBillingSystem"))

from app import app, users_collection, init_users

def run_tests():
    print("==================================================")
    print("      RUNNING SMART TROLLEY AUTH & RBAC TESTS     ")
    print("==================================================")
    
    client = app.test_client()

    # 1. Test Login with Valid Admin Credentials
    print("\n[TEST 1] Testing Admin Login...")
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    data = res.get_json()
    assert data.get("success") is True
    admin_token = data.get("token")
    assert admin_token is not None
    print(f"[PASS] Admin Login Successful. Token received: {admin_token[:20]}...")

    # 2. Test Login with Cashier Credentials
    print("\n[TEST 2] Testing Cashier Login...")
    res = client.post("/api/auth/login", json={"username": "cashier", "password": "cashier123"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    data = res.get_json()
    cashier_token = data.get("token")
    assert cashier_token is not None
    print("[PASS] Cashier Login Successful.")

    # 3. Test Invalid Credentials
    print("\n[TEST 3] Testing Invalid Password rejection...")
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("[PASS] Invalid Password rejected correctly with 401.")

    # 4. Test /api/auth/me with Admin Token
    print("\n[TEST 4] Testing /api/auth/me session validation...")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    print("[PASS] Session validated successfully for Admin.")

    # 5. Test Unauthenticated Access to Protected Endpoint
    print("\n[TEST 5] Testing Unauthenticated Access to /api/settings/update...")
    res = client.post("/api/settings/update", json={"serialPort": "COM3"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("[PASS] Unauthenticated access blocked with 401.")

    # 6. Test RBAC: Cashier attempting Admin-only endpoint
    print("\n[TEST 6] Testing RBAC (Cashier attempting /api/settings/update)...")
    res = client.post("/api/settings/update", json={"serialPort": "COM3"}, headers={"Authorization": f"Bearer {cashier_token}"})
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.data}"
    print("[PASS] Cashier access to Settings forbidden with 403.")

    # 7. Test RBAC: Admin accessing Settings endpoint
    print("\n[TEST 7] Testing Admin Access to /api/settings/update...")
    res = client.post("/api/settings/update", json={"serialPort": "COM3"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print("[PASS] Admin access to Settings granted with 200.")

    # 8. Test Admin registering a new employee/user
    print("\n[TEST 8] Testing User Registration by Admin...")
    res = client.post("/api/auth/register", json={
        "username": "supercashier1",
        "password": "pass123456",
        "name": "Alex Smith",
        "role": "cashier",
        "email": "alex@smarttrolley.local"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    print("[PASS] New user registered successfully by Admin.")

    # 9. Test Login with the newly registered user
    print("\n[TEST 9] Testing Login with newly registered user...")
    res = client.post("/api/auth/login", json={"username": "supercashier1", "password": "pass123456"})
    assert res.status_code == 200
    new_user_data = res.get_json()
    assert new_user_data["user"]["name"] == "Alex Smith"
    print("[PASS] Newly registered user authenticated successfully.")

    # Clean up test user
    client.delete("/api/auth/users/supercashier1", headers={"Authorization": f"Bearer {admin_token}"})

    print("\n==================================================")
    print("      ALL AUTHENTICATION & RBAC TESTS PASSED!     ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
