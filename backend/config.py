import os
from datetime import date
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env if present
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.dirname(os.path.abspath(__file__))

env_file = find_dotenv(usecwd=True)
if not env_file:
    for candidate in [os.path.join(base_dir, ".env"), os.path.join(backend_dir, ".env")]:
        if os.path.exists(candidate):
            env_file = candidate
            break

if env_file:
    load_dotenv(env_file, override=True)
else:
    load_dotenv(override=True)

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "smart-inventory-risk-secret-key-2026")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    PORT = int(os.getenv("PORT", 5000))
    
    # MongoDB Configuration
    MONGODB_URI = (os.getenv("MONGODB_URI") or "").strip()
    MONGODB_DATABASE = (os.getenv("MONGODB_DATABASE") or "smart_inventory").strip()
    MONGODB_COLLECTION = (os.getenv("MONGODB_COLLECTION") or "products").strip()
    MONGODB_USERS_COLLECTION = (os.getenv("MONGODB_USERS_COLLECTION") or "users").strip()
    MONGODB_TIMEOUT_MS = int(os.getenv("MONGODB_TIMEOUT_MS", 3000))

    # Reference date for static date comparison (matching current environment context)
    CURRENT_SIMULATION_DATE = date(2026, 8, 25)
    
    # Risk Score Weights & Coefficients
    WEIGHT_STOCK_DEPLETION = 35.0  # Max score for stock deficit vs min_stock
    WEIGHT_STOCKOUT_PROXIMITY = 25.0  # Max score for days to stockout
    WEIGHT_EXPIRY_PROXIMITY = 20.0  # Max score for imminent expiry
    WEIGHT_ANOMALY = 20.0  # Max score for consumption surge or unusual pattern
    
    # Risk Tiers
    RISK_LEVEL_SAFE = "Safe"           # 0 - 30
    RISK_LEVEL_WARNING = "Warning"     # 31 - 60
    RISK_LEVEL_HIGH = "High Risk"      # 61 - 80
    RISK_LEVEL_CRITICAL = "Critical"   # 81 - 100
    
    # Anomaly Threshold Multipliers
    SURGE_ANOMALY_MULTIPLIER = 2.5     # Consumption > 2.5x average is an anomaly
    ZERO_MOVEMENT_BASELINE_MIN = 10.0  # If avg >= 10 and movement == 0, mark unusual drop
