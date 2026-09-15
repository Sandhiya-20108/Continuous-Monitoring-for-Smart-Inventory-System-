import math
from datetime import datetime, date
from backend.config import Config

def calculate_days_to_stockout(current_stock: float, average_daily_usage: float) -> float:
    """
    Calculates estimated days to stockout using rule-based formula:
    days_to_stockout = current_stock / average_daily_usage
    """
    if current_stock <= 0:
        return 0.0
    if average_daily_usage <= 0:
        return 999.0  # Infinite/No stockout risk based on usage
    return round(float(current_stock) / float(average_daily_usage), 1)


def calculate_expiry_metrics(expiry_date_str: str, ref_date: date = None) -> dict:
    """
    Evaluates proximity to expiry date and computes days remaining and risk level.
    """
    if ref_date is None:
        ref_date = Config.CURRENT_SIMULATION_DATE

    try:
        exp_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        days_remaining = (exp_date - ref_date).days
    except (ValueError, TypeError):
        return {
            "days_remaining": 999,
            "status": "Unknown",
            "is_expiring_soon": False
        }

    if days_remaining <= 0:
        status = "Expired"
        is_expiring_soon = True
    elif days_remaining <= 7:
        status = "Critical Expiry"
        is_expiring_soon = True
    elif days_remaining <= 14:
        status = "Approaching Expiry"
        is_expiring_soon = True
    else:
        status = "Good"
        is_expiring_soon = False

    return {
        "days_remaining": days_remaining,
        "status": status,
        "is_expiring_soon": is_expiring_soon
    }


def classify_demand_trend(daily_usage_history: list) -> str:
    """
    Classifies demand trend over the 7-day usage history into Increasing, Decreasing, or Stable.
    Uses simple linear trend / endpoints comparison.
    """
    if not daily_usage_history or len(daily_usage_history) < 3:
        return "Stable"

    first_half_avg = sum(daily_usage_history[:3]) / 3.0
    second_half_avg = sum(daily_usage_history[-3:]) / 3.0
    diff = second_half_avg - first_half_avg

    if diff > 1.5:
        return "Increasing"
    elif diff < -1.5:
        return "Decreasing"
    else:
        return "Stable"


def detect_movement_anomaly(today_movement: float, average_daily_usage: float) -> dict:
    """
    Detects unusual stock movement based on baseline daily usage.
    """
    if average_daily_usage <= 0:
        return {"has_anomaly": False, "type": None, "description": "Normal usage"}

    ratio = today_movement / average_daily_usage

    if ratio >= Config.SURGE_ANOMALY_MULTIPLIER:
        return {
            "has_anomaly": True,
            "type": "surge",
            "ratio": round(ratio, 1),
            "description": f"Unusual consumption surge: Today's movement ({today_movement} units) is {round(ratio, 1)}x baseline ({average_daily_usage}/day)."
        }
    elif today_movement == 0 and average_daily_usage >= Config.ZERO_MOVEMENT_BASELINE_MIN:
        return {
            "has_anomaly": True,
            "type": "drop",
            "ratio": 0.0,
            "description": f"Unusual zero movement: Baseline is {average_daily_usage}/day, but 0 units consumed today."
        }
    
    return {"has_anomaly": False, "type": None, "ratio": round(ratio, 1), "description": "Normal inventory movement"}


