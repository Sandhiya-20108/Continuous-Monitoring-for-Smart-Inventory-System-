import io
import csv
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
from backend.services.inventory_service import InventoryService
from backend.services.auth_service import AuthService
from backend.services.stock_forecast_service import StockForecastService
from backend.utils import risk_engine
from backend.utils.date_formatter import format_date_filter, SUPPORTED_DATE_FORMATS, DEFAULT_DATE_FORMAT

web_bp = Blueprint("web", __name__)
inventory_service = InventoryService()
auth_service = AuthService()

@web_bp.app_template_filter("format_date")
def format_date_template_filter(value, date_format_name=None):
    return format_date_filter(value, date_format_name)

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
    range_param = request.args.get("range", "6")
    try:
        selected_range = int(range_param)
        if selected_range not in [3, 6, 9, 12]:
            selected_range = 6
    except (ValueError, TypeError):
        selected_range = 6

    selected_month = request.args.get("month")

    raw_products = inventory_service.get_all_products()
    products = StockForecastService.enrich_products_with_forecast(raw_products)
    metrics = inventory_service.get_dashboard_metrics()
    alerts = inventory_service.get_alerts()
    recent_transactions = inventory_service.get_recent_transactions(limit=6)

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

    stock_movement = inventory_service.get_stock_movement_analytics(months=selected_range, selected_month=selected_month)
    top_categories = inventory_service.get_top_categories_analytics()

    return render_template(
        "dashboard.html",
        current_view="dashboard",
        page_title="Executive Overview",
        page_breadcrumb="Inventory Intelligence",
        products=products,
        metrics=metrics,
        alerts=alerts,
        recent_transactions=recent_transactions,
        stock_movement=stock_movement,
        top_categories=top_categories,
        selected_range=selected_range,
        selected_month=selected_month,
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
    filter_type = request.args.get("filter", "all").strip().lower()
    
    all_prods = inventory_service.get_all_products(category=category)
    
    if filter_type == "low_stock":
        products = [p for p in all_prods if p.get("current_stock", 0) < p.get("min_stock", 10) or p.get("risk_level") in ["Critical", "High Risk", "Warning"]]
        title = "Low Stock & Reorder Catalog"
    elif filter_type == "expiring":
        products = [p for p in all_prods if p.get("expiry_info", {}).get("is_expiring_soon")]
        title = "Expiring Batches Catalog"
    else:
        products = all_prods
        title = "Browse Product Catalog"

    stock_id = request.args.get("stock_id")
    stock_product = inventory_service.get_product_by_id(stock_id) if stock_id else None

    return render_template(
        "staff_products.html",
        current_view="staff_products",
        page_title=title,
        page_breadcrumb="Browse Products",
        products=products,
        selected_category=category,
        filter_type=filter_type,
        stock_product=stock_product
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
    if not product:
        flash(f"Product with ID '{product_id}' not found.", "error")
        return redirect(url_for("web.staff_products"))
        
    history_records = inventory_service.get_product_history(product_id)

    return render_template(
        "staff_product_details.html",
        current_view="staff_product_details",
        page_title="Product Specifications",
        page_breadcrumb="Product Details",
        product=product,
        history_records=history_records
    )

@web_bp.route("/staff/stock/<product_id>", methods=["POST"])
@login_required
def staff_update_stock(product_id):
    user_info = session.get("user", {})
    user_label = user_info.get("full_name") or user_info.get("username") or "Staff User"
    user_role = user_info.get("role", "staff")

    operation = request.form.get("operation", "STOCK_IN").strip()
    quantity_raw = request.form.get("quantity") or "0"
    notes = request.form.get("notes", "").strip()

    try:
        qty = int(quantity_raw)
        res = inventory_service.update_stock_quantity(
            product_id=product_id,
            quantity=qty,
            operation=operation,
            user=user_label,
            role=user_role,
            notes=notes
        )
        if not res["success"]:
            flash(res["message"], "error")
        else:
            flash(res["message"], "success")
    except (ValueError, TypeError):
        flash("Invalid quantity: Please enter a valid number.", "error")

    redirect_url = request.form.get("redirect_url") or request.referrer or url_for("web.staff_products")
    return redirect(redirect_url)

@web_bp.route("/staff/transactions", methods=["GET"])
@login_required
def staff_transactions():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))

    recent_transactions = inventory_service.get_recent_transactions(limit=50)

    return render_template(
        "staff_transactions.html",
        current_view="staff_transactions",
        page_title="Audit Trail & Stock History",
        page_breadcrumb="Recent Transactions",
        recent_transactions=recent_transactions
    )

