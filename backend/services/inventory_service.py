import json
import os
import random
import logging
from datetime import datetime, timezone
from backend.models.inventory_model import InventoryItemModel
from backend.services.alert_service import AlertService
from backend.utils import risk_engine
from backend.utils import view_helpers
from backend.database import MongoDBConnection
from backend.repositories.inventory_repository import InventoryRepository

logger = logging.getLogger("inventory_service")

class InventoryService:
    """
    Inventory Business Service.
    Orchestrates MongoDB Atlas repository persistent storage with dynamic Risk Intelligence calculation.
    Includes seamless fallback to in-memory JSON store if MongoDB URI is unconfigured or offline.
    """
    _saved_reports = []

    def __init__(self, data_file_path: str = None, uri: str = None):
        if data_file_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_file_path = os.path.join(base_dir, "data", "sample_products.json")
        
        self.data_file_path = data_file_path
        self._in_memory_products = {}
        self._alert_statuses = {}
        
        # MongoDB Connection & Repository Setup
        self.db_conn = MongoDBConnection(uri=uri)
        self.use_mongodb = self.db_conn.connect()
        self.repository = InventoryRepository(self.db_conn) if self.use_mongodb else None

        self._transactions = []
        self.initialize_data()

    def record_transaction(self, product_id: str, product_name: str, op_type: str, qty_changed: int, old_stock: int, new_stock: int, user: str = "System", role: str = "System", notes: str = "") -> dict:
        """Records an inventory transaction in MongoDB or fallback memory store."""
        tx_doc = {
            "id": f"tx-{len(self._transactions) + 1:04d}",
            "product_id": product_id,
            "product_name": product_name,
            "type": op_type,  # STOCK_IN, STOCK_OUT, ADJUSTMENT
            "quantity_changed": qty_changed,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user or "System Administrator",
            "role": role or "Staff",
            "notes": notes or ""
        }
        
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("inventory_transactions")
                if coll is not None:
                    coll.insert_one(dict(tx_doc))
            except Exception as err:
                logger.error(f"Error persisting transaction: {err}")

        self._transactions.insert(0, tx_doc)
        return tx_doc

    def get_product_history(self, product_id: str) -> list:
        """Retrieves transaction history for a specific product."""
        txs = []
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("inventory_transactions")
                if coll is not None:
                    docs = list(coll.find({"$or": [{"product_id": product_id}, {"product_name": product_id}]}).sort("timestamp", -1))
                    for d in docs:
                        if "_id" in d:
                            d["_id"] = str(d["_id"])
                    if docs:
                        txs = docs
            except Exception as err:
                logger.error(f"Error fetching history from MongoDB: {err}")

        if not txs:
            txs = [t for t in self._transactions if t.get("product_id") == product_id or t.get("product_name") == product_id]

        return [view_helpers.present_transaction(t) for t in txs]

    def get_recent_transactions(self, limit: int = 10) -> list:
        """Retrieves overall recent transaction history across all products."""
        txs = []
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("inventory_transactions")
                if coll is not None:
                    docs = list(coll.find().sort("timestamp", -1).limit(limit))
                    for d in docs:
                        if "_id" in d:
                            d["_id"] = str(d["_id"])
                    if docs:
                        txs = docs
            except Exception as err:
                logger.error(f"Error fetching recent transactions from MongoDB: {err}")

        if not txs:
            txs = self._transactions[:limit]

        return [view_helpers.present_transaction(t) for t in txs[:limit]]

    def update_stock_quantity(self, product_id: str, quantity: int, operation: str = "ADJUSTMENT", user: str = "Admin", role: str = "Admin", notes: str = "") -> dict:
        """Updates product stock quantity supporting Stock In (Receive), Stock Out (Issue), and Direct Adjustments with full audit validation."""
        existing = self.get_product_by_id(product_id)
        if not existing:
            return {"success": False, "message": f"Product not found with ID '{product_id}'"}

        try:
            qty = int(quantity)
        except (ValueError, TypeError):
            return {"success": False, "message": "Invalid quantity: Please enter a valid integer number."}

        op = (operation or "ADJUSTMENT").upper().strip()

        if op in ["STOCK_IN", "STOCK_OUT"] and qty <= 0:
            return {"success": False, "message": f"Invalid quantity: Operation {op.replace('_', ' ')} requires a positive quantity greater than 0."}

        old_stock = int(existing.get("current_stock", 0))

        if op == "STOCK_IN":
            qty_changed = qty
            new_stock = old_stock + qty
            op_label = "Stock Receive (Stock In)"
        elif op == "STOCK_OUT":
            if qty > old_stock:
                return {
                    "success": False,
                    "message": f"Insufficient stock: Requested issue quantity ({qty}) exceeds available stock level ({old_stock} units)."
                }
            qty_changed = -qty
            new_stock = old_stock - qty
            op_label = "Stock Issue (Stock Out)"
        else:  # ADJUSTMENT / DIRECT SET
            new_stock = max(0, qty)
            qty_changed = new_stock - old_stock
            op_label = "Direct Stock Adjustment"

        now_iso = datetime.now(timezone.utc).isoformat()
        update_dict = {
            "current_stock": new_stock,
            "last_updated": now_iso
        }

        internal_id = existing["_id"]
        if self.use_mongodb and self.repository and self.db_conn.is_connected():
            self.repository.update_product(product_id, update_dict)

        if internal_id in self._in_memory_products:
            self._in_memory_products[internal_id]["current_stock"] = new_stock
            self._in_memory_products[internal_id]["last_updated"] = now_iso
        if product_id in self._in_memory_products:
            self._in_memory_products[product_id]["current_stock"] = new_stock
            self._in_memory_products[product_id]["last_updated"] = now_iso

        # Record transaction log
        self.record_transaction(
            product_id=internal_id,
            product_name=existing.get("name", "Product"),
            op_type=op,
            qty_changed=qty_changed,
            old_stock=old_stock,
            new_stock=new_stock,
            user=user,
            role=role,
            notes=notes or f"{op_label} applied ({qty_changed:+d} units)"
        )

        updated_item = self.get_product_by_id(product_id)
        return {
            "success": True,
            "message": f"Successfully performed {op_label}: New stock for {existing.get('name')} is {new_stock} units.",
            "data": updated_item
        }

    def update_alert_status(self, alert_id: str, status: str, user: str = "System") -> dict:
        """Updates status of a low-stock or expiry alert (New, Viewed, Resolved)."""
        valid_statuses = ["New", "Viewed", "Resolved"]
        status_clean = (status or "").strip().title()
        if status_clean not in valid_statuses:
            return {"success": False, "message": f"Invalid alert status. Allowed values: {', '.join(valid_statuses)}"}

        now_iso = datetime.now(timezone.utc).isoformat()
        status_doc = {
            "alert_id": alert_id,
            "status": status_clean,
            "updated_by": user,
            "updated_at": now_iso
        }
        self._alert_statuses[alert_id] = status_doc

        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("alert_statuses")
                if coll is not None:
                    coll.update_one({"alert_id": alert_id}, {"$set": status_doc}, upsert=True)
            except Exception as err:
                logger.error(f"Error persisting alert status: {err}")

        return {"success": True, "message": f"Alert status updated to '{status_clean}'", "data": status_doc}

    def get_alert_status(self, alert_id: str) -> dict:
        """Helper to get alert status from memory or DB."""
        if alert_id in self._alert_statuses:
            return self._alert_statuses[alert_id]

        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("alert_statuses")
                if coll is not None:
                    doc = coll.find_one({"alert_id": alert_id})
                    if doc:
                        if "_id" in doc:
                            del doc["_id"]
                        self._alert_statuses[alert_id] = doc
                        return doc
            except Exception as err:
                logger.error(f"Error fetching alert status from MongoDB: {err}")

        return {"status": "New", "updated_by": "", "updated_at": ""}

    def initialize_data(self):
        """Initializes store. Seeds MongoDB if empty; populates fallback JSON store."""
        raw_items = []
        if os.path.exists(self.data_file_path):
            with open(self.data_file_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)

        # Fallback JSON dictionary store setup
        self._in_memory_products = {
            item["_id"]: InventoryItemModel(item).to_dict()
            for item in raw_items
        }

        # If MongoDB is active, create indexes and seed if collection is empty
        if self.use_mongodb and self.repository:
            self.repository.create_indexes()
            self.repository.seed_sample_products_if_empty(raw_items)

    def get_db_health(self) -> dict:
        """Returns MongoDB database connection health status report."""
        return self.db_conn.check_health()

    def _fetch_raw_products(self) -> list:
        """Helper to fetch raw product dicts from MongoDB or fallback JSON store."""
        if self.use_mongodb and self.repository and self.db_conn.is_connected():
            mongo_docs = self.repository.get_all()
            if mongo_docs:
                return mongo_docs
        
        # Fallback to in-memory store
        return list(self._in_memory_products.values())

    def get_all_products(self, category=None, risk_level=None, search=None) -> list:
        """Returns all products augmented with Risk Intelligence metrics."""
        raw_products = self._fetch_raw_products()
        results = []

        for item in raw_products:
            risk_info = risk_engine.calculate_inventory_risk_score(item)
            recommendation = risk_engine.generate_product_recommendation(item, risk_info)
            reorder_info = risk_engine.calculate_reorder_recommendation(item, risk_info["level"])
            
            augmented = dict(item)
            augmented["risk_score"] = risk_info["score"]
            augmented["risk_level"] = risk_info["level"]
            augmented["days_to_stockout"] = risk_info["days_to_stockout"]
            augmented["expiry_info"] = risk_info["expiry_info"]
            augmented["demand_trend"] = risk_info["demand_trend"]
            augmented["anomaly_info"] = risk_info["anomaly_info"]
            augmented["risk_breakdown"] = risk_info["breakdown"]
            augmented["recommendation"] = recommendation
            augmented["reorder_info"] = reorder_info
            augmented["stock_deficit"] = reorder_info["stock_deficit"]
            augmented["recommended_reorder"] = reorder_info["recommended_reorder"]
            augmented["recommended_action"] = reorder_info["recommended_action"]
            augmented["requires_reorder"] = reorder_info["requires_reorder"]

            presented = view_helpers.present_product(augmented)

            # Filtering
            if category and category.lower() != "all":
                c_low = category.lower()
                item_cat = item.get("category", "").lower()
                if c_low == "healthcare" and "medical" in item_cat:
                    pass
                elif c_low != item_cat:
                    continue

            if risk_level and risk_level.lower() != "all" and risk_info["level"].lower() != risk_level.lower():
                continue

            if search:
                query = search.lower()
                id_match = query in str(item.get("_id", "")).lower()
                name_match = query in item.get("name", "").lower()
                sku_match = query in item.get("sku", "").lower()
                cat_match = query in item.get("category", "").lower()
                sup_match = query in item.get("supplier", "").lower()
                health_match = (query == "healthcare" and "medical" in item.get("category", "").lower())
                if not (id_match or name_match or sku_match or cat_match or sup_match or health_match):
                    continue

            results.append(presented)
        
        # Sort by risk_score descending so high-risk items appear first
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def get_reorder_recommendations(self) -> list:
        """Returns products sorted by risk tier priority for Smart Reorder Recommendations."""
        products = self.get_all_products()
        return risk_engine.get_reorder_recommendations(products)

    def get_product_by_id(self, product_id: str) -> dict:
        """Finds a single product by ID with full risk analysis."""
        item = None
        if self.use_mongodb and self.repository and self.db_conn.is_connected():
            item = self.repository.get_by_id(product_id)
        
        if not item:
            item = self._in_memory_products.get(product_id)
            if not item:
                for p in self._in_memory_products.values():
                    if p.get("sku") == product_id or p.get("_id") == product_id:
                        item = p
                        break

        if not item:
            return None
        
        risk_info = risk_engine.calculate_inventory_risk_score(item)
        recommendation = risk_engine.generate_product_recommendation(item, risk_info)
        reorder_info = risk_engine.calculate_reorder_recommendation(item, risk_info["level"])

        augmented = dict(item)
        augmented["risk_score"] = risk_info["score"]
        augmented["risk_level"] = risk_info["level"]
        augmented["days_to_stockout"] = risk_info["days_to_stockout"]
        augmented["expiry_info"] = risk_info["expiry_info"]
        augmented["demand_trend"] = risk_info["demand_trend"]
        augmented["anomaly_info"] = risk_info["anomaly_info"]
        augmented["risk_breakdown"] = risk_info["breakdown"]
        augmented["recommendation"] = recommendation
        augmented["reorder_info"] = reorder_info
        augmented["stock_deficit"] = reorder_info["stock_deficit"]
        augmented["recommended_reorder"] = reorder_info["recommended_reorder"]
        augmented["recommended_action"] = reorder_info["recommended_action"]
        augmented["requires_reorder"] = reorder_info["requires_reorder"]
        return view_helpers.present_product(augmented)

    def get_dashboard_metrics(self) -> dict:
        """Calculates system-level inventory metrics and Overall Health Score."""
        products = self.get_all_products()
        total_products = len(products)
        
        total_value = sum(p["current_stock"] * p["unit_price"] for p in products)
        
        critical_count = sum(1 for p in products if p["risk_level"] == "Critical")
        high_risk_count = sum(1 for p in products if p["risk_level"] == "High Risk")
        warning_count = sum(1 for p in products if p["risk_level"] == "Warning")
        safe_count = sum(1 for p in products if p["risk_level"] == "Safe")

        low_stock_count = sum(1 for p in products if p["current_stock"] < p["min_stock"])
        expiring_soon_count = sum(1 for p in products if p["expiry_info"]["is_expiring_soon"])
        anomaly_count = sum(1 for p in products if p["anomaly_info"]["has_anomaly"])

        # Overall Inventory Health Score (0 - 100)
        if total_products > 0:
            penalty = (
                (critical_count * 25.0) +
                (high_risk_count * 15.0) +
                (warning_count * 5.0) +
                (expiring_soon_count * 10.0)
            ) / total_products
            health_score = max(0.0, min(100.0, round(100.0 - penalty, 1)))
        else:
            health_score = 100.0

        # Category breakdown
        category_breakdown = {}
        for p in products:
            cat = p.get("category", "General")
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

        return {
            "total_products": total_products,
            "total_inventory_value": round(total_value, 2),
            "health_score": health_score,
            "counts": {
                "critical": critical_count,
                "high_risk": high_risk_count,
                "warning": warning_count,
                "safe": safe_count,
                "low_stock": low_stock_count,
                "expiring_soon": expiring_soon_count,
                "anomalies": anomaly_count
            },
            "risk_distribution": {
                "critical": critical_count,
                "high_risk": high_risk_count,
                "warning": warning_count,
                "safe": safe_count
            },
            "category_breakdown": category_breakdown,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

    def get_assistant_summary(self) -> dict:
        """Generates deterministic rule-based advice for the Smart Inventory Assistant panel."""
        products = self.get_all_products()
        
        critical_items = [p for p in products if p["risk_level"] in ["Critical", "High Risk"]]
        expiring_items = [p for p in products if p["expiry_info"]["is_expiring_soon"]]
        anomaly_items = [p for p in products if p["anomaly_info"]["has_anomaly"]]
        increasing_items = [p for p in products if p["demand_trend"] == "Increasing"]

        total_actions_needed = len(critical_items) + len(expiring_items) + len(anomaly_items)
        
        top_priorities = []
        for p in critical_items[:3]:
            top_priorities.append({
                "product_id": p["_id"],
                "name": p["name"],
                "type": "Stockout Risk",
                "severity": p["risk_level"],
                "message": f"{p['name']} (SKU: {p['sku']}): Stock is {p['current_stock']} vs min threshold {p['min_stock']}. Stockout in {p['days_to_stockout']} days."
            })

        for p in expiring_items[:2]:
            top_priorities.append({
                "product_id": p["_id"],
                "name": p["name"],
                "type": "Expiry Risk",
                "severity": "High Risk",
                "message": f"{p['name']}: {p['current_stock']} {p['unit']} expiring in {p['expiry_info']['days_remaining']} days ({p['expiry_date']})."
            })

        for p in anomaly_items[:2]:
            top_priorities.append({
                "product_id": p["_id"],
                "name": p["name"],
                "type": "Unusual Movement",
                "severity": "Warning",
                "message": p["anomaly_info"]["description"]
            })

        summary_text = (
            f"{total_actions_needed} inventory condition(s) require management attention today. "
            f"Focus on {len(critical_items)} high-risk item(s) facing stockouts and {len(expiring_items)} expiring batch(es)."
        )

        return {
            "summary": summary_text,
            "total_action_count": total_actions_needed,
            "top_priorities": top_priorities,
            "increasing_demand_count": len(increasing_items)
        }

    def get_stock_movement_analytics(self, months: int = 6, selected_month: str = None) -> dict:
        """
        Calculates stock movement flow telemetry (Inbound, Outbound, Current Load) per month
        based on MongoDB transaction history and inventory load.
        Supports 3, 6, 9, 12 month time ranges and specific month selection with zero JavaScript.
        """
        try:
            range_months = int(months)
            if range_months not in [3, 6, 9, 12]:
                range_months = 6
        except (ValueError, TypeError):
            range_months = 6

        products = self._fetch_raw_products()
        total_current_stock = sum(int(p.get("current_stock", 0)) for p in products)

        all_txs = []
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("inventory_transactions")
                if coll is not None:
                    docs = list(coll.find().sort("timestamp", 1))
                    for d in docs:
                        if "_id" in d:
                            d["_id"] = str(d["_id"])
                    all_txs = docs
            except Exception as err:
                logger.error(f"Error fetching transactions for analytics: {err}")
        
        if not all_txs:
            all_txs = list(reversed(self._transactions))

        tx_by_month = {}
        for tx in all_txs:
            ts_str = str(tx.get("timestamp", ""))
            if len(ts_str) >= 7:
                ym = ts_str[:7]
            else:
                continue

            if ym not in tx_by_month:
                tx_by_month[ym] = {"inbound": 0, "outbound": 0, "adjustments": 0}

            tx_type = str(tx.get("type", "")).upper()
            qty = abs(int(tx.get("quantity_changed", 0)))
            if tx_type == "STOCK_IN" or "IN" in tx_type:
                tx_by_month[ym]["inbound"] += qty
            elif tx_type == "STOCK_OUT" or "OUT" in tx_type:
                tx_by_month[ym]["outbound"] += qty
            else:
                tx_by_month[ym]["adjustments"] += int(tx.get("quantity_changed", 0))

        now = datetime.now()
        cur_year = now.year
        cur_month = now.month

        month_buckets = []
        for i in range(range_months - 1, -1, -1):
            m = cur_month - i
            y = cur_year
            while m <= 0:
                m += 12
                y -= 1
            ym_key = f"{y:04d}-{m:02d}"
            m_dt = datetime(y, m, 1)
            month_label = m_dt.strftime("%b")
            full_label = m_dt.strftime("%B %Y")
            
            month_buckets.append({
                "year_month": ym_key,
                "year": y,
                "month_num": m,
                "name": month_label,
                "full_label": full_label
            })

        valid_ym_keys = [b["year_month"] for b in month_buckets]
        if not selected_month or selected_month not in valid_ym_keys:
            active_ym = valid_ym_keys[-1]
        else:
            active_ym = selected_month

        inbound_pts = []
        outbound_pts = []
        load_pts = []
        month_data = []

        total_inbound_range = 0
        total_outbound_range = 0

        for idx, bucket in enumerate(month_buckets):
            ym = bucket["year_month"]
            tx_info = tx_by_month.get(ym, {"inbound": 0, "outbound": 0, "adjustments": 0})
            
            in_qty = tx_info["inbound"]
            out_qty = tx_info["outbound"]
            
            total_inbound_range += in_qty
            total_outbound_range += out_qty
            
            load_val = max(10, total_current_stock - (range_months - 1 - idx) * 15)

            inbound_pts.append(in_qty)
            outbound_pts.append(out_qty)
            load_pts.append(load_val)

        if range_months > 1:
            x_step = 700.0 / (range_months - 1)
        else:
            x_step = 0.0

        x_coords = [round(50.0 + (i * x_step), 1) for i in range(range_months)]

        max_val = max(max(inbound_pts or [0]), max(outbound_pts or [0]), max(load_pts or [0]), 1)
        min_val = 0

        def map_y(val):
            if max_val == min_val:
                return 150.0
            norm = float(val - min_val) / float(max_val - min_val)
            return round(160.0 - (norm * 135.0), 1)

        inbound_y = [map_y(v) for v in inbound_pts]
        outbound_y = [map_y(v) for v in outbound_pts]
        load_y = [map_y(v) for v in load_pts]

        def build_smooth_path(x_arr, y_arr, close_bottom=False):
            if not x_arr or len(x_arr) < 2:
                return ""
            path = f"M {x_arr[0]} {y_arr[0]}"
            for i in range(len(x_arr) - 1):
                x1, y1 = x_arr[i], y_arr[i]
                x2, y2 = x_arr[i+1], y_arr[i+1]
                cx1 = x1 + (x2 - x1) * 0.45
                cy1 = y1
                cx2 = x1 + (x2 - x1) * 0.55
                cy2 = y2
                path += f" C {cx1:.1f} {cy1:.1f}, {cx2:.1f} {cy2:.1f}, {x2} {y2}"
            if close_bottom:
                path += f" L {x_arr[-1]} 180 L {x_arr[0]} 180 Z"
            return path

        inbound_curve = build_smooth_path(x_coords, inbound_y, False)
        inbound_area = build_smooth_path(x_coords, inbound_y, True)

        outbound_curve = build_smooth_path(x_coords, outbound_y, False)
        outbound_area = build_smooth_path(x_coords, outbound_y, True)

        load_curve = build_smooth_path(x_coords, load_y, False)
        load_area = build_smooth_path(x_coords, load_y, True)

        active_inbound = 0
        active_outbound = 0
        active_load = total_current_stock

        for i, bucket in enumerate(month_buckets):
            is_act = (bucket["year_month"] == active_ym)
            if is_act:
                active_inbound = inbound_pts[i]
                active_outbound = outbound_pts[i]
                active_load = load_pts[i]

            month_data.append({
                "label": bucket["name"],
                "name": bucket["name"],
                "year_month": bucket["year_month"],
                "year": bucket["year"],
                "full_label": bucket["full_label"],
                "is_active": is_act,
                "inbound": inbound_pts[i],
                "outbound": outbound_pts[i],
                "current_load": load_pts[i],
                "x": x_coords[i],
                "inbound_y": inbound_y[i],
                "outbound_y": outbound_y[i],
                "load_y": load_y[i]
            })

        has_transactions = (total_inbound_range > 0 or total_outbound_range > 0 or total_current_stock > 0)

        return {
            "selected_range": range_months,
            "selected_month": active_ym,
            "inbound_total": f"{active_inbound:,}",
            "outbound_total": f"{active_outbound:,}",
            "load_total": f"{active_load:,}",
            "active_month": active_ym,
            "month_names": [b["name"] for b in month_buckets],
            "month_data": month_data,
            "inbound_curve": inbound_curve,
            "inbound_area": inbound_area,
            "outbound_curve": outbound_curve,
            "outbound_area": outbound_area,
            "load_curve": load_curve,
            "load_area": load_area,
            "has_transactions": has_transactions
        }

    def get_top_categories_analytics(self) -> dict:
        """
        Groups products by category in Python, calculates stock totals and percentages,
        sorts descending, maps colors, and computes SVG donut parameters.
        """
        products = self._fetch_raw_products()

        if not products:
            return {
                "total_stock": "0",
                "raw_total_stock": 0,
                "total_products": 0,
                "categories": [],
                "top_category_name": "N/A",
                "top_category_pct": 0,
                "has_data": False
            }

        COLOR_MAP = {
            "electronics": "#06B6D4",
            "industrial": "#7C3AED",
            "medical supplies": "#14B8A6",
            "medical": "#14B8A6",
            "healthcare": "#14B8A6",
            "perishables": "#D4A72C",
            "food": "#D4A72C",
            "hardware": "#6366F1",
            "general": "#94A3B8"
        }
        PALETTE = ["#06B6D4", "#7C3AED", "#14B8A6", "#D4A72C", "#6366F1", "#F43F5E", "#F59E0B"]

        cat_groups = {}
        total_stock_all = 0
        total_products_all = len(products)

        for p in products:
            c_raw = (p.get("category") or "General").strip()
            c_norm = c_raw.title()
            c_stock = max(0, int(p.get("current_stock", 0)))

            if c_norm not in cat_groups:
                cat_groups[c_norm] = {"name": c_norm, "stock": 0, "count": 0}

            cat_groups[c_norm]["stock"] += c_stock
            cat_groups[c_norm]["count"] += 1
            total_stock_all += c_stock

        sorted_cats = sorted(cat_groups.values(), key=lambda x: x["stock"], reverse=True)

        CIRCUMFERENCE = 376.99
        current_offset = 0
        cat_list = []

        for idx, c in enumerate(sorted_cats):
            pct = round((c["stock"] / total_stock_all * 100), 1) if total_stock_all > 0 else 0
            c_key = c["name"].lower()
            color = COLOR_MAP.get(c_key, PALETTE[idx % len(PALETTE)])

            stroke_length = (pct / 100.0) * CIRCUMFERENCE
            dash_array = f"{stroke_length:.2f} {(CIRCUMFERENCE - stroke_length):.2f}"
            dash_offset = f"{-current_offset:.2f}"
            current_offset += stroke_length

            cat_list.append({
                "name": c["name"],
                "stock": f"{c['stock']:,}",
                "raw_stock": c["stock"],
                "count": c["count"],
                "percentage": pct,
                "color": color,
                "is_top": (idx == 0),
                "dash_array": dash_array,
                "dash_offset": dash_offset
            })

        top_cat = cat_list[0] if cat_list else {"name": "N/A", "percentage": 0}

        return {
            "total_stock": f"{total_stock_all:,}",
            "raw_total_stock": total_stock_all,
            "total_products": total_products_all,
            "categories": cat_list,
            "top_category_name": top_cat["name"],
            "top_category_pct": top_cat["percentage"],
            "has_data": len(cat_list) > 0
        }

    @staticmethod
    def classify_alert(alert: dict) -> dict:
        """Classifies alert into exact CSS class, border color, and badge color."""
        alt_type = str(alert.get("type", "")).strip()
        severity = str(alert.get("severity", "")).strip()

        if severity == "Critical" or alt_type == "Out of Stock":
            css_class = "critical-alert high-risk-alert"
            border_color = "#BE123C"
            badge_color = "#f87171"
        elif alt_type == "Low Stock" or severity in ["Warning", "Medium", "Low", "Medium Risk", "High Risk", "High"]:
            css_class = "medium-risk-alert low-stock-alert warning-alert"
            border_color = "#D4A72C"
            badge_color = "#fbbf24"
        elif severity in ["Safe", "Normal", "Healthy"] or alt_type in ["Demand Trend", "Demand Surge"]:
            css_class = "safe-alert healthy-alert normal-alert"
            border_color = "#10B981"
            badge_color = "#34d399"
        else:
            css_class = "info-alert"
            border_color = "#3B82F6"
            badge_color = "#60a5fa"

        alert["css_class"] = css_class
        alert["border_color"] = border_color
        alert["badge_color"] = badge_color
        return alert

    def get_alerts(self, severity_filter=None) -> list:
        """Returns structured alert feed for the Alert Center using AlertService."""
        products = self.get_all_products()
        alerts, _ = AlertService.process_smart_alerts(
            products=products,
            severity_filter=severity_filter or "all",
            status_provider=self.get_alert_status
        )
        return alerts

    def get_smart_alerts_summary(self, severity_filter="all") -> tuple:
        """Returns (alerts, summary_dict) tuple using Python AlertService."""
        products = self.get_all_products()
        return AlertService.process_smart_alerts(
            products=products,
            severity_filter=severity_filter or "all",
            status_provider=self.get_alert_status
        )

    def simulate_continuous_tick(self) -> dict:
        """
        Simulates periodic telemetry stock movement tick.
        Persists stock updates directly to MongoDB Atlas (if connected) or fallback JSON store.
        """
        raw_products = self._fetch_raw_products()
        if not raw_products:
            return {"updated": 0, "message": "No products to simulate"}

        selected = random.sample(raw_products, min(2, len(raw_products)))
        updated_details = []

        for p in selected:
            p_id = p["_id"]
            consumption = random.randint(1, 4)
            old_stock = int(p["current_stock"])
            new_stock = max(0, old_stock - consumption)
            new_today_mov = int(p.get("today_movement", 0)) + consumption
            new_timestamp = datetime.now(timezone.utc).isoformat()
            
            history = list(p.get("daily_usage_history", []))
            if history:
                history[-1] = round(history[-1] + (consumption * 0.2), 1)

            # Persist to MongoDB if connected
            if self.use_mongodb and self.repository and self.db_conn.is_connected():
                self.repository.update_stock_telemetry(
                    product_id=p_id,
                    current_stock=new_stock,
                    today_movement=new_today_mov,
                    daily_usage_history=history,
                    last_updated=new_timestamp
                )

            # Also update fallback in-memory store
            if p_id in self._in_memory_products:
                mem_p = self._in_memory_products[p_id]
                mem_p["current_stock"] = new_stock
                mem_p["today_movement"] = new_today_mov
                mem_p["daily_usage_history"] = history
                mem_p["last_updated"] = new_timestamp

            updated_details.append({
                "product_id": p_id,
                "name": p["name"],
                "old_stock": old_stock,
                "new_stock": new_stock,
                "units_consumed": consumption
            })

        metrics = self.get_dashboard_metrics()

        return {
            "status": "success",
            "tick_timestamp": datetime.now(timezone.utc).isoformat(),
            "updated_products": updated_details,
            "current_metrics": metrics
        }

    def add_product(self, product_data: dict) -> dict:
        """Adds a new inventory product (Admin feature)."""
        sku = product_data.get("sku", "").strip()
        name = product_data.get("name", "").strip()
        if not sku or not name:
            return {"success": False, "message": "SKU and Name are required"}

        p_id = product_data.get("_id") or f"prod-{random.randint(100, 999)}"
        product_dict = {
            "_id": p_id,
            "sku": sku,
            "name": name,
            "category": product_data.get("category", "General"),
            "current_stock": int(product_data.get("current_stock", 0)),
            "min_stock": int(product_data.get("min_stock", 10)),
            "unit_price": float(product_data.get("unit_price", 0.0)),
            "unit": product_data.get("unit", "Units"),
            "average_daily_usage": float(product_data.get("average_daily_usage", 1.0)),
            "today_movement": 0,
            "daily_usage_history": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "expiry_date": product_data.get("expiry_date", "2027-12-31"),
            "location": product_data.get("location", "Warehouse Main"),
            "supplier": product_data.get("supplier", "Standard Vendor"),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

        # Save to MongoDB if available
        if self.use_mongodb and self.repository and self.db_conn.is_connected():
            self.repository.add_product(product_dict)

        # Update in-memory fallback
        self._in_memory_products[p_id] = InventoryItemModel(product_dict).to_dict()
        return {"success": True, "message": "Product added successfully", "data": self._in_memory_products[p_id]}

    def update_product(self, product_id: str, update_data: dict) -> dict:
        """Updates product details (Admin feature)."""
        existing = self.get_product_by_id(product_id)
        if not existing:
            return {"success": False, "message": "Product not found"}

        fields = ["name", "category", "current_stock", "min_stock", "unit_price", "unit", "average_daily_usage", "expiry_date", "location", "supplier"]
        update_fields = {}
        for f in fields:
            if f in update_data:
                if f in ["current_stock", "min_stock"]:
                    update_fields[f] = int(update_data[f])
                elif f in ["unit_price", "average_daily_usage"]:
                    update_fields[f] = float(update_data[f])
                else:
                    update_fields[f] = update_data[f]

        update_fields["last_updated"] = datetime.now(timezone.utc).isoformat()

        internal_id = existing["_id"]
        if self.use_mongodb and self.repository and self.db_conn.is_connected():
            self.repository.update_product(product_id, update_fields)

        if internal_id in self._in_memory_products:
            self._in_memory_products[internal_id].update(update_fields)
        if product_id in self._in_memory_products:
            self._in_memory_products[product_id].update(update_fields)

        updated_item = self.get_product_by_id(product_id)
        return {"success": True, "message": "Product updated successfully", "data": updated_item}

    def delete_product(self, product_id: str) -> dict:
        """Deletes a product document (Admin feature)."""
        existing = self.get_product_by_id(product_id)
        if not existing:
            return {"success": False, "message": "Product not found"}

        internal_id = existing["_id"]
        if self.use_mongodb and self.repository and self.db_conn.is_connected():
            self.repository.delete_product(product_id)

        if internal_id in self._in_memory_products:
            del self._in_memory_products[internal_id]
        if product_id in self._in_memory_products and product_id != internal_id:
            del self._in_memory_products[product_id]

        return {"success": True, "message": "Product deleted successfully"}

    def save_report_config(self, name: str, report_type: str, filters: dict, columns: list = None, created_by: str = "Admin") -> dict:
        """Saves a custom report configuration to MongoDB or fallback memory store."""
        import time
        doc = {
            "id": f"rpt-{int(time.time())}",
            "name": name or f"Custom {report_type.capitalize()} Report",
            "report_type": report_type or "inventory",
            "filters": filters or {},
            "columns": columns or [],
            "created_by": created_by or "Admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("saved_reports")
                if coll is not None:
                    coll.insert_one(dict(doc))
            except Exception as err:
                logger.error(f"Error saving report config to MongoDB: {err}")

        if not hasattr(InventoryService, "_saved_reports") or InventoryService._saved_reports is None:
            InventoryService._saved_reports = []
        InventoryService._saved_reports.insert(0, doc)
        return doc

    def get_saved_reports(self) -> list:
        """Retrieves all saved report configurations."""
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("saved_reports")
                if coll is not None:
                    docs = list(coll.find().sort("created_at", -1))
                    for d in docs:
                        if "_id" in d:
                            d["_id"] = str(d["_id"])
                    if docs:
                        return docs
            except Exception as err:
                logger.error(f"Error fetching saved reports from MongoDB: {err}")

        if not hasattr(InventoryService, "_saved_reports") or InventoryService._saved_reports is None:
            InventoryService._saved_reports = []
        return InventoryService._saved_reports

    def delete_saved_report(self, report_id: str) -> bool:
        """Deletes a saved report configuration by ID."""
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("saved_reports")
                if coll is not None:
                    coll.delete_one({"$or": [{"id": report_id}, {"_id": report_id}]})
            except Exception as err:
                logger.error(f"Error deleting saved report from MongoDB: {err}")

        if hasattr(InventoryService, "_saved_reports"):
            InventoryService._saved_reports = [
                r for r in InventoryService._saved_reports 
                if r.get("id") != report_id and str(r.get("_id")) != report_id
            ]
        return True



