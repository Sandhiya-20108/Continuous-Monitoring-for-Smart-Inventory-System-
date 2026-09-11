import io
import csv
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
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
            flash("You do not have permission to access that page.", "error")
            return redirect(url_for("web.staff_dashboard"))
        return f(*args, **kwargs)
    return decorated

def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        token = session.get("auth_token")
        if not user or not token or not auth_service.validate_token(token):
            session.clear()
            return redirect(url_for("web.login_view"))
        if user.get("role") == "admin":
            return redirect(url_for("web.dashboard"))
        return f(*args, **kwargs)
    return decorated

@web_bp.route("/")
def index():
    user = session.get("user")
    token = session.get("auth_token")
    if user and token and auth_service.validate_token(token):
        if user.get("role") == "admin":
            return redirect(url_for("web.dashboard"))
        return redirect(url_for("web.staff_dashboard"))
    session.clear()
    return redirect(url_for("web.login_view"))

@web_bp.route("/login", methods=["GET"])
def login_view():
    user = session.get("user")
    token = session.get("auth_token")
    if user and token and auth_service.validate_token(token):
        if user.get("role") == "admin":
            return redirect(url_for("web.dashboard"))
        return redirect(url_for("web.staff_dashboard"))
    active_tab = request.args.get("tab") or request.args.get("active_tab") or "admin"
    return render_template("login.html", error=request.args.get("error"), active_tab=active_tab)

@web_bp.route("/login", methods=["POST"])
def login():
    identifier = request.form.get("identifier", "").strip()
    password = request.form.get("password", "").strip()
    login_type = request.form.get("login_type", "").strip().lower()

    res = auth_service.authenticate_user(identifier, password)
    if not res["success"]:
        return render_template("login.html", error=res["message"], active_tab=login_type or "admin")

    user_role = (res["user"].get("role") or "customer").lower()

    if login_type == "admin" and user_role != "admin":
        return render_template("login.html", error="Access denied: Staff accounts cannot log in through the Admin Portal.", active_tab="admin")

    session["user"] = res["user"]
    session["auth_token"] = res["token"]

    if user_role == "admin":
        return redirect(url_for("web.dashboard"))
    return redirect(url_for("web.staff_dashboard"))

@web_bp.route("/demo/admin-login", methods=["GET", "POST"])
def demo_admin_login():
    res = auth_service.authenticate_user("admin@inventory.com", "Admin@123456")
    if res["success"]:
        session["user"] = res["user"]
        session["auth_token"] = res["token"]
        return redirect(url_for("web.dashboard"))
    flash("Demo Admin authentication failed.", "error")
    return redirect(url_for("web.login_view", tab="admin"))

@web_bp.route("/demo/staff-login", methods=["GET", "POST"])
def demo_staff_login():
    res = auth_service.authenticate_user("staff@inventory.com", "Staff@123456")
    if res["success"]:
        session["user"] = res["user"]
        session["auth_token"] = res["token"]
        return redirect(url_for("web.staff_dashboard"))
    flash("Demo Staff authentication failed.", "error")
    return redirect(url_for("web.login_view", tab="staff"))

@web_bp.route("/staff/register", methods=["GET"])
def staff_register_view():
    user = session.get("user")
    token = session.get("auth_token")
    if user and token and auth_service.validate_token(token):
        if user.get("role") == "admin":
            return redirect(url_for("web.dashboard"))
        return redirect(url_for("web.staff_dashboard"))
    return render_template("register_staff.html")

@web_bp.route("/staff/register", methods=["POST"])
def staff_register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not full_name:
        return render_template("register_staff.html", error="Full Name cannot be empty.", form_data=request.form)

    if not email or "@" not in email or "." not in email:
        return render_template("register_staff.html", error="Please enter a valid email address.", form_data=request.form)

    if not password or len(password) < 6:
        return render_template("register_staff.html", error="Password must be at least 6 characters long.", form_data=request.form)

    if password != confirm_password:
        return render_template("register_staff.html", error="Password and Confirm Password do not match.", form_data=request.form)

    res = auth_service.create_staff_user(
        email=email,
        username=username or email.split("@")[0],
        password=password,
        full_name=full_name
    )
    if not res["success"]:
        return render_template("register_staff.html", error=res["message"], form_data=request.form)

    flash("Staff account created successfully! Please sign in with your credentials.", "success")
    return redirect(url_for("web.login_view", tab="staff"))