@web_bp.route("/staff/profile", methods=["GET"])
@login_required
def staff_profile():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("web.dashboard"))

    session_user = session.get("user", {})
    user_id = session_user.get("id") or session_user.get("_id") or session_user.get("email")

    user_doc = auth_service.repository.find_by_id(user_id) or auth_service.repository.find_by_email_or_username(session_user.get("email", ""))
    
    can_edit_profile = False
    if user_doc:
        can_edit_profile = bool(user_doc.get("allow_profile_edit", False))
        session_user["allow_profile_edit"] = can_edit_profile
        session_user["full_name"] = user_doc.get("full_name", session_user.get("full_name"))
        session["user"] = session_user

    return render_template(
        "staff_profile.html",
        current_view="staff_profile",
        page_title="My Staff Profile",
        page_breadcrumb="Account Profile",
        user_doc=user_doc,
        can_edit_profile=can_edit_profile
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
    session_user = session.get("user") or {}
    user_role = session_user.get("role", "staff")
    user_id = session_user.get("id") or session_user.get("_id") or session_user.get("email")

    redirect_url = request.referrer or (url_for("web.dashboard") if user_role == "admin" else url_for("web.staff_profile"))

    # Security check: validate user's own profile edit permission from DB
    user_doc = auth_service.repository.find_by_id(user_id) or auth_service.repository.find_by_email_or_username(session_user.get("email", ""))

    if user_role != "admin":
        allow_edit = bool(user_doc.get("allow_profile_edit", False)) if user_doc else False
        if not allow_edit:
            flash("Your administrator has disabled profile editing.", "error")
            return redirect(url_for("web.staff_profile"))

    # Security check: prevent staff from updating another user's profile
    target_user_id = request.form.get("user_id")
    if target_user_id and target_user_id != user_id and user_role != "admin":
        flash("Unauthorized profile modification attempt.", "error")
        return redirect(url_for("web.staff_profile"))

    full_name = request.form.get("full_name", "").strip()
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not full_name:
        flash("Full Name is required.", "error")
        return redirect(redirect_url)

    updates = {"full_name": full_name}

    if new_password:
        if len(new_password) < 8:
            flash("New Password must be at least 8 characters long.", "error")
            return redirect(redirect_url)
        if new_password != confirm_password:
            flash("New Password and Confirm Password do not match.", "error")
            return redirect(redirect_url)
        
        from werkzeug.security import generate_password_hash
        updates["password_hash"] = generate_password_hash(new_password)

    now_iso = datetime.now(timezone.utc).isoformat()
    session_user["full_name"] = full_name
    session_user["updated_at"] = now_iso
    session["user"] = session_user

    if user_id:
        auth_service.update_staff_user(user_id, updates)

    if new_password:
        flash("Profile information and account password updated successfully.", "success")
    else:
        flash("Profile information updated successfully.", "success")

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
@login_required
def alerts():
    severity = request.args.get("severity", "all")
    alerts_list, summary = inventory_service.get_smart_alerts_summary(severity_filter=severity)

    return render_template(
        "alerts.html",
        current_view="alerts",
        page_title="Smart Alert Center",
        page_breadcrumb="Alerts Center",
        alerts=alerts_list,
        summary=summary,
        selected_severity=severity
    )

@web_bp.route("/alerts/update-status", methods=["POST"])
@login_required
def update_alert_status():
    user_info = session.get("user", {})
    user_label = user_info.get("full_name") or user_info.get("username") or "User"

    alert_id = request.form.get("alert_id", "").strip()
    status = request.form.get("status", "Viewed").strip()

    if alert_id:
        res = inventory_service.update_alert_status(alert_id=alert_id, status=status, user=user_label)
        if res["success"]:
            flash(res["message"], "success")
        else:
            flash(res["message"], "error")
    else:
        flash("Alert ID is missing.", "error")

    redirect_url = request.form.get("redirect_url") or request.referrer or url_for("web.alerts")
    return redirect(redirect_url)

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

@web_bp.route("/users/toggle-profile-edit/<user_id>", methods=["POST"])
@admin_required
def toggle_staff_profile_edit(user_id):
    action = request.form.get("action", "").strip().lower()
    allow = (action == "allow") or (request.form.get("allow_profile_edit") == "true")
    
    res = auth_service.toggle_staff_profile_edit(user_id, allow)
    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "error")
        
    redirect_url = request.referrer or url_for("web.admin_settings", section="staff_permissions")
    return redirect(redirect_url)

