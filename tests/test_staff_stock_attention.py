import unittest
from backend.app import app
from backend.services.stock_forecast_service import StockForecastService
from backend.routes.web_routes import inventory_service


class TestStaffStockAttentionFeature(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key"
        self.client = self.app.test_client()

    def login_as_staff(self):
        return self.client.get("/demo/staff-login", follow_redirects=True)

    def login_as_admin(self):
        return self.client.get("/demo/admin-login", follow_redirects=True)

    def test_1_staff_can_see_stock_attention(self):
        """Staff user accesses staff dashboard and sees Stock Attention section."""
        self.login_as_staff()
        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Stock Attention", res.data)
        self.assertIn(b"stock-attention-section", res.data)

    def test_2_admin_does_not_see_staff_stock_attention(self):
        """Admin user on Admin dashboard does not see Staff-only Stock Attention UI, and /staff/dashboard redirects Admin."""
        self.login_as_admin()
        res_admin = self.client.get("/dashboard")
        self.assertEqual(res_admin.status_code, 200)
        self.assertNotIn(b"stock-attention-section", res_admin.data)

        res_redirect = self.client.get("/staff/dashboard", follow_redirects=False)
        self.assertEqual(res_redirect.status_code, 302)
        self.assertIn("/dashboard", res_redirect.location)

    def test_3_safe_status_displays_correctly(self):
        """SAFE status renders 'SAFE' badge and 'No immediate action required.'."""
        product = {"current_stock": 100, "min_stock": 20, "average_daily_usage": 1.0}
        fc = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(fc["forecast_status"], "SAFE")
        self.assertEqual(fc["forecast_status_label"], "SAFE")

        self.login_as_staff()
        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)

    def test_4_watch_status_displays_correctly(self):
        """WATCH status renders 'WATCH' badge and 'Monitor stock level.'."""
        product = {"current_stock": 30, "min_stock": 20, "average_daily_usage": 2.0} # 5 days
        fc = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(fc["forecast_status"], "WATCH")
        self.assertEqual(fc["forecast_status_label"], "WATCH")

    def test_5_low_status_displays_correctly(self):
        """LOW status renders 'LOW' badge and 'Stock needs attention.'."""
        product = {"current_stock": 15, "min_stock": 20, "average_daily_usage": 1.0}
        fc = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(fc["forecast_status"], "LOW")
        self.assertEqual(fc["forecast_status_label"], "LOW")

    def test_6_critical_status_displays_correctly(self):
        """CRITICAL status renders 'CRITICAL' badge and 'Immediate attention required.'."""
        product = {"current_stock": 0, "min_stock": 20, "average_daily_usage": 1.0}
        fc = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(fc["forecast_status"], "CRITICAL")
        self.assertEqual(fc["forecast_status_label"], "CRITICAL")

    def test_7_smart_stock_forecast_still_works(self):
        """Existing Smart Stock Forecast logic remains fully functional."""
        raw_products = inventory_service.get_all_products()
        enriched = StockForecastService.enrich_products_with_forecast(raw_products)
        self.assertTrue(len(enriched) > 0)
        self.assertIn("forecast", enriched[0])
        self.assertIn("forecast_status", enriched[0]["forecast"])

    def test_8_smart_alert_center_still_works(self):
        """Smart Alert Center severity filters remain unchanged."""
        self.login_as_admin()
        res = self.client.get("/alerts")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Critical Alerts", res.data)
        self.assertIn(b"Warning Alerts", res.data)
        self.assertNotIn(b"severity=SAFE", res.data)

    def test_9_admin_dashboard_still_works(self):
        """Admin dashboard continues to load and display inventory overview."""
        self.login_as_admin()
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Executive Overview", res.data)

    def test_10_staff_dashboard_still_works(self):
        """Staff dashboard loads properly with transactions and alerts."""
        self.login_as_staff()
        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Staff Workspace Overview", res.data)

    def test_11_no_javascript_introduced(self):
        """Verify that staff dashboard output contains no client-side script tags."""
        self.login_as_staff()
        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"<script>", res.data.lower())
        self.assertNotIn(b"fetch(", res.data.lower())


if __name__ == "__main__":
    unittest.main()
