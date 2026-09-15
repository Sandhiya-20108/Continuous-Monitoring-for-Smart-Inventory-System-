import unittest
from backend.app import app
from backend.services.auth_service import AuthService

class TestRoleBasedAuthentication(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_default_admin_login(self):
        res = self.client.post("/api/auth/login", json={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["role"], "admin")
        self.assertIn("token", data)

    def test_default_staff_login(self):
        res = self.client.post("/api/auth/login", json={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["role"], "staff")

    def test_invalid_login(self):
        res = self.client.post("/api/auth/login", json={
            "identifier": "admin@inventory.com",
            "password": "WrongPassword!"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertEqual(data["status"], "error")

    def test_role_permissions_admin_vs_staff(self):
        # 1. Admin login
        admin_res = self.client.post("/api/auth/login", json={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        }).get_json()
        admin_token = admin_res["token"]

        # 2. Staff login
        staff_res = self.client.post("/api/auth/login", json={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        }).get_json()
        staff_token = staff_res["token"]

        # 3. Add product (Admin allowed, Staff forbidden)
        new_prod = {
            "sku": "SKU-AUTH-TEST-001",
            "name": "Auth Test Item",
            "category": "Electronics",
            "current_stock": 50,
            "min_stock": 10
        }
        
        # Staff attempt -> 403 Forbidden
        staff_add_res = self.client.post("/api/products", json=new_prod, headers={"Authorization": f"Bearer {staff_token}"})
        self.assertEqual(staff_add_res.status_code, 403)

        # Admin attempt -> 200 OK
        admin_add_res = self.client.post("/api/products", json=new_prod, headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(admin_add_res.status_code, 200)

        # 4. Stock update (Both Staff and Admin allowed)
        staff_stock_res = self.client.patch("/api/products/SKU-AUTH-TEST-001/stock", json={"current_stock": 42}, headers={"Authorization": f"Bearer {staff_token}"})
        self.assertEqual(staff_stock_res.status_code, 200)
        self.assertEqual(staff_stock_res.get_json()["data"]["current_stock"], 42)

        # 5. Delete product (Staff forbidden -> 403, Admin allowed -> 200)
        staff_del_res = self.client.delete("/api/products/SKU-AUTH-TEST-001", headers={"Authorization": f"Bearer {staff_token}"})
        self.assertEqual(staff_del_res.status_code, 403)

        admin_del_res = self.client.delete("/api/products/SKU-AUTH-TEST-001", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(admin_del_res.status_code, 200)

    def test_logout(self):
        login_res = self.client.post("/api/auth/login", json={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        }).get_json()
        token = login_res["token"]

        # Logout
        logout_res = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # Accessing protected route with invalidated token -> 401
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 401)

if __name__ == "__main__":
    unittest.main()
