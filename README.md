# SmartShelf Guardian: Continuous Monitoring & Predictive Inventory System

A production-grade, server-side web application designed for real-time inventory telemetry monitoring, predictive risk estimation, stock control, and role-based workspace management.

---

## 📌 Project Overview

**SmartShelf Guardian** provides continuous stock telemetry tracking, risk evaluation, automated stockout forecasting, and strict role-based separation between administrative management and staff workspace interfaces.

### Problem Statement
Traditional inventory management applications suffer from static data entry, lack of proactive stockout indicators, uniform access layouts that expose high-level managerial actions to routine operational staff, and security risks stemming from client-side role enforcement.

### Main Objectives
1. **Continuous Telemetry Tracking**: Real-time simulation and tracking of stock consumption rates and expiry dates.
2. **Predictive Risk Engine**: Dynamic calculation of stockout probability, expiry risk, and overall health scores using rule-based telemetry metrics.
3. **Role-Based Access Control (RBAC)**: Complete server-side separation between **Admin Portal** and **Staff Portal**.
4. **Zero-JavaScript Architecture**: Server-side rendering using Python 3, Flask, Jinja2, HTML5 forms, and CSS for security and accessibility.

---

## 🌟 Key Features

### 👑 Admin Portal
- **Executive Overview**: High-level dashboard with total products, total stock quantity, health scores, and critical risk alerts.
- **Inventory Telemetry Monitor**: Complete product management (Add, Edit, Delete, Stock In, Stock Out, Stock Adjustments).
- **Transaction History**: Audit logs capturing user ID, operation type, quantity change, notes, and UTC timestamps.
- **What-If Demand Simulator**: Interactive scenario testing for demand surges (e.g., +50%, +100%).
- **Predictive Risk Intelligence**: Risk level categorization (*Safe*, *Moderate*, *High*, *Critical*) and automated reorder recommendations.
- **Alert Center & Analytics**: Filterable alert feed and consumption rate reporting.
- **User Administration**: Staff account creation, management, and revocation.
- **CSV Data Export**: One-click telemetry report generation.

### 📦 Staff Portal
- **Staff Workspace**: Simplified, non-admin interface focused on product browsing and inventory lookups.
- **Product Catalog Grid**: Responsive card layout displaying product status (*In Stock*, *Low Stock*, *Out of Stock*).
- **Search & Category Filters**: Multi-category lookup (*Healthcare*, *Electronics*, *Industrial*, *Safety & Hazmat*, *Office & IT*).
- **Product Details Drawer**: Item specifications, SKU code, unit price, and stock availability.
- **Staff Account Profile**: Self-service profile updates (Full Name and Password management).

---

## 🔒 Role-Based Access Control (RBAC)

| User Role | Permitted Routes | Admin Route Access Behavior |
|-----------|------------------|------------------------------|
| **Admin** | `/dashboard`, `/inventory`, `/risk-monitor`, `/alerts`, `/analytics`, `/users`, `/export-report` | Full Access |
| **Staff** | `/staff/dashboard`, `/staff/profile` | Auto-redirects to `/staff/dashboard` with a professional flash message. No 403 page displayed. |
| **Customer** | `/staff/dashboard` | Redirects to permitted workspace. |

---

## 🛠 Technology Stack

- **Backend**: Python 3.10+, Flask 3.1
- **Template Engine**: Jinja2 (HTML5)
- **Styling**: Vanilla CSS3 (Custom Design System with Dark/Light Theme Support)
- **Database**: MongoDB Atlas / PyMongo
- **Authentication**: Flask Session, `werkzeug.security` (PBKDF2:SHA256 password hashing)
- **Testing**: `unittest`, `pytest`
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions

---

## 🏗 System Architecture & Database Structure

### Database Collections
1. **`products`**:
   - `sku`, `name`, `category`, `current_stock`, `min_stock`, `unit_price`, `average_daily_usage`, `expiry_date`, `last_updated`.
2. **`users`**:
   - `email`, `username`, `password_hash`, `role` (`admin`, `staff`), `full_name`, `created_at`.
3. **`transactions`**:
   - `product_id`, `sku`, `operation` (`STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`), `quantity`, `user`, `timestamp`, `notes`.

---

## 🚀 Local Setup Instructions

### Prerequisites
- Python 3.10 or higher
- Git

### Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Sandhiya-20108/Continuous-Monitoring-for-Smart-Inventory-System-.git
   cd Continuous-Monitoring-for-Smart-Inventory-System-
   ```

2. **Set Up Virtual Environment**:
   ```bash
   python -m venv backend/venv
   # Windows:
   backend\venv\Scripts\activate
   # Linux/macOS:
   source backend/venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   *Note: `.env` is ignored by Git and should contain your local configuration or MongoDB Atlas URI.*

5. **Run the Flask Application**:
   ```bash
   python backend/app.py
   ```
   Access the portal in your browser at `http://localhost:5000`.

---

## 🧪 Running Automated Tests

Run the test suite using `unittest`:
```bash
python -m unittest discover tests
```

Or using `pytest`:
```bash
pytest tests/
```

---

## 🐳 Docker Deployment

### Using Docker Compose
```bash
docker-compose up --build
```

### Using Docker CLI
```bash
docker build -t smart-inventory .
docker run -p 5000:5000 --env-file .env smart-inventory
```

---

## 🔑 Quick Demo Access

For demonstration purposes, pre-seeded accounts are provided on the login page:
- **Admin Demo Portal**: Use the **Admin Demo** button on `/login` to access `/dashboard`.
- **Staff Demo Portal**: Use the **Staff Demo** button on `/login` to access `/staff/dashboard`.

---

## ⚠️ Known Limitations & Disclaimers

- **Predictive Metrics**: Risk scores, days-to-stockout calculations, and health metrics are rule-based telemetry estimates based on consumption usage algorithms rather than trained machine learning models.
- **Zero JavaScript Constraint**: All interactions rely on Flask route handling, HTTP POST forms, redirects, and Jinja template logic to adhere to strict server-side rendering guidelines.
