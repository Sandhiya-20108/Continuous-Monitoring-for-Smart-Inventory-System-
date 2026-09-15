from datetime import datetime, timezone

class UserModel:
    """
    Data abstraction class representing a user document in MongoDB.
    Roles supported: 'admin', 'staff', 'customer'
    """
    def __init__(self, data: dict):
        self.id = str(data.get("_id")) if data.get("_id") is not None else None
        self.email = data.get("email", "").strip().lower()
        self.username = data.get("username", "").strip()
        self.password_hash = data.get("password_hash", "")
        self.role = data.get("role", "customer").strip().lower()
        self.full_name = data.get("full_name", "").strip()
        self.allow_profile_edit = bool(data.get("allow_profile_edit", False))
        self.created_at = data.get("created_at", datetime.now(timezone.utc).isoformat())

    def to_dict(self, include_sensitive: bool = False) -> dict:
        doc = {
            "email": self.email,
            "username": self.username,
            "role": self.role,
            "full_name": self.full_name,
            "allow_profile_edit": self.allow_profile_edit,
            "created_at": self.created_at
        }
        if self.id:
            doc["_id"] = self.id
        if include_sensitive:
            doc["password_hash"] = self.password_hash
        return doc
