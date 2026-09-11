import json
import os
import random
import logging
from datetime import datetime
from backend.models.inventory_model import InventoryItemModel
from backend.utils import risk_engine
from backend.database import MongoDBConnection
from backend.repositories.inventory_repository import InventoryRepository

logger = logging.getLogger("inventory_service")

class InventoryService:
    """
    Inventory Business Service.
    Orchestrates MongoDB Atlas repository persistent storage with dynamic Risk Intelligence calculation.
    Includes seamless fallback to in-memory JSON store if MongoDB URI is unconfigured or offline.
    """
    def __init__(self, data_file_path: str = None, uri: str = None):
        if data_file_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_file_path = os.path.join(base_dir, "data", "sample_products.json")
        
        self.data_file_path = data_file_path
        self._in_memory_products = {}
        
        # MongoDB Connection & Repository Setup
        self.db_conn = MongoDBConnection(uri=uri)
        self.use_mongodb = self.db_conn.connect()
        self.repository = InventoryRepository(self.db_conn) if self.use_mongodb else None

        self._transactions = []
        self.initialize_data()

    def record_transaction(self, product_id: str, product_name: str, op_type: str, qty_changed: int, old_stock: int, new_stock: int, user: str = "System", notes: str = "") -> dict:
        """Records an inventory transaction in MongoDB or fallback memory store."""
        tx_doc = {
            "id": f"tx-{len(self._transactions) + 1:04d}",
            "product_id": product_id,
            "product_name": product_name,
            "type": op_type,  # STOCK_IN, STOCK_OUT, ADJUSTMENT
            "quantity_changed": qty_changed,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "timestamp": datetime.utcnow().isoformat(),
            "user": user or "System Administrator",
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
        if self.use_mongodb and self.db_conn and self.db_conn.is_connected():
            try:
                coll = self.db_conn.get_collection("inventory_transactions")
                if coll is not None:
                    docs = list(coll.find({"$or": [{"product_id": product_id}, {"product_name": product_id}]}).sort("timestamp", -1))
                    for d in docs:
                        if "_id" in d:
                            d["_id"] = str(d["_id"])
                    if docs:
                        return docs
            except Exception as err:
                logger.error(f"Error fetching history from MongoDB: {err}")

        return [t for t in self._transactions if t.get("product_id") == product_id or t.get("product_name") == product_id]

    def update_stock_quantity(self, product_id: str, quantity: int, operation: str = "ADJUSTMENT", user: str = "Admin", notes: str = "") -> dict:
        """Updates product stock quantity supporting Stock In, Stock Out, and Direct Adjustments with full audit validation."""
        existing = self.get_product_by_id(product_id)
        if not existing:
            return {"success": False, "message": "Product not found"}

        old_stock = int(existing.get("current_stock", 0))
        op = (operation or "ADJUSTMENT").upper().strip()
        qty = abs(int(quantity))

        if op == "STOCK_IN":
            qty_changed = qty
            new_stock = old_stock + qty
            op_label = "Stock In"
        elif op == "STOCK_OUT":
            if qty > old_stock:
                return {
                    "success": False,
                    "message": f"Stock Out failure: Quantity ({qty}) exceeds available stock level ({old_stock} units)."
                }
            qty_changed = -qty
            new_stock = old_stock - qty
            op_label = "Stock Out"
        else:  # ADJUSTMENT / DIRECT SET
            new_stock = max(0, int(quantity))
            qty_changed = new_stock - old_stock
            op_label = "Direct Adjustment"

        now_iso = datetime.utcnow().isoformat()
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
            notes=notes or f"{op_label} applied ({qty_changed:+d} units)"
        )

        updated_item = self.get_product_by_id(product_id)
        return {
            "success": True,
            "message": f"Successfully performed {op_label}: New stock for {existing.get('name')} is {new_stock} units.",
            "data": updated_item
        }

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

            # Filtering
            if category and category.lower() != "all" and item.get("category", "").lower() != category.lower():
                continue
            if risk_level and risk_level.lower() != "all" and risk_info["level"].lower() != risk_level.lower():
                continue
            if search:
                query = search.lower()
                name_match = query in item.get("name", "").lower()
                sku_match = query in item.get("sku", "").lower()
                cat_match = query in item.get("category", "").lower()
                if not (name_match or sku_match or cat_match):
                    continue

            results.append(augmented)
        
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

        augmented = dict(item)
        augmented["risk_score"] = risk_info["score"]
        augmented["risk_level"] = risk_info["level"]
        augmented["days_to_stockout"] = risk_info["days_to_stockout"]
        augmented["expiry_info"] = risk_info["expiry_info"]
        augmented["demand_trend"] = risk_info["demand_trend"]
        augmented["anomaly_info"] = risk_info["anomaly_info"]
        augmented["risk_breakdown"] = risk_info["breakdown"]
        augmented["recommendation"] = recommendation
        return augmented

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
            "last_updated": datetime.utcnow().isoformat()
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

    def get_alerts(self, severity_filter=None) -> list:
        """Returns structured alert feed for the Alert Center."""
        products = self.get_all_products()
        alerts = []

        for p in products:
            if p["current_stock"] <= 0:
                alerts.append({
                    "id": f"alert-out-{p['_id']}",
                    "product_id": p["_id"],
                    "product_name": p["name"],
                    "category": p["category"],
                    "severity": "Critical",
                    "type": "Out of Stock",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"CRITICAL: {p['name']} is completely OUT OF STOCK (0 units)."
                })
            elif p["current_stock"] < p["min_stock"]:
                alerts.append({
                    "id": f"alert-low-{p['_id']}",
                    "product_id": p["_id"],
                    "product_name": p["name"],
                    "category": p["category"],
                    "severity": "High Risk" if p["days_to_stockout"] <= 3 else "Warning",
                    "type": "Low Stock",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"Stock level for {p['name']} ({p['current_stock']} {p['unit']}) has dropped below min safety threshold ({p['min_stock']})."
                })

            if p["expiry_info"]["is_expiring_soon"]:
                alerts.append({
                    "id": f"alert-exp-{p['_id']}",
                    "product_id": p["_id"],
                    "product_name": p["name"],
                    "category": p["category"],
                    "severity": "Critical" if p["expiry_info"]["days_remaining"] <= 3 else "Warning",
                    "type": "Expiry Approaching",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"EXPIRY ALERT: {p['name']} ({p['current_stock']} units) expires in {p['expiry_info']['days_remaining']} days."
                })

            if p["anomaly_info"]["has_anomaly"]:
                alerts.append({
                    "id": f"alert-anom-{p['_id']}",
                    "product_id": p["_id"],
                    "product_name": p["name"],
                    "category": p["category"],
                    "severity": "Warning",
                    "type": "Unusual Movement",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": p["anomaly_info"]["description"]
                })

            if p["demand_trend"] == "Increasing":
                alerts.append({
                    "id": f"alert-trend-{p['_id']}",
                    "product_id": p["_id"],
                    "product_name": p["name"],
                    "category": p["category"],
                    "severity": "Safe",
                    "type": "Demand Trend",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"DEMAND SURGE: {p['name']} daily consumption trend is increasing over the last 7 days."
                })

        if severity_filter and severity_filter.lower() != "all":
            alerts = [a for a in alerts if a["severity"].lower() == severity_filter.lower()]

        severity_order = {"Critical": 0, "High Risk": 1, "Warning": 2, "Safe": 3}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
        return alerts

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
            new_timestamp = datetime.utcnow().isoformat()
            
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
            "tick_timestamp": datetime.utcnow().isoformat(),
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
            "last_updated": datetime.utcnow().isoformat()
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

        update_fields["last_updated"] = datetime.utcnow().isoformat()

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


