import unittest
from datetime import date
from backend.utils import risk_engine

class TestRiskEngine(unittest.TestCase):

    def test_calculate_days_to_stockout(self):
        # 30 stock / 10 daily usage = 3 days
        self.assertEqual(risk_engine.calculate_days_to_stockout(30, 10.0), 3.0)
        # 0 stock = 0 days
        self.assertEqual(risk_engine.calculate_days_to_stockout(0, 10.0), 0.0)
        # 0 usage = 999 days (no consumption)
        self.assertEqual(risk_engine.calculate_days_to_stockout(50, 0.0), 999.0)

    def test_calculate_expiry_metrics(self):
        ref = date(2026, 8, 25)
        # Expiry in 2 days (2026-08-27)
        res = risk_engine.calculate_expiry_metrics("2026-08-27", ref_date=ref)
        self.assertEqual(res["days_remaining"], 2)
        self.assertTrue(res["is_expiring_soon"])
        self.assertEqual(res["status"], "Critical Expiry")

    def test_classify_demand_trend(self):
        increasing_history = [5.0, 6.0, 7.0, 9.0, 11.0, 14.0, 18.0]
        self.assertEqual(risk_engine.classify_demand_trend(increasing_history), "Increasing")

        stable_history = [10.0, 10.5, 9.8, 10.2, 10.0, 9.9, 10.1]
        self.assertEqual(risk_engine.classify_demand_trend(stable_history), "Stable")

    def test_detect_movement_anomaly(self):
        # Surge: 50 units today vs 10 baseline = 5x surge
        surge = risk_engine.detect_movement_anomaly(50, 10)
        self.assertTrue(surge["has_anomaly"])
        self.assertEqual(surge["type"], "surge")

        # Normal: 12 units today vs 10 baseline
        normal = risk_engine.detect_movement_anomaly(12, 10)
        self.assertFalse(normal["has_anomaly"])

    def test_risk_score_bounds_and_tiers(self):
        ref = date(2026, 8, 25)
        
        # High Risk Product
        critical_prod = {
            "current_stock": 2,
            "min_stock": 20,
            "average_daily_usage": 5.0,
            "today_movement": 25, # surge
            "daily_usage_history": [4, 5, 5, 6, 8, 12, 25],
            "expiry_date": "2026-08-26"
        }
        res = risk_engine.calculate_inventory_risk_score(critical_prod, ref_date=ref)
        self.assertGreaterEqual(res["score"], 81.0)
        self.assertEqual(res["level"], "Critical")

        # Safe Product
        safe_prod = {
            "current_stock": 100,
            "min_stock": 20,
            "average_daily_usage": 2.0,
            "today_movement": 2,
            "daily_usage_history": [2, 2, 2, 2, 2, 2, 2],
            "expiry_date": "2029-12-31"
        }
        res_safe = risk_engine.calculate_inventory_risk_score(safe_prod, ref_date=ref)
        self.assertLessEqual(res_safe["score"], 30.0)
        self.assertEqual(res_safe["level"], "Safe")

    def test_simulate_what_if(self):
        product = {
            "_id": "p1",
            "name": "Test Item",
            "current_stock": 50,
            "min_stock": 20,
            "average_daily_usage": 10.0
        }
        # +50% demand -> daily usage becomes 15.0 -> days to stockout = 50/15 = 3.3
        sim = risk_engine.simulate_what_if(product, 50.0)
        self.assertEqual(sim["adjusted_daily_usage"], 15.0)
        self.assertEqual(sim["new_days_to_stockout"], 3.3)

if __name__ == "__main__":
    unittest.main()
