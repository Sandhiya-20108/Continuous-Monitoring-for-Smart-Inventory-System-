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
        self.assertIn(b"Admin Sign In", response.data)

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

        # Test filtering by Safe alerts
        resp_safe = self.client.get("/alerts?severity=Safe")
        self.assertEqual(resp_safe.status_code, 200)

        # Verify CSS contains safe green border rule
        resp_css = self.client.get("/static/css/styles.css")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn(b".alert-item.Safe", resp_css.data)
        self.assertIn(b"border-left: 4px solid #10B981", resp_css.data)
        resp_css.close()

    def test_analytics_page(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        response = self.client.get("/analytics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Telemetry Analytics", response.data)



    def test_staff_profile_view_and_security_validation(self):
        """Test Staff Profile page rendering and password/profile update validations."""
        self.client.post("/login", data={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        })

        res = self.client.get("/staff/profile")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Staff Account Profile & Security Center", res.data)
        self.assertIn(b"Personal Information", res.data)
        self.assertIn(b"Account Security", res.data)

        # Test updating full name with blank password
        res_name = self.client.post("/update-profile", data={
            "full_name": "Updated Staff Officer",
            "new_password": "",
            "confirm_password": ""
        }, follow_redirects=True)
        self.assertEqual(res_name.status_code, 200)
        self.assertIn(b"Profile information updated successfully", res_name.data)

        # Test short password rejection
        res_short = self.client.post("/update-profile", data={
            "full_name": "Updated Staff Officer",
            "new_password": "short",
            "confirm_password": "short"
        }, follow_redirects=True)
        self.assertEqual(res_short.status_code, 200)
        self.assertIn(b"New Password must be at least 8 characters long", res_short.data)

        # Test password mismatch rejection
        res_mismatch = self.client.post("/update-profile", data={
            "full_name": "Updated Staff Officer",
            "new_password": "Password123",
            "confirm_password": "Password999"
        }, follow_redirects=True)
        self.assertEqual(res_mismatch.status_code, 200)
        self.assertIn(b"New Password and Confirm Password do not match", res_mismatch.data)

        # Test valid password update
        res_valid_pw = self.client.post("/update-profile", data={
            "full_name": "Updated Staff Officer",
            "new_password": "NewStaffPassword123",
            "confirm_password": "NewStaffPassword123"
        }, follow_redirects=True)
        self.assertEqual(res_valid_pw.status_code, 200)
        self.assertIn(b"Profile information and account password updated successfully", res_valid_pw.data)

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
        self.assertIn(b"Admin Sign In", logout_res.data)

    def test_simulate_tick_route(self):
        self.client.post("/login", data={"identifier": "admin@inventory.com", "password": "Admin@123456"})
        res = self.client.post("/simulate-tick", data={"redirect_url": "/dashboard"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

    def test_toggle_theme_route(self):
        # Default theme should be dark or fallback
        with self.client:
            res = self.client.post("/toggle-theme", data={"redirect_url": "/login"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            from flask import session
            self.assertEqual(session.get("theme"), "light")
            self.assertIn(b'light-theme', res.data)
            self.assertIn(b'fa-moon', res.data)

            # Toggle back to dark
            res2 = self.client.post("/toggle-theme", data={"redirect_url": "/login"}, follow_redirects=True)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(session.get("theme"), "dark")
            self.assertIn(b'dark-theme', res2.data)
            self.assertIn(b'fa-sun', res2.data)

    def test_admin_settings_access_control(self):
        # 1. Unauthenticated user -> redirect to /login
        unauth_res = self.client.get("/admin/settings", follow_redirects=False)
        self.assertEqual(unauth_res.status_code, 302)
        self.assertIn("/login", unauth_res.location)

        # 2. Staff user -> access blocked
        self.client.post("/login", data={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        })
        staff_res = self.client.get("/admin/settings", follow_redirects=True)
        self.assertIn(b"You do not have permission to access that page", staff_res.data)

        # Logout staff
        self.client.post("/logout")

        # 3. Admin user -> success
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        admin_res = self.client.get("/admin/settings")
        self.assertEqual(admin_res.status_code, 200)
        self.assertIn(b"Enterprise Settings Center", admin_res.data)
        self.assertIn(b"General Store Settings", admin_res.data)

    def test_admin_settings_post_general(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        res = self.client.post("/admin/settings?section=general", data={
            "action_type": "general",
            "store_name": "Apex Global Supply",
            "contact_email": "apex@supplies.com",
            "phone": "+1 800 123 4567",
            "currency": "EUR (\xe2\x82\xac)",
            "timezone": "EST (UTC-5)"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"General Enterprise Settings updated successfully", res.data)

    def test_admin_settings_post_inventory_rules(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        res = self.client.post("/admin/settings?section=inventory_rules", data={
            "action_type": "inventory_rules",
            "default_min_stock": "12",
            "low_stock_threshold": "20",
            "critical_stock_threshold": "6",
            "default_reorder_qty": "60",
            "expiry_monitoring": "on"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Inventory Telemetry Rules updated successfully", res.data)

    def test_admin_settings_date_format_saving(self):
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        # Test saving DD-MM-YYYY format
        res = self.client.post("/admin/settings?section=general", data={
            "action_type": "general",
            "store_name": "Apex Global Supply",
            "contact_email": "apex@supplies.com",
            "phone": "+1 800 123 4567",
            "currency": "EUR (€)",
            "date_format": "DD-MM-YYYY",
            "timezone": "EST (UTC-5)"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"General Enterprise Settings updated successfully", res.data)
        
        # Verify selected option remains selected on refresh
        settings_page = self.client.get("/admin/settings?section=general")
        self.assertIn(b'value="DD-MM-YYYY" selected', settings_page.data)

        # Test date_formatter filter directly
        from backend.utils.date_formatter import format_date_filter
        formatted = format_date_filter("2026-09-14", "DD MMM YYYY")
        self.assertEqual(formatted, "14 Sep 2026")

    def test_admin_settings_staff_permissions_section_renders(self):
        # 1. Admin login -> opens section cleanly without BuildError
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        res = self.client.get("/admin/settings?section=staff_permissions")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Staff Accounts & Role Permissions", res.data)
        self.assertIn(b"Role-Based Access Control (RBAC) Matrix", res.data)

        # Logout Admin
        self.client.post("/logout")

        # 2. Staff login -> blocked from accessing admin settings
        self.client.post("/login", data={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        })
        staff_res = self.client.get("/admin/settings?section=staff_permissions", follow_redirects=True)
        self.assertIn(b"You do not have permission to access that page", staff_res.data)

    def test_export_three_distinct_reports_and_rbac(self):
        # 1. Staff access attempt to export reports -> Blocked and redirected
        self.client.post("/login", data={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        })
        res_staff_inv = self.client.get("/export-report/inventory", follow_redirects=True)
        self.assertIn(b"You do not have permission to access that page", res_staff_inv.data)
        
        res_staff_tx = self.client.get("/export-report/transactions", follow_redirects=True)
        self.assertIn(b"You do not have permission to access that page", res_staff_tx.data)

        res_staff_alert = self.client.get("/export-report/alerts", follow_redirects=True)
        self.assertIn(b"You do not have permission to access that page", res_staff_alert.data)

        self.client.post("/logout")

        # 2. Admin login -> can download all three distinct reports
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })

        # Report 1: Inventory CSV
        resp_inv = self.client.get("/export-report/inventory")
        self.assertEqual(resp_inv.status_code, 200)
        self.assertEqual(resp_inv.mimetype, "text/csv")
        self.assertIn("filename=inventory_report.csv", resp_inv.headers.get("Content-Disposition", ""))
        self.assertIn(b"Product ID,Product Name,Category,Current Stock,Minimum Stock,Price,Expiry Date,Risk Level,Status", resp_inv.data)

        # Report 2: Transactions CSV
        resp_tx = self.client.get("/export-report/transactions")
        self.assertEqual(resp_tx.status_code, 200)
        self.assertEqual(resp_tx.mimetype, "text/csv")
        self.assertIn("filename=transaction_history_report.csv", resp_tx.headers.get("Content-Disposition", ""))
        self.assertIn(b"Transaction ID,Product Name,Transaction Type,Quantity,Previous Stock,Updated Stock,Performed By,Date,Time", resp_tx.data)

        # Report 3: Risk & Alerts Report CSV
        resp_alt = self.client.get("/export-report/alerts")
        self.assertEqual(resp_alt.status_code, 200)
        self.assertEqual(resp_alt.mimetype, "text/csv")
        self.assertIn("filename=risk_alert_report.csv", resp_alt.headers.get("Content-Disposition", ""))
        self.assertIn(b"Alert ID,Product Name,Category,Current Stock,Minimum Stock,Risk Type,Risk Level,Alert Message,Created Date,Alert Status", resp_alt.data)

        # Verify all 3 filenames and data structures are distinct
        self.assertNotEqual(resp_inv.data, resp_tx.data)
        self.assertNotEqual(resp_inv.data, resp_alt.data)
        self.assertNotEqual(resp_tx.data, resp_alt.data)

    def test_dedicated_reports_page_view_and_saved_config_crud(self):
        # 1. Staff access attempt to /reports -> Blocked and redirected to staff dashboard
        self.client.post("/login", data={
            "identifier": "staff@inventory.com",
            "password": "Staff@123456"
        })
        res_staff = self.client.get("/reports", follow_redirects=True)
        self.assertIn(b"You do not have permission to access that page", res_staff.data)
        self.assertIn(b"Staff Workspace", res_staff.data)
        self.client.post("/logout")

        # 2. Admin login -> opens dedicated Reports page cleanly without auto download
        self.client.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })

        # Test GET /reports -> Renders HTML page (200 status, html mimetype, no Content-Disposition header)
        res_reports = self.client.get("/reports")
        self.assertEqual(res_reports.status_code, 200)
        self.assertEqual(res_reports.mimetype, "text/html")
        self.assertNotIn("Content-Disposition", res_reports.headers)
        self.assertIn(b"Executive Reports & Intelligence Center", res_reports.data)
        self.assertIn(b"Report Telemetry Summary", res_reports.data)

        # Test tabs & filters
        res_inv_tab = self.client.get("/reports?tab=inventory&stock_status=in_stock")
        self.assertEqual(res_inv_tab.status_code, 200)
        self.assertIn(b"Inventory Catalogue Report Preview", res_inv_tab.data)

        res_tx_tab = self.client.get("/reports?tab=transactions&tx_type=STOCK_IN")
        self.assertEqual(res_tx_tab.status_code, 200)
        self.assertIn(b"Stock Movement Transaction History Preview", res_tx_tab.data)

        res_alt_tab = self.client.get("/reports?tab=alerts&alert_severity=Critical")
        self.assertEqual(res_alt_tab.status_code, 200)
        self.assertIn(b"Risk & Alert Report Preview", res_alt_tab.data)

        # Test saving a report configuration
        res_save = self.client.post("/reports", data={
            "action_type": "save_config",
            "report_name": "Monthly Critical Stock Audit",
            "report_type": "inventory",
            "category": "Electronics",
            "risk_level": "Critical",
            "tx_type": "all",
            "visible_columns": ["product_id", "product_name", "current_stock"]
        }, follow_redirects=True)
        self.assertEqual(res_save.status_code, 200)
        self.assertIn(b"Report configuration saved successfully", res_save.data)
        self.assertIn(b"Monthly Critical Stock Audit", res_save.data)

        # Test deleting saved report configuration
        from backend.services.inventory_service import InventoryService
        service = InventoryService()
        saved_list = service.get_saved_reports()
        self.assertTrue(len(saved_list) > 0)
        saved_id = saved_list[0].get("id") or str(saved_list[0].get("_id"))

        res_del = self.client.post("/reports", data={
            "action_type": "delete_config",
            "report_id": saved_id
        }, follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b"Report configuration deleted successfully", res_del.data)

if __name__ == "__main__":
    unittest.main()



