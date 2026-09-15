from datetime import datetime
from backend.utils.date_formatter import format_date_filter
from backend.utils import risk_engine

def present_product(product: dict, date_format: str = None) -> dict:
    """
    Transforms a raw inventory product dict into a Python View Model
    with pre-calculated UI presentation attributes (CSS classes, labels, formatted prices, stock percentages).
    """
    if not product:
        return {}

    p = dict(product)

    # 1. Stock calculations & limits
    try:
        current_stock = float(p.get("current_stock", 0))
    except (ValueError, TypeError):
        current_stock = 0.0

    try:
        min_stock = float(p.get("min_stock", 10))
    except (ValueError, TypeError):
        min_stock = 10.0

    try:
        max_stock = float(p.get("max_stock", max(current_stock, min_stock * 3, 50)))
    except (ValueError, TypeError):
        max_stock = max(current_stock, min_stock * 3, 50)

    # Stock Percentage (clamped 0-100%)
    if max_stock > 0:
        stock_pct = min(100.0, max(0.0, round((current_stock / max_stock) * 100.0, 1)))
    else:
        stock_pct = 0.0

    # Stock Status Classification
    if current_stock <= 0:
        status_label = "Out of Stock"
        status_class = "status-out-of-stock"
        badge_class = "badge-danger"
    elif current_stock < min_stock:
        status_label = "Low Stock"
        status_class = "status-low-stock"
        badge_class = "badge-warning"
    else:
        status_label = "In Stock"
        status_class = "status-in-stock"
        badge_class = "badge-success"

    # Risk Engine Assessment
    risk_analysis = p.get("risk_analysis") or risk_engine.calculate_inventory_risk_score(p)
    risk_level = risk_analysis.get("level", p.get("risk_level", "SAFE")).upper()
    risk_score = risk_analysis.get("score", p.get("risk_score", 0))

    if "CRITICAL" in risk_level:
        risk_label = "Critical Risk"
        risk_class = "risk-critical"
        risk_badge = "badge-critical"
    elif "HIGH" in risk_level:
        risk_label = "High Risk"
        risk_class = "risk-high"
        risk_badge = "badge-danger"
    elif "WARNING" in risk_level or "MEDIUM" in risk_level:
        risk_label = "Warning"
        risk_class = "risk-warning"
        risk_badge = "badge-warning"
    else:
        risk_label = "Safe"
        risk_class = "risk-safe"
        risk_badge = "badge-success"

    # Reorder Recommendation
    reorder_info = risk_engine.calculate_reorder_recommendation(p, risk_level)

    # Price & Value Formatting
    try:
        unit_price = float(p.get("unit_price", p.get("price", 0.0)))
    except (ValueError, TypeError):
        unit_price = 0.0

    total_val = unit_price * current_stock

    # Date formatting
    expiry_date_raw = p.get("expiry_date", "")
    formatted_expiry = format_date_filter(expiry_date_raw, date_format) if expiry_date_raw else "N/A"

    p.update({
        "current_stock_int": int(current_stock) if current_stock.is_integer() else current_stock,
        "min_stock_int": int(min_stock) if min_stock.is_integer() else min_stock,
        "stock_pct": stock_pct,
        "status_label": status_label,
        "status_class": status_class,
        "badge_class": badge_class,
        "risk_label": risk_label,
        "risk_class": risk_class,
        "risk_badge": risk_badge,
        "risk_score": risk_score,
        "unit_price_float": unit_price,
        "formatted_unit_price": f"${unit_price:,.2f}",
        "total_value_float": total_val,
        "formatted_total_value": f"${total_val:,.2f}",
        "formatted_expiry_date": formatted_expiry,
        "reorder_info": reorder_info,
        "requires_reorder": reorder_info["requires_reorder"],
        "recommended_reorder": reorder_info["recommended_reorder"],
        "days_to_stockout": risk_analysis.get("days_to_stockout", 999)
    })

    return p

def present_alert(alert: dict, date_format: str = None) -> dict:
    """
    Transforms a raw alert dict into a Python View Model
    with risk border class, severity labels, and formatted timestamps.
    """
    if not alert:
        return {}

    a = dict(alert)
    alert_type = str(a.get("type", "")).strip()
    severity = str(a.get("severity", a.get("risk_level", "SAFE"))).strip()

    # Border Class Mapping (Exact UI preservation matching classify_alert)
    if severity == "Critical" or alert_type == "Out of Stock":
        border_class = "critical-alert high-risk-alert"
        badge_class = "badge-danger"
        severity_label = "Critical Risk"
    elif alert_type == "Low Stock" or severity in ["Warning", "Medium", "Low", "Medium Risk", "High Risk", "High"]:
        border_class = "medium-risk-alert low-stock-alert warning-alert"
        badge_class = "badge-warning"
        severity_label = "Medium Risk / Warning"
    elif severity in ["Safe", "Normal", "Healthy"] or alert_type in ["Demand Trend", "Demand Surge"]:
        border_class = "safe-alert healthy-alert normal-alert"
        badge_class = "badge-success"
        severity_label = "Safe / Normal"
    else:
        border_class = "info-alert"
        badge_class = "badge-secondary"
        severity_label = severity.capitalize()

    timestamp_raw = a.get("timestamp", a.get("created_at", ""))
    formatted_timestamp = format_date_filter(timestamp_raw, date_format) if timestamp_raw else "Recently"

    a.update({
        "border_class": border_class,
        "badge_class": badge_class,
        "severity_label": severity_label,
        "formatted_timestamp": formatted_timestamp
    })

    return a

def present_transaction(tx: dict, date_format: str = None) -> dict:
    """
    Transforms a raw transaction dict into a Python View Model.
    """
    if not tx:
        return {}

    t = dict(tx)
    op_type = str(t.get("type", "ADJUSTMENT")).upper()

    if op_type == "STOCK_IN":
        type_badge_class = "badge-success"
        type_label = "Stock In (+)"
    elif op_type == "STOCK_OUT":
        type_badge_class = "badge-danger"
        type_label = "Stock Out (-)"
    else:
        type_badge_class = "badge-info"
        type_label = "Adjustment"

    timestamp_raw = t.get("timestamp", "")
    formatted_timestamp = format_date_filter(timestamp_raw, date_format) if timestamp_raw else "Recently"

    t.update({
        "type_badge_class": type_badge_class,
        "type_label": type_label,
        "formatted_timestamp": formatted_timestamp
    })

    return t

def present_dashboard_metrics(metrics: dict) -> dict:
    """
    Prepares aggregated dashboard numbers & health score.
    """
    if not metrics:
        return {
            "total_products": 0,
            "total_inventory_value": "$0.00",
            "low_stock_count": 0,
            "out_of_stock_count": 0,
            "expiring_soon_count": 0,
            "critical_risk_count": 0,
            "high_risk_count": 0,
            "warning_risk_count": 0,
            "safe_risk_count": 0,
            "health_score": 100
        }

    m = dict(metrics)

    total_val = float(m.get("total_inventory_value", m.get("total_value", 0.0)))
    m["formatted_total_value"] = f"${total_val:,.2f}"

    return m