@web_bp.route("/reports", methods=["GET", "POST"])
@web_bp.route("/admin/reports", methods=["GET", "POST"])
@admin_required
def reports_view():
    """Renders the dedicated Admin Reports & Intelligence Center UI."""
    if request.method == "POST":
        action_type = request.form.get("action_type")
        if action_type == "save_config":
            name = request.form.get("report_name", "").strip()
            report_type = request.form.get("report_type", "inventory").strip()
            category = request.form.get("category", "all")
            risk_level = request.form.get("risk_level", "all")
            tx_type = request.form.get("tx_type", "all")
            columns = request.form.getlist("visible_columns")

            filters = {
                "category": category,
                "risk_level": risk_level,
                "tx_type": tx_type
            }
            user = session.get("user", {})
            created_by = user.get("username", "Admin")

            inventory_service.save_report_config(name, report_type, filters, columns, created_by)
            flash("Report configuration saved successfully.", "success")
            return redirect(url_for("web.reports_view", tab="saved"))

        elif action_type == "delete_config":
            report_id = request.form.get("report_id")
            if report_id:
                inventory_service.delete_saved_report(report_id)
                flash("Report configuration deleted successfully.", "info")
            return redirect(url_for("web.reports_view", tab="saved"))

    active_tab = request.args.get("tab", "overview")

    # Inventory filters
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "all").strip()
    stock_status = request.args.get("stock_status", "all").strip()
    risk_level = request.args.get("risk_level", "all").strip()
    sort_by = request.args.get("sort_by", "stock").strip()

    # Transaction filters
    tx_type = request.args.get("tx_type", "all").strip()
    tx_user = request.args.get("tx_user", "").strip()

    # Alert filters
    alert_severity = request.args.get("alert_severity", "all").strip()
    alert_type = request.args.get("alert_type", "all").strip()

    # Get data collections
    raw_products = inventory_service.get_all_products(
        category=category if category != "all" else None,
        risk_level=risk_level if risk_level != "all" else None,
        search=search if search else None
    )

    if stock_status == "in_stock":
        raw_products = [p for p in raw_products if p.get("current_stock", 0) > 0]
    elif stock_status == "low_stock":
        raw_products = [p for p in raw_products if 0 < p.get("current_stock", 0) < p.get("min_stock", 0)]
    elif stock_status == "out_of_stock":
        raw_products = [p for p in raw_products if p.get("current_stock", 0) <= 0]

    if sort_by == "stock":
        raw_products.sort(key=lambda x: x.get("current_stock", 0))
    elif sort_by == "price":
        raw_products.sort(key=lambda x: x.get("unit_price", 0.0), reverse=True)
    elif sort_by == "expiry":
        raw_products.sort(key=lambda x: str(x.get("expiry_date", "9999-99-99")))

    all_txs = inventory_service.get_recent_transactions(limit=1000)
    filtered_txs = []
    for t in all_txs:
        t_type = t.get("type", t.get("transaction_type", "ADJUSTMENT"))
        t_user = t.get("user", "")
        if tx_type != "all" and str(t_type).upper() != tx_type.upper():
            continue
        if tx_user and tx_user.lower() not in str(t_user).lower():
            continue
        filtered_txs.append(t)

    all_alerts = inventory_service.get_alerts()
    products_all = inventory_service.get_all_products()
    prod_map = {p.get("_id"): p for p in products_all}
    alerts_list = []
    seen_ids = set()

    for a in all_alerts:
        p_id = a.get("product_id")
        p = prod_map.get(p_id, {})
        alert_id = a.get("id", f"alert-{len(alerts_list)+1}")
        seen_ids.add(alert_id)
        alerts_list.append({
            "id": alert_id,
            "product_name": a.get("product_name", p.get("name", "N/A")),
            "category": a.get("category", p.get("category", "General")),
            "current_stock": p.get("current_stock", 0),
            "min_stock": p.get("min_stock", 0),
            "risk_type": a.get("type", "Low Stock"),
            "risk_level": a.get("severity", "Warning"),
            "alert_message": a.get("message", ""),
            "timestamp": a.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "status": "Active"
        })

    for p in products_all:
        p_id = p.get("_id")
        curr_stock = p.get("current_stock", 0)
        min_stock = p.get("min_stock", 0)
        if min_stock > 0 and curr_stock > (min_stock * 3):
            over_id = f"alert-over-{p_id}"
            if over_id not in seen_ids:
                seen_ids.add(over_id)
                alerts_list.append({
                    "id": over_id,
                    "product_name": p.get("name", "N/A"),
                    "category": p.get("category", "General"),
                    "current_stock": curr_stock,
                    "min_stock": min_stock,
                    "risk_type": "Overstock",
                    "risk_level": "Warning",
                    "alert_message": f"Excess inventory holding ({curr_stock} units vs {min_stock} min threshold).",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "Active"
                })
        if p.get("requires_reorder"):
            reorder_id = f"alert-reorder-{p_id}"
            if reorder_id not in seen_ids:
                seen_ids.add(reorder_id)
                alerts_list.append({
                    "id": reorder_id,
                    "product_name": p.get("name", "N/A"),
                    "category": p.get("category", "General"),
                    "current_stock": curr_stock,
                    "min_stock": min_stock,
                    "risk_type": "Reorder Required",
                    "risk_level": p.get("risk_level", "Warning"),
                    "alert_message": f"Recommended reorder quantity: {p.get('recommended_reorder', 0)} units.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "Active"
                })

    filtered_alerts = []
    for alt in alerts_list:
        if alert_severity != "all" and alt["risk_level"].lower() != alert_severity.lower():
            continue
        if alert_type != "all" and alt["risk_type"].lower() != alert_type.lower():
            continue
        filtered_alerts.append(alt)

    saved_reports = inventory_service.get_saved_reports()

    total_prods = len(products_all)
    total_stock_qty = sum(p.get("current_stock", 0) for p in products_all)
    low_stock_cnt = sum(1 for p in products_all if p.get("current_stock", 0) < p.get("min_stock", 0))
    critical_cnt = sum(1 for p in products_all if p.get("risk_level") == "Critical")
    total_tx_cnt = len(all_txs)

    metrics = {
        "total_products": total_prods,
        "total_stock_qty": total_stock_qty,
        "low_stock_count": low_stock_cnt,
        "critical_stock_count": critical_cnt,
        "total_tx_count": total_tx_cnt
    }

    categories = list(set(p.get("category", "General") for p in products_all))
    categories.sort()

    filters = {
        "search": search,
        "category": category,
        "stock_status": stock_status,
        "risk_level": risk_level,
        "sort_by": sort_by,
        "tx_type": tx_type,
        "tx_user": tx_user,
        "alert_severity": alert_severity,
        "alert_type": alert_type
    }

    return render_template(
        "reports.html",
        current_view="reports",
        active_tab=active_tab,
        metrics=metrics,
        products=raw_products,
        transactions=filtered_txs,
        alerts=filtered_alerts,
        saved_reports=saved_reports,
        categories=categories,
        filters=filters
    )

