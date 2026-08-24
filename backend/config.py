"""
Border Intelligence Configuration Module.
Loads environment variables using Pydantic Settings.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Border Intelligence"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_VERSION: str = "0.1.0"
    # Explicit dev origins: the Vite dev server needs credentialed CORS, and
    # "*" is rejected by browsers when allow_credentials is on.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    # Gateway & Authentication (Phase 1)
    JWT_SECRET_KEY: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 480
    DEMO_MODE: bool = True  # True bypasses strict token checks for judge/demo walkthroughs
    RATE_LIMIT_PER_MINUTE: int = 120

    # Hardware & Model Performance Configuration
    DEVICE: str = "auto"  # "auto", "cpu", "cuda"
    DEFAULT_INFERENCE_SIZE: int = 640
    CONFIDENCE_THRESHOLD: float = 0.25
    IOU_THRESHOLD: float = 0.45
    TARGET_FPS: float = 25.0
    MIN_FRAME_STRIDE: int = 1
    # Headroom for CPU-only hosts. YOLOv8n costs ~40-70 ms per frame here, so a
    # ceiling of 3 cannot reach TARGET_FPS and the controller saturates while
    # still missing the target. Skipped frames are not dropped from the display:
    # each one is Kalman-predicted and annotated, so the operator still sees a
    # box on every frame -- stride trades detection frequency, not smoothness.
    MAX_FRAME_STRIDE: int = 5
    DEFAULT_FRAME_STRIDE: int = 2
    ADAPTIVE_STRIDE_ENABLED: bool = True
    PERFORMANCE_SAMPLE_WINDOW: int = 15
    STRIDE_COOLDOWN_FRAMES: int = 30

    # Live perception
    # Register + start the bundled demo clip on boot so the dashboard opens on
    # real video instead of an empty grid.
    AUTOSTART_DEMO_CAMERA: bool = True
    MJPEG_JPEG_QUALITY: int = 78
    MAX_MJPEG_CLIENTS: int = 12

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./border_intelligence.db"

    # Storage paths
    STORAGE_DIR: str = "./storage"
    EVIDENCE_DIR: str = "./storage/evidence"
    SNAPSHOTS_DIR: str = "./storage/snapshots"
    DATASETS_DIR: str = "./datasets"
    CONFIGS_DIR: str = "./configs"
    MODELS_DIR: str = "./models"
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


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
