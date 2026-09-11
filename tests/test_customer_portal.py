import unittest
from backend.app import app

class TestCustomerPortalAndRBAC(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key"
        self.client = self.app.test_client()

    def test_customer_login_redirects_to_customer_dashboard(self):
        response = self.client.post("/login", data={
            "identifier": "customer@inventory.com",
            "password": "Customer@123456"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Product Catalog", response.data)
        self.assertIn(b"Staff Workspace", response.data)

    def test_customer_cannot_access_admin_dashboard(self):
        # Login as customer/staff
        self.client.post("/login", data={
            "identifier": "customer@inventory.com",
            "password": "Customer@123456"
        })
        # Attempt to access admin dashboard
        response = self.client.get("/dashboard", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You do not have permission to access that page.", response.data)
        self.assertIn(b"Staff Workspace", response.data)

    def test_customer_cannot_access_users_management(self):
        self.client.post("/login", data={
            "identifier": "customer@inventory.com",
            "password": "Customer@123456"
        })
        response = self.client.get("/users", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You do not have permission to access that page.", response.data)

    def test_customer_cannot_access_risk_monitor(self):
        self.client.post("/login", data={
            "identifier": "customer@inventory.com",
            "password": "Customer@123456"
        })
        response = self.client.get("/risk-monitor", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You do not have permission to access that page.", response.data)

    def test_customer_profile_page(self):
        self.client.post("/login", data={
            "identifier": "customer@inventory.com",
            "password": "Customer@123456"
        })
        response = self.client.get("/staff/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Staff Account Profile", response.data)

    def test_demo_admin_login_redirects_to_dashboard(self):
        response = self.client.get("/demo/admin-login", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Executive Overview", response.data)

    def test_demo_staff_login_redirects_to_customer_dashboard(self):
        response = self.client.get("/demo/staff-login", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Staff Workspace", response.data)

    def test_staff_registration_success(self):
        import uuid
        unique_email = f"newstaff_{uuid.uuid4().hex[:6]}@inventory.com"
        reg_data = {
            "full_name": "New Test Staff",
            "email": unique_email,
            "username": f"staff_{uuid.uuid4().hex[:6]}",
            "password": "Password@123",
            "confirm_password": "Password@123"
        }
        res = self.client.post("/staff/register", data=reg_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Staff account created successfully", res.data)

    def test_staff_registration_password_mismatch(self):
        reg_data = {
            "full_name": "Mismatch Staff",
            "email": "mismatch@inventory.com",
            "username": "mismatch",
            "password": "Password@123",
            "confirm_password": "DifferentPassword@123"
        }
        res = self.client.post("/staff/register", data=reg_data)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Password and Confirm Password do not match", res.data)

    def test_staff_registration_duplicate_email(self):
        reg_data = {
            "full_name": "Duplicate Staff",
            "email": "staff@inventory.com",  # Already seeded
            "username": "dupstaff",
            "password": "Password@123",
            "confirm_password": "Password@123"
        }
        res = self.client.post("/staff/register", data=reg_data)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"already exists", res.data)

    def test_staff_login_via_admin_form_blocked(self):
        res = self.client.post("/login", data={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456",
            "login_type": "admin"
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Access denied: Staff accounts cannot log in through the Admin Portal", res.data)

    def test_staff_browse_products_page(self):
        self.client.get("/demo/staff-login", follow_redirects=True)
        res = self.client.get("/staff/products")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Browse Product Catalog", res.data)
        self.assertIn(b"Available Inventory Items", res.data)

    def test_staff_search_products_page(self):
        self.client.get("/demo/staff-login", follow_redirects=True)
        res_empty = self.client.get("/staff/products/search")
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn(b"Search Product Catalog", res_empty.data)

        res_search = self.client.get("/staff/products/search?search=Healthcare")
        self.assertEqual(res_search.status_code, 200)
        self.assertIn(b"Matching Search Results", res_search.data)

    def test_staff_product_details_page(self):
        self.client.get("/demo/staff-login", follow_redirects=True)
        
        # Test invalid product ID
        res_invalid = self.client.get("/staff/products/non_existent_id_999")
        self.assertEqual(res_invalid.status_code, 200)
        self.assertIn(b"Product Not Found", res_invalid.data)

        # Test valid product ID (seeded SKU-MED-001 or prod-001)
        res_valid = self.client.get("/staff/products/prod-001")
        self.assertEqual(res_valid.status_code, 200)
        self.assertIn(b"Technical Details", res_valid.data)

if __name__ == "__main__":
    unittest.main()
