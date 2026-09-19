import os
from datetime import datetime, date, timezone
from backend.config import Config
from backend.utils import risk_engine
from backend.utils.date_formatter import format_date_filter

SEVERITY_PRIORITY = {
    "CRITICAL": 1,
    "WARNING": 2,
    "RISK": 3,
    "NOTICE": 4
}

SEVERITY_PRESENTATION = {
    "CRITICAL": {
        "css_class": "critical-alert high-risk-alert",
        "border_color": "#BE123C",
        "badge_color": "#f87171",
        "badge_class": "badge-danger",
        "severity_label": "Critical Alert"
    },
    "WARNING": {
        "css_class": "medium-risk-alert low-stock-alert warning-alert",
        "border_color": "#D4A72C",
        "badge_color": "#fbbf24",
        "badge_class": "badge-warning",
        "severity_label": "Warning Alert"
    },
    "RISK": {
        "css_class": "risk-alert anomaly-alert",
        "border_color": "#F97316",
        "badge_color": "#fb923c",
        "badge_class": "badge-orange",
        "severity_label": "Risk Monitor Alert"
    },
    "NOTICE": {
        "css_class": "info-alert notice-alert",
        "border_color": "#3B82F6",
        "badge_color": "#60a5fa",
        "badge_class": "badge-info",
        "severity_label": "Notice"
    }
}


