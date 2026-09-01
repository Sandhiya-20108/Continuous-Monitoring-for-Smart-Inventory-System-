import secrets
import logging
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from backend.database import MongoDBConnection
from backend.repositories.user_repository import UserRepository
from backend.models.user_model import UserModel

logger = logging.getLogger("auth_service")

class AuthService:
    """
    Authentication & User Management Service.
    Handles login, token issuance, session management, and role authorization.
    """
    def __init__(self, db_conn: MongoDBConnection = None):
        self.db_conn = db_conn or MongoDBConnection()
        self.repository = UserRepository(self.db_conn)
        self._active_sessions = {}
        
        # Initialize user repository indexes and seed default users
        if self.db_conn.is_connected():
            self.repository.create_indexes()
            self.repository.seed_default_users_if_empty()

    def authenticate_user(self, identifier: str, password: str) -> dict:
        """Validates credentials and returns session payload if successful."""
        if not identifier or not password:
            return {"success": False, "message": "Email/Username and Password are required"}

        user_doc = self.repository.find_by_email_or_username(identifier)
        if not user_doc:
            return {"success": False, "message": "Invalid email/username or password"}

        stored_hash = user_doc.get("password_hash", "")
        if not check_password_hash(stored_hash, password):
            return {"success": False, "message": "Invalid email/username or password"}

        token = secrets.token_hex(24)
        user_info = {
            "id": str(user_doc.get("_id")),
            "email": user_doc.get("email"),
            "username": user_doc.get("username"),
            "role": user_doc.get("role", "staff"),
            "full_name": user_doc.get("full_name")
        }

        self._active_sessions[token] = {
            "user": user_info,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24)
        }

        logger.info(f"User '{user_info['email']}' ({user_info['role']}) logged in successfully.")
        return {
            "success": True,
            "token": token,
            "user": user_info
        }

    def validate_token(self, token: str) -> dict:
        """Returns session user if token is valid and active."""
        if not token or token not in self._active_sessions:
            return None

        session = self._active_sessions[token]
        if datetime.utcnow() > session["expires_at"]:
            del self._active_sessions[token]
            return None

        return session["user"]

    def logout_token(self, token: str) -> bool:
        """Invalidates active session token."""
        if token in self._active_sessions:
            del self._active_sessions[token]
            return True
        return False

    def list_staff_users(self) -> list:
        """Returns list of staff user accounts (Admin operation)."""
        return self.repository.get_all_staff()

    def create_staff_user(self, email: str, username: str, password: str, full_name: str) -> dict:
        """Creates a new Staff user account (Admin operation)."""
        if not email or not username or not password:
            return {"success": False, "message": "Email, Username, and Password are required"}

        if self.repository.find_by_email_or_username(email) or self.repository.find_by_email_or_username(username):
            return {"success": False, "message": "User with this Email or Username already exists"}

        user_dict = {
            "_id": f"user-staff-{secrets.token_hex(4)}",
            "email": email.strip().lower(),
            "username": username.strip().lower(),
            "password_hash": generate_password_hash(password),
            "role": "staff",
            "full_name": full_name.strip() if full_name else username,
            "created_at": datetime.utcnow().isoformat()
        }

        if self.repository.create_user(user_dict):
            return {"success": True, "message": "Staff account created successfully"}
        return {"success": False, "message": "Failed to create staff account"}

    def delete_staff_user(self, user_id: str) -> dict:
        """Deletes a staff user account (Admin operation)."""
        if self.repository.delete_user(user_id):
            return {"success": True, "message": "Staff account deleted successfully"}
        return {"success": False, "message": "Staff account not found or cannot be deleted"}
