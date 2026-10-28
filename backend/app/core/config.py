"""
Centralized application configuration.
Everything is read from environment variables (.env). Nothing is hard-coded.
"""
from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.exists() else None,
        extra="ignore",
    )

    APP_NAME: str = "AI Fashion Search"

    DATABASE_URL: str = "sqlite:///./fashion.db"

    JWT_SECRET: str = "dev_secret_change_me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 8

    # Comma-separated list of directories to search for catalog images (high-res candidates first, then thumbnails)
    DATASET_IMAGES_DIR: str = "./data/fashion-dataset/images,./data/images"

    AI_MODE: str = "model"  # "demo" | "model"
    MODEL_PATH: str = "./models/vit_fashion_classifier/vit_fashion_classifier.pt"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:3000,http://127.0.0.1:3000,https://ai-image-pi-nine.vercel.app"

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 30
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_GLOBAL_PER_MINUTE: int = 120

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def resolve_database_url(cls, v: str) -> str:
        if not v or not v.startswith("sqlite:///"):
            return v

        raw_path = v[len("sqlite:///"):]
        if not raw_path or raw_path == ":memory:" or raw_path.startswith("?"):
            return v

        path_obj = Path(raw_path)
        if path_obj.is_absolute():
            return v

        resolved_db = (BACKEND_DIR / path_obj).resolve()
        if not resolved_db.exists():
            raise FileNotFoundError(
                f"Configured SQLite database not found at resolved path: {resolved_db}"
            )

        db_posix = resolved_db.as_posix()
        if not db_posix.startswith("/"):
            return f"sqlite:///{db_posix}"
        return f"sqlite:////{db_posix.lstrip('/')}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def dataset_image_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        for p in self.DATASET_IMAGES_DIR.split(","):
            clean = p.strip()
            if clean:
                base = Path(clean)
                dirs.append(base)
                # Also check common nested subdirectories if base exists
                if (base / "images").exists():
                    dirs.append(base / "images")
                if (base / "fashion-dataset" / "images").exists():
                    dirs.append(base / "fashion-dataset" / "images")
        return dirs


@lru_cache
def get_settings() -> Settings:
    return Settings()
