import unittest
from backend.utils import view_helpers, risk_engine
from backend.services.inventory_service import InventoryService

class TestPythonArchitecture(unittest.TestCase):
    def setUp(self):
        self.service = InventoryService()
        self.sample_product = {
            "_id": "test-prod-101",
            "name": "Surgical Nitrile Gloves",
            "category": "Medical Supplies",
            "current_stock": 5,
            "min_stock": 20,
            "max_stock": 100,
            "unit_price": 45.50,
            "unit": "Boxes",
            "average_daily_usage": 3.0,
            "today_movement": 12,
            "daily_usage_history": [2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5],
            "expiry_date": "2026-10-15",
            "risk_level": "CRITICAL"
        }

    def test_01_present_product_formatting(self):
        """Test that present_product creates all expected Python view-model attributes."""
        presented = view_helpers.present_product(self.sample_product)
        self.assertEqual(presented["status_label"], "Low Stock")
        self.assertEqual(presented["status_class"], "status-low-stock")
        self.assertEqual(presented["badge_class"], "badge-warning")
        self.assertEqual(presented["formatted_unit_price"], "$45.50")
        self.assertEqual(presented["formatted_total_value"], "$227.50")
        self.assertTrue(presented["requires_reorder"])

    def test_02_present_alert_formatting(self):
        """Test present_alert generates correct border_class and labels in Python."""
        raw_alert = {
            "id": "alert-1",
            "product_id": "test-prod-101",
            "product_name": "Surgical Nitrile Gloves",
            "type": "Low Stock",
            "severity": "High Risk",
            "timestamp": "2026-09-14T10:00:00"
        }
        presented = view_helpers.present_alert(raw_alert)
        self.assertIn("medium-risk-alert", presented["border_class"])
        self.assertEqual(presented["badge_class"], "badge-warning")

    def test_03_present_transaction_formatting(self):
        """Test present_transaction formats transaction types and timestamps in Python."""
        raw_tx = {
            "id": "tx-001",
            "product_id": "test-prod-101",
            "type": "STOCK_IN",
            "quantity_changed": 50,
            "timestamp": "2026-09-14T12:00:00"
        }
        presented = view_helpers.present_transaction(raw_tx)
        self.assertEqual(presented["type_badge_class"], "badge-success")
        self.assertEqual(presented["type_label"], "Stock In (+)")

    def test_04_inventory_service_presents_products(self):
        """Test InventoryService returns presented product dicts with pre-computed attributes."""
        products = self.service.get_all_products()
        if products:
            first = products[0]
            self.assertIn("status_class", first)
            self.assertIn("risk_class", first)
            self.assertIn("formatted_unit_price", first)

if __name__ == "__main__":
    unittest.main()
