from typing import Any, Dict, List, Optional
import logging
from pymongo import ASCENDING
from pymongo.errors import PyMongoError
from backend.database import MongoDBConnection
from backend.models.inventory_model import InventoryItemModel

logger = logging.getLogger("inventory_repository")

class InventoryRepository:
    """
    Data-Access Layer / Repository for managing inventory documents in MongoDB Atlas.
    Handles indexes, CRUD operations, telemetry updates, and safe data seeding.
    """
    def __init__(self, db_conn: MongoDBConnection):
        self.db_conn = db_conn

    def _get_collection(self):
        return self.db_conn.get_collection()

    def create_indexes(self):
        """Creates unique index on 'sku' and secondary index on 'category'."""
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            coll.create_index([("sku", ASCENDING)], unique=True, name="sku_unique_idx")
            coll.create_index([("category", ASCENDING)], name="category_idx")
            logger.info("MongoDB indexes verified/created: sku (unique), category.")
            return True
        except PyMongoError as err:
            logger.error(f"Error creating MongoDB indexes: {err}")
            return False

    def seed_sample_products_if_empty(self, sample_items: list) -> int:
        """
        Safely seeds sample inventory items into MongoDB if the collection is empty.
        Uses SKU to avoid duplicating products on application restarts.
        """
        coll = self._get_collection()
        if coll is None or not sample_items:
            return 0

        try:
            current_count = coll.count_documents({})
            if current_count > 0:
                logger.info(f"MongoDB collection already contains {current_count} documents. Skipping seed.")
                return 0

            inserted_count = 0
            for item in sample_items:
                model_dict = InventoryItemModel(item).to_dict()
                sku = model_dict.get("sku")
                if not sku:
                    continue
                # Upsert by SKU to ensure zero duplication
                coll.update_one({"sku": sku}, {"$setOnInsert": model_dict}, upsert=True)
                inserted_count += 1

            logger.info(f"Seeded {inserted_count} sample products into MongoDB collection.")
            return inserted_count
        except PyMongoError as err:
            logger.error(f"Error seeding MongoDB sample products: {err}")
            return 0

    def get_all(self) -> list:
        """Retrieves all inventory product documents from MongoDB."""
        coll = self._get_collection()
        if coll is None:
            return []

        try:
            documents = list(coll.find({}))
            results = []
            for doc in documents:
                # Format MongoDB _id cleanly for frontend JSON serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                results.append(InventoryItemModel(doc).to_dict())
            return results
        except PyMongoError as err:
            logger.error(f"Error querying MongoDB all products: {err}")
            return []

    def get_by_id(self, product_id: str) -> dict | None:
        """Finds inventory item by _id or sku."""
        coll = self._get_collection()
        if coll is None:
            return None

        try:
            # Query by _id or sku
            doc = coll.find_one({"$or": [{"_id": product_id}, {"sku": product_id}]})
            if doc:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                return InventoryItemModel(doc).to_dict()
            return None
        except PyMongoError as err:
            logger.error(f"Error querying MongoDB product by id '{product_id}': {err}")
            return None

    def upsert_product(self, product_data: dict) -> bool:
        """Inserts or updates an inventory product by SKU."""
        coll = self._get_collection()
        if coll is None:
            return False

        try:
            model_dict = InventoryItemModel(product_data).to_dict()
            sku = model_dict.get("sku")
            coll.update_one({"sku": sku}, {"$set": model_dict}, upsert=True)
            return True
        except PyMongoError as err:
            logger.error(f"Error upserting product '{product_data.get('sku')}': {err}")
            return False

    def update_stock_telemetry(self, product_id: str, current_stock: int, today_movement: int, daily_usage_history: list | None = None, last_updated: str | None = None) -> bool:
        """Updates real-time telemetry, stock levels, and consumption history in MongoDB."""
        coll = self._get_collection()
        if coll is None:
            return False

        try:
            update_fields: dict[str, Any] = {
                "current_stock": current_stock,
                "today_movement": today_movement
            }
            if daily_usage_history is not None:
                update_fields["daily_usage_history"] = daily_usage_history
            if last_updated:
                update_fields["last_updated"] = last_updated

            res = coll.update_one(
                {"$or": [{"_id": product_id}, {"sku": product_id}]},
                {"$set": update_fields}
            )
            return res.modified_count > 0 or res.matched_count > 0
        except PyMongoError as err:
            logger.error(f"Error updating telemetry for product '{product_id}': {err}")
            return False

    def add_product(self, product_dict: dict) -> bool:
        """Adds a new inventory product document."""
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            model_dict = InventoryItemModel(product_dict).to_dict()
            coll.insert_one(model_dict)
            return True
        except PyMongoError as err:
            logger.error(f"Error adding product: {err}")
            return False

    def update_product(self, product_id: str, update_dict: dict) -> bool:
        """Updates fields of an existing product document."""
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            res = coll.update_one(
                {"$or": [{"_id": product_id}, {"sku": product_id}]},
                {"$set": update_dict}
            )
            return res.modified_count > 0 or res.matched_count > 0
        except PyMongoError as err:
            logger.error(f"Error updating product '{product_id}': {err}")
            return False

    def delete_product(self, product_id: str) -> bool:
        """Deletes a product document from MongoDB by _id or sku."""
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            res = coll.delete_one({"$or": [{"_id": product_id}, {"sku": product_id}]})
            return res.deleted_count > 0
        except PyMongoError as err:
            logger.error(f"Error deleting product '{product_id}': {err}")
            return False
