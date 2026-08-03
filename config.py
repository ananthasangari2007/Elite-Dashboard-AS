import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()


def normalize_database_url(url):
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url


def is_production_environment():
    env = (os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development").lower()
    return env in {"production", "prod", "staging"}


class Config:
    is_production = is_production_environment()

    if os.getenv("SECRET_KEY"):
        SECRET_KEY = os.getenv("SECRET_KEY")
    elif is_production:
        raise RuntimeError("SECRET_KEY must be set in production")
    else:
        SECRET_KEY = "dev-secret-change-me"

    _db_url = normalize_database_url(os.getenv("DATABASE_URL"))
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    elif is_production:
        raise RuntimeError("DATABASE_URL must be set to a PostgreSQL URL in production")
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'elite_dashboard.sqlite3'}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {
            "sslmode": "require",
        },
    }

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
