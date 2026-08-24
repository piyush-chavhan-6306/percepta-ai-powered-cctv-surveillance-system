"""
Border Intelligence Main FastAPI Application.
Initializes lifespan lifecycle, database connections, event bus, API gateway, and REST/WebSocket routers.
"""
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from backend.api.alerts import router as alerts_router
from backend.api.cameras import DEFAULT_DEMO_CLIP, resolve_video_path, router as cameras_router
from backend.api.events import router as events_router
from backend.api.export import router as export_router
from backend.api.forensics import router as forensics_router
from backend.api.health import router as health_router
from backend.api.incidents import router as incidents_router
from backend.api.intelligence import router as intelligence_router
from backend.api.sensors import router as sensors_router
from backend.api.streaming import router as streaming_router
from backend.api.system import router as system_router
from backend.api.threat import router as threat_router
from backend.api.zones import router as zones_router
from backend.config import get_settings
from backend.database import close_db, init_db
from backend.events.schema import SourceType
from backend.gateway.auth import router as auth_router
from backend.gateway.middleware import GatewaySecurityMiddleware, log_gateway_startup_banner
from backend.gateway.rate_limit import limiter, rate_limit_exceeded_handler
from backend.ingestion.camera_manager import get_camera_manager
from backend.ingestion.video_adapter import VideoFileAdapter
from backend.tracking.live_worker import get_worker_registry

logger = logging.getLogger(__name__)

DEMO_CAMERA_ID = "CAM-01"


async def bootstrap_demo_camera() -> None:
    """
    Register and start the bundled demo clip on startup.

    Best-effort: a missing dataset must not stop the server from booting, since
    the operator can still add a webcam, an RTSP URL, or an upload from the UI.
    """
    manager = get_camera_manager()
    if manager.get_camera(DEMO_CAMERA_ID) is not None:
        return

    clip = resolve_video_path(DEFAULT_DEMO_CLIP)
    if clip is None:
        logger.warning(
            f"Demo clip '{DEFAULT_DEMO_CLIP}' not found; skipping demo camera bootstrap. "
            "Add a camera from the dashboard to begin."
        )
        return

    try:
        adapter = VideoFileAdapter(
            camera_id=DEMO_CAMERA_ID,
            video_path=clip,
            loop=True,  # loop so an unattended demo never runs dry
        )
        manager.register_camera(
            camera_id=DEMO_CAMERA_ID,
            adapter=adapter,
            name="Sector 7 — North Perimeter",
            location_label="Border Post Alpha",
            source_type=SourceType.VIDEO_FILE,
        )
        if await manager.start_camera(DEMO_CAMERA_ID):
            await get_worker_registry().start_worker(DEMO_CAMERA_ID)
            logger.info(f"Demo camera '{DEMO_CAMERA_ID}' live on {clip}")
        else:
            await manager.deregister_camera(DEMO_CAMERA_ID)
    except Exception as err:
        logger.warning(f"Demo camera bootstrap failed: {err}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown lifecycle."""
    settings = get_settings()
    settings.ensure_directories()

    # 1. Initialize SQLite Database with WAL mode
    await init_db()

    # 2. Log Gateway Status Banner
    log_gateway_startup_banner()

    # 3. Bring up the demo camera so the dashboard has live, real video on load
    #    rather than an empty grid the operator has to populate by hand.
    if settings.AUTOSTART_DEMO_CAMERA:
        await bootstrap_demo_camera()

    yield

    # 4. Stop perception workers before their sources, then close the database.
    await get_worker_registry().stop_all()
    manager = get_camera_manager()
    await manager.stop_all()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with Gateway Security."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="Persistent AI Intelligence Layer for Border Surveillance (SIH Prototype)",
        version=settings.API_VERSION,
        lifespan=lifespan,
    )

    # Attach Gateway Rate Limiter state and error handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Attach Gateway Security & Telemetry Middleware
    app.add_middleware(GatewaySecurityMiddleware)

    # CORS configuration for frontend dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Gateway Auth Router
    app.include_router(auth_router)

    # Register Domain Routers
    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(intelligence_router)
    app.include_router(threat_router)
    app.include_router(forensics_router)
    app.include_router(cameras_router)
    app.include_router(alerts_router)
    app.include_router(incidents_router)
    app.include_router(zones_router)
    app.include_router(export_router)
    app.include_router(sensors_router)
    app.include_router(system_router)
    app.include_router(streaming_router)

    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "status": "online",
            "docs_url": "/docs",
            "health_url": "/api/health",
            "auth_status": "demo_mode" if settings.DEMO_MODE else "strict_jwt",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
