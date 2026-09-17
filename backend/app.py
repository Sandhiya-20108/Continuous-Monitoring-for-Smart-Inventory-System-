import os
import sys

# Ensure root workspace directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_cors import CORS
from backend.config import Config
from backend.routes.inventory import inventory_bp
from backend.routes.auth import auth_bp
from backend.routes.web_routes import web_bp
from backend.utils.theme_helpers import get_current_theme, get_theme_styles, get_theme_class

def create_app():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(backend_dir, "templates"),
        static_folder=os.path.join(backend_dir, "static")
    )
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # Enable CORS for frontend clients if needed
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register Python Theme Context Processor for templates
    @app.context_processor
    def inject_theme_helpers():
        return {
            "current_theme": get_current_theme(),
            "theme_config": get_theme_styles(),
            "get_theme_class": get_theme_class
        }

    # Register blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(auth_bp)

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting Smart Inventory System Server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)