@web_bp.route("/logout", methods=["POST"])
def logout():
    token = session.get("auth_token")
    if token:
        auth_service.logout_token(token)
    session.clear()
    return redirect(url_for("web.login_view"))

def get_time_based_greeting(dt=None):
    if dt is None:
        dt = datetime.now()
    hour = dt.hour
    if 5 <= hour < 12:
        return "Good Morning"
    elif 12 <= hour < 17:
        return "Good Afternoon"
    else:
        return "Good Night"

@web_bp.route("/dashboard", methods=["GET"])
@admin_required
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
    greeting = get_time_based_greeting(now)

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
        current_date=current_date,
        greeting=greeting
    )

@web_bp.route("/staff/dashboard", methods=["GET"])
@login_required
def staff_dashboard():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    
    products = inventory_service.get_all_products()
    total_products = len(products)
    out_of_stock_count = sum(1 for p in products if p.get("current_stock", 0) <= 0)
    low_stock_count = sum(1 for p in products if 0 < p.get("current_stock", 0) <= p.get("min_stock", 10))
    in_stock_count = max(0, total_products - out_of_stock_count - low_stock_count)

    recent_transactions = inventory_service.get_recent_transactions(limit=6)
    alerts = inventory_service.get_alerts()
    greeting = get_time_based_greeting()

    return render_template(
        "staff_dashboard.html",
        current_view="staff_dashboard",
        page_title="Staff Workspace",
        page_breadcrumb="Dashboard Overview",
        total_products=total_products,
        in_stock_count=in_stock_count,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        recent_transactions=recent_transactions,
        alerts=alerts[:5],
        greeting=greeting
    )

@web_bp.route("/staff/products", methods=["GET"])
@login_required
def staff_products():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    
    category = request.args.get("category", "all")
    products = inventory_service.get_all_products(category=category)

    return render_template(
        "staff_products.html",
        current_view="staff_products",
        page_title="Browse Product Catalog",
        page_breadcrumb="Browse Products",
        products=products,
        selected_category=category
    )

@web_bp.route("/staff/products/search", methods=["GET"])
@login_required
def staff_product_search():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    
    search_query = request.args.get("search", "").strip()
    products = []
    has_searched = False

    if search_query:
        has_searched = True
        products = inventory_service.get_all_products(search=search_query)

    return render_template(
        "staff_product_search.html",
        current_view="staff_product_search",
        page_title="Search Product Catalog",
        page_breadcrumb="Search Products",
        products=products,
        search_query=search_query,
        has_searched=has_searched
    )

@web_bp.route("/staff/products/<product_id>", methods=["GET"])
@login_required
def staff_product_details(product_id):
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    
    product = inventory_service.get_product_by_id(product_id)
    history_records = inventory_service.get_product_history(product_id) if product else []

    return render_template(
        "staff_product_details.html",
        current_view="staff_product_details",
        page_title="Product Specifications",
        page_breadcrumb="Product Details",
        product=product,
        history_records=history_records
    )

@web_bp.route("/staff/profile", methods=["GET"])
@login_required
def staff_profile():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    return render_template(
        "staff_profile.html",
        current_view="staff_profile",
        page_title="My Staff Profile",
        page_breadcrumb="Account Profile"
    )

@web_bp.route("/customer/dashboard", methods=["GET"])
@login_required
def customer_dashboard():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    return redirect(url_for("web.staff_dashboard"))

@web_bp.route("/customer/profile", methods=["GET"])
@login_required
def customer_profile():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))
    return redirect(url_for("web.staff_profile"))

@web_bp.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    user = session.get("user") or {}
    full_name = request.form.get("full_name", "").strip()

    if full_name:
        user["full_name"] = full_name
        session["user"] = user
        flash("Profile information updated successfully.", "success")

    redirect_url = request.referrer or (url_for("web.dashboard") if user.get("role") == "admin" else url_for("web.staff_profile"))
    return redirect(redirect_url)

@web_bp.route("/simulate-tick", methods=["POST"])
@login_required
def simulate_tick():
    inventory_service.simulate_continuous_tick()
    redirect_url = request.form.get("redirect_url") or url_for("web.dashboard")
    return redirect(redirect_url)

