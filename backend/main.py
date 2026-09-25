"""
Border Intelligence Main FastAPI Application.
Initializes lifespan lifecycle, database connections, event bus, API gateway, and REST/WebSocket routers.
"""
import sys
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

import cv2
try:
    cv2.ocl.setUseOpenCL(False)
except Exception:
    pass

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from backend.api.alerts import router as alerts_router
from backend.api.cameras import DEFAULT_DEMO_CLIP, resolve_video_path, router as cameras_router
from backend.api.entities import router as entities_router
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
from backend.api.topology import router as topology_router
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


async def bootstrap_demo_camera(autostart: bool = False) -> None:
    """
    Register default surveillance cameras in inventory in standby state.
    Perception starts only when the operator explicitly starts analysis.
    """
    manager = get_camera_manager()
    clip = resolve_video_path(DEFAULT_DEMO_CLIP)
    if clip is None:
        logger.warning(
            f"Demo clip '{DEFAULT_DEMO_CLIP}' not found; skipping demo camera bootstrap. "
            "Add a camera from the dashboard to begin."
        )
        return

    configs = [
        ("CAM-01", "Border Post Alpha (Optical CCTV)", "Sector 7 Perimeter", "STANDARD"),
    ]

    for cid, name, loc, mod in configs:
        if manager.get_camera(cid) is not None:
            continue
        try:
            adapter = VideoFileAdapter(
                camera_id=cid,
                video_path=clip,
                loop=True,
                modality=mod,
            )
            manager.register_camera(
                camera_id=cid,
                adapter=adapter,
                name=name,
                location_label=loc,
                modality=mod,
                source_type=SourceType.VIDEO_FILE,
            )
            if autostart:
                if await manager.start_camera(cid):
                    await get_worker_registry().start_worker(cid)
                    logger.info(f"Multi-Modal Camera '{cid}' [{mod}] live on {clip}")
                else:
                    await manager.deregister_camera(cid)
            else:
                logger.info(f"Registered camera '{cid}' in STANDBY mode (ready for operator activation).")
        except Exception as err:
            logger.warning(f"Camera bootstrap failed for {cid}: {err}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown lifecycle."""
    settings = get_settings()
    settings.ensure_directories()

    # 1. Initialize Database with dialect-aware async engine
    await init_db()

    # 1b. Verify Model Manifest and offline surveillance bundle readiness
    from backend.core.model_manager import report_model_readiness
    report_model_readiness()

    # 2. Log Gateway Status Banner
    log_gateway_startup_banner()

    # 2b. Ensure EventBus to WebSocket broadcast is pre-subscribed
    try:
        from backend.api.streaming import ws_manager
        from backend.events.bus import get_event_bus
        bus = get_event_bus()
        if not ws_manager._subscribed:
            await bus.subscribe(ws_manager._broadcast_event)
            ws_manager._subscribed = True
    except Exception as ws_sub_err:
        logger.warning(f"Failed to pre-subscribe ws_manager: {ws_sub_err}")

    # 2b-ii. Subscribe EvidenceBridge: ALERT events → Incident + Evidence DB records
    try:
        from backend.events.evidence_bridge import get_evidence_bridge
        bridge = get_evidence_bridge()
        await bridge.subscribe()
    except Exception as eb_err:
        logger.warning(f"Failed to subscribe EvidenceBridge: {eb_err}")

    # 2c. Ensure default tactical security perimeter zones exist if none defined
    try:
        from backend.zones.security_zone import get_zone_monitor, SecurityZone, VirtualBoundary, ZoneSeverity
        zone_mon = get_zone_monitor()
        # Preserve old demo definitions on disk but never activate them in an
        # operator session. Operators explicitly create the rules they need.
        for demo_id in ("BORDER_RESTRICTED_STRIP_01", "VIRTUAL_PERIMETER_FENCE_01"):
            demo_rule = zone_mon.zones.get(demo_id) or zone_mon.boundaries.get(demo_id)
            if demo_rule is not None:
                demo_rule.is_active = False
        if settings.AUTO_CREATE_DEMO_ZONES and len(zone_mon.zones) == 0 and len(zone_mon.boundaries) == 0:
            zone_mon.add_zone(
                SecurityZone(
                    zone_id="SECTOR_NORTH_PERIMETER_01",
                    name="North Fence Restricted Perimeter",
                    polygon=[[150.0, 180.0], [1400.0, 180.0], [1400.0, 750.0], [150.0, 750.0]],
                    severity=ZoneSeverity.RESTRICTED,
                    loitering_threshold_seconds=3.5,
                    loitering_debounce_seconds=15.0,
                )
            )
            zone_mon.add_boundary(
                VirtualBoundary(
                    boundary_id="PERIMETER_GATE_TRIPWIRE_01",
                    name="Perimeter Access Gate Tripwire",
                    pt1=(180.0, 480.0),
                    pt2=(1350.0, 480.0),
                    severity=ZoneSeverity.CRITICAL,
                    direction="BIDIRECTIONAL",
                    debounce_seconds=5.0,
                )
            )
            logger.info("Initialized default tactical perimeter zones and tripwire.")
    except Exception as zm_err:
        logger.warning(f"Failed to initialize default zones: {zm_err}")

    # 2d. Start Offline-First Durable Synchronization Worker
    try:
        from backend.database.sync_worker import get_sync_worker
        await get_sync_worker().start()
    except Exception as sw_err:
        logger.warning(f"Failed to start sync worker: {sw_err}")

    # 3. Register default camera in inventory (standby by default)
    await bootstrap_demo_camera(autostart=settings.AUTOSTART_DEMO_CAMERA)

    yield

    # 4. Stop sync worker and perception workers, then close the database.
    try:
        from backend.database.sync_worker import get_sync_worker
        await get_sync_worker().stop()
    except Exception:
        pass
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

    # CORS — allow Vercel and ngrok tunnel origins dynamically
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=r"(https://.*\.vercel\.app|https://.*\.ngrok-free\.app|https://.*\.ngrok\.io)",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Gateway Auth Router
    app.include_router(auth_router)

    # ── Edge Registration endpoint (allows the edge to announce its public URL) ──
    import json as _json
    from pathlib import Path as _Path
    from fastapi import Body as _Body
    from fastapi.responses import JSONResponse as _JSONResponse

    _EDGE_STATE_FILE = _Path("runtime/edge_url.txt")

    @app.post("/api/edge/register", tags=["Edge"])
    async def register_edge_url(payload: dict = _Body(...)):
        """Edge node posts its public tunnel URL here so the C2 can discover it."""
        url = payload.get("url", "").strip()
        if not url or not url.startswith("http"):
            return _JSONResponse(status_code=400, content={"error": "Invalid edge URL"})
        _EDGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _EDGE_STATE_FILE.write_text(url)
        logger.info(f"[EDGE-REGISTER] Edge URL registered: {url}")
        return {"status": "ok", "edge_url": url}

    @app.get("/api/edge/url", tags=["Edge"])
    async def get_edge_url():
        """Return the currently registered public edge URL."""
        if _EDGE_STATE_FILE.exists():
            url = _EDGE_STATE_FILE.read_text().strip()
            if url:
                return {"edge_url": url, "mode": "online"}
        return {"edge_url": None, "mode": "local"}

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
    app.include_router(topology_router)
    app.include_router(entities_router)

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/api/info", tags=["Gateway"])
        async def api_info():
            return {
                "name": settings.APP_NAME,
                "status": "online",
                "docs_url": "/docs",
                "health_url": "/api/health",
                "auth_status": "demo_mode" if settings.DEMO_MODE else "strict_jwt",
            }

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(request: Request, full_path: str):
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json") or full_path.startswith("ws/"):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Endpoint not found")

            # If JSON explicitly requested on root, return API status dictionary
            if not full_path and "application/json" in request.headers.get("accept", ""):
                return {
                    "name": settings.APP_NAME,
                    "status": "online",
                    "docs_url": "/docs",
                    "health_url": "/api/health",
                    "auth_status": "demo_mode" if settings.DEMO_MODE else "strict_jwt",
                }
            # Serve specific file if present in frontend/dist
            target_file = frontend_dist / full_path
            if full_path and target_file.is_file():
                return FileResponse(target_file)
            # SPA fallback to index.html
            index_path = frontend_dist / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)
            return {
                "name": settings.APP_NAME,
                "status": "online",
                "docs_url": "/docs",
                "health_url": "/api/health",
            }
    else:
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
