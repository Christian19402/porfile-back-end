# routes/__init__.py
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()  # ✅ JWT manager

def create_app():
    app = Flask(__name__)

    # 1) .env
    load_dotenv()

    # 2) Config básica
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-secret")
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///app.db")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ✅ Clave para JWT (puede ser la misma que SECRET_KEY o una distinta)
    app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", app.config['SECRET_KEY'])

    # (Opcional) otras configs útiles
    app.config['JSON_SORT_KEYS'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))  # 50MB

    # carpeta de subidas
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config['UPLOADS_DIR'] = os.getenv("UPLOADS_DIR", os.path.join(BASE_DIR, "uploads"))

    # 3) Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)  # ✅ inicializar JWT

    # 4) CORS (frontend en localhost:3000). Añadimos /uploads por si lo necesitas.
    CORS(
        app,
        resources={
            r"/api/*": {"origins": "*"},
            r"/uploads/*": {"origins": "*"},  # opcional
        },
        supports_credentials=True,
    )

    # 5) Importa modelos para que Migrate los detecte
    from models import User, Category, ProjectImage, ProjectVideo, Message, CV, SocialLink
    try:
        from models import SocialLink  # si existe
    except Exception:
        pass

    # 6) Blueprints
    from routes.auth import auth_bp
    from routes.categories import categories_bp
    try:
        from routes.messages import messages_bp
    except Exception:
        messages_bp = None
    try:
        from routes.cv import cv_bp
    except Exception:
        cv_bp = None
    try:
        from routes.socials import socials_bp
    except Exception:
        socials_bp = None

    app.register_blueprint(auth_bp,       url_prefix="/api/auth")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    if messages_bp:
        app.register_blueprint(messages_bp,  url_prefix="/api/messages")
    if cv_bp:
        app.register_blueprint(cv_bp,        url_prefix="/api/cv")
    if socials_bp:
        app.register_blueprint(socials_bp,   url_prefix="/api/socials")  # ✅

    # 7) Servir /uploads/... a nivel app (coincide con rutas absolutas del frontend)
    @app.route("/uploads/<path:filename>")
    def serve_uploads(filename):
        uploads_dir = app.config.get("UPLOADS_DIR")
        return send_from_directory(uploads_dir, filename)

    return app
