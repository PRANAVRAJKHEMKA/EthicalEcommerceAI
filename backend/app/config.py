import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings

# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _is_running_tests() -> bool:
    """Detects if execution is under automated test frameworks (unittest, pytest)."""
    if os.environ.get("FAIRCART_TESTING") == "1":
        return True
    if any(m in sys.modules for m in ("pytest",)):
        return True
    main_mod = sys.modules.get("__main__")
    if main_mod:
        main_file = getattr(main_mod, "__file__", "") or ""
        main_name = getattr(main_mod, "__name__", "") or ""
        if "unittest" in main_file or "unittest" in main_name:
            return True
    if any(
        "unittest" in str(arg).lower()
        or "pytest" in str(arg).lower()
        or "discover" in str(arg).lower()
        for arg in sys.argv
    ):
        return True
    return False


# Deterministic test isolation safeguard:
# When executing under automated tests, suppress ambient DATABASE_URL from .env
# to isolate tests to local SQLite fixtures, unless FAIRCART_LIVE_DB_TEST=1 is set.
if _is_running_tests() and not os.environ.get("FAIRCART_LIVE_DB_TEST"):
    os.environ["DATABASE_URL"] = ""


class Settings(BaseSettings):
    APP_NAME: str = "FairCart AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    
    # Runtime & Environment
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
    ADMIN_TOKEN: str | None = None
    SECRET_KEY: str | None = None
    CONNECTOR_VAULT_KEY: str | None = None
    
    # Database
    DATABASE_PATH: str = str(BASE_DIR / "faircart.db")
    DATABASE_URL: str | None = None
    
    # External Services
    GEMINI_API_KEY: str | None = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

if _is_running_tests() and not os.environ.get("FAIRCART_LIVE_DB_TEST"):
    settings.DATABASE_URL = None
    os.environ["DATABASE_URL"] = ""
