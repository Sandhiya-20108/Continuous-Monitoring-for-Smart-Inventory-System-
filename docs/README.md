# Continuous Monitoring for Smart Inventory System
## Inventory Risk Intelligence & Continuous Monitoring System (Phase 2 - MongoDB Atlas Integration)

The **Inventory Risk Intelligence & Continuous Monitoring System** is an advanced operational platform designed to analyze inventory telemetry continuously and identify stockout, expiry, and consumption risks before they impact business operations.

In **Phase 2**, the backend is integrated with **MongoDB Atlas / PyMongo** for persistent document storage, automated unique indexing, safe data seeding, and real-time telemetry updates, while preserving 100% API schema compatibility and UI responsiveness.

---

## 1. System Architecture

```
[ Frontend Dashboard ] (HTML5 / CSS3 / Vanilla JS)
        │
        ▼ (REST API / JSON)
[ Flask REST API ] (backend/app.py & backend/routes/inventory.py)
        │
        ▼
[ Inventory Service ] (backend/services/inventory_service.py)
        │  ├── Risk Intelligence Engine (backend/utils/risk_engine.py)
        │  └── Dual-Mode Fallback (JSON store if offline)
        ▼
[ MongoDB Repository ] (backend/repositories/inventory_repository.py)
        │
        ▼ (PyMongo Driver)
[ MongoDB Atlas Database ] (smart_inventory.products)
```

---

## 2. Environment Variables Configuration

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

Set your MongoDB Atlas connection details inside `.env`:

```env
# Server Settings
PORT=5000
FLASK_DEBUG=True
SECRET_KEY=smart-inventory-risk-secret-key-2026

# MongoDB Atlas Settings
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.example.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=smart_inventory
MONGODB_COLLECTION=products
MONGODB_TIMEOUT_MS=3000
```

> [!IMPORTANT]
> Never commit `.env` to version control. The `.env` file is listed in `.gitignore`.

---

## 3. MongoDB Atlas Setup & Seeding

### Step 1: Create a Cluster on MongoDB Atlas
1. Create a free cluster on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create a Database User under **Database Access**.
3. Add your IP address under **Network Access** (or `0.0.0.0/0` for development access).
4. Get your connection string (`mongodb+srv://...`) under **Database -> Connect -> Drivers**.

### Step 2: Configure Local `.env`
Paste your connection string into `MONGODB_URI` in `.env`.

### Step 3: Automated Indexing & Seeding
When the Flask backend starts:
- It automatically verifies connection to MongoDB Atlas.
- It creates a **unique index** on `sku` and an index on `category`.
- If the target collection is empty, it automatically seeds all 12 sample inventory items.
- Duplicate insertion is prevented using SKU unique constraints.

---

## 4. REST API Specification & Health Verification

### Check Server & Database Health: `GET /api/health`

**Sample Response (MongoDB Connected):**
```json
{
  "status": "online",
  "service": "Inventory Risk Intelligence API",
  "version": "2.0.0-phase2-mongodb",
  "mongodb": {
    "status": "connected",
    "database": "smart_inventory",
    "collection": "products",
    "details": "MongoDB Atlas connection active and responsive."
  }
}
```

### Complete Endpoints List

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check reporting API and MongoDB Atlas status |
| `GET` | `/api/products` | Query inventory items with calculated risk scores (`?category=&risk_level=&search=`) |
| `GET` | `/api/products/<id>` | Detailed view for a single product |
| `GET` | `/api/metrics` | System KPI metrics & Overall Inventory Health Score |
| `GET` | `/api/assistant` | Smart Inventory Assistant summary & priorities |
| `GET` | `/api/alerts` | Active risk alerts (`?severity=`) |
| `POST` | `/api/simulate-tick` | Triggers live stock consumption tick & persists to MongoDB |
| `POST` | `/api/simulate-what-if` | Computes what-if demand variance scenario |

---

## 5. Running the Application & Unit Tests

### A. Run Unit Test Suite
```bash
backend\venv\Scripts\python.exe -m unittest discover -s tests
```

### B. Run Backend API Server
```bash
backend\venv\Scripts\python.exe backend/app.py
```

### C. Open Frontend Dashboard
Open `frontend/index.html` in your web browser.