@web_bp.route("/export-report/inventory", methods=["GET"])
@web_bp.route("/export-inventory", methods=["GET"])
@admin_required
def export_inventory_csv():
    """Generates and exports the complete or filtered inventory catalogue CSV."""
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "all").strip()
    stock_status = request.args.get("stock_status", "all").strip()
    risk_level = request.args.get("risk_level", "all").strip()

    products = inventory_service.get_all_products(
        category=category if category != "all" else None,
        risk_level=risk_level if risk_level != "all" else None,
        search=search if search else None
    )

    if stock_status == "in_stock":
        products = [p for p in products if p.get("current_stock", 0) > 0]
    elif stock_status == "low_stock":
        products = [p for p in products if 0 < p.get("current_stock", 0) < p.get("min_stock", 0)]
    elif stock_status == "out_of_stock":
        products = [p for p in products if p.get("current_stock", 0) <= 0]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Product ID", "Product Name", "Category", "Current Stock",
        "Minimum Stock", "Price", "Expiry Date", "Risk Level", "Status"
    ])
    if products:
        for p in products:
            curr_stock = p.get("current_stock", 0)
            min_stock = p.get("min_stock", 0)
            status = "Out of Stock" if curr_stock <= 0 else ("Low Stock" if curr_stock < min_stock else "Active")
            writer.writerow([
                p.get("_id", p.get("sku", "N/A")),
                p.get("name", "N/A"),
                p.get("category", "General"),
                curr_stock,
                min_stock,
                p.get("unit_price", 0.0),
                p.get("expiry_date", "N/A"),
                p.get("risk_level", "Safe"),
                status
            ])
    else:
        writer.writerow([
            "N/A", "No inventory records found for the selected filters", "N/A", 0, 0, 0.0, "N/A", "N/A", "Inactive"
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventory_report.csv"}
    )

@web_bp.route("/export-report/transactions", methods=["GET"])
@web_bp.route("/export-transactions", methods=["GET"])
@admin_required
def export_transactions_csv():
    """Generates and exports the complete or filtered stock movement transaction history CSV."""
    tx_type = request.args.get("tx_type", "all").strip()
    tx_user = request.args.get("tx_user", "").strip()

    all_txs = inventory_service.get_recent_transactions(limit=1000)
    txs = []
    for t in all_txs:
        t_type = t.get("type", t.get("transaction_type", "ADJUSTMENT"))
        t_user = t.get("user", "")
        if tx_type != "all" and str(t_type).upper() != tx_type.upper():
            continue
        if tx_user and tx_user.lower() not in str(t_user).lower():
            continue
        txs.append(t)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Transaction ID", "Product Name", "Transaction Type", "Quantity",
        "Previous Stock", "Updated Stock", "Performed By", "Date", "Time"
    ])
    if txs:
        for t in txs:
            ts_str = str(t.get("timestamp", ""))
            date_part = "N/A"
            time_part = "N/A"
            if ts_str:
                if "T" in ts_str:
                    parts = ts_str.split("T")
                    date_part = parts[0]
                    if len(parts) > 1:
                        time_part = parts[1].split(".")[0].replace("Z", "")
                elif " " in ts_str:
                    parts = ts_str.split(" ")
                    date_part = parts[0]
                    if len(parts) > 1:
                        time_part = parts[1]
                else:
                    date_part = ts_str[:10]
            
            t_type = t.get("type", t.get("transaction_type", "ADJUSTMENT"))
            writer.writerow([
                t.get("id", t.get("_id", "N/A")),
                t.get("product_name", "N/A"),
                t_type,
                t.get("quantity_changed", t.get("quantity", 0)),
                t.get("old_stock", 0),
                t.get("new_stock", 0),
                t.get("user", "System"),
                date_part,
                time_part
            ])
    else:
        writer.writerow([
            "N/A", "No transaction history found for this period", "N/A", 0, 0, 0, "N/A", "N/A", "N/A"
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=transaction_history_report.csv"}
    )

@web_bp.route("/export-report/alerts", methods=["GET"])
@web_bp.route("/export-alerts", methods=["GET"])
@admin_required
def export_alerts_report():
    """Generates and exports the inventory risk and alert information CSV."""
    alert_severity = request.args.get("alert_severity", "all").strip()
    alert_type = request.args.get("alert_type", "all").strip()

    raw_alerts = inventory_service.get_alerts()
    products = inventory_service.get_all_products()
    prod_map = {p.get("_id"): p for p in products}

    alerts_list = []
    seen_ids = set()

    for a in raw_alerts:
        p_id = a.get("product_id")
        p = prod_map.get(p_id, {})
        alert_id = a.get("id", f"alert-{len(alerts_list)+1}")
        seen_ids.add(alert_id)
        alerts_list.append({
            "id": alert_id,
            "product_name": a.get("product_name", p.get("name", "N/A")),
            "category": a.get("category", p.get("category", "General")),
            "current_stock": p.get("current_stock", 0),
            "min_stock": p.get("min_stock", 0),
            "risk_type": a.get("type", "Low Stock"),
            "risk_level": a.get("severity", "Warning"),
            "alert_message": a.get("message", ""),
            "timestamp": a.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "status": "Active"
        })

    for p in products:
        p_id = p.get("_id")
        curr_stock = p.get("current_stock", 0)
        min_stock = p.get("min_stock", 0)
        if min_stock > 0 and curr_stock > (min_stock * 3):
            over_id = f"alert-over-{p_id}"
            if over_id not in seen_ids:
                seen_ids.add(over_id)
                alerts_list.append({
                    "id": over_id,
                    "product_name": p.get("name", "N/A"),
                    "category": p.get("category", "General"),
                    "current_stock": curr_stock,
                    "min_stock": min_stock,
                    "risk_type": "Overstock",
                    "risk_level": "Warning",
                    "alert_message": f"Excess inventory holding ({curr_stock} units vs {min_stock} min threshold).",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "Active"
                })
        if p.get("requires_reorder"):
            reorder_id = f"alert-reorder-{p_id}"
            if reorder_id not in seen_ids:
                seen_ids.add(reorder_id)
                alerts_list.append({
                    "id": reorder_id,
                    "product_name": p.get("name", "N/A"),
                    "category": p.get("category", "General"),
                    "current_stock": curr_stock,
                    "min_stock": min_stock,
                    "risk_type": "Reorder Required",
                    "risk_level": p.get("risk_level", "Warning"),
                    "alert_message": f"Recommended reorder quantity: {p.get('recommended_reorder', 0)} units.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "Active"
                })

    filtered_alerts = []
    for alt in alerts_list:
        if alert_severity != "all" and alt["risk_level"].lower() != alert_severity.lower():
            continue
        if alert_type != "all" and alt["risk_type"].lower() != alert_type.lower():
            continue
        filtered_alerts.append(alt)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Alert ID", "Product Name", "Category", "Current Stock",
        "Minimum Stock", "Risk Type", "Risk Level", "Alert Message",
        "Created Date", "Alert Status"
    ])

    if filtered_alerts:
        for a in filtered_alerts:
            ts_str = str(a.get("timestamp", ""))
            date_str = ts_str.split("T")[0] if "T" in ts_str else ts_str[:10]
            writer.writerow([
                a["id"],
                a["product_name"],
                a["category"],
                a["current_stock"],
                a["min_stock"],
                a["risk_type"],
                a["risk_level"],
                a["alert_message"],
                date_str,
                a["status"]
            ])
    else:
        writer.writerow([
            "N/A", "No active risk alerts found", "N/A", 0, 0, "N/A", "N/A", "System healthy - no risk alerts active", "N/A", "Clean"
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=risk_alert_report.csv"}
    )

@web_bp.route("/export-report/filtered", methods=["GET"])
@web_bp.route("/export-filtered", methods=["GET"])
@admin_required
def export_filtered_csv():
    """Exports the currently selected filtered report dataset."""
    report_type = request.args.get("report_type", "inventory").lower()
    if report_type == "transactions":
        return export_transactions_csv()
    elif report_type == "alerts":
        return export_alerts_report()
    return export_inventory_csv()

@web_bp.route("/export-report", methods=["GET"])
@admin_required
def export_report():
    """Backwards-compatible report dispatcher endpoint."""
    report_type = request.args.get("type", "").lower()
    if report_type == "transactions":
        return export_transactions_csv()
    elif report_type == "alerts":
        return export_alerts_report()
    return export_inventory_csv()

@web_bp.route("/toggle-theme", methods=["POST", "GET"])
def toggle_theme():
    current_theme = session.get("theme", "dark")
    session["theme"] = "light" if current_theme == "dark" else "dark"
    redirect_url = request.form.get("redirect_url") or request.args.get("redirect_url") or request.referrer or url_for("web.dashboard")
    return redirect(redirect_url)

@web_bp.route("/admin/settings", methods=["GET", "POST"])
@web_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    section = request.args.get("section", "general")
    
    if request.method == "POST":
        action_type = request.form.get("action_type")
        
        if action_type == "general":
            session["store_name"] = request.form.get("store_name", "SmartShelf Guardian").strip()
            session["contact_email"] = request.form.get("contact_email", "admin@smartshelfguardian.com").strip()
            session["phone"] = request.form.get("phone", "+1 (800) 555-0199").strip()
            session["address"] = request.form.get("address", "Enterprise HQ Warehouse 101, Tech Park").strip()
            session["currency"] = request.form.get("currency", "USD ($)").strip()
            session["timezone"] = request.form.get("timezone", "UTC").strip()
            
            date_format_val = request.form.get("date_format", DEFAULT_DATE_FORMAT).strip()
            if date_format_val in SUPPORTED_DATE_FORMATS:
                session["date_format"] = date_format_val
            else:
                session["date_format"] = DEFAULT_DATE_FORMAT

            flash("General Enterprise Settings updated successfully.", "success")
            
        elif action_type == "inventory_rules":
            session["default_min_stock"] = int(request.form.get("default_min_stock", 10))
            session["low_stock_threshold"] = int(request.form.get("low_stock_threshold", 15))
            session["critical_stock_threshold"] = int(request.form.get("critical_stock_threshold", 5))
            session["default_reorder_qty"] = int(request.form.get("default_reorder_qty", 50))
            session["expiry_monitoring"] = request.form.get("expiry_monitoring") == "on"
            session["overstock_monitoring"] = request.form.get("overstock_monitoring") == "on"
            session["unusual_movement_monitoring"] = request.form.get("unusual_movement_monitoring") == "on"
            flash("Inventory Telemetry Rules updated successfully.", "success")
            
        elif action_type == "notifications":
            session["notify_low_stock"] = request.form.get("notify_low_stock") == "on"
            session["notify_critical_risk"] = request.form.get("notify_critical_risk") == "on"
            session["notify_expiry"] = request.form.get("notify_expiry") == "on"
            session["notify_reorder"] = request.form.get("notify_reorder") == "on"
            session["notify_staff_activity"] = request.form.get("notify_staff_activity") == "on"
            session["daily_summary_pref"] = request.form.get("daily_summary_pref", "Dashboard Feed & Email")
            flash("Notification Preferences saved successfully.", "success")

        elif action_type == "change_password":
            current_pw = request.form.get("current_password", "").strip()
            new_pw = request.form.get("new_password", "").strip()
            confirm_pw = request.form.get("confirm_password", "").strip()
            
            if new_pw != confirm_pw:
                flash("New password and confirm password do not match.", "error")
            elif len(new_pw) < 6:
                flash("Password must be at least 6 characters long.", "error")
            else:
                user = session.get("user", {})
                res = auth_service.update_user_profile(user.get("_id"), {"password": new_pw})
                if res.get("success"):
                    flash("Admin Password updated successfully.", "success")
                else:
                    flash(res.get("message", "Failed to update password."), "error")

        elif action_type == "appearance":
            table_view = request.form.get("table_view", "comfortable")
            session["table_view"] = table_view
            flash("Appearance & Table Layout Preferences updated.", "success")

        elif action_type == "logout_all":
            flash("Logged out from all remote active sessions.", "success")

        return redirect(url_for("web.admin_settings", section=section))

    products = inventory_service.get_all_products()
    metrics = inventory_service.get_dashboard_metrics()
    staff_users = auth_service.list_staff_users()
    recent_transactions = inventory_service.get_recent_transactions(limit=10)
    db_health = inventory_service.db_conn.check_health() if hasattr(inventory_service, 'db_conn') else {"status": "Active (Local Store)"}

    return render_template(
        "settings.html",
        current_view="settings",
        page_title="Enterprise Settings Center",
        page_breadcrumb="Settings & System Admin",
        section=section,
        products=products,
        metrics=metrics,
        staff_users=staff_users,
        recent_transactions=recent_transactions,
        db_health=db_health
    )
