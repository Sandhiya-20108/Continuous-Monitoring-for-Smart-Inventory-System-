# SmartShelf Guardian: Continuous Monitoring & Predictive Inventory System

**SmartShelf Guardian** is an enterprise-grade inventory intelligence and telemetry monitoring platform. It continuously analyzes stock movement, predicts stockouts, detects imminent expiries, calculates transparent stock health scores, identifies unusual consumption anomalies, and enforces strict Role-Based Access Control (RBAC) across Admin and Customer portals.

---

## 1. User Roles & Permission Matrix

The application provides two distinct operational portals enforcing strict backend and frontend access controls.

| Feature / Portal Route | Admin Role (`admin`) | Staff Role (`staff`) | Customer Role (`customer`) |
| :--- | :---: | :---: | :---: |
| **Admin Portal** (`/dashboard`, `/inventory`, `/risk-monitor`, `/alerts`, `/analytics`, `/users`) | ✅ Full Access | ❌ Restricted (Auto-redirected) | ❌ Restricted (Auto-redirected) |
| **Staff Portal** (`/staff/dashboard`, `/staff/profile`) | 🔄 Redirects Admin | ✅ Primary Access | ✅ Access |
| **Add / Edit / Delete Products** (`/inventory/add`, `/inventory/edit/*`, `/inventory/delete/*`) | ✅ Full Access | ❌ Forbidden | ❌ Forbidden |
| **Stock In & Stock Out Operations** (`/inventory/stock/*`) | ✅ Full Access | ❌ Forbidden | ❌ Forbidden |
| **View Internal Telemetry & Costs** (Supplier, Unit Price Margin, Anomaly Scores) | ✅ Visible | ❌ Hidden | ❌ Hidden |
| **Export Inventory CSV Report** (`/export-report`) | ✅ Available | ❌ Forbidden | ❌ Forbidden |
| **Staff Account Administration** (`/users`, `/users/create`, `/users/delete/*`) | ✅ Full Access | ❌ Forbidden | ❌ Forbidden |
| **View Catalog & Stock Availability** (Product Name, SKU, Price, Status) | ✅ Visible | ✅ Visible | ✅ Visible |

### Default Credentials
- 👑 **Admin**: `admin@inventory.com` / `Admin@123456`
- 📦 **Staff**: `staff@inventory.com` / `Staff@123456`

---

## 2. System Architecture

```
                               ┌───────────────────────────┐
                               │     Client Web Browser    │
                               └─────────────┬─────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             [ Admin Portal ]                           [ Customer Portal ]
      (/dashboard, /inventory, etc.)             (/customer/dashboard, /profile)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │ (HTML / Pure Server-Side Forms)
                                             ▼
                               ┌───────────────────────────┐
                               │   Flask Server-Side Web   │
                               │  (backend/routes/web.py)  │
                               └─────────────┬─────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
            [ REST API Blueprint ]                       [ Auth & RBAC Service ]
             (backend/routes/api)                          (Auth & Security)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │     Inventory Service     │
                               │(backend/services/inventory)│
                               └─────────────┬─────────────┘
                                             │  ├── Risk Engine (Predictive Analytics)
                                             │  └── Transaction Audit Tracker
                                             ▼
                               ┌───────────────────────────┐
                               │     MongoDB Repository    │
                               │ (Dual-Mode Mongo/In-Mem)  │
                               └───────────────────────────┘
```

---

## 3. Key Operational Features

1. **Role-Based Access Control (RBAC)**:
   - Automated post-login redirection based on role (`admin` -> Admin Portal, `customer`/`staff` -> Customer Portal).
   - Direct URL access protection via `@admin_required` and `@customer_required` Flask decorators.
2. **Customer Catalog Portal**:
   - Clean, customer-facing interface showing available products, live availability status ("In Stock", "Low Stock", "Out of Stock"), unit pricing, search, category filters, and customer profile management.
3. **Stock In & Stock Out Operations**:
   - Explicit stock movement handling (`STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`) with audit log notes.
   - Validation against negative stock or stock-out exceeding current available units.
4. **Inventory Transaction Audit History**:
   - Every stock movement is logged with timestamp, operator name, quantity change (+/-), resulting stock level, and optional reason notes.
5. **Smart Risk & Telemetry Engine**:
   - **Predictive Stock Duration**: Estimated days to stockout (`Current Stock / Average Daily Usage`).
   - **Expiry Monitoring**: Proximity alerts ("Safe", "Approaching Expiry", "Critical Expiry", "Expired").
   - **Stock Health Score**: Transparent 0–100 rule-based score factoring depletion, expiry, and demand anomalies.
   - **Unusual Stock Movement**: High consumption surge (>2.5x) or zero-movement warnings flagged for Admin review.
6. **Export & Reporting**:
   - Download complete inventory telemetry as CSV (`/export-report`).

---

## 4. DevOps Setup & CI/CD Pipeline

### Docker Containerization
- **Dockerfile**: Containerizes the Flask application with Python 3.10-slim and automated healthcheck.
- **docker-compose.yml**: Orchestrates Flask web server (`web`) and MongoDB database container (`mongo`).

To launch with Docker Compose:
```bash
docker-compose up --build -d
```

### GitHub Actions CI
- Workflow file `.github/workflows/ci.yml` automatically triggers on push/PR to `main` or `master`.
- Executes automated `unittest` / `pytest` suite and verifies Docker container builds.

---

## 5. Clean Coding & Server-Side Rules

- **Zero JavaScript Requirement**: Built with 100% pure server-side Flask Jinja2 rendering, query-parameter views, and HTML forms. No script tags, `onclick` handlers, or JS modal logic.
- **Single Responsibility Principle**: Distinct separation between data models, repositories, business logic services, risk calculators, and route handlers.
- **Comprehensive Validation**: Input parameters sanitized and checked against invalid values or negative quantities.

---

## 6. Running tests & Local Server

### Run Automated Unit Test Suite
```bash
backend\venv\Scripts\python.exe -m unittest discover tests
```

### Run Server Locally
```bash
backend\venv\Scripts\python.exe backend/app.py
```
Application will be accessible on `http://localhost:5000`.
