import unittest
from werkzeug.security import generate_password_hash
from backend.app import app
from backend.routes.web_routes import auth_service
from backend.models.user_model import UserModel

class TestStaffProfilePermission(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.auth_service = auth_service

        # Ensure teststaff exists with fresh password for every test
        staff_doc = self.auth_service.repository.find_by_email_or_username("teststaff")
        if not staff_doc:
            self.auth_service.create_staff_user(
                email="teststaff@inventory.com",
                username="teststaff",
                password="StaffPassword123!",
                full_name="Test Staff Member"
            )
            staff_doc = self.auth_service.repository.find_by_email_or_username("teststaff")
        else:
            self.auth_service.repository.update_user(
                staff_doc["_id"],
                {
                    "password_hash": generate_password_hash("StaffPassword123!"),
                    "full_name": "Test Staff Member"
                }
            )

        self.staff_user = staff_doc

        # Ensure staff2 exists
        staff2_doc = self.auth_service.repository.find_by_email_or_username("staff2")
        if not staff2_doc:
            self.auth_service.create_staff_user(
                email="staff2@inventory.com",
                username="staff2",
                password="Password@123",
                full_name="Second Staff Officer"
            )
            staff2_doc = self.auth_service.repository.find_by_email_or_username("staff2")

        self.staff2_user = staff2_doc

    def _login(self, identifier, password):
        return self.client.post("/login", data={
            "identifier": identifier,
            "password": password
        }, follow_redirects=True)

    def test_01_default_permission_is_disabled_for_new_staff(self):
        """Test default permission state is disabled for newly created staff accounts."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], False)
        staff_doc = self.auth_service.repository.find_by_email_or_username("teststaff")
        self.assertFalse(staff_doc.get("allow_profile_edit", False))

    def test_02_admin_enables_staff_profile_editing(self):
        """Test 1: Admin enables Staff profile editing."""
        self._login("admin", "Admin@123456")
        
        res = self.client.post(
            f"/users/toggle-profile-edit/{self.staff_user['_id']}",
            data={"action": "allow"},
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)
        
        updated_staff = self.auth_service.repository.find_by_id(self.staff_user["_id"])
        self.assertTrue(updated_staff.get("allow_profile_edit", False))

    def test_03_staff_can_edit_full_name_when_allowed(self):
        """Test 2: Staff can edit Full Name when enabled."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], True)
        self._login("teststaff", "StaffPassword123!")

        res = self.client.post("/update-profile", data={
            "full_name": "Updated Test Staff Name",
            "new_password": "",
            "confirm_password": ""
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Profile information updated successfully", res.data)

        updated_staff = self.auth_service.repository.find_by_id(self.staff_user["_id"])
        self.assertEqual(updated_staff["full_name"], "Updated Test Staff Name")

    def test_04_staff_can_change_password_securely(self):
        """Test 3: Staff can change password securely."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], True)
        self._login("teststaff", "StaffPassword123!")

        res = self.client.post("/update-profile", data={
            "full_name": "Test Staff Member",
            "new_password": "NewStaffPassword123!",
            "confirm_password": "NewStaffPassword123!"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Profile information and account password updated successfully", res.data)

        # Verify login with new password
        self.client.get("/logout", follow_redirects=True)
        login_res = self._login("teststaff", "NewStaffPassword123!")
        self.assertIn(b"Staff Workspace", login_res.data)

    def test_05_staff_cannot_edit_email_username_role_status(self):
        """Test 4: Staff cannot edit email, username, role or status."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], True)
        self._login("teststaff", "StaffPassword123!")

        self.client.post("/update-profile", data={
            "full_name": "Test Staff Member",
            "email": "hacked@inventory.com",
            "username": "hacked_admin",
            "role": "admin",
            "status": "Inactive"
        }, follow_redirects=True)

        staff_doc = self.auth_service.repository.find_by_id(self.staff_user["_id"])
        self.assertEqual(staff_doc["email"], "teststaff@inventory.com")
        self.assertEqual(staff_doc["username"], "teststaff")
        self.assertEqual(staff_doc["role"], "staff")

    def test_06_admin_disables_staff_profile_editing(self):
        """Test 5: Admin disables Staff profile editing."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], True)
        self._login("admin", "Admin@123456")
        
        res = self.client.post(
            f"/users/toggle-profile-edit/{self.staff_user['_id']}",
            data={"action": "disable"},
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)

        staff_doc = self.auth_service.repository.find_by_id(self.staff_user["_id"])
        self.assertFalse(staff_doc.get("allow_profile_edit", False))

    def test_07_staff_profile_becomes_view_only(self):
        """Test 6: Staff profile becomes view-only when disabled."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], False)
        self._login("teststaff", "StaffPassword123!")

        res = self.client.get("/staff/profile")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Profile editing has been disabled by your administrator.", res.data)
        self.assertIn(b"Editing Disabled by Admin", res.data)

    def test_08_direct_post_rejected_when_disabled(self):
        """Test 7: Direct POST request is rejected when editing is disabled."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], False)
        self._login("teststaff", "StaffPassword123!")

        res = self.client.post("/update-profile", data={
            "full_name": "Tampered Name"
        }, follow_redirects=True)
        
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your administrator has disabled profile editing.", res.data)

    def test_09_staff_cannot_edit_another_staff_profile(self):
        """Test 8: Staff cannot edit another Staff member's profile."""
        self.auth_service.toggle_staff_profile_edit(self.staff_user["_id"], True)
        self._login("teststaff", "StaffPassword123!")

        res = self.client.post("/update-profile", data={
            "user_id": self.staff2_user["_id"],
            "full_name": "Hacked Name for Staff 2"
        }, follow_redirects=True)

        staff2_doc = self.auth_service.repository.find_by_id(self.staff2_user["_id"])
        self.assertNotEqual(staff2_doc["full_name"], "Hacked Name for Staff 2")

    def test_10_admin_can_manage_staff_permissions(self):
        """Test 9: Admin can manage Staff permissions."""
        self._login("admin", "Admin@123456")
        
        res = self.client.get("/admin/settings?section=staff_permissions")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Staff Accounts", res.data)
        self.assertIn(b"Profile Editing", res.data)

    def test_11_no_javascript_added(self):
        """Test 11: Ensure no <script> tags were added to staff profile or settings templates."""
        with open("backend/templates/staff_profile.html", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertNotIn("<script>", content.lower())
        
        with open("backend/templates/settings.html", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertNotIn("<script>", content.lower())

if __name__ == "__main__":
    unittest.main()
