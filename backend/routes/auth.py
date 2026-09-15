from functools import wraps
from flask import Blueprint, jsonify, request
from backend.services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
auth_service = AuthService()

def get_auth_token():
    """Extracts bearer token from Authorization header or X-Auth-Token."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.headers.get("X-Auth-Token", "").strip()

def get_current_user():
    """Helper to retrieve current user dict from token."""
    token = get_auth_token()
    if not token:
        return None
    return auth_service.validate_token(token)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"status": "error", "message": "Authentication required. Please log in."}), 401
        return f(user, *args, **kwargs)
    return decorated

def require_role(required_role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"status": "error", "message": "Authentication required. Please log in."}), 401
            
            allowed_roles = [required_role] if isinstance(required_role, str) else list(required_role)
            if user.get("role") not in allowed_roles:
                role_str = ", ".join([r.capitalize() for r in allowed_roles])
                return jsonify({"status": "error", "message": f"Access denied. Required role: {role_str}."}), 403
            return f(user, *args, **kwargs)
        return decorated
    return decorator

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("identifier") or data.get("email") or data.get("username")
    password = data.get("password")

    res = auth_service.authenticate_user(identifier, password)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 401

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "token": res["token"],
        "user": res["user"]
    })

@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = get_auth_token()
    if token:
        auth_service.logout_token(token)
    return jsonify({"status": "success", "message": "Logged out successfully"})

@auth_bp.route("/me", methods=["GET"])
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    return jsonify({"status": "success", "user": user})

@auth_bp.route("/staff", methods=["GET"])
@require_role("admin")
def list_staff(current_user):
    staff_members = auth_service.list_staff_users()
    return jsonify({"status": "success", "count": len(staff_members), "data": staff_members})

@auth_bp.route("/staff", methods=["POST"])
@require_role("admin")
def create_staff(current_user):
    data = request.get_json() or {}
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")
    full_name = data.get("full_name")

    res = auth_service.create_staff_user(email, username, password, full_name)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 400

    return jsonify({"status": "success", "message": res["message"]})

@auth_bp.route("/staff/<user_id>", methods=["DELETE"])
@require_role("admin")
def delete_staff(current_user, user_id):
    res = auth_service.delete_staff_user(user_id)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 400
    return jsonify({"status": "success", "message": res["message"]})
