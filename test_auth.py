"""
Verification script for Smart Trolley Authentication & RBAC
"""
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(r"c:\Users\LOHITH\OneDrive\Desktop\MAIN PROJECT\SmartTrolleyBillingSystem"))

from app import app, users_collection, password_resets_collection, init_users

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

    # 10. Test Public Customer Self-Registration (/api/auth/signup)
    print("\n[TEST 10] Testing Public Customer Self-Registration (/api/auth/signup)...")
    res = client.post("/api/auth/signup", json={
        "username": "customer_jane",
        "password": "custpassword123",
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "9876543210"
    })
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    signup_data = res.get_json()
    assert signup_data.get("success") is True
    assert signup_data["user"]["role"] == "customer"
    cust_token = signup_data.get("token")
    assert cust_token is not None
    print("[PASS] Customer registered successfully with auto-generated JWT token.")

    # 11. Test Privilege Escalation Prevention (Passing role='admin' in /api/auth/signup must be ignored)
    print("\n[TEST 11] Testing Privilege Escalation Prevention on /api/auth/signup...")
    res = client.post("/api/auth/signup", json={
        "username": "hacker_bob",
        "password": "secretpass123",
        "name": "Bob FakeAdmin",
        "role": "admin"  # Attempt to escalate role to admin
    })
    assert res.status_code == 200
    hacker_data = res.get_json()
    assert hacker_data["user"]["role"] == "customer", f"Role was not locked! Got: {hacker_data['user']['role']}"
    print("[PASS] Privilege escalation prevented: Role was strictly locked to 'customer'.")

    # 12. Test Customer Access Restriction (Customer attempting admin endpoint)
    print("\n[TEST 12] Testing Customer Access Restriction to Admin Endpoints...")
    res = client.post("/api/settings/update", json={"serialPort": "COM9"}, headers={"Authorization": f"Bearer {cust_token}"})
    assert res.status_code == 403, f"Expected 403 Forbidden for customer, got {res.status_code}"
    print("[PASS] Customer access to Admin endpoint correctly blocked with 403 Forbidden.")

    # 13. Test Password Length Validation (< 6 chars)
    print("\n[TEST 13] Testing Short Password Validation on /api/auth/signup...")
    res = client.post("/api/auth/signup", json={
        "username": "shortpassuser",
        "password": "123",
        "name": "Short Pass User"
    })
    assert res.status_code == 400
    print("[PASS] Short password correctly rejected with 400 Bad Request.")

    # 14. Test Admin Resetting Employee Password (/api/auth/users/<username>/password)
    print("\n[TEST 14] Testing Admin Password Reset for Employee...")
    res = client.put("/api/auth/users/supercashier1/password", json={"password": "newpass789"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    print("[PASS] Admin successfully reset employee password.")

    # 15. Test Login with New Password
    print("\n[TEST 15] Testing Login with Newly Reset Password...")
    res = client.post("/api/auth/login", json={"username": "supercashier1", "password": "newpass789"})
    assert res.status_code == 200
    new_token = res.get_json()["token"]
    print("[PASS] Employee logged in with newly reset password.")

    # 16. Test User Self Password Change (/api/auth/change-password)
    print("\n[TEST 16] Testing User Changing Own Password...")
    res = client.post("/api/auth/change-password", json={
        "current_password": "newpass789",
        "new_password": "selfchangedpassword123"
    }, headers={"Authorization": f"Bearer {new_token}"})
    assert res.status_code == 200
    print("[PASS] User successfully changed their own password.")

    # 17. Test RBAC: Non-admin attempting to reset another user's password
    print("\n[TEST 17] Testing RBAC on Password Reset (Cashier attempting reset)...")
    res = client.put("/api/auth/users/admin/password", json={"password": "hackpassword"}, headers={"Authorization": f"Bearer {new_token}"})
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}"
    print("[PASS] Non-admin password reset attempt blocked with 403 Forbidden.")

    # 18. Test Admin resetting password via Employee ID (/api/employees/<emp_id>/password)
    print("\n[TEST 18] Testing Admin Password Reset via Employee ID...")
    res = client.put("/api/employees/E001/password", json={"password": "empcustompass123"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    print("[PASS] Admin successfully reset password via Employee ID.")

    # 19. Test Forgot Password - Real OTP Generation (/api/auth/forgot-password/request)
    print("\n[TEST 19] Testing Forgot Password OTP Generation & Real Dispatch...")
    res = client.post("/api/auth/forgot-password/request", json={"identifier": "customer"})
    assert res.status_code == 200
    fp_data = res.get_json()
    assert fp_data.get("success") is True
    assert "channels" in fp_data
    # Retrieve securely generated OTP from database
    reset_record = password_resets_collection.find_one({"username": "customer"})
    assert reset_record is not None
    real_otp = reset_record["otp"]
    assert len(real_otp) == 6
    print(f"[PASS] OTP generated & saved in DB: {real_otp}. Dispatched to: {fp_data.get('masked_target')}")

    # 20. Test Forgot Password - Non-existent Identifier
    print("\n[TEST 20] Testing Forgot Password Non-existent Identifier...")
    res = client.post("/api/auth/forgot-password/request", json={"identifier": "nonexistent_user_999"})
    assert res.status_code == 404
    print("[PASS] Non-existent user rejected with 404.")

    # 21. Test Forgot Password - Invalid OTP Code Verification
    print("\n[TEST 21] Testing Invalid OTP rejection...")
    res = client.post("/api/auth/forgot-password/verify", json={
        "identifier": "customer",
        "otp": "000000",
        "new_password": "customerNewPass123"
    })
    assert res.status_code == 400
    print("[PASS] Invalid OTP rejected with 400.")

    # 22. Test Forgot Password - Valid OTP and Password Reset
    print("\n[TEST 22] Testing Valid OTP Verification & Password Reset...")
    res = client.post("/api/auth/forgot-password/verify", json={
        "identifier": "customer",
        "otp": real_otp,
        "new_password": "customerNewPass123"
    })
    assert res.status_code == 200
    assert res.get_json().get("success") is True
    print("[PASS] Customer password successfully reset via OTP.")

    # 23. Test Login with newly reset password
    print("\n[TEST 23] Testing Customer Login with new password...")
    res = client.post("/api/auth/login", json={"username": "customer", "password": "customerNewPass123"})
    assert res.status_code == 200
    assert res.get_json().get("token") is not None
    print("[PASS] Customer logged in with newly reset password.")

    # 24. Test Notification Settings API (/api/settings/notifications)
    print("\n[TEST 24] Testing Notification Settings API...")
    res = client.get("/api/settings/notifications", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    notif_data = res.get_json()
    assert notif_data.get("success") is True
    print("[PASS] Notification settings retrieved successfully.")

    # Reset customer password back to default 'customer123' for subsequent tests
    client.put("/api/auth/users/customer/password", json={"password": "customer123"}, headers={"Authorization": f"Bearer {admin_token}"})

    # Clean up test users
    client.delete("/api/auth/users/supercashier1", headers={"Authorization": f"Bearer {admin_token}"})
    client.delete("/api/auth/users/customer_jane", headers={"Authorization": f"Bearer {admin_token}"})
    client.delete("/api/auth/users/hacker_bob", headers={"Authorization": f"Bearer {admin_token}"})

    print("\n==================================================")
    print("      ALL AUTHENTICATION & RBAC TESTS PASSED!     ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
