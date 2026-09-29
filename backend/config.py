import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Back2You"
    PROJECT_DESCRIPTION: str = "AI-Powered Campus Lost & Found Intelligence Platform"
    API_PREFIX: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "back2you-super-secret-production-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Supabase Configuration (Optional for cloud, auto-falls back to local SQLite if empty)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "item-images")

    # Local SQLite DB and Upload directory
    SQLITE_DB_PATH: str = str(BASE_DIR / "back2you.db")
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")

    # CORS / Deployment origins
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")

    # Matching Weights (Configurable)
    WEIGHT_IMAGE: float = 0.40
    WEIGHT_TEXT: float = 0.30
    WEIGHT_LOCATION: float = 0.15
    WEIGHT_TIME: float = 0.10
    WEIGHT_ATTRIBUTES: float = 0.05

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

