import urllib.request
import json

def test():
    # 1. Page load
    res = urllib.request.urlopen('http://127.0.0.1:5000/customer-portal.html')
    assert res.status == 200, 'Page failed'
    print('[OK] customer-portal.html served successfully (200)')

    # 2. Customer profile
    res = urllib.request.urlopen('http://127.0.0.1:5000/api/customer/profile?customer_id=CUST-1001')
    p = json.loads(res.read().decode('utf-8'))
    assert p['success'] == True, 'Profile failed'
    cust = p['customer']
    print(f"[OK] Customer profile loaded: {cust['name']} (Tier: {cust['tier']}, Points: {cust['points']}, Spent: Rs.{cust['total_spent']})")

    # 3. Wishlist Add
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/customer/wishlist?customer_id=CUST-1001',
        data=json.dumps({'name': 'Dark Chocolate 100g', 'price': 90.0, 'category': 'Snacks', 'shelf': 'Aisle D'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    w = json.loads(res.read().decode('utf-8'))
    assert w['success'] == True, 'Wishlist add failed'
    print(f"[OK] Wishlist add success: count={len(w['wishlist'])}")

    # 4. Wishlist Remove
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/customer/wishlist?customer_id=CUST-1001',
        data=json.dumps({'name': 'Dark Chocolate 100g'}).encode(),
        headers={'Content-Type': 'application/json'},
        method='DELETE'
    )
    res = urllib.request.urlopen(req)
    w2 = json.loads(res.read().decode('utf-8'))
    assert w2['success'] == True, 'Wishlist remove failed'
    print(f"[OK] Wishlist remove success: count={len(w2['wishlist'])}")

    # 5. Feedback submission
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/feedback',
        data=json.dumps({'rating': 5, 'comments': 'Fantastic live trolley cart updates!'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    fb = json.loads(res.read().decode('utf-8'))
    assert fb['success'] == True, 'Feedback failed'
    print('[OK] Customer feedback submitted successfully')

    # 6. Check Active Trolley data if assigned
    if p.get('active_trolley'):
        at = p['active_trolley']
        print(f"[OK] Active Trolley details present: {at['trolley_id']}, connected={at['is_connected']}, items={len(at['items'])}, mode={at['current_mode']}")

if __name__ == '__main__':
    test()