def calculate_inventory_risk_score(product: dict, ref_date: date = None) -> dict:
    """
    Calculates 0-100 Risk Score for a product considering stock deficit, stockout days,
    expiry proximity, demand surge, and anomalies.
    """
    current_stock = float(product.get("current_stock", 0))
    min_stock = float(product.get("min_stock", 1))
    avg_usage = float(product.get("average_daily_usage", 1))
    today_mov = float(product.get("today_movement", 0))
    history = product.get("daily_usage_history", [])
    expiry_str = product.get("expiry_date", "")

    # 1. Stock Depletion Score (0 - 35 pts)
    if current_stock <= 0:
        score_depletion = 35.0
    elif current_stock < min_stock:
        deficit_ratio = (min_stock - current_stock) / min_stock
        score_depletion = 20.0 + (15.0 * deficit_ratio)
    elif current_stock < (2 * min_stock):
        ratio = (current_stock - min_stock) / min_stock
        score_depletion = 20.0 * (1.0 - ratio)
    else:
        score_depletion = 0.0

    # 2. Stockout Proximity Score (0 - 25 pts)
    days_stockout = calculate_days_to_stockout(current_stock, avg_usage)
    if days_stockout <= 1.0:
        score_stockout = 25.0
    elif days_stockout <= 3.0:
        score_stockout = 20.0
    elif days_stockout <= 7.0:
        score_stockout = 12.0
    elif days_stockout <= 14.0:
        score_stockout = 5.0
    else:
        score_stockout = 0.0

    # 3. Expiry Proximity Score (0 - 20 pts)
    expiry_info = calculate_expiry_metrics(expiry_str, ref_date)
    days_exp = expiry_info["days_remaining"]
    if days_exp <= 2:
        score_expiry = 20.0
    elif days_exp <= 5:
        score_expiry = 15.0
    elif days_exp <= 10:
        score_expiry = 10.0
    elif days_exp <= 20:
        score_expiry = 5.0
    else:
        score_expiry = 0.0

    # 4. Anomaly & Surge Score (0 - 20 pts)
    anomaly_info = detect_movement_anomaly(today_mov, avg_usage)
    score_anomaly = 0.0
    if anomaly_info["has_anomaly"]:
        if anomaly_info["type"] == "surge":
            score_anomaly += 15.0
        elif anomaly_info["type"] == "drop":
            score_anomaly += 5.0

    demand_trend = classify_demand_trend(history)
    if demand_trend == "Increasing":
        score_anomaly += 5.0

    # Total Risk Score (Clamped to 0 - 100)
    raw_total = score_depletion + score_stockout + score_expiry + score_anomaly
    total_score = min(100.0, max(0.0, round(raw_total, 1)))

    # Assign Risk Level
    if total_score >= 81.0:
        level = Config.RISK_LEVEL_CRITICAL
    elif total_score >= 61.0:
        level = Config.RISK_LEVEL_HIGH
    elif total_score >= 31.0:
        level = Config.RISK_LEVEL_WARNING
    else:
        level = Config.RISK_LEVEL_SAFE

    return {
        "score": total_score,
        "level": level,
        "days_to_stockout": days_stockout,
        "expiry_info": expiry_info,
        "demand_trend": demand_trend,
        "anomaly_info": anomaly_info,
        "breakdown": {
            "depletion": round(score_depletion, 1),
            "stockout": round(score_stockout, 1),
            "expiry": round(score_expiry, 1),
            "anomaly": round(score_anomaly, 1)
        }
    }


def generate_product_recommendation(product: dict, risk_analysis: dict) -> str:
    """
    Generates deterministic, clear operational recommendations based on risk metrics.
    """
    level = risk_analysis["level"]
    days_to_stockout = risk_analysis["days_to_stockout"]
    expiry_info = risk_analysis["expiry_info"]
    anomaly_info = risk_analysis["anomaly_info"]
    demand_trend = risk_analysis["demand_trend"]
    current_stock = product.get("current_stock", 0)
    min_stock = product.get("min_stock", 0)
    avg_usage = product.get("average_daily_usage", 1)

    reorder_suggested = max(0, int((min_stock * 2.5) - current_stock))

    recs = []
    if current_stock == 0:
        recs.append(f"OUT OF STOCK! Place immediate expedited order for {reorder_suggested} {product.get('unit', 'units')}.")
    elif days_to_stockout <= 3:
        recs.append(f"Stockout imminent in {days_to_stockout} days. Reorder {reorder_suggested} units immediately.")
    elif current_stock < min_stock:
        recs.append(f"Stock ({current_stock}) is below safety threshold ({min_stock}). Schedule reorder of {reorder_suggested} units.")

    if expiry_info["days_remaining"] <= 3:
        recs.append(f"CRITICAL EXPIRY: {current_stock} units expire in {expiry_info['days_remaining']} days! Prioritize immediate clearance or internal transfer.")
    elif expiry_info["days_remaining"] <= 10:
        recs.append(f"Approaching expiry in {expiry_info['days_remaining']} days. Monitor usage rate.")

    if anomaly_info["has_anomaly"] and anomaly_info["type"] == "surge":
        recs.append(f"Surge detected ({anomaly_info['ratio']}x normal). Verify if this is a one-off order or systemic demand shift.")

    if demand_trend == "Increasing" and not recs:
        recs.append(f"Demand is trending upwards. Consider raising safety stock threshold from {min_stock} to {int(min_stock * 1.3)}.")

    if not recs:
        recs.append("Inventory levels healthy and operating within normal parameters.")

    return " ".join(recs)


