import secrets
import logging
from datetime import datetime, timedelta, timezone
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
            "full_name": user_doc.get("full_name"),
            "allow_profile_edit": bool(user_doc.get("allow_profile_edit", False))
        }

        self._active_sessions[token] = {
            "user": user_info,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=24)
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
        if datetime.now(timezone.utc) > session["expires_at"]:
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
        """Creates a new Staff user account with backend validation."""
        email_clean = (email or "").strip().lower()
        username_clean = (username or "").strip().lower() or email_clean.split("@")[0]
        full_name_clean = (full_name or "").strip()
        pwd = (password or "").strip()

        if not full_name_clean:
            return {"success": False, "message": "Full Name is required."}

        if not email_clean or "@" not in email_clean or "." not in email_clean:
            return {"success": False, "message": "Please enter a valid email address."}

        if not pwd or len(pwd) < 6:
            return {"success": False, "message": "Password must be at least 6 characters long."}

        if self.repository.find_by_email_or_username(email_clean) or self.repository.find_by_email_or_username(username_clean):
            return {"success": False, "message": "An account with this Email or Username already exists."}

        user_dict = {
            "_id": f"user-staff-{secrets.token_hex(4)}",
            "email": email_clean,
            "username": username_clean,
            "password_hash": generate_password_hash(pwd),
            "role": "staff",
            "full_name": full_name_clean,
            "allow_profile_edit": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if self.repository.create_user(user_dict):
            return {"success": True, "message": "Staff account created successfully! Please sign in below."}
        return {"success": False, "message": "Failed to create staff account due to a database error."}

    def toggle_staff_profile_edit(self, user_id: str, allow: bool) -> dict:
        """Enables or disables profile editing permission for a staff member."""
        user = self.repository.find_by_id(user_id)
        if not user:
            return {"success": False, "message": "Staff member not found."}
        
        success = self.repository.update_user(user_id, {"allow_profile_edit": allow})
        if success:
            status_str = "allowed" if allow else "disabled"
            return {"success": True, "message": f"Profile editing has been {status_str} for {user.get('full_name') or user.get('username')}."}
        return {"success": False, "message": "Failed to update staff profile permission."}

    def update_staff_user(self, user_id: str, updates: dict) -> dict:
        """Updates staff profile details in persistent repository."""
        if not user_id:
            return {"success": False, "message": "User ID is required."}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.repository.update_user(user_id, updates):
            return {"success": True, "message": "Profile updated successfully."}
        return {"success": False, "message": "Failed to update profile due to database error."}

    def delete_staff_user(self, user_id: str) -> dict:
        """Deletes a staff user account (Admin operation)."""
        if self.repository.delete_user(user_id):
            return {"success": True, "message": "Staff account deleted successfully"}
        return {"success": False, "message": "Staff account not found or cannot be deleted"}
