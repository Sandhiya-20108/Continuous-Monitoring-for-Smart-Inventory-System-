import unittest
from backend.app import app

class TestServerSideWebRoutes(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key"
        self.client = self.app.test_client()

    def test_login_page_renders(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Continuous Monitoring for", response.data)
        self.assertIn(b"Sign In to Dashboard", response.data)

    def test_successful_web_login_redirects_to_dashboard(self):
        response = self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Executive Overview", response.data)
        self.assertIn(b"Overall Inventory Health", response.data)

    def test_dashboard_displays_current_date(self):
        from datetime import datetime
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        now = datetime.now()
        expected_date = now.strftime("%A, %B ") + str(now.day) + now.strftime(", %Y")
        self.assertIn(expected_date.encode('utf-8'), response.data)

    def test_dynamic_time_based_greeting(self):
        from datetime import datetime
        from backend.routes.web_routes import get_time_based_greeting

        # Test Morning (e.g. 9 AM)
        dt_morning = datetime(2026, 9, 5, 9, 0, 0)
        self.assertEqual(get_time_based_greeting(dt_morning), "Good Morning")

        # Test Afternoon (e.g. 2 PM)
        dt_afternoon = datetime(2026, 9, 5, 14, 0, 0)
        self.assertEqual(get_time_based_greeting(dt_afternoon), "Good Afternoon")

        # Test Night (e.g. 10 PM)
        dt_night = datetime(2026, 9, 5, 22, 0, 0)
        self.assertEqual(get_time_based_greeting(dt_night), "Good Night")

        # Test Early Morning / Night (e.g. 2 AM)
        dt_early = datetime(2026, 9, 5, 2, 0, 0)
        self.assertEqual(get_time_based_greeting(dt_early), "Good Night")

        # Test Dashboard Render Contains Current Time-Based Greeting
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        current_greeting = get_time_based_greeting()
        self.assertIn(current_greeting.encode('utf-8'), res.data)

    def test_unauthenticated_access_redirects_to_login(self):
        response = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_root_url_unauthenticated_redirects_to_login(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_inventory_page_and_filtering(self):
        # Login first
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        response = self.client.get("/inventory")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Inventory Items Monitor", response.data)

    def test_risk_monitor_page(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        response = self.client.get("/risk-monitor")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Predictive Risk Intelligence", response.data)
        self.assertIn(b"Prioritized Risk Assessment Table", response.data)
        self.assertIn(b"Risk Tier Distribution", response.data)
        self.assertIn(b"css-donut-chart", response.data)
        self.assertIn(b"conic-gradient", response.data)

    def test_alerts_page(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        response = self.client.get("/alerts")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Central Alert Feed", response.data)

    def test_analytics_page(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        response = self.client.get("/analytics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Telemetry Analytics", response.data)



    def test_add_and_delete_product_web_flow(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        
        # Add Product
        new_prod = {
            "sku": "SKU-WEB-TEST-999",
            "name": "Web Flow Test Item",
            "category": "Electronics",
            "current_stock": "50",
            "min_stock": "10",
            "unit_price": "29.99",
            "average_daily_usage": "2.5",
            "expiry_date": "2028-01-01"
        }
        add_res = self.client.post("/inventory/add", data=new_prod, follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)
        self.assertIn(b"Web Flow Test Item", add_res.data)

        # Delete Product
        del_res = self.client.post("/inventory/delete/SKU-WEB-TEST-999", follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertNotIn(b"Web Flow Test Item", del_res.data)

    def test_web_logout(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        logout_res = self.client.post("/logout", follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn(b"Sign In to Dashboard", logout_res.data)

    def test_simulate_tick_route(self):
        self.client.post("/login", data={"identifier": "admin@inventory.com", "password": "Admin@123456"})
        res = self.client.post("/simulate-tick", data={"redirect_url": "/dashboard"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