def simulate_what_if(product: dict, demand_change_pct: float, target_supply_days: int = 30) -> dict:
    """
    Simulates impact of demand change (+X% or -X%) on days to stockout & recommended reorder quantity.
    """
    current_stock = float(product.get("current_stock", 0))
    base_usage = float(product.get("average_daily_usage", 1.0))
    min_stock = float(product.get("min_stock", 1.0))

    multiplier = 1.0 + (float(demand_change_pct) / 100.0)
    adjusted_daily_usage = max(0.1, round(base_usage * multiplier, 2))

    new_days_to_stockout = calculate_days_to_stockout(current_stock, adjusted_daily_usage)
    base_days_to_stockout = calculate_days_to_stockout(current_stock, base_usage)

    target_stock = adjusted_daily_usage * target_supply_days
    suggested_reorder_qty = max(0, math.ceil(target_stock - current_stock))

    return {
        "product_id": product.get("_id"),
        "product_name": product.get("name"),
        "demand_change_pct": demand_change_pct,
        "base_daily_usage": base_usage,
        "adjusted_daily_usage": adjusted_daily_usage,
        "base_days_to_stockout": base_days_to_stockout,
        "new_days_to_stockout": new_days_to_stockout,
        "suggested_reorder_qty": suggested_reorder_qty,
        "impact_summary": f"At {demand_change_pct:+}% demand, daily usage becomes {adjusted_daily_usage}/day. Stock will last {new_days_to_stockout} days (vs {base_days_to_stockout} days originally)."
    }


def calculate_reorder_recommendation(product: dict, risk_level: str = None) -> dict:
    """
    Calculates recommended reorder quantity, stock deficit, and recommended action
    based on current stock, minimum stock limit, and risk tier.
    """
    try:
        raw_current = product.get("current_stock")
        current_stock = float(raw_current) if raw_current is not None else 0.0
    except (ValueError, TypeError):
        current_stock = 0.0

    try:
        raw_min = product.get("min_stock")
        min_stock = float(raw_min) if raw_min is not None else 0.0
    except (ValueError, TypeError):
        min_stock = 0.0

    current_clean = max(0.0, current_stock)
    min_clean = max(0.0, min_stock)

    if current_clean < min_clean:
        deficit = min_clean - current_clean
        recommended_reorder = deficit

        level = str(risk_level or product.get("risk_level", "SAFE")).upper()
        if "CRITICAL" in level:
            action = "REORDER IMMEDIATELY"
        elif "HIGH" in level:
            action = "REORDER SOON"
        elif "WARNING" in level:
            action = "MONITOR & PLAN REORDER"
        else:
            action = "NO REORDER REQUIRED"
    else:
        deficit = 0.0
        recommended_reorder = 0.0
        action = "NO REORDER REQUIRED"

    def fmt_num(val):
        if isinstance(val, (int, float)):
            return int(val) if float(val).is_integer() else round(float(val), 2)
        return 0

    return {
        "current_stock": fmt_num(current_stock),
        "min_stock": fmt_num(min_stock),
        "stock_deficit": fmt_num(deficit),
        "recommended_reorder": fmt_num(recommended_reorder),
        "recommended_action": action,
        "requires_reorder": recommended_reorder > 0
    }


def get_reorder_recommendations(products: list) -> list:
    """
    Computes reorder recommendations for a list of products and sorts them by risk tier priority:
    CRITICAL (1) -> HIGH (2) -> WARNING (3) -> SAFE (4).
    Within each tier, items with stock deficit come first (sorted by deficit descending).
    """
    tier_priority = {
        "CRITICAL": 1,
        "HIGH": 2,
        "WARNING": 3,
        "SAFE": 4
    }

    recs = []
    for item in products:
        risk_level = item.get("risk_level", "SAFE")
        reorder_info = calculate_reorder_recommendation(item, risk_level)
        rec_item = dict(item)
        rec_item["reorder_info"] = reorder_info
        rec_item["stock_deficit"] = reorder_info["stock_deficit"]
        rec_item["recommended_reorder"] = reorder_info["recommended_reorder"]
        rec_item["recommended_action"] = reorder_info["recommended_action"]
        rec_item["requires_reorder"] = reorder_info["requires_reorder"]
        recs.append(rec_item)

    recs.sort(key=lambda x: (
        tier_priority.get(str(x.get("risk_level", "SAFE")).upper(), 99),
        -float(x.get("stock_deficit", 0)),
        x.get("name", "")
    ))
    return recs
