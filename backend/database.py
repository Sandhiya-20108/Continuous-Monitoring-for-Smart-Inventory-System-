import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, PyMongoError
from backend.config import Config

try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

logger = logging.getLogger("inventory_database")

class MongoDBConnection:
    """
    MongoDB Connection Manager with connection timeout, health check, and error handling.
    """
    def __init__(self, uri: str = None, db_name: str = None, timeout_ms: int = None):
        self.uri = uri if uri is not None else Config.MONGODB_URI
        self.db_name = db_name or Config.MONGODB_DATABASE
        self.collection_name = Config.MONGODB_COLLECTION
        self.timeout_ms = timeout_ms or Config.MONGODB_TIMEOUT_MS
        
        self.client = None
        self.db = None

    def connect(self) -> bool:
        """Establishes connection to MongoDB Atlas or local MongoDB."""
        if not self.uri:
            logger.info("MONGODB_URI is not set. Database mode: disabled (fallback to in-memory/JSON store).")
            return False

        try:
            client_kwargs = {
                "serverSelectionTimeoutMS": self.timeout_ms,
                "connectTimeoutMS": self.timeout_ms
            }
            if HAS_CERTIFI:
                client_kwargs["tlsCAFile"] = certifi.where()

            self.client = MongoClient(
                self.uri,
                **client_kwargs
            )
            # Send ping to confirm connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            logger.info(f"Successfully connected to MongoDB database: {self.db_name}")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as err:
            logger.warning(f"MongoDB connection timeout/failure: {err}")
            self.close()
            return False
        except PyMongoError as err:
            logger.error(f"MongoDB error during connection: {err}")
            self.close()
            return False

    def is_connected(self) -> bool:
        """Checks if MongoDB connection is active and responsive."""
        if not self.client or self.db is None:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except Exception:
            return False

    def get_collection(self, collection_name: str = None):
        """Returns target PyMongo collection."""
        if not self.is_connected():
            return None
        target = collection_name or self.collection_name
        return self.db[target]

    def check_health(self) -> dict:
        """Returns health status report for MongoDB connection."""
        if not self.uri:
            return {
                "status": "disabled",
                "database": self.db_name,
                "collection": self.collection_name,
                "details": "MONGODB_URI not configured in .env. Running on JSON file store."
            }

        connected = self.is_connected()
        if connected:
            return {
                "status": "connected",
                "database": self.db_name,
                "collection": self.collection_name,
                "details": "MongoDB Atlas connection active and responsive."
            }
        else:
            return {
                "status": "disconnected",
                "database": self.db_name,
                "collection": self.collection_name,
                "details": "Unable to connect to MongoDB server. Running in fallback mode."
            }

    def close(self):
        """Closes PyMongo client connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
