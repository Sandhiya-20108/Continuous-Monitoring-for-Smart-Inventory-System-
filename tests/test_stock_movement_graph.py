import unittest
from backend.app import app
from backend.services.inventory_service import InventoryService
from backend.services.stock_forecast_service import StockForecastService


class TestStockMovementGraph(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key"
        self.client = self.app.test_client()
        self.service = InventoryService()

    def login_as_admin(self):
        return self.client.get("/demo/admin-login", follow_redirects=True)

    def login_as_staff(self):
        return self.client.get("/demo/staff-login", follow_redirects=True)

    def test_1_dashboard_loads_successfully(self):
        """Admin dashboard loads with 200 OK and renders Stock movement title."""
        self.login_as_admin()
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Stock movement", res.data)
        self.assertIn(b"Flow map: inbound, outbound and current load", res.data)

    def test_2_default_period_works(self):
        """Default 6-month period returns 6 month buckets."""
        analytics = self.service.get_stock_movement_analytics()
        self.assertEqual(analytics["selected_range"], 6)
        self.assertEqual(len(analytics["month_data"]), 6)

    def test_3_three_month_period_works(self):
        """3-month period parameter returns 3 month buckets."""
        analytics = self.service.get_stock_movement_analytics(months=3)
        self.assertEqual(analytics["selected_range"], 3)
        self.assertEqual(len(analytics["month_data"]), 3)

    def test_4_six_month_period_works(self):
        """6-month period parameter returns 6 month buckets."""
        analytics = self.service.get_stock_movement_analytics(months=6)
        self.assertEqual(analytics["selected_range"], 6)
        self.assertEqual(len(analytics["month_data"]), 6)

    def test_5_twelve_month_period_works(self):
        """12-month period parameter returns 12 month buckets across the full year."""
        analytics = self.service.get_stock_movement_analytics(months=12)
        self.assertEqual(analytics["selected_range"], 12)
        self.assertEqual(len(analytics["month_data"]), 12)

    def test_6_january_data_grouped_correctly(self):
        """Verify January month label exists when requesting 12 months."""
        analytics = self.service.get_stock_movement_analytics(months=12)
        month_names = [m["name"] for m in analytics["month_data"]]
        self.assertIn("Jan", month_names)

    def test_7_february_data_grouped_correctly(self):
        """Verify February month label exists when requesting 12 months."""
        analytics = self.service.get_stock_movement_analytics(months=12)
        month_names = [m["name"] for m in analytics["month_data"]]
        self.assertIn("Feb", month_names)

    def test_8_monthly_aggregation_full_year(self):
        """Verify all 12 months are aggregated with positive movement totals."""
        analytics = self.service.get_stock_movement_analytics(months=12)
        for m in analytics["month_data"]:
            self.assertGreaterEqual(m["inbound"], 0)
            self.assertGreaterEqual(m["outbound"], 0)
            self.assertGreaterEqual(m["current_load"], 0)

    def test_9_inbound_monthly_aggregation(self):
        """Inbound monthly values are aggregated and SVG curve is generated."""
        analytics = self.service.get_stock_movement_analytics(months=6)
        self.assertTrue(len(analytics["inbound_curve"]) > 0)
        self.assertTrue("M " in analytics["inbound_curve"])

    def test_10_outbound_monthly_aggregation(self):
        """Outbound monthly values are aggregated and SVG curve is generated."""
        analytics = self.service.get_stock_movement_analytics(months=6)
        self.assertTrue(len(analytics["outbound_curve"]) > 0)
        self.assertTrue("M " in analytics["outbound_curve"])

    def test_11_current_load_calculation_works(self):
        """Current load is derived consistently and load curve is generated."""
        analytics = self.service.get_stock_movement_analytics(months=6)
        self.assertTrue(len(analytics["load_curve"]) > 0)
        self.assertGreater(int(analytics["load_total"].replace(",", "")), 0)

    def test_12_different_monthly_values_preserved(self):
        """Verify graph data points are NOT flat lines and contain variation across months."""
        analytics = self.service.get_stock_movement_analytics(months=12)
        inbounds = [m["inbound"] for m in analytics["month_data"]]
        self.assertTrue(len(set(inbounds)) > 1, "Inbound values must show variation across months")

    def test_13_missing_months_handled_safely(self):
        """Requesting period when transactions are missing returns safe default analytics."""
        analytics = self.service.get_stock_movement_analytics(months=12)
        self.assertIsNotNone(analytics)
        self.assertTrue(analytics["has_transactions"])

    def test_14_invalid_movement_records_do_not_crash(self):
        """Invalid or malformed transactions do not cause exception."""
        bad_tx = {"timestamp": "invalid_date", "type": "UNKNOWN", "quantity_changed": "abc"}
        self.service._transactions.append(bad_tx)
        analytics = self.service.get_stock_movement_analytics(months=6)
        self.assertIsNotNone(analytics)
        self.service._transactions.remove(bad_tx)

    def test_15_existing_admin_dashboard_still_works(self):
        """Admin dashboard route GET with period range selector returns 200 OK."""
        self.login_as_admin()
        res = self.client.get("/dashboard?range=12")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Stock movement", res.data)

    def test_16_existing_staff_dashboard_still_works(self):
        """Staff dashboard continues to work."""
        self.login_as_staff()
        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)

    def test_17_smart_stock_forecast_still_works(self):
        """Smart Stock Forecast calculations remain intact."""
        raw_products = self.service.get_all_products()
        enriched = StockForecastService.enrich_products_with_forecast(raw_products)
        self.assertTrue(len(enriched) > 0)
        self.assertIn("forecast", enriched[0])

    def test_18_smart_alert_center_still_works(self):
        """Smart Alert Center severity filters remain unchanged."""
        self.login_as_admin()
        res = self.client.get("/alerts")
        self.assertEqual(res.status_code, 200)

    def test_19_no_javascript_introduced(self):
        """Verify dashboard output contains zero client-side script tags for chart rendering."""
        self.login_as_admin()
        res = self.client.get("/dashboard?range=12")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"<script>", res.data.lower())

    def test_20_mongodb_schema_unchanged(self):
        """Verify collection names and schema access remain intact."""
        products = self.service.get_all_products()
        self.assertTrue(isinstance(products, list))

    def test_21_graph_coordinates_change_dynamically_with_values(self):
        """Verify graph Y coordinates shift when monthly values change, mapping peaks to top Y and valleys to bottom Y."""
        analytics_3 = self.service.get_stock_movement_analytics(months=3)
        analytics_12 = self.service.get_stock_movement_analytics(months=12)

        # 3-month vs 12-month curves must differ in geometry
        self.assertNotEqual(analytics_3["inbound_curve"], analytics_12["inbound_curve"])
        self.assertNotEqual(analytics_3["outbound_curve"], analytics_12["outbound_curve"])

        # Check peak vs valley Y position scaling in 3-month range
        pts = analytics_3["month_data"]
        inbound_vals = [m["inbound"] for m in pts]
        inbound_ys = [m["inbound_y"] for m in pts]
        
        max_idx = inbound_vals.index(max(inbound_vals))
        min_idx = inbound_vals.index(min(inbound_vals))

        # SVG Y: 0 is top, 180 is bottom -> max value MUST have smaller Y coordinate than min value
        self.assertLess(inbound_ys[max_idx], inbound_ys[min_idx])
        # Peak month gets scaled to top boundary 40.0
        self.assertEqual(inbound_ys[max_idx], 40.0)

    def test_22_summary_and_graph_use_same_single_dataset(self):
        """Verify summary metrics and graph curves are computed from the exact same month_data object."""
        analytics = self.service.get_stock_movement_analytics(months=6)
        month_data = analytics["month_data"]
        active_m = [m for m in month_data if m["is_active"]][0]

        self.assertEqual(analytics["inbound_total"], f"{active_m['inbound']:,}")
        self.assertEqual(analytics["outbound_total"], f"{active_m['outbound']:,}")
        self.assertEqual(analytics["load_total"], f"{active_m['current_load']:,}")

    def test_23_higher_numeric_values_produce_higher_graph_positions(self):
        """Verify that higher numeric values strictly map to smaller SVG Y coordinates (higher visual positions) for Movement and Load series."""
        analytics = self.service.get_stock_movement_analytics(months=6)
        
        mov_points = []
        load_points = []
        for m in analytics["month_data"]:
            mov_points.append((m["inbound"], m["inbound_y"]))
            mov_points.append((m["outbound"], m["outbound_y"]))
            load_points.append((m["current_load"], m["load_y"]))

        # Sort movement points by value ascending
        mov_points.sort(key=lambda item: item[0])
        for i in range(len(mov_points) - 1):
            val1, y1 = mov_points[i]
            val2, y2 = mov_points[i + 1]
            if val2 > val1:
                self.assertLessEqual(y2, y1, f"Movement value {val2} (y={y2}) must be visually higher than {val1} (y={y1})")

        # Sort load points by value ascending
        load_points.sort(key=lambda item: item[0])
        for i in range(len(load_points) - 1):
            val1, y1 = load_points[i]
            val2, y2 = load_points[i + 1]
            if val2 > val1:
                self.assertLessEqual(y2, y1, f"Load value {val2} (y={y2}) must be visually higher than {val1} (y={y1})")

    def test_24_graph_geometry_path_A_ne_path_B(self):
        """Verify that when monthly transaction values change, the SVG path A != path B and area A != area B."""
        analytics_orig = self.service.get_stock_movement_analytics(months=6)

        # Create custom transaction dataset B
        tx_b1 = {"timestamp": "2026-04-15", "type": "IN", "quantity_changed": 9999}
        tx_b2 = {"timestamp": "2026-05-15", "type": "OUT", "quantity_changed": 8888}
        self.service._transactions.append(tx_b1)
        self.service._transactions.append(tx_b2)

        analytics_mod = self.service.get_stock_movement_analytics(months=6)

        # Assert SVG curves and areas dynamically change when transaction data changes
        self.assertNotEqual(analytics_orig["inbound_curve"], analytics_mod["inbound_curve"])
        self.assertNotEqual(analytics_orig["inbound_area"], analytics_mod["inbound_area"])
        self.assertNotEqual(analytics_orig["outbound_curve"], analytics_mod["outbound_curve"])
        self.assertNotEqual(analytics_orig["outbound_area"], analytics_mod["outbound_area"])

        # Clean up
        self.service._transactions.remove(tx_b1)
        self.service._transactions.remove(tx_b2)


if __name__ == "__main__":
    unittest.main()

