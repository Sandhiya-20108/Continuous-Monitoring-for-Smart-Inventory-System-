from datetime import datetime, timezone

class InventoryItemModel:
    """
    Data abstraction class representing an inventory item document.
    Formatted to align with MongoDB collections for seamless Phase 2 integration.
    """
    def __init__(self, data: dict):
        self.id = data.get("_id")
        self.sku = data.get("sku", "")
        self.name = data.get("name", "")
        self.category = data.get("category", "")
        self.current_stock = int(data.get("current_stock", 0))
        self.min_stock = int(data.get("min_stock", 0))
        self.unit_price = float(data.get("unit_price", 0.0))
        self.unit = data.get("unit", "Units")
        self.average_daily_usage = float(data.get("average_daily_usage", 0.0))
        self.today_movement = int(data.get("today_movement", 0))
        self.daily_usage_history = data.get("daily_usage_history", [])
        self.expiry_date = data.get("expiry_date", "")
        self.location = data.get("location", "Warehouse Main")
        self.supplier = data.get("supplier", "Standard Vendor")
        self.last_updated = data.get("last_updated", datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "_id": self.id,
            "sku": self.sku,
            "name": self.name,
            "category": self.category,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "unit_price": self.unit_price,
            "unit": self.unit,
            "average_daily_usage": self.average_daily_usage,
            "today_movement": self.today_movement,
            "daily_usage_history": self.daily_usage_history,
            "expiry_date": self.expiry_date,
            "location": self.location,
            "supplier": self.supplier,
            "last_updated": self.last_updated
        }
