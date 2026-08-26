import unittest
import json
import time
from app import app, db, products_collection, carts_collection, transactions_collection, trolleys_collection, init_trolleys

class MultiTrolleyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Seed fresh data
        init_trolleys()

    def test_01_default_trolleys_exist(self):
        """Verify TROLLEY-001, TROLLEY-002, TROLLEY-003 are initialized."""
        res = self.app.get('/api/trolleys')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        trolley_ids = [t['id'] for t in data]
        self.assertIn('TROLLEY-001', trolley_ids)
        self.assertIn('TROLLEY-002', trolley_ids)
        self.assertIn('TROLLEY-003', trolley_ids)
        print("[OK] Test 1 Passed: Default trolleys exist in registry.")

    def test_02_heartbeat_and_online_status(self):
        """Verify heartbeat updates device health (battery, RSSI, IP) and sets status online."""
        payload = {
            "trolley_id": "TROLLEY-001",
            "battery": 88,
            "wifi_rssi": -62,
            "ip_address": "192.168.1.101",
            "firmware_version": "2.0"
        }
        res = self.app.post('/api/trolley/heartbeat', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify trolley detail reflects online & health info
        res_detail = self.app.get('/api/trolleys/TROLLEY-001')
        self.assertEqual(res_detail.status_code, 200)
        t_data = res_detail.get_json()
        self.assertEqual(t_data['status'], 'online')
        self.assertEqual(t_data['battery'], 88)
        self.assertEqual(t_data['wifi_rssi'], -62)
        self.assertEqual(t_data['ip_address'], "192.168.1.101")
        print("[OK] Test 2 Passed: Heartbeat updates device health and marks trolley online.")

    def test_03_independent_carts_for_multiple_trolleys(self):
        """Verify scanning on TROLLEY-001, TROLLEY-002, and TROLLEY-003 maintain completely independent carts."""
        # Reset all carts first
        for tid in ["TROLLEY-001", "TROLLEY-002", "TROLLEY-003"]:
            self.app.post('/api/cart/reset', data=json.dumps({"trolley_id": tid}), content_type='application/json')

        # Add Rice to TROLLEY-001
        res1 = self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-001",
            "action": "ADD",
            "uid": "5C 1E 7E 05" # Rice 1kg, price 60.0
        }), content_type='application/json')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.get_json()['cart']['total'], 60.0)

        # Add Sugar (45.0) twice to TROLLEY-002
        self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-002",
            "action": "ADD",
            "uid": "76 E3 33 06" # Sugar 1kg
        }), content_type='application/json')
        res2 = self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-002",
            "action": "ADD",
            "uid": "76 E3 33 06" # Sugar 1kg
        }), content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()['cart']['total'], 90.0)

        # Add Bread (25.0) to TROLLEY-003
        res3 = self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-003",
            "action": "ADD",
            "uid": "A3 B4 C5 D6" # Whole Wheat Bread
        }), content_type='application/json')
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.get_json()['cart']['total'], 25.0)

        # Check cart 1
        c1 = self.app.get('/api/trolleys/TROLLEY-001/cart').get_json()
        self.assertEqual(c1['total'], 60.0)
        self.assertEqual(c1['itemsContained'], 1)

        # Check cart 2
        c2 = self.app.get('/api/trolleys/TROLLEY-002/cart').get_json()
        self.assertEqual(c2['total'], 90.0)
        self.assertEqual(c2['itemsContained'], 2)

        # Check cart 3
        c3 = self.app.get('/api/trolleys/TROLLEY-003/cart').get_json()
        self.assertEqual(c3['total'], 25.0)
        self.assertEqual(c3['itemsContained'], 1)

        print("[OK] Test 3 Passed: 3 trolleys maintain completely isolated carts and running totals.")

    def test_04_centralized_global_inventory(self):
        """Verify stock is global and reduced regardless of which trolley scans the product."""
        # Find current stock of Rice
        p_initial = products_collection.find_one({"name": "Rice 1kg"})
        initial_stock = p_initial.get('stock', 20)

        # Scan Rice in TROLLEY-001
        self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-001",
            "action": "ADD",
            "uid": "5C 1E 7E 05"
        }), content_type='application/json')

        # Stock should decrease by 1
        p_after_1 = products_collection.find_one({"name": "Rice 1kg"})
        self.assertEqual(p_after_1['stock'], initial_stock - 1)

        # Scan Rice in TROLLEY-002
        self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-002",
            "action": "ADD",
            "uid": "5C 1E 7E 05"
        }), content_type='application/json')

        # Stock should decrease by another 1
        p_after_2 = products_collection.find_one({"name": "Rice 1kg"})
        self.assertEqual(p_after_2['stock'], initial_stock - 2)
        print("[OK] Test 4 Passed: Centralized global inventory correctly shared across all trolleys.")

    def test_05_independent_checkout_and_transactions(self):
        """Verify checking out TROLLEY-001 records transaction with trolley_id and clears only TROLLEY-001's cart."""
        # Checkout TROLLEY-001 via /api/cart/pay
        res_pay = self.app.post('/api/cart/pay', data=json.dumps({
            "trolley_id": "TROLLEY-001",
            "paymentMethod": "UPI"
        }), content_type='application/json')
        self.assertEqual(res_pay.status_code, 200)
        self.assertTrue(res_pay.get_json()['success'])

        # Cart 1 should now be empty
        c1 = self.app.get('/api/trolleys/TROLLEY-001/cart').get_json()
        self.assertEqual(c1['itemsContained'], 0)
        self.assertEqual(c1['total'], 0.0)

        # Cart 2 should still have its items untouched!
        c2 = self.app.get('/api/trolleys/TROLLEY-002/cart').get_json()
        self.assertGreater(c2['itemsContained'], 0)

        # Check transactions list contains trolley_id = TROLLEY-001
        txs = self.app.get('/api/transactions?trolley_id=TROLLEY-001').get_json()
        self.assertGreater(len(txs), 0)
        self.assertEqual(txs[0]['trolley_id'], 'TROLLEY-001')
        print("[OK] Test 5 Passed: Independent checkout and transactions recorded with trolley_id.")

    def test_06_add_future_trolley_auto_registration(self):
        """Verify adding TROLLEY-004 automatically registers without core backend redesign."""
        res_hb = self.app.post('/api/trolley/heartbeat', data=json.dumps({
            "trolley_id": "TROLLEY-004",
            "name": "Smart Trolley 004",
            "battery": 95,
            "wifi_rssi": -50,
            "ip_address": "192.168.1.104",
            "firmware_version": "2.0"
        }), content_type='application/json')
        self.assertEqual(res_hb.status_code, 200)

        # Query all trolleys
        trolleys = self.app.get('/api/trolleys').get_json()
        trolley_ids = [t['id'] for t in trolleys]
        self.assertIn('TROLLEY-004', trolley_ids)

        # Cart operation on TROLLEY-004
        res_act = self.app.post('/api/cart/action', data=json.dumps({
            "trolley_id": "TROLLEY-004",
            "action": "ADD",
            "uid": "11 22 33 44" # Milk
        }), content_type='application/json')
        self.assertEqual(res_act.status_code, 200)
        self.assertEqual(res_act.get_json()['trolley_id'], 'TROLLEY-004')
        print("[OK] Test 6 Passed: Dynamic addition of future trolleys (TROLLEY-004, etc.) supported effortlessly.")

if __name__ == '__main__':
    unittest.main()
