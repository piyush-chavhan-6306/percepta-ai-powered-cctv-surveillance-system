"""
Border Intelligence Main FastAPI Application.
Initializes lifespan lifecycle, database connections, event bus, API gateway, and REST/WebSocket routers.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from backend.api.alerts import router as alerts_router
from backend.api.cameras import router as cameras_router
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
from backend.gateway.auth import router as auth_router
from backend.gateway.middleware import GatewaySecurityMiddleware, log_gateway_startup_banner
from backend.gateway.rate_limit import limiter, rate_limit_exceeded_handler
from backend.ingestion.camera_manager import get_camera_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown lifecycle."""
    settings = get_settings()
    settings.ensure_directories()

    # 1. Initialize SQLite Database with WAL mode
    await init_db()

    # 2. Log Gateway Status Banner
    log_gateway_startup_banner()

    yield

    # 3. Cleanup and close database connections and camera streams
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
