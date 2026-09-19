import unittest
from datetime import date, timedelta
from backend.services.alert_service import AlertService
from backend.services.inventory_service import InventoryService
from backend.app import app


class TestSmartAlertCenter(unittest.TestCase):
    def setUp(self):
        self.ref_date = date(2026, 9, 20)
        self.app = app.test_client()
        self.app.testing = True

    def test_1_low_stock_product_generates_alert(self):
        product = {
            "_id": "p1",
            "name": "Laptop",
            "category": "Electronics",
            "current_stock": 5,
            "min_stock": 10,
            "expiry_date": ""
        }
        alerts = AlertService.evaluate_low_stock_alerts(product)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "Low Stock")
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertIn("below the minimum required level", alerts[0]["message"])

    def test_2_product_above_min_stock_no_low_stock_alert(self):
        product = {
            "_id": "p2",
            "name": "Desktop Monitor",
            "category": "Electronics",
            "current_stock": 15,
            "min_stock": 10,
            "expiry_date": ""
        }
        alerts = AlertService.evaluate_low_stock_alerts(product)
        self.assertEqual(len(alerts), 0)

    def test_3_expired_product_generates_critical_expiry_alert(self):
        expired_date_str = (self.ref_date - timedelta(days=2)).strftime("%Y-%m-%d")
        product = {
            "_id": "p3",
            "name": "Milk",
            "category": "Dairy",
            "current_stock": 20,
            "min_stock": 5,
            "expiry_date": expired_date_str
        }
        alerts = AlertService.evaluate_expiry_alerts(product, ref_date=self.ref_date)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertEqual(alerts[0]["message"], "Product has expired.")

    def test_4_expiring_1_to_7_days_generates_warning_alert(self):
        near_expiry_str = (self.ref_date + timedelta(days=4)).strftime("%Y-%m-%d")
        product = {
            "_id": "p4",
            "name": "Yogurt",
            "category": "Dairy",
            "current_stock": 20,
            "min_stock": 5,
            "expiry_date": near_expiry_str
        }
        alerts = AlertService.evaluate_expiry_alerts(product, ref_date=self.ref_date)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "WARNING")
        self.assertIn("Product will expire within 4 days.", alerts[0]["message"])

    def test_5_expiring_8_to_30_days_generates_notice_alert(self):
        notice_expiry_str = (self.ref_date + timedelta(days=15)).strftime("%Y-%m-%d")
        product = {
            "_id": "p5",
            "name": "Cheese",
            "category": "Dairy",
            "current_stock": 20,
            "min_stock": 5,
            "expiry_date": notice_expiry_str
        }
        alerts = AlertService.evaluate_expiry_alerts(product, ref_date=self.ref_date)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "NOTICE")
        self.assertIn("Product will expire within 15 days.", alerts[0]["message"])

    def test_6_expiry_beyond_threshold_no_alert(self):
        future_expiry_str = (self.ref_date + timedelta(days=45)).strftime("%Y-%m-%d")
        product = {
            "_id": "p6",
            "name": "Canned Beans",
            "category": "Pantry",
            "current_stock": 20,
            "min_stock": 5,
            "expiry_date": future_expiry_str
        }
        alerts = AlertService.evaluate_expiry_alerts(product, ref_date=self.ref_date)
        self.assertEqual(len(alerts), 0)

    def test_7_multiple_alerts_for_one_product(self):
        expired_date_str = (self.ref_date - timedelta(days=1)).strftime("%Y-%m-%d")
        product = {
            "_id": "p7",
            "name": "Medicine A",
            "category": "Pharma",
            "current_stock": 2,
            "min_stock": 10,
            "expiry_date": expired_date_str,
            "today_movement": 50,
            "average_daily_usage": 5
        }
        alerts = AlertService.generate_alerts_for_product(product, ref_date=self.ref_date)
        # Should generate Low Stock alert + Expiry alert + Risk alert
        types = [a["alert_type"] for a in alerts]
        self.assertIn("Low Stock", types)
        self.assertIn("Expiry Alert", types)
        self.assertIn("Risk Alert", types)
        self.assertGreaterEqual(len(alerts), 3)

    def test_8_severity_classification_attributes(self):
        alert_critical = {"severity": "CRITICAL", "generated_at": "2026-09-20T10:00:00Z"}
        alert_warning = {"severity": "WARNING", "generated_at": "2026-09-20T10:00:00Z"}
        alert_risk = {"severity": "RISK", "generated_at": "2026-09-20T10:00:00Z"}
        alert_notice = {"severity": "NOTICE", "generated_at": "2026-09-20T10:00:00Z"}

        pres_c = AlertService.enrich_alert_presentation(alert_critical)
        pres_w = AlertService.enrich_alert_presentation(alert_warning)
        pres_r = AlertService.enrich_alert_presentation(alert_risk)
        pres_n = AlertService.enrich_alert_presentation(alert_notice)

        self.assertEqual(pres_c["badge_class"], "badge-danger")
        self.assertEqual(pres_w["badge_class"], "badge-warning")
        self.assertEqual(pres_r["badge_class"], "badge-orange")
        self.assertEqual(pres_n["badge_class"], "badge-info")

    def test_9_summary_counts_calculation(self):
        alerts = [
            {"severity": "CRITICAL"},
            {"severity": "CRITICAL"},
            {"severity": "WARNING"},
            {"severity": "RISK"},
            {"severity": "RISK"},
            {"severity": "NOTICE"}
        ]
        summary = AlertService.calculate_alert_summary(alerts)
        self.assertEqual(summary["critical_count"], 2)
        self.assertEqual(summary["warning_count"], 1)
        self.assertEqual(summary["risk_count"], 2)
        self.assertEqual(summary["notice_count"], 1)
        self.assertEqual(summary["total_count"], 6)

    def test_10_alert_priority_sorting(self):
        alerts = [
            {"severity": "NOTICE", "product_name": "N Product", "alert_type": "Expiry"},
            {"severity": "CRITICAL", "product_name": "C Product", "alert_type": "Low Stock"},
            {"severity": "RISK", "product_name": "R Product", "alert_type": "Risk"},
            {"severity": "WARNING", "product_name": "W Product", "alert_type": "Expiry"}
        ]
        sorted_alerts = AlertService.sort_alerts_by_severity(alerts)
        ordered_severities = [a["severity"] for a in sorted_alerts]
        self.assertEqual(ordered_severities, ["CRITICAL", "WARNING", "RISK", "NOTICE"])

    def test_11_risk_monitor_integration(self):
        product = {
            "_id": "p11",
            "name": "Surge Product",
            "category": "Electronics",
            "current_stock": 50,
            "min_stock": 10,
            "average_daily_usage": 5.0,
            "today_movement": 35.0, # 7x surge
            "expiry_date": ""
        }
        alerts = AlertService.evaluate_risk_alerts(product, ref_date=self.ref_date)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "Risk Alert")
        self.assertEqual(alerts[0]["severity"], "RISK")
        self.assertIn("surge", alerts[0]["message"].lower())

    def test_12_route_authentication_and_access(self):
        # Unauthenticated request redirects to login
        res = self.app.get("/alerts")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)

    def test_13_existing_inventory_service_integration(self):
        svc = InventoryService()
        alerts, summary = svc.get_smart_alerts_summary()
        self.assertIsInstance(alerts, list)
        self.assertIn("critical_count", summary)
        self.assertIn("total_count", summary)


if __name__ == "__main__":
    unittest.main()
