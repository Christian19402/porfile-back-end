# backend/config.py
import os
from pathlib import Path

# Carga .env automáticamente
try:
    from dotenv import load_dotenv  
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)  
except Exception:
    pass

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # --- Base de datos ---
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'database.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Seguridad ---
    SECRET_KEY = os.getenv("SECRET_KEY", "valor_por_defecto")
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "valor_por_defecto")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hora

    # --- Uploads ---
    UPLOADS_DIR = os.path.join(basedir, "uploads")
    IMAGES_DIR  = os.path.join(UPLOADS_DIR, "projects", "images")
    VIDEOS_DIR  = os.path.join(UPLOADS_DIR, "projects", "videos")
    CV_DIR      = os.path.join(UPLOADS_DIR, "cvs")

    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(CV_DIR, exist_ok=True)

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # --- Email (desde .env) ---
    MAIL_SERVER   = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT     = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS  = str(os.getenv("MAIL_USE_TLS", "True")).lower() in ("1","true","yes","y")
    MAIL_USE_SSL  = str(os.getenv("MAIL_USE_SSL", "False")).lower() in ("1","true","yes","y")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    CONTACT_DEST_EMAIL = os.getenv("CONTACT_DEST_EMAIL")
    MAIL_TIMEOUT = float(os.getenv("MAIL_TIMEOUT", "15"))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', Config.SQLALCHEMY_DATABASE_URI)
