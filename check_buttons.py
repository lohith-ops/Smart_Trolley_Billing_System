import urllib.request, json, re

resp = urllib.request.urlopen("http://127.0.0.1:5000/", timeout=5)
html = resp.read().decode("utf-8")

scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
print("Scripts:", scripts)

for btn_id in ["reset-btn", "main-reset-btn", "sim-reset-btn", "sim-scan-btn", "checkout-btn"]:
    found = ('id="' + btn_id + '"') in html or ("id='" + btn_id + "'") in html
    print("  id=" + btn_id + ": " + ("FOUND" if found else "MISSING"))

# Check if dashboard.js is served correctly
try:
    r2 = urllib.request.urlopen("http://127.0.0.1:5000/dashboard.js", timeout=5)
    js = r2.read().decode("utf-8")
    print("\ndashboard.js served: YES, length=" + str(len(js)))
    print("  initDashboard defined:", "function initDashboard" in js)
    print("  resetCart defined:", "function resetCart" in js)
    print("  DOMContentLoaded used:", "DOMContentLoaded" in js)
    print("  main-reset-btn referenced:", "main-reset-btn" in js)
except Exception as e:
    print("dashboard.js error:", str(e))
