import unittest
from backend.database import MongoDBConnection
from backend.repositories.inventory_repository import InventoryRepository
from backend.config import Config

class TestMongoDBIntegration(unittest.TestCase):

    def test_database_connection_disabled_mode(self):
        # Empty URI should result in disabled mode without throwing exceptions
        db_conn = MongoDBConnection(uri="")
        self.assertFalse(db_conn.connect())
        self.assertFalse(db_conn.is_connected())

        health = db_conn.check_health()
        self.assertEqual(health["status"], "disabled")
        self.assertEqual(health["database"], Config.MONGODB_DATABASE)

    def test_database_connection_timeout_handling(self):
        # Invalid URI should timeout gracefully (300ms) without crashing
        db_conn = MongoDBConnection(
            uri="mongodb://invalidhost:27017/?serverSelectionTimeoutMS=300",
            timeout_ms=300
        )
        self.assertFalse(db_conn.connect())
        health = db_conn.check_health()
        self.assertEqual(health["status"], "disconnected")

    def test_repository_handles_disconnected_db(self):
        db_conn = MongoDBConnection(uri="")
        repo = InventoryRepository(db_conn)

        # Operations on disconnected DB should return safe fallbacks (empty list / None)
        self.assertEqual(repo.get_all(), [])
        self.assertIsNone(repo.get_by_id("prod-001"))
        self.assertFalse(repo.create_indexes())
        self.assertEqual(repo.seed_sample_products_if_empty([{"_id": "p1", "sku": "S1"}]), 0)

if __name__ == "__main__":
    unittest.main()
