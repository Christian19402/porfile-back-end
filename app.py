# app.py
import os
import logging
from flask import Flask, send_from_directory, current_app
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

from extensions import db
from config import Config

# Blueprints
from routes.categories import categories_bp
from routes.cv import cv_bp
from routes.messages import messages_bp
from routes.auth import auth_bp
from routes.socials import socials_bp
from routes.contact import contact_bp

# Modelos
from models import User, Category, Message, CV, ProjectImage, ProjectVideo

logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)

# === CORS ===
    # Acepta cualquier subdominio de Vercel (previews/prod) y localhost
    default_allowed_origins = {
        "https://portfolio-carlos-martin.vercel.app",
        "https://portfolio-carlosmartin.vercel.app",  # Por si el dominio cambia sin guion
        "http://localhost:3000",
    }
    
    extra_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if extra_origins:
        default_allowed_origins.update(
            origin.strip()
            for origin in extra_origins.split(",")
            if origin.strip()
        )

    allowed_origins = sorted(default_allowed_origins)

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": allowed_origins,
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Requested-With",
                ],
            },
            r"/uploads/*": {
                "origins": allowed_origins,
                "methods": ["GET", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Requested-With",
                ],
            },
        },
        supports_credentials=True,
        expose_headers=["Content-Type"],
        always_send=True,
    )

    # === Blueprints ===
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(cv_bp, url_prefix="/api/cv")
    app.register_blueprint(messages_bp, url_prefix="/api/messages")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(socials_bp, url_prefix="/api/socials")
    app.register_blueprint(contact_bp, url_prefix="/api/contact")

    # Servir subidas
    @app.route("/uploads/<path:filename>")
    def serve_uploads(filename):
        return send_from_directory(current_app.config["UPLOADS_DIR"], filename)

    @app.get("/api/ping")
    def ping():
        return {"pong": True}, 200

    @app.get("/")
    def index():
        return {"message": "Backend portfolio listo"}, 200

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Recurso no encontrado"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {"error": "Error interno del servidor"}, 500

    if not app.debug:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler("error.log", maxBytes=10000, backupCount=3)
        handler.setLevel(logging.ERROR)
        app.logger.addHandler(handler)

    @app.shell_context_processor
    def make_shell_context():
        return {
            "app": app,
            "db": db,
            "User": User,
            "Category": Category,
            "Message": Message,
            "CV": CV,
            "ProjectImage": ProjectImage,
            "ProjectVideo": ProjectVideo,
        }

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
