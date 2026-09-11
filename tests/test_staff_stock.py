import unittest
from backend.app import app
from backend.routes.web_routes import inventory_service

class TestStaffStockOperationsAndFeatures(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key"
        self.client = self.app.test_client()
        self.service = inventory_service

    def login_as_admin(self):
        return self.client.get("/demo/admin-login", follow_redirects=True)

    def login_as_staff(self):
        return self.client.get("/demo/staff-login", follow_redirects=True)

    def test_staff_stock_receive_success(self):
        """Test Staff receiving stock (STOCK_IN) updates quantity and creates transaction record."""
        self.login_as_staff()
        products = self.service.get_all_products()
        prod = products[0]
        initial_stock = prod["current_stock"]

        res = self.client.post(f"/staff/stock/{prod['_id']}", data={
            "operation": "STOCK_IN",
            "quantity": "5",
            "notes": "Test receiving 5 units"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        updated = self.service.get_product_by_id(prod["_id"])
        self.assertEqual(updated["current_stock"], initial_stock + 5)

        history = self.service.get_product_history(prod["_id"])
        self.assertTrue(len(history) > 0)
        self.assertEqual(history[0]["type"], "STOCK_IN")
        self.assertEqual(history[0]["quantity_changed"], 5)

    def test_staff_stock_issue_success(self):
        """Test Staff issuing stock (STOCK_OUT) reduces quantity correctly."""
        self.login_as_staff()
        products = self.service.get_all_products()
        prod = products[0]
        
        # Ensure stock > 2
        self.service.update_stock_quantity(prod["_id"], 20, "ADJUSTMENT")
        initial_stock = 20

        res = self.client.post(f"/staff/stock/{prod['_id']}", data={
            "operation": "STOCK_OUT",
            "quantity": "4",
            "notes": "Test issuing 4 units"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        updated = self.service.get_product_by_id(prod["_id"])
        self.assertEqual(updated["current_stock"], initial_stock - 4)

    def test_insufficient_stock_rejection(self):
        """Test issuing quantity greater than available stock is rejected."""
        self.login_as_staff()
        products = self.service.get_all_products()
        prod = products[0]
        self.service.update_stock_quantity(prod["_id"], 5, "ADJUSTMENT")

        res = self.client.post(f"/staff/stock/{prod['_id']}", data={
            "operation": "STOCK_OUT",
            "quantity": "500",
            "notes": "Attempting to issue more than available"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Insufficient stock", res.data)
        updated = self.service.get_product_by_id(prod["_id"])
        self.assertEqual(updated["current_stock"], 5)

    def test_invalid_quantity_rejection(self):
        """Test zero or negative quantities are rejected."""
        self.login_as_staff()
        products = self.service.get_all_products()
        prod = products[0]

        res = self.client.post(f"/staff/stock/{prod['_id']}", data={
            "operation": "STOCK_IN",
            "quantity": "-10",
            "notes": "Negative stock"
        }, follow_redirects=True)

        self.assertIn(b"Invalid quantity", res.data)

    def test_alert_status_update(self):
        """Test updating alert status to Viewed and Resolved."""
        self.login_as_admin()
        alerts = self.service.get_alerts()
        self.assertTrue(len(alerts) > 0)
        alert_id = alerts[0]["id"]

        res = self.client.post("/alerts/update-status", data={
            "alert_id": alert_id,
            "status": "Resolved"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        st_info = self.service.get_alert_status(alert_id)
        self.assertEqual(st_info["status"], "Resolved")

    def test_reorder_recommendation_rule_calculation(self):
        """Test rule-based reorder recommendation logic."""
        products = self.service.get_all_products()
        prod = products[0]
        # Force low stock
        self.service.update_stock_quantity(prod["_id"], 2, "ADJUSTMENT")
        
        updated = self.service.get_product_by_id(prod["_id"])
        self.assertTrue(updated["requires_reorder"])
        self.assertEqual(updated["stock_deficit"], updated["min_stock"] - 2)

    def test_staff_restricted_from_creating_deleting_products(self):
        """Test Staff role cannot access Admin routes for creating or deleting products."""
        self.login_as_staff()

        # Try to add product
        res_add = self.client.post("/inventory/add", data={
            "sku": "HACK-001",
            "name": "Unauthorized Product",
            "current_stock": 100
        }, follow_redirects=True)

        self.assertIn(b"permission", res_add.data.lower())

        # Try to delete product
        products = self.service.get_all_products()
        res_del = self.client.post(f"/inventory/delete/{products[0]['_id']}", follow_redirects=True)
        self.assertIn(b"permission", res_del.data.lower())

    def test_admin_product_creation_success(self):
        """Test Admin role can create products successfully."""
        self.login_as_admin()

        res = self.client.post("/inventory/add", data={
            "sku": "ADM-TEST-99",
            "name": "Admin Test Item",
            "category": "Electronics",
            "current_stock": 50,
            "min_stock": 10,
            "unit_price": 49.99
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Product added successfully", res.data)

    def test_invalid_product_id_handled_gracefully(self):
        """Test accessing non-existent product ID returns clear error message without 500 error."""
        self.login_as_staff()
        res = self.client.get("/staff/products/nonexistent-id-9999", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"not found", res.data)

if __name__ == "__main__":
    unittest.main()
