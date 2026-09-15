from flask import Blueprint, jsonify, request
from backend.services.inventory_service import InventoryService
from backend.utils import risk_engine

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api")
service = InventoryService()

@inventory_bp.route("/health", methods=["GET"])
def health_check():
    db_health = service.get_db_health()
    return jsonify({
        "status": "online",
        "service": "Inventory Risk Intelligence API",
        "version": "2.0.0-phase2-mongodb",
        "mongodb": db_health
    })

@inventory_bp.route("/products", methods=["GET"])
def get_products():
    category = request.args.get("category")
    risk_level = request.args.get("risk_level")
    search = request.args.get("search")
    
    products = service.get_all_products(category=category, risk_level=risk_level, search=search)
    return jsonify({
        "status": "success",
        "count": len(products),
        "data": products
    })

@inventory_bp.route("/products/<product_id>", methods=["GET"])
def get_product_detail(product_id):
    product = service.get_product_by_id(product_id)
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404
    return jsonify({"status": "success", "data": product})

@inventory_bp.route("/metrics", methods=["GET"])
def get_metrics():
    metrics = service.get_dashboard_metrics()
    return jsonify({"status": "success", "data": metrics})

@inventory_bp.route("/assistant", methods=["GET"])
def get_assistant():
    assistant_data = service.get_assistant_summary()
    return jsonify({"status": "success", "data": assistant_data})

@inventory_bp.route("/alerts", methods=["GET"])
def get_alerts():
    severity = request.args.get("severity")
    alerts = service.get_alerts(severity_filter=severity)
    return jsonify({
        "status": "success",
        "count": len(alerts),
        "data": alerts
    })

@inventory_bp.route("/simulate-tick", methods=["POST"])
def simulate_tick():
    result = service.simulate_continuous_tick()
    return jsonify(result)

from backend.routes.auth import require_auth, require_role

@inventory_bp.route("/products", methods=["POST"])
@require_role("admin")
def add_product_route(current_user):
    data = request.get_json() or {}
    res = service.add_product(data)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 400
    return jsonify({"status": "success", "message": res["message"], "data": res["data"]})

@inventory_bp.route("/products/<product_id>", methods=["PUT"])
@require_role("admin")
def update_product_route(current_user, product_id):
    data = request.get_json() or {}
    res = service.update_product(product_id, data)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 400
    return jsonify({"status": "success", "message": res["message"], "data": res["data"]})

@inventory_bp.route("/products/<product_id>", methods=["DELETE"])
@require_role("admin")
def delete_product_route(current_user, product_id):
    res = service.delete_product(product_id)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 400
    return jsonify({"status": "success", "message": res["message"]})

@inventory_bp.route("/products/<product_id>/stock", methods=["PATCH"])
@require_auth
def update_stock_route(current_user, product_id):
    data = request.get_json() or {}
    new_stock = data.get("current_stock")
    if new_stock is None:
        return jsonify({"status": "error", "message": "current_stock is required"}), 400

    try:
        new_stock = int(new_stock)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "current_stock must be a valid integer"}), 400

    res = service.update_stock_quantity(product_id, new_stock)
    if not res["success"]:
        return jsonify({"status": "error", "message": res["message"]}), 400
    return jsonify({"status": "success", "message": res["message"], "data": res["data"]})

@inventory_bp.route("/simulate-what-if", methods=["POST"])
def simulate_what_if_route():
    data = request.get_json() or {}
    product_id = data.get("product_id")
    
    if not product_id:
        return jsonify({"status": "error", "message": "product_id is required"}), 400

    try:
        demand_change_pct = float(data.get("demand_change_pct", 0.0))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "demand_change_pct must be a valid number"}), 400

    product = service.get_product_by_id(product_id)
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404

    simulation = risk_engine.simulate_what_if(product, demand_change_pct)
    return jsonify({"status": "success", "data": simulation})
