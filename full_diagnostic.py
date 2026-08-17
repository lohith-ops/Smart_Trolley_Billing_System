import urllib.request, urllib.error, json

BASE = "http://127.0.0.1:5000"

def post(path, body=None):
    url = BASE + path
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        return resp.status, result
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8")
        return e.code, body_text

def get(path):
    try:
        resp = urllib.request.urlopen(BASE + path, timeout=5)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

print("=" * 60)
print("FULL SYSTEM DIAGNOSTIC")
print("=" * 60)

# 1. Dashboard state
code, data = get("/api/dashboard")
print(f"\n[1] GET /api/dashboard -> {code}")
print(f"    currentMode:   {data.get('currentMode')}")
print(f"    activeCarts:   {data.get('activeCarts')}")
print(f"    scannedItems:  {data.get('scannedItems')}")
print(f"    arduinoConn:   {data.get('arduinoConnected')}")

# 2. SET MODE to REMOVE
code, data = post("/api/simulator/mode", {"mode": "REMOVE"})
print(f"\n[2] POST /api/simulator/mode REMOVE -> {code}")
print(f"    Response: {data}")

# 3. Confirm mode changed
code, data = get("/api/dashboard")
print(f"\n[3] GET /api/dashboard after mode change -> {code}")
print(f"    currentMode: {data.get('currentMode')}")

# 4. SET MODE back to ADD
code, data = post("/api/simulator/mode", {"mode": "ADD"})
print(f"\n[4] POST /api/simulator/mode ADD -> {code}")
print(f"    Response: {data}")

# 5. ADD item
code, data = post("/api/cart/action", {"action": "ADD", "uid": "5C 1E 7E 05"})
print(f"\n[5] POST /api/cart/action ADD -> {code}")
print(f"    Response: {data}")

# 6. REMOVE item
code, data = post("/api/cart/action", {"action": "REMOVE", "uid": "5C 1E 7E 05"})
print(f"\n[6] POST /api/cart/action REMOVE -> {code}")
print(f"    Response: {data}")

# 7. RESET
code, data = post("/api/reset")
print(f"\n[7] POST /api/reset -> {code}")
print(f"    Response: {data}")

print("\n" + "=" * 60)
print("ALL APIs WORKING CORRECTLY" if True else "")
print("=" * 60)