class AlertService:
    """
    Python business logic for Smart Alert Center.
    Handles dynamic alert detection (Low Stock, Expiry, Risk Monitor),
    severity classification, priority sorting, and summary metrics.
    """

    @staticmethod
    def parse_date(date_val) -> date:
        """Helper to parse date string or return date object."""
        if not date_val:
            return None
        if isinstance(date_val, date) and not isinstance(date_val, datetime):
            return date_val
        if isinstance(date_val, datetime):
            return date_val.date()
        if isinstance(date_val, str):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(date_val.strip(), fmt).date()
                except ValueError:
                    continue
        return None

    @classmethod
    def evaluate_low_stock_alerts(cls, product: dict) -> list:
        """
        Evaluates low stock condition for a product in Python:
        if quantity <= minimum_stock_level -> generate Low Stock alert (CRITICAL severity).
        """
        alerts = []
        try:
            qty = float(product.get("current_stock", product.get("quantity", 0)))
        except (ValueError, TypeError):
            qty = 0.0

        try:
            min_qty = float(product.get("min_stock", product.get("minimum_stock_level", 0)))
        except (ValueError, TypeError):
            min_qty = 0.0

        product_id = str(product.get("_id", product.get("id", "unknown")))
        product_name = str(product.get("name", product.get("product_name", "Unknown Product")))
        category = str(product.get("category", "General"))
        expiry_date_str = str(product.get("expiry_date", ""))

        if qty <= min_qty:
            if qty <= 0:
                msg = f"{product_name} is completely OUT OF STOCK (0 units)."
            else:
                msg = f"{product_name} stock is below the minimum required level."

            alerts.append({
                "id": f"alert-low-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Low Stock",
                "type": "Low Stock",
                "severity": "CRITICAL",
                "message": msg,
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_date_str,
                "days_remaining": None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })

        return alerts

    @classmethod
    def evaluate_expiry_alerts(cls, product: dict, ref_date: date = None) -> list:
        """
        Evaluates product expiry in Python using datetime/date remaining calculation:
        - Expired (days_remaining <= 0): CRITICAL -> "Product has expired."
        - Expiring in 1-7 days: WARNING -> "Product will expire within X days."
        - Expiring in 8-30 days: NOTICE -> "Product will expire within X days."
        - > 30 days: No expiry alert.
        """
        alerts = []
        expiry_str = product.get("expiry_date", "")
        exp_date = cls.parse_date(expiry_str)

        if not exp_date:
            return alerts

        if ref_date is None:
            ref_date = getattr(Config, "CURRENT_SIMULATION_DATE", date.today())
            if isinstance(ref_date, datetime):
                ref_date = ref_date.date()

        days_remaining = (exp_date - ref_date).days

        product_id = str(product.get("_id", product.get("id", "unknown")))
        product_name = str(product.get("name", product.get("product_name", "Unknown Product")))
        category = str(product.get("category", "General"))
        try:
            qty = float(product.get("current_stock", product.get("quantity", 0)))
        except (ValueError, TypeError):
            qty = 0.0

        try:
            min_qty = float(product.get("min_stock", product.get("minimum_stock_level", 0)))
        except (ValueError, TypeError):
            min_qty = 0.0

        if days_remaining <= 0:
            alerts.append({
                "id": f"alert-exp-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Expiry Alert",
                "type": "Expiry Alert",
                "severity": "CRITICAL",
                "message": "Product has expired.",
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_str,
                "days_remaining": days_remaining,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })
        elif 1 <= days_remaining <= 7:
            alerts.append({
                "id": f"alert-exp-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Expiry Alert",
                "type": "Expiry Alert",
                "severity": "WARNING",
                "message": f"Product will expire within {days_remaining} days.",
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_str,
                "days_remaining": days_remaining,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })
        elif 8 <= days_remaining <= 30:
            alerts.append({
                "id": f"alert-exp-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Expiry Alert",
                "type": "Expiry Alert",
                "severity": "NOTICE",
                "message": f"Product will expire within {days_remaining} days.",
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_str,
                "days_remaining": days_remaining,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })

        return alerts

    @classmethod
    def evaluate_risk_alerts(cls, product: dict, ref_date: date = None) -> list:
        """
        Integrates existing Risk Monitor logic (risk_engine) into Smart Alert Center entries.
        """
        alerts = []
        product_id = str(product.get("_id", product.get("id", "unknown")))
        product_name = str(product.get("name", product.get("product_name", "Unknown Product")))
        category = str(product.get("category", "General"))
        expiry_str = str(product.get("expiry_date", ""))

        try:
            qty = float(product.get("current_stock", product.get("quantity", 0)))
        except (ValueError, TypeError):
            qty = 0.0

        try:
            min_qty = float(product.get("min_stock", product.get("minimum_stock_level", 0)))
        except (ValueError, TypeError):
            min_qty = 0.0

        risk_analysis = product.get("risk_analysis")
        if not risk_analysis:
            try:
                risk_analysis = risk_engine.calculate_inventory_risk_score(product, ref_date=ref_date)
            except Exception:
                risk_analysis = {}

        anomaly_info = risk_analysis.get("anomaly_info", {})
        demand_trend = risk_analysis.get("demand_trend", "")
        risk_score = risk_analysis.get("score", 0)

        # Check for movement anomaly or demand surge/trend risk
        if anomaly_info and anomaly_info.get("has_anomaly"):
            alerts.append({
                "id": f"alert-anom-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Risk Alert",
                "type": "Risk Alert",
                "severity": "RISK",
                "message": anomaly_info.get("description", f"Unusual stock movement anomaly detected for {product_name}."),
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_str,
                "days_remaining": None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })
        elif demand_trend == "Increasing" and qty < (min_qty * 1.5):
            alerts.append({
                "id": f"alert-trend-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Risk Alert",
                "type": "Risk Alert",
                "severity": "RISK",
                "message": f"Demand surge: Daily consumption trend for {product_name} is increasing rapidly.",
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_str,
                "days_remaining": None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })
        elif risk_score >= 61.0 and qty > min_qty: # High risk score non-low-stock
            alerts.append({
                "id": f"alert-risk-{product_id}",
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "alert_type": "Risk Alert",
                "type": "Risk Alert",
                "severity": "RISK",
                "message": f"High risk score ({risk_score}/100) computed by Risk Monitor engine.",
                "current_quantity": qty,
                "current_stock": qty,
                "minimum_stock_level": min_qty,
                "min_stock": min_qty,
                "expiry_date": expiry_str,
                "days_remaining": None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })

        return alerts

    @classmethod
    def generate_alerts_for_product(cls, product: dict, ref_date: date = None) -> list:
        """
        Generates all distinct Python alerts for a single product.
        One product can generate multiple different alerts (Low Stock, Expiry, Risk).
        """
        alerts = []
        alerts.extend(cls.evaluate_low_stock_alerts(product))
        alerts.extend(cls.evaluate_expiry_alerts(product, ref_date=ref_date))
        alerts.extend(cls.evaluate_risk_alerts(product, ref_date=ref_date))
        return alerts

    @classmethod
    def enrich_alert_presentation(cls, alert: dict, status_info: dict = None) -> dict:
        """Enriches alert dict with presentation attributes for Jinja/CSS."""
        a = dict(alert)
        sev = str(a.get("severity", "NOTICE")).upper()

        pres = SEVERITY_PRESENTATION.get(sev, SEVERITY_PRESENTATION["NOTICE"])
        a["css_class"] = pres["css_class"]
        a["border_color"] = pres["border_color"]
        a["badge_color"] = pres["badge_color"]
        a["badge_class"] = pres["badge_class"]
        a["severity_label"] = pres["severity_label"]

        if status_info:
            a["status"] = status_info.get("status", "New")
            a["updated_by"] = status_info.get("updated_by", "")
            a["updated_at"] = status_info.get("updated_at", "")
        else:
            a.setdefault("status", "New")
            a.setdefault("updated_by", "")
            a.setdefault("updated_at", "")

        raw_ts = a.get("generated_at", a.get("timestamp", ""))
        a["formatted_timestamp"] = format_date_filter(raw_ts) if raw_ts else "Recently"
        return a

    @classmethod
    def sort_alerts_by_severity(cls, alerts: list) -> list:
        """
        Sorts alerts in Python based on priority:
        1. CRITICAL
        2. WARNING
        3. RISK
        4. NOTICE
        """
        return sorted(
            alerts,
            key=lambda x: (
                SEVERITY_PRIORITY.get(str(x.get("severity", "NOTICE")).upper(), 99),
                x.get("product_name", "").lower(),
                x.get("alert_type", "").lower()
            )
        )

    @classmethod
    def calculate_alert_summary(cls, alerts: list) -> dict:
        """
        Generates Python summary counts:
        - Critical Alerts
        - Warning Alerts
        - Risk Alerts
        - Notice Alerts
        - Total Alerts
        """
        critical_count = 0
        warning_count = 0
        risk_count = 0
        notice_count = 0

        for a in alerts:
            sev = str(a.get("severity", "")).upper()
            if sev == "CRITICAL":
                critical_count += 1
            elif sev == "WARNING":
                warning_count += 1
            elif sev == "RISK":
                risk_count += 1
            elif sev == "NOTICE":
                notice_count += 1

        return {
            "critical_count": critical_count,
            "warning_count": warning_count,
            "risk_count": risk_count,
            "notice_count": notice_count,
            "total_count": len(alerts)
        }

    @classmethod
    def process_smart_alerts(cls, products: list, ref_date: date = None, severity_filter: str = "all", status_provider=None) -> tuple:
        """
        End-to-end Python pipeline for Smart Alert Center:
        1. Evaluate all product alerts
        2. Filter by severity if requested
        3. Enrich presentation attributes & DB status
        4. Sort by severity priority
        5. Compute summary counts
        Returns (sorted_alerts, summary_dict)
        """
        raw_alerts = []
        for p in products:
            raw_alerts.extend(cls.generate_alerts_for_product(p, ref_date=ref_date))

        # Enriched alerts list before severity filtering for complete summary counts
        enriched_all = []
        for a in raw_alerts:
            st = status_provider(a["id"]) if status_provider else None
            enriched_all.append(cls.enrich_alert_presentation(a, st))

        # Calculate summary counts from ALL active alerts
        summary = cls.calculate_alert_summary(enriched_all)

        # Apply severity filtering for display
        if severity_filter and severity_filter.lower() != "all":
            target = severity_filter.upper()
            display_alerts = [a for a in enriched_all if str(a.get("severity", "")).upper() == target]
        else:
            display_alerts = enriched_all

        # Sort display alerts by severity priority
        sorted_alerts = cls.sort_alerts_by_severity(display_alerts)

        return sorted_alerts, summary
