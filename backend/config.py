"""
Border Intelligence Configuration Module.
Loads environment variables using Pydantic Settings.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "PERCEPTA"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_VERSION: str = "0.1.0"
    # Runtime deployment mode: "edge" (local CV execution) or "cloud" (lightweight C2 / Vercel cloud runtime)
    DEPLOYMENT_MODE: str = "edge"
    # Explicit dev and cloud origins: the Vite dev server needs credentialed CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
    ]

    # Gateway & Authentication (Phase 1)
    JWT_SECRET_KEY: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 480
    DEMO_MODE: bool = True  # True bypasses strict token checks for judge/demo walkthroughs
    RATE_LIMIT_PER_MINUTE: int = 120

    # Hardware & Model Performance Configuration
    DEVICE: str = "auto"  # "auto", "cpu", "cuda"
    DEFAULT_INFERENCE_SIZE: int = 416
    CONFIDENCE_THRESHOLD: float = 0.15
    IOU_THRESHOLD: float = 0.45
    TORCH_NUM_THREADS: int = 4
    TARGET_FPS: float = 25.0
    MIN_FRAME_STRIDE: int = 1
    MAX_FRAME_STRIDE: int = 3
    DEFAULT_FRAME_STRIDE: int = 2
    ADAPTIVE_STRIDE_ENABLED: bool = True
    PERFORMANCE_SAMPLE_WINDOW: int = 15
    STRIDE_COOLDOWN_FRAMES: int = 30

    # Live perception
    AUTOSTART_DEMO_CAMERA: bool = True
    AUTO_CREATE_DEMO_ZONES: bool = False
    MJPEG_JPEG_QUALITY: int = 40
    MAX_MJPEG_CLIENTS: int = 16

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./percepta.db"

    # Storage paths
    STORAGE_DIR: str = "./storage"
    EVIDENCE_DIR: str = "./storage/evidence"
    SNAPSHOTS_DIR: str = "./storage/snapshots"
    DATASETS_DIR: str = "./dataset"
    CONFIGS_DIR: str = "./configs"
    MODELS_DIR: str = "./models"
    RUNTIME_DIR: str = "./runtime"
    YOLO_MODEL_NAME: str = "yolov8n.pt"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        Path(self.STORAGE_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.EVIDENCE_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DATASETS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.CONFIGS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.MODELS_DIR).mkdir(parents=True, exist_ok=True)
        # Runtime directories for generated artifacts
        runtime = Path(self.RUNTIME_DIR)
        for sub in ("evidence", "clips", "snapshots", "exports", "logs", "cache"):
            (runtime / sub).mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
