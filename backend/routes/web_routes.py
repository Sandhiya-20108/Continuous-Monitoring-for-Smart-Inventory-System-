from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from backend.services.inventory_service import InventoryService
from backend.services.auth_service import AuthService
from backend.utils import risk_engine

web_bp = Blueprint("web", __name__)
inventory_service = InventoryService()
auth_service = AuthService()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        token = session.get("auth_token")
        if not user or not token or not auth_service.validate_token(token):
            session.clear()
            return redirect(url_for("web.login_view"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        token = session.get("auth_token")
        if not user or not token or not auth_service.validate_token(token):
            session.clear()
            return redirect(url_for("web.login_view"))
        if user.get("role") != "admin":
            flash("Access denied. Administrator privileges required.", "error")
            return redirect(url_for("web.dashboard"))
        return f(*args, **kwargs)
    return decorated

@web_bp.route("/")
def index():
    user = session.get("user")
    token = session.get("auth_token")
    if user and token and auth_service.validate_token(token):
        return redirect(url_for("web.dashboard"))
    session.clear()
    return redirect(url_for("web.login_view"))

@web_bp.route("/login", methods=["GET"])
def login_view():
    user = session.get("user")
    token = session.get("auth_token")
    if user and token and auth_service.validate_token(token):
        return redirect(url_for("web.dashboard"))
    return render_template("login.html", error=request.args.get("error"))

@web_bp.route("/login", methods=["POST"])
def login():
    identifier = request.form.get("identifier", "").strip()
    password = request.form.get("password", "").strip()

    res = auth_service.authenticate_user(identifier, password)
    if not res["success"]:
        return render_template("login.html", error=res["message"])

    session["user"] = res["user"]
    session["auth_token"] = res["token"]
    return redirect(url_for("web.dashboard"))

@web_bp.route("/logout", methods=["POST"])
def logout():
    token = session.get("auth_token")
    if token:
        auth_service.logout_token(token)
    session.clear()
    return redirect(url_for("web.login_view"))

@web_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    products = inventory_service.get_all_products()
    metrics = inventory_service.get_dashboard_metrics()
    alerts = inventory_service.get_alerts()

    # What-If Demand Simulator
    sim_product_id = request.args.get("sim_product_id")
    sim_demand_change_pct = float(request.args.get("sim_demand_change_pct", 50))
    selected_sim_product = None
    sim_result = None

    if sim_product_id:
        selected_sim_product = inventory_service.get_product_by_id(sim_product_id)
        if selected_sim_product:
            sim_result = risk_engine.simulate_what_if(selected_sim_product, sim_demand_change_pct)
    elif products:
        selected_sim_product = products[0]
        sim_result = risk_engine.simulate_what_if(selected_sim_product, sim_demand_change_pct)

    now = datetime.now()
    current_date = now.strftime("%A, %B ") + str(now.day) + now.strftime(", %Y")

    return render_template(
        "dashboard.html",
        current_view="dashboard",
        page_title="Executive Overview",
        page_breadcrumb="Inventory Intelligence",
        products=products,
        metrics=metrics,
        alerts=alerts,
        selected_sim_product=selected_sim_product,
        sim_demand_change_pct=sim_demand_change_pct,
        sim_result=sim_result,
        current_date=current_date
    )

@web_bp.route("/simulate-tick", methods=["POST"])
@login_required
def simulate_tick():
    inventory_service.simulate_continuous_tick()
    redirect_url = request.form.get("redirect_url") or url_for("web.dashboard")
    return redirect(redirect_url)

@web_bp.route("/inventory", methods=["GET"])
@login_required
def inventory():
    category = request.args.get("category", "all")
    risk_level = request.args.get("risk_level", "all")
    search = request.args.get("search", "")

    products = inventory_service.get_all_products(category=category, risk_level=risk_level, search=search)

    # Server-Side Drawer / Modal triggers
    view_id = request.args.get("view_id")
    stock_id = request.args.get("stock_id")
    edit_id = request.args.get("edit_id")
    add_product_flag = request.args.get("add_product") == "true"

    drawer_product = inventory_service.get_product_by_id(view_id) if view_id else None
    stock_product = inventory_service.get_product_by_id(stock_id) if stock_id else None
    edit_product = inventory_service.get_product_by_id(edit_id) if edit_id else None

    return render_template(
        "inventory.html",
        current_view="inventory",
        page_title="Inventory Telemetry Monitor",
        page_breadcrumb="Inventory",
        products=products,
        selected_category=category,
        selected_risk=risk_level,
        search_query=search,
        drawer_product=drawer_product,
        stock_product=stock_product,
        edit_product=edit_product,
        show_product_modal=add_product_flag or bool(edit_product)
    )

@web_bp.route("/inventory/add", methods=["POST"])
@admin_required
def add_product():
    product_data = {
        "sku": request.form.get("sku", "").strip(),
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", "General"),
        "current_stock": int(request.form.get("current_stock", 0)),
        "min_stock": int(request.form.get("min_stock", 10)),
        "unit_price": float(request.form.get("unit_price", 0.0)),
        "average_daily_usage": float(request.form.get("average_daily_usage", 1.0)),
        "expiry_date": request.form.get("expiry_date", "2027-12-31")
    }

    res = inventory_service.add_product(product_data)
    if not res["success"]:
        flash(res["message"], "error")

    return redirect(url_for("web.inventory"))

@web_bp.route("/inventory/edit/<product_id>", methods=["POST"])
@admin_required
def update_product(product_id):
    product_data = {
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", "General"),
        "current_stock": int(request.form.get("current_stock", 0)),
        "min_stock": int(request.form.get("min_stock", 10)),
        "unit_price": float(request.form.get("unit_price", 0.0)),
        "average_daily_usage": float(request.form.get("average_daily_usage", 1.0)),
        "expiry_date": request.form.get("expiry_date", "2027-12-31")
    }

    res = inventory_service.update_product(product_id, product_data)
    if not res["success"]:
        flash(res["message"], "error")

    return redirect(url_for("web.inventory"))

@web_bp.route("/inventory/stock/<product_id>", methods=["POST"])
@login_required
def update_stock(product_id):
    try:
        new_stock = int(request.form.get("current_stock", 0))
        inventory_service.update_stock_quantity(product_id, new_stock)
    except (ValueError, TypeError):
        flash("Invalid stock quantity", "error")

    return redirect(url_for("web.inventory"))

@web_bp.route("/inventory/delete/<product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    res = inventory_service.delete_product(product_id)
    if not res["success"]:
        flash(res["message"], "error")

    return redirect(url_for("web.inventory"))

@web_bp.route("/risk-monitor", methods=["GET"])
@login_required
def risk_monitor():
    products = inventory_service.get_all_products()
    metrics = inventory_service.get_dashboard_metrics()
    reorder_recommendations = inventory_service.get_reorder_recommendations()

    view_id = request.args.get("view_id")
    drawer_product = inventory_service.get_product_by_id(view_id) if view_id else None

    return render_template(
        "risk_monitor.html",
        current_view="risk_monitor",
        page_title="Predictive Risk Intelligence",
        page_breadcrumb="Risk Monitor",
        products=products,
        metrics=metrics,
        drawer_product=drawer_product,
        reorder_recommendations=reorder_recommendations
    )

@web_bp.route("/alerts", methods=["GET"])
@login_required
def alerts():
    severity = request.args.get("severity", "all")
    alerts_list = inventory_service.get_alerts(severity_filter=severity)

    return render_template(
        "alerts.html",
        current_view="alerts",
        page_title="Central Risk Alert Feed",
        page_breadcrumb="Alerts Center",
        alerts=alerts_list,
        selected_severity=severity
    )

@web_bp.route("/analytics", methods=["GET"])
@login_required
def analytics():
    metrics = inventory_service.get_dashboard_metrics()

    return render_template(
        "analytics.html",
        current_view="analytics",
        page_title="Consumption & Expiry Analytics",
        page_breadcrumb="Analytics",
        metrics=metrics
    )

@web_bp.route("/users", methods=["GET"])
@admin_required
def users():
    staff_list = auth_service.list_staff_users()

    return render_template(
        "users.html",
        current_view="users",
        page_title="Staff Account Administration",
        page_breadcrumb="Staff Users",
        staff_users=staff_list,
        error=request.args.get("error")
    )

@web_bp.route("/users/create", methods=["POST"])
@admin_required
def create_staff():
    email = request.form.get("email", "").strip()
    username = request.form.get("username", "").strip()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "").strip()

    res = auth_service.create_staff_user(email, username, password, full_name)
    if not res["success"]:
        return redirect(url_for("web.users", error=res["message"]))

    return redirect(url_for("web.users"))

@web_bp.route("/users/delete/<user_id>", methods=["POST"])
@admin_required
def delete_staff(user_id):
    res = auth_service.delete_staff_user(user_id)
    if not res["success"]:
        flash(res["message"], "error")

    return redirect(url_for("web.users"))

@web_bp.route("/toggle-theme", methods=["POST", "GET"])
def toggle_theme():
    current_theme = session.get("theme", "dark")
    session["theme"] = "light" if current_theme == "dark" else "dark"
    redirect_url = request.form.get("redirect_url") or request.args.get("redirect_url") or request.referrer or url_for("web.dashboard")
    return redirect(redirect_url)
