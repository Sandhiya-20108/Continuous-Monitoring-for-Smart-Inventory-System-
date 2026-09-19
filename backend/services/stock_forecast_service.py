import logging

logger = logging.getLogger("stock_forecast_service")


class StockForecastService:
    """
    Python business service for Smart Stock Forecast.
    Computes projected future stock levels, estimated days to minimum stock,
    forecast status classification, and replenishment guidance without client-side JavaScript.
    """

    @staticmethod
    def _safe_float(val, default=0.0) -> float:
        """Safely converts input value to float, handling None, empty strings, and type errors."""
        if val is None:
            return default
        try:
            res = float(val)
            return res if not (res != res) else default  # NaN check
        except (ValueError, TypeError):
            return default

    @classmethod
    def calculate_product_forecast(cls, product: dict) -> dict:
        """
        Calculates forecast metrics for a single product dictionary:
        - current_stock
        - min_stock
        - daily_usage
        - estimated_days_to_minimum
        - future_stock (+7d, +14d, +30d)
        - forecast_status (CRITICAL, LOW, WATCH, HEALTHY)
        - forecast_message
        """
        if not product or not isinstance(product, dict):
            product = {}

        # 1. Parse numeric fields safely
        raw_qty = product.get("current_stock", product.get("quantity", product.get("stock", 0)))
        current_stock = max(0.0, cls._safe_float(raw_qty, 0.0))

        raw_min = product.get("min_stock", product.get("minimum_stock_level", product.get("critical_stock", 0)))
        min_stock = max(0.0, cls._safe_float(raw_min, 0.0))

        raw_usage = product.get("average_daily_usage", product.get("daily_usage", 0))
        daily_usage = max(0.0, cls._safe_float(raw_usage, 0.0))

        # 2. Estimated Days to Minimum Stock calculation
        if current_stock <= min_stock:
            estimated_days_to_minimum = 0.0
        elif daily_usage > 0:
            deficit_room = current_stock - min_stock
            estimated_days_to_minimum = round(deficit_room / daily_usage, 1)
        else:
            estimated_days_to_minimum = None  # Telemetry / usage unavailable

        # 3. Future Stock Projections (+7d, +14d, +30d)
        stock_7d = max(0.0, round(current_stock - (daily_usage * 7.0), 1))
        stock_14d = max(0.0, round(current_stock - (daily_usage * 14.0), 1))
        stock_30d = max(0.0, round(current_stock - (daily_usage * 30.0), 1))

        # 4. Forecast Status Classification
        if current_stock <= min_stock:
            status = "CRITICAL"
            status_label = "Critical Deficit"
            badge_class = "pill-critical"
            msg = "Stock is currently at or below minimum safety level."
        elif estimated_days_to_minimum is not None and estimated_days_to_minimum <= 7.0:
            status = "LOW"
            status_label = "Min Stock Imminent"
            badge_class = "pill-low"
            msg = f"Stock is expected to reach minimum level in {estimated_days_to_minimum} days."
        elif estimated_days_to_minimum is not None and estimated_days_to_minimum <= 30.0:
            status = "WATCH"
            status_label = "Monitor Depletion"
            badge_class = "pill-warning"
            msg = f"Stock is expected to reach minimum level in {estimated_days_to_minimum} days."
        else:
            status = "HEALTHY"
            status_label = "Healthy Forecast"
            badge_class = "pill-healthy"
            if daily_usage > 0:
                msg = "Stock is expected to remain above minimum level for the forecast period."
            else:
                msg = "Stock levels stable; usage telemetry indicates no depletion risk."

        return {
            "current_stock": int(current_stock) if current_stock.is_integer() else current_stock,
            "min_stock": int(min_stock) if min_stock.is_integer() else min_stock,
            "daily_usage": round(daily_usage, 2),
            "estimated_days_to_minimum": estimated_days_to_minimum,
            "estimated_days_display": f"{estimated_days_to_minimum} days" if estimated_days_to_minimum is not None else "N/A",
            "future_stock": {
                "day_7": int(stock_7d) if stock_7d.is_integer() else stock_7d,
                "day_14": int(stock_14d) if stock_14d.is_integer() else stock_14d,
                "day_30": int(stock_30d) if stock_30d.is_integer() else stock_30d,
            },
            "forecast_status": status,
            "forecast_status_label": status_label,
            "badge_class": badge_class,
            "forecast_message": msg
        }

    @classmethod
    def enrich_product_with_forecast(cls, product: dict) -> dict:
        """Enriches product dict with 'forecast' key containing pre-calculated forecast metrics."""
        if not product or not isinstance(product, dict):
            return {}
        p = dict(product)
        p["forecast"] = cls.calculate_product_forecast(p)
        return p

    @classmethod
    def enrich_products_with_forecast(cls, products: list) -> list:
        """Enriches list of product dicts with pre-calculated Python forecast metrics."""
        if not products or not isinstance(products, list):
            return []
        return [cls.enrich_product_with_forecast(p) for p in products]
