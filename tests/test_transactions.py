import unittest
from backend.services.inventory_service import InventoryService

class TestInventoryTransactions(unittest.TestCase):

    def setUp(self):
        self.service = InventoryService()
        # Seed test product
        self.test_product_id = "prod-test-tx-001"
        self.service.delete_product(self.test_product_id)
        self.service.add_product({
            "_id": self.test_product_id,
            "sku": "SKU-TX-001",
            "name": "Transaction Test Product",
            "category": "Electronics",
            "current_stock": 50,
            "min_stock": 10,
            "unit_price": 100.0,
            "average_daily_usage": 5.0
        })

    def tearDown(self):
        if hasattr(self, "service") and hasattr(self, "test_product_id"):
            self.service.delete_product(self.test_product_id)

    def test_stock_in_increases_stock_and_records_transaction(self):
        res = self.service.update_stock_quantity(
            product_id=self.test_product_id,
            quantity=20,
            operation="STOCK_IN",
            user="Tester Admin",
            notes="Received shipment batch"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["current_stock"], 70)

        history = self.service.get_product_history(self.test_product_id)
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertEqual(latest["type"], "STOCK_IN")
        self.assertEqual(latest["quantity_changed"], 20)
        self.assertEqual(latest["new_stock"], 70)

    def test_stock_out_decreases_stock(self):
        res = self.service.update_stock_quantity(
            product_id=self.test_product_id,
            quantity=15,
            operation="STOCK_OUT",
            user="Tester Admin",
            notes="Fulfilling order"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["current_stock"], 35)

    def test_stock_out_exceeding_current_stock_fails(self):
        res = self.service.update_stock_quantity(
            product_id=self.test_product_id,
            quantity=9999,
            operation="STOCK_OUT",
            user="Tester Admin"
        )
        self.assertFalse(res["success"])
        self.assertIn("exceeds available stock", res["message"])

if __name__ == "__main__":
    unittest.main()
