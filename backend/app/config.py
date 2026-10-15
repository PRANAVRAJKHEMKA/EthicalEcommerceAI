import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent

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
    
    # Database
    DATABASE_PATH: str = str(BASE_DIR / "faircart.db")
    
    # External Services
    GEMINI_API_KEY: str | None = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
