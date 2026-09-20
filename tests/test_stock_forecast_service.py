import unittest
from backend.services.stock_forecast_service import StockForecastService
from backend.services.inventory_service import InventoryService
from backend.app import app


class TestStockForecastService(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_1_normal_stock_forecast(self):
        product = {
            "name": "Laptop Pro",
            "current_stock": 50,
            "min_stock": 10,
            "average_daily_usage": 2.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["current_stock"], 50)
        self.assertEqual(forecast["min_stock"], 10)
        self.assertEqual(forecast["daily_usage"], 2.0)
        self.assertEqual(forecast["estimated_days_to_minimum"], 20.0) # (50-10)/2 = 20
        self.assertEqual(forecast["forecast_status"], "SAFE")

    def test_2_current_stock_above_minimum(self):
        product = {
            "name": "Monitor",
            "current_stock": 100,
            "min_stock": 10,
            "average_daily_usage": 1.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["estimated_days_to_minimum"], 90.0)
        self.assertEqual(forecast["forecast_status"], "SAFE")

    def test_3_current_stock_equal_to_minimum(self):
        product = {
            "name": "Keyboard",
            "current_stock": 10,
            "min_stock": 10,
            "average_daily_usage": 2.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["estimated_days_to_minimum"], 0.0)
        self.assertEqual(forecast["forecast_status"], "LOW")

    def test_4_current_stock_below_minimum(self):
        product = {
            "name": "Mouse",
            "current_stock": 4,
            "min_stock": 10,
            "average_daily_usage": 2.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["estimated_days_to_minimum"], 0.0)
        self.assertEqual(forecast["forecast_status"], "LOW")

    def test_5_average_daily_usage_greater_than_zero(self):
        product = {
            "name": "Printer Paper",
            "current_stock": 30,
            "min_stock": 10,
            "average_daily_usage": 5.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["estimated_days_to_minimum"], 4.0) # (30-10)/5 = 4
        self.assertEqual(forecast["forecast_status"], "WATCH") # <= 14 days

    def test_6_average_daily_usage_zero(self):
        product = {
            "name": "Desk Lamp",
            "current_stock": 30,
            "min_stock": 10,
            "average_daily_usage": 0.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertIsNone(forecast["estimated_days_to_minimum"])
        self.assertEqual(forecast["estimated_days_display"], "N/A")
        self.assertEqual(forecast["forecast_status"], "UNAVAILABLE")
        self.assertEqual(forecast["forecast_status_label"], "FORECAST UNAVAILABLE")

    def test_7_missing_average_daily_usage(self):
        product = {
            "name": "Stapler",
            "current_stock": 30,
            "min_stock": 10
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertIsNone(forecast["estimated_days_to_minimum"])
        self.assertEqual(forecast["daily_usage"], 0.0)
        self.assertEqual(forecast["forecast_status"], "UNAVAILABLE")

    def test_8_missing_minimum_stock(self):
        product = {
            "name": "Pen Set",
            "current_stock": 30,
            "average_daily_usage": 2.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["min_stock"], 0)
        self.assertEqual(forecast["estimated_days_to_minimum"], 15.0)
        self.assertEqual(forecast["forecast_status"], "SAFE")

    def test_9_missing_quantity(self):
        product = {
            "name": "Notebook",
            "min_stock": 10,
            "average_daily_usage": 2.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["current_stock"], 0)
        self.assertEqual(forecast["forecast_status"], "CRITICAL")

    def test_10_invalid_numeric_values(self):
        product = {
            "name": "Folder",
            "current_stock": "invalid_num",
            "min_stock": "abc",
            "average_daily_usage": None
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["current_stock"], 0)
        self.assertEqual(forecast["min_stock"], 0)
        self.assertEqual(forecast["daily_usage"], 0.0)
        self.assertEqual(forecast["forecast_status"], "CRITICAL")

    def test_11_future_stock_never_becomes_negative(self):
        product = {
            "name": "High Usage Item",
            "current_stock": 10,
            "min_stock": 5,
            "average_daily_usage": 10.0 # 10/day
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        # 10 - 70 = -60 -> clamped to 0
        self.assertEqual(forecast["future_stock"]["day_7"], 0)
        self.assertEqual(forecast["future_stock"]["day_14"], 0)
        self.assertEqual(forecast["future_stock"]["day_30"], 0)

    def test_12_estimated_days_calculation_accuracy(self):
        product = {
            "current_stock": 25,
            "min_stock": 5,
            "average_daily_usage": 4.0
        }
        forecast = StockForecastService.calculate_product_forecast(product)
        self.assertEqual(forecast["estimated_days_to_minimum"], 5.0)

    def test_13_forecast_status_calculation_tiers(self):
        crit = StockForecastService.calculate_product_forecast({"current_stock": 0, "min_stock": 10, "average_daily_usage": 1})
        low = StockForecastService.calculate_product_forecast({"current_stock": 5, "min_stock": 10, "average_daily_usage": 1})
        watch = StockForecastService.calculate_product_forecast({"current_stock": 15, "min_stock": 10, "average_daily_usage": 1}) # 5 days
        safe = StockForecastService.calculate_product_forecast({"current_stock": 100, "min_stock": 10, "average_daily_usage": 1}) # 90 days
        unavail = StockForecastService.calculate_product_forecast({"current_stock": 100, "min_stock": 10, "average_daily_usage": 0})

        self.assertEqual(crit["forecast_status"], "CRITICAL")
        self.assertEqual(low["forecast_status"], "LOW")
        self.assertEqual(watch["forecast_status"], "WATCH")
        self.assertEqual(safe["forecast_status"], "SAFE")
        self.assertEqual(unavail["forecast_status"], "UNAVAILABLE")

    def test_14_dashboard_route_passes_forecast_data(self):
        self.app.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        res = self.app.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Inventory list", res.data)
        self.assertIn(b"EST. DAYS TO MIN", res.data)
        self.assertIn(b"SMART FORECAST", res.data)

    def test_15_existing_dashboard_behavior_preserved(self):
        self.app.post("/login", data={
            "identifier": "admin@inventory.com",
            "password": "Admin@123456"
        })
        res = self.app.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Total items", res.data)
        self.assertIn(b"Stock movement", res.data)
        self.assertIn(b"Top categories", res.data)


if __name__ == "__main__":
    unittest.main()
