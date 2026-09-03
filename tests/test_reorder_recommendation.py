import unittest
from backend.utils.risk_engine import calculate_reorder_recommendation, get_reorder_recommendations

class TestSmartReorderRecommendation(unittest.TestCase):

    def test_stock_below_minimum(self):
        prod = {"current_stock": 10, "min_stock": 30, "risk_level": "CRITICAL"}
        res = calculate_reorder_recommendation(prod)
        self.assertEqual(res["stock_deficit"], 20)
        self.assertEqual(res["recommended_reorder"], 20)
        self.assertEqual(res["recommended_action"], "REORDER IMMEDIATELY")
        self.assertTrue(res["requires_reorder"])

    def test_stock_equal_to_minimum(self):
        prod = {"current_stock": 30, "min_stock": 30, "risk_level": "WARNING"}
        res = calculate_reorder_recommendation(prod)
        self.assertEqual(res["stock_deficit"], 0)
        self.assertEqual(res["recommended_reorder"], 0)
        self.assertEqual(res["recommended_action"], "NO REORDER REQUIRED")
        self.assertFalse(res["requires_reorder"])

    def test_stock_above_minimum(self):
        prod = {"current_stock": 50, "min_stock": 30, "risk_level": "SAFE"}
        res = calculate_reorder_recommendation(prod)
        self.assertEqual(res["stock_deficit"], 0)
        self.assertEqual(res["recommended_reorder"], 0)
        self.assertEqual(res["recommended_action"], "NO REORDER REQUIRED")
        self.assertFalse(res["requires_reorder"])

    def test_zero_stock(self):
        prod = {"current_stock": 0, "min_stock": 25, "risk_level": "CRITICAL"}
        res = calculate_reorder_recommendation(prod)
        self.assertEqual(res["stock_deficit"], 25)
        self.assertEqual(res["recommended_reorder"], 25)
        self.assertEqual(res["recommended_action"], "REORDER IMMEDIATELY")

    def test_zero_minimum_stock(self):
        prod = {"current_stock": 15, "min_stock": 0, "risk_level": "SAFE"}
        res = calculate_reorder_recommendation(prod)
        self.assertEqual(res["stock_deficit"], 0)
        self.assertEqual(res["recommended_reorder"], 0)
        self.assertEqual(res["recommended_action"], "NO REORDER REQUIRED")

    def test_missing_and_invalid_values(self):
        # Missing keys
        prod_empty = {}
        res = calculate_reorder_recommendation(prod_empty)
        self.assertEqual(res["recommended_reorder"], 0)
        self.assertEqual(res["recommended_action"], "NO REORDER REQUIRED")

        # Invalid string values
        prod_invalid = {"current_stock": "invalid", "min_stock": "invalid_min", "risk_level": "HIGH"}
        res_inv = calculate_reorder_recommendation(prod_invalid)
        self.assertEqual(res_inv["recommended_reorder"], 0)
        self.assertEqual(res_inv["recommended_action"], "NO REORDER REQUIRED")

    def test_risk_level_action_mapping(self):
        # Critical
        c_res = calculate_reorder_recommendation({"current_stock": 5, "min_stock": 20}, risk_level="CRITICAL")
        self.assertEqual(c_res["recommended_action"], "REORDER IMMEDIATELY")

        # High
        h_res = calculate_reorder_recommendation({"current_stock": 5, "min_stock": 20}, risk_level="HIGH")
        self.assertEqual(h_res["recommended_action"], "REORDER SOON")

        # Warning
        w_res = calculate_reorder_recommendation({"current_stock": 5, "min_stock": 20}, risk_level="WARNING")
        self.assertEqual(w_res["recommended_action"], "MONITOR & PLAN REORDER")

        # Safe
        s_res = calculate_reorder_recommendation({"current_stock": 5, "min_stock": 20}, risk_level="SAFE")
        self.assertEqual(s_res["recommended_action"], "NO REORDER REQUIRED")

    def test_reorder_recommendations_sorting_order(self):
        items = [
            {"name": "Safe Item", "current_stock": 100, "min_stock": 20, "risk_level": "SAFE"},
            {"name": "Warning Item", "current_stock": 15, "min_stock": 20, "risk_level": "WARNING"},
            {"name": "Critical Item", "current_stock": 2, "min_stock": 20, "risk_level": "CRITICAL"},
            {"name": "High Risk Item", "current_stock": 5, "min_stock": 20, "risk_level": "HIGH"},
        ]
        recs = get_reorder_recommendations(items)
        self.assertEqual(len(recs), 4)
        self.assertEqual(recs[0]["name"], "Critical Item")
        self.assertEqual(recs[1]["name"], "High Risk Item")
        self.assertEqual(recs[2]["name"], "Warning Item")
        self.assertEqual(recs[3]["name"], "Safe Item")

if __name__ == "__main__":
    unittest.main()
