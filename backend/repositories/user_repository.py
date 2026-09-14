import logging
from datetime import datetime, timezone
from pymongo import ASCENDING
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash
from backend.database import MongoDBConnection
from backend.config import Config
from backend.models.user_model import UserModel

logger = logging.getLogger("user_repository")

DEFAULT_SEED_USERS = [
    {
        "_id": "user-admin-001",
        "email": "admin@inventory.com",
        "username": "admin",
        "password_hash": generate_password_hash("Admin@123456"),
        "role": "admin",
        "full_name": "System Administrator",
        "allow_profile_edit": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "_id": "user-staff-001",
        "email": "staff@inventory.com",
        "username": "staff",
        "password_hash": generate_password_hash("Staff@123456"),
        "role": "staff",
        "full_name": "Inventory Staff Officer",
        "allow_profile_edit": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "_id": "user-customer-001",
        "email": "customer@inventory.com",
        "username": "customer",
        "password_hash": generate_password_hash("Customer@123456"),
        "role": "customer",
        "full_name": "Valued Customer",
        "allow_profile_edit": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
]

class UserRepository:
    """
    Data-Access Layer / Repository for managing user accounts in MongoDB.
    Includes dual-mode fallback (in-memory store) if MongoDB is offline.
    """
    def __init__(self, db_conn: MongoDBConnection):
        self.db_conn = db_conn
        self.users_collection_name = Config.MONGODB_USERS_COLLECTION
        self._in_memory_users = {}
        self._init_memory_store()

    def _get_collection(self):
        if self.db_conn and self.db_conn.is_connected():
            return self.db_conn.get_collection(self.users_collection_name)
        return None

    def _init_memory_store(self):
        for user_dict in DEFAULT_SEED_USERS:
            self._in_memory_users[user_dict["email"].lower()] = dict(user_dict)

    def create_indexes(self) -> bool:
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            coll.create_index([("email", ASCENDING)], unique=True, name="email_unique_idx")
            coll.create_index([("username", ASCENDING)], unique=True, name="username_unique_idx")
            logger.info("MongoDB user collection indexes created.")
            return True
        except PyMongoError as err:
            logger.error(f"Error creating user indexes: {err}")
            return False

    def seed_default_users_if_empty(self) -> int:
        coll = self._get_collection()
        if coll is None:
            return 0
        try:
            if coll.count_documents({}) > 0:
                return 0

            inserted_count = 0
            for u in DEFAULT_SEED_USERS:
                coll.update_one({"email": u["email"]}, {"$setOnInsert": u}, upsert=True)
                inserted_count += 1
            logger.info(f"Seeded {inserted_count} default users into MongoDB.")
            return inserted_count
        except PyMongoError as err:
            logger.error(f"Error seeding default users: {err}")
            return 0

    def find_by_email_or_username(self, identifier: str) -> dict:
        identifier_clean = identifier.strip().lower()
        coll = self._get_collection()
        if coll is not None:
            try:
                doc = coll.find_one({
                    "$or": [
                        {"email": identifier_clean},
                        {"username": identifier_clean}
                    ]
                })
                if doc:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                    return doc
                return None
            except PyMongoError as err:
                logger.error(f"Error finding user '{identifier_clean}': {err}")

        # Fallback to in-memory store
        for u in self._in_memory_users.values():
            if u["email"].lower() == identifier_clean or u["username"].lower() == identifier_clean:
                return dict(u)
        return None

    def find_by_id(self, user_id: str) -> dict:
        coll = self._get_collection()
        if coll is not None:
            try:
                doc = coll.find_one({"_id": user_id})
                if doc:
                    doc["_id"] = str(doc["_id"])
                    return doc
            except PyMongoError:
                pass

        for u in self._in_memory_users.values():
            if u.get("_id") == user_id:
                return dict(u)
        return None

    def get_all_staff(self) -> list:
        coll = self._get_collection()
        if coll is not None:
            try:
                docs = list(coll.find({"role": "staff"}))
                results = []
                for d in docs:
                    d["_id"] = str(d["_id"])
                    d.pop("password_hash", None)
                    results.append(d)
                return results
            except PyMongoError:
                pass

        return [
            {k: v for k, v in u.items() if k != "password_hash"}
            for u in self._in_memory_users.values()
            if u.get("role") == "staff"
        ]

    def create_user(self, user_dict: dict) -> bool:
        coll = self._get_collection()
        email = user_dict["email"].lower()
        if coll is not None:
            try:
                coll.update_one({"email": email}, {"$setOnInsert": user_dict}, upsert=True)
                return True
            except PyMongoError as err:
                logger.error(f"Error creating user in MongoDB: {err}")
                return False

        self._in_memory_users[email] = dict(user_dict)
        return True

    def update_user(self, user_id: str, updates: dict) -> bool:
        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one({"$or": [{"_id": user_id}, {"email": user_id}]}, {"$set": updates})
                return True
            except PyMongoError as err:
                logger.error(f"Error updating user '{user_id}': {err}")
                return False

        for email, u in self._in_memory_users.items():
            if u.get("_id") == user_id or email == user_id.lower() or u.get("email", "").lower() == user_id.lower():
                u.update(updates)
                return True
        return False

    def delete_user(self, user_id: str) -> bool:
        coll = self._get_collection()
        if coll is not None:
            try:
                res = coll.delete_one({"_id": user_id, "role": "staff"})
                return res.deleted_count > 0
            except PyMongoError as err:
                logger.error(f"Error deleting user: {err}")
                return False

        to_delete = None
        for email, u in self._in_memory_users.items():
            if u.get("_id") == user_id and u.get("role") == "staff":
                to_delete = email
                break
        if to_delete:
            del self._in_memory_users[to_delete]
            return True
        return False
