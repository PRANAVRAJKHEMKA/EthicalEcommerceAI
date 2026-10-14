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
    
    # Database
    DATABASE_PATH: str = str(BASE_DIR / "faircart.db")
    
    # External Services
    GEMINI_API_KEY: str | None = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