@web_bp.route("/inventory", methods=["GET"])
@admin_required
def inventory():
    category = request.args.get("category", "all")
    risk_level = request.args.get("risk_level", "all")
    search = request.args.get("search", "")

    products = inventory_service.get_all_products(category=category, risk_level=risk_level, search=search)

    # Server-Side Drawer / Modal triggers
    view_id = request.args.get("view_id")
    stock_id = request.args.get("stock_id")
    edit_id = request.args.get("edit_id")
    history_id = request.args.get("history_id")
    add_product_flag = request.args.get("add_product") == "true"

    drawer_product = inventory_service.get_product_by_id(view_id) if view_id else None
    stock_product = inventory_service.get_product_by_id(stock_id) if stock_id else None
    edit_product = inventory_service.get_product_by_id(edit_id) if edit_id else None
    history_product = inventory_service.get_product_by_id(history_id) if history_id else None
    history_records = inventory_service.get_product_history(history_id) if history_id else []

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
        history_product=history_product,
        history_records=history_records,
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
    else:
        flash(res["message"], "success")

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
    else:
        flash(res["message"], "success")

    return redirect(url_for("web.inventory"))

@web_bp.route("/inventory/stock/<product_id>", methods=["POST"])
@admin_required
def update_stock(product_id):
    user_info = session.get("user", {})
    user_label = user_info.get("full_name") or user_info.get("username") or "Admin"

    operation = request.form.get("operation", "ADJUSTMENT").strip()
    quantity_raw = request.form.get("quantity") or request.form.get("current_stock") or "0"
    notes = request.form.get("notes", "").strip()

    try:
        qty = int(quantity_raw)
        res = inventory_service.update_stock_quantity(
            product_id=product_id,
            quantity=qty,
            operation=operation,
            user=user_label,
            notes=notes
        )
        if not res["success"]:
            flash(res["message"], "error")
        else:
            flash(res["message"], "success")
    except (ValueError, TypeError):
        flash("Invalid stock quantity value entered.", "error")

    return redirect(url_for("web.inventory"))

@web_bp.route("/inventory/delete/<product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    res = inventory_service.delete_product(product_id)
    if not res["success"]:
        flash(res["message"], "error")
    else:
        flash("Product deleted successfully.", "success")

    return redirect(url_for("web.inventory"))

@web_bp.route("/risk-monitor", methods=["GET"])
@admin_required
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
@admin_required
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
@admin_required
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

    flash("Staff account created successfully.", "success")
    return redirect(url_for("web.users"))

@web_bp.route("/users/delete/<user_id>", methods=["POST"])
@admin_required
def delete_staff(user_id):
    res = auth_service.delete_staff_user(user_id)
    if not res["success"]:
        flash(res["message"], "error")
    else:
        flash("Staff account deleted successfully.", "success")

    return redirect(url_for("web.users"))

@web_bp.route("/export-report", methods=["GET"])
@admin_required
def export_report():
    products = inventory_service.get_all_products()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "SKU", "Product Name", "Category", "Current Stock", "Min Stock",
        "Unit Price ($)", "Avg Daily Usage", "Days to Stockout",
        "Expiry Date", "Expiry Status", "Risk Score", "Risk Level", "Last Updated"
    ])
    for p in products:
        exp_status = p.get("expiry_info", {}).get("status", "Good")
        writer.writerow([
            p.get("sku", ""),
            p.get("name", ""),
            p.get("category", ""),
            p.get("current_stock", 0),
            p.get("min_stock", 0),
            p.get("unit_price", 0.0),
            p.get("average_daily_usage", 1.0),
            p.get("days_to_stockout", 0),
            p.get("expiry_date", ""),
            exp_status,
            p.get("risk_score", 0.0),
            p.get("risk_level", "Safe"),
            p.get("last_updated", "")
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventory_telemetry_report.csv"}
    )

@web_bp.route("/toggle-theme", methods=["POST", "GET"])
def toggle_theme():
    current_theme = session.get("theme", "dark")
    session["theme"] = "light" if current_theme == "dark" else "dark"
    redirect_url = request.form.get("redirect_url") or request.args.get("redirect_url") or request.referrer or url_for("web.dashboard")
    return redirect(redirect_url)
