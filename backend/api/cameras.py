"""
Border Intelligence Camera Management REST API.
Provides endpoints to register cameras (video file, upload, webcam, RTSP), start
and stop live perception on them, and query stream status and diagnostics.
"""
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.config import get_settings
from backend.ingestion.camera_manager import CameraManager, get_camera_manager
from backend.tracking.live_worker import get_worker_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["Cameras"])

DEFAULT_DEMO_CLIP = (
    "frontend/public/videos/cam01_person_border.mp4"
    if Path("frontend/public/videos/cam01_person_border.mp4").is_file()
    else "dataset/surveillance/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4"
)
ALLOWED_VIDEO_SUFFIXES = {
    ".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".webm",
    ".flv", ".wmv", ".m4v", ".3gp", ".3g2", ".ts", ".mts", ".m2ts",
    ".vob", ".ogv", ".divx", ".asf", ".f4v", ".h264", ".hevc",
}
MAX_UPLOAD_BYTES = 2 * (1 << 30)  # 2 GB
# Directories scanned when the UI asks what footage is available locally.
VIDEO_SEARCH_ROOTS = ("dataset/surveillance", "videos", "frontend/public/videos", "storage/uploads")


def resolve_video_path(candidate: str) -> Optional[str]:
    """
    Resolve a client-supplied video path to a real file.

    Accepts an absolute path or one relative to the repo root, and falls back to
    a filename search under the known dataset roots so the UI can pass just a
    clip name. Returns None when nothing matches, so the caller can 400 instead
    of registering a camera that will fail to open.
    """
    raw = (candidate or "").strip().strip('"')
    if not raw:
        return None

    direct = Path(raw)
    if direct.is_file():
        return str(direct)

    for root in VIDEO_SEARCH_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        joined = base / raw
        if joined.is_file():
            return str(joined)

    name = direct.name.lower()
    if name:
        for root in VIDEO_SEARCH_ROOTS:
            base = Path(root)
            if not base.exists():
                continue
            for found in base.rglob("*"):
                if found.is_file() and found.name.lower() == name:
                    return str(found)
    return None


class CameraResponse(BaseModel):
    camera_id: str
    name: str
    source_type: str
    location_label: str
    status: str
    resolution: str
    native_fps: float
    fps: float
    frames_processed: int
    dropped_frames: int
    last_seen: Optional[str] = None
    is_running: bool
    last_error: Optional[str] = None
    codec: Optional[str] = None
    duration_sec: Optional[float] = None
    source_path: Optional[str] = None


class CameraListResponse(BaseModel):
    count: int
    cameras: List[CameraResponse]


@router.get("", response_model=CameraListResponse)
async def list_cameras() -> CameraListResponse:
    """List all registered surveillance cameras and their operational statuses."""
    manager = get_camera_manager()
    cams = manager.list_cameras()
    return CameraListResponse(count=len(cams), cameras=cams)


@router.get("/sources/available")
async def list_available_sources() -> Dict[str, Any]:
    """
    Enumerate video sources the operator can actually pick right now: bundled
    dataset clips found on disk, plus previously uploaded footage.
    """
    clips: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for root in VIDEO_SEARCH_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix.lower() not in ALLOWED_VIDEO_SUFFIXES or not path.is_file():
                continue
            rel = path.as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            clips.append(
                {
                    "path": rel,
                    "label": path.stem,
                    "group": base.name,
                    "size_mb": round(path.stat().st_size / (1 << 20), 1),
                }
            )
            if len(clips) >= 200:
                break

    bundled = [c for c in clips if c["group"] != "uploads"]
    uploaded = [c for c in clips if c["group"] == "uploads"]
    return {
        "count": len(clips),
        "total_count": len(clips),
        "default": DEFAULT_DEMO_CLIP,
        "videos": clips,
        "bundled_clips": [{"name": c["label"], "path": c["path"], "size_mb": c["size_mb"]} for c in bundled],
        "uploaded_clips": [{"name": c["label"], "path": c["path"], "size_mb": c["size_mb"]} for c in uploaded],
    }


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str) -> CameraResponse:
    """Get metadata and operational status for a single camera."""
    manager = get_camera_manager()
    cam = manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )
    return CameraResponse(**cam.to_dict())


@router.get("/{camera_id}/video")
@router.head("/{camera_id}/video")
async def get_camera_video_file(camera_id: str):
    """
    Stream the raw/source video file for a camera using HTTP range requests.
    Enables native HTML5 <video> hardware acceleration, scrubbing, and smooth 30/60fps playback.
    """
    from fastapi.responses import FileResponse
    manager = get_camera_manager()
    cam = manager.get_camera(camera_id)
    video_path = None

    if cam and getattr(cam, "adapter", None):
        video_path = getattr(cam.adapter, "video_path", None)

    if not video_path or not Path(video_path).is_file():
        matched = (
            (resolve_video_path(cam.name) if cam else None)
            or resolve_video_path(camera_id)
            or resolve_video_path(DEFAULT_DEMO_CLIP)
            or resolve_video_path("frontend/public/videos/virat_cctv.mp4")
            or resolve_video_path("videos/virat_cctv.mp4")
            or resolve_video_path("frontend/dist/videos/virat_cctv.mp4")
        )
        if matched and Path(matched).is_file():
            video_path = matched
        else:
            # Fallback to any available CCTV/surveillance video
            candidates = [
                Path("frontend/public/videos/virat_cctv.mp4"),
                Path("dataset/surveillance/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4"),
                Path("frontend/public/videos/border-demo.mp4"),
            ]
            for c in candidates:
                if c.is_file():
                    video_path = str(c.resolve())
                    break

    if not video_path or not Path(video_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No playable video file found for camera '{camera_id}'",
        )

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


class RegisterCameraRequest(BaseModel):
    camera_id: str
    name: Optional[str] = None
    source_type: str = "video_file"  # "video_file", "webcam", "rtsp", "simulation"
    source_url: Optional[str] = None  # video path, RTSP URL, or webcam device index
    file_path: Optional[str] = None  # alternative direct local file path
    location_label: str = "Sector Border Post"
    modality: str = "STANDARD"
    inference_size: str = "auto"  # "auto" | 416 | 512 | 640 (per-camera ONNX input)
    loop: bool = True
    fps: Optional[float] = None
    device_index: int = 0
    autostart: bool = True


@router.post("/register", response_model=CameraResponse)
async def register_camera(request: RegisterCameraRequest) -> CameraResponse:
    """
    Register a surveillance camera and, by default, begin live perception on it.

    Registration starts the real pipeline (detection -> tracking -> zones ->
    annotated MJPEG) rather than only recording metadata, so a camera added from
    the UI is immediately watchable with boxes on it.
    """
    from backend.events.schema import SourceType
    from backend.ingestion.rtsp_adapter import RTSPAdapter
    from backend.ingestion.simulation_adapter import SimulationAdapter
    from backend.ingestion.video_adapter import VideoFileAdapter
    from backend.ingestion.webcam_adapter import WebcamAdapter

    manager = get_camera_manager()
    src_type = request.source_type.lower()

    if manager.get_camera(request.camera_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera '{request.camera_id}' is already registered",
        )

    if src_type == "rtsp":
        if not request.source_url:
            raise HTTPException(status_code=400, detail="RTSP camera requires 'source_url'")
        adapter = RTSPAdapter(
            camera_id=request.camera_id,
            rtsp_url=request.source_url,
            target_fps=request.fps,
        )
        src_enum = SourceType.VIDEO_FILE
    elif src_type == "webcam":
        # `source_url` doubles as the device index when it parses as an integer,
        # so the UI can use one text field for both webcams and RTSP URLs.
        device_index = request.device_index
        if request.source_url:
            try:
                device_index = int(str(request.source_url).strip())
            except ValueError:
                pass
        adapter = WebcamAdapter(
            camera_id=request.camera_id,
            device_index=device_index,
            target_fps=request.fps,
        )
        src_enum = SourceType.VIDEO_FILE
    elif src_type == "simulation":
        adapter = SimulationAdapter(
            camera_id=request.camera_id,
            fps=request.fps or 15.0,
        )
        src_enum = SourceType.SIMULATION
    else:  # default video_file
        video_path = request.file_path or request.source_url or DEFAULT_DEMO_CLIP
        resolved = resolve_video_path(video_path)
        if resolved is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video file not found: {video_path}",
            )
        adapter = VideoFileAdapter(
            camera_id=request.camera_id,
            video_path=resolved,
            loop=request.loop,
            target_fps=request.fps,
            modality=request.modality,
        )
        src_enum = SourceType.VIDEO_FILE

    record = manager.register_camera(
        camera_id=request.camera_id,
        adapter=adapter,
        name=request.name or f"Camera {request.camera_id}",
        location_label=request.location_label,
        modality=request.modality,
        source_type=src_enum,
        inference_size=str(request.inference_size or "auto"),
    )

    if request.autostart:
        # A live source that is temporarily unreachable still registers: the
        # worker enters its reconnect loop and the tile shows SIGNAL LOSS until
        # the camera comes back. Refusing registration here would mean a camera
        # that drops during a restart could never be re-added unattended.
        started = await manager.start_camera(request.camera_id)
        if not started:
            logger.warning(
                f"Camera '{request.camera_id}' registered but its source did not open "
                f"({record.last_error}); the worker will keep retrying."
            )
        await get_worker_registry().start_worker(request.camera_id)

    return CameraResponse(**record.to_dict())


@router.post("/upload", response_model=CameraResponse)
async def upload_camera_video(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    location_label: str = Form("Uploaded Footage"),
    loop: bool = Form(True),
    modality: str = Form("STANDARD"),
) -> CameraResponse:
    """
    Accept an uploaded video file and register it as a live camera.
    Features instant zero-copy detection for existing local footage and
    threaded non-blocking spooling for new uploads.
    """
    import shutil
    from backend.events.schema import SourceType
    from backend.ingestion.video_adapter import VideoFileAdapter

    original_filename = file.filename or "video.mp4"
    raw_suffix = Path(original_filename).suffix.lower()
    suffix = raw_suffix if raw_suffix in ALLOWED_VIDEO_SUFFIXES else (raw_suffix or ".mp4")

    manager = get_camera_manager()
    cam_id = (camera_id or "").strip() or f"CAM-UP-{uuid.uuid4().hex[:6].upper()}"
    if manager.get_camera(cam_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera '{cam_id}' is already registered",
        )

    # 1. Zero-copy optimization: check if file is already on the server!
    existing_match = resolve_video_path(original_filename)
    if existing_match and Path(existing_match).is_file():
        matched_path = Path(existing_match)
        logger.info(f"Zero-copy match found for upload '{original_filename}' -> {matched_path}")
        adapter = VideoFileAdapter(
            camera_id=cam_id,
            video_path=str(matched_path),
            loop=loop,
            modality=modality,
        )
        record = manager.register_camera(
            camera_id=cam_id,
            adapter=adapter,
            name=name or matched_path.stem,
            location_label=location_label,
            modality=modality,
            source_type=SourceType.VIDEO_FILE,
        )

        # Stop existing running cameras so the uploaded camera runs with dedicated resources
        worker_reg = get_worker_registry()
        for other_id in manager.get_running_cameras():
            if other_id != cam_id:
                logger.info(f"Stopping active camera '{other_id}' before starting uploaded '{cam_id}'")
                await worker_reg.stop_worker(other_id)
                await manager.stop_camera(other_id)

        if not await manager.start_camera(cam_id):
            error = record.last_error or "unreadable video"
            await manager.deregister_camera(cam_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not decode video: {error}",
            )
        await worker_reg.start_worker(cam_id)
        return CameraResponse(**record.to_dict())

    # 2. Genuine new file: stream to storage in a background thread to keep event loop 100% fluid
    upload_dir = Path(get_settings().STORAGE_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{cam_id}{suffix}"

    def _save_file_threaded(src_obj, dst_path: Path):
        with open(dst_path, "wb") as out:
            shutil.copyfileobj(src_obj, out, length=1 << 20)

    try:
        await asyncio.to_thread(_save_file_threaded, file.file, dest)
    except Exception as copy_err:
        dest.unlink(missing_ok=True)
        logger.error(f"Failed to stream upload to disk: {copy_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save video upload: {copy_err}",
        )
    finally:
        await file.close()

    if not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file was empty")

    adapter = VideoFileAdapter(
        camera_id=cam_id,
        video_path=str(dest),
        loop=loop,
        modality=modality,
    )
    record = manager.register_camera(
        camera_id=cam_id,
        adapter=adapter,
        name=name or Path(original_filename).stem,
        location_label=location_label,
        modality=modality,
        source_type=SourceType.VIDEO_FILE,
    )

    # Stop existing running cameras so the uploaded camera runs with dedicated resources
    worker_reg = get_worker_registry()
    for other_id in manager.get_running_cameras():
        if other_id != cam_id:
            logger.info(f"Stopping active camera '{other_id}' before starting uploaded '{cam_id}'")
            await worker_reg.stop_worker(other_id)
            await manager.stop_camera(other_id)

    if not await manager.start_camera(cam_id):
        error = record.last_error or "unreadable video"
        await manager.deregister_camera(cam_id)
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not decode uploaded video: {error}",
        )

    await worker_reg.start_worker(cam_id)
    return CameraResponse(**record.to_dict())



@router.delete("/{camera_id}")
async def deregister_camera(camera_id: str) -> Dict[str, Any]:
    """
    Stop perception, release the capture, remove camera, and clean up active incidents/topology.
    Enforces Phase 24: Camera deletion must not leave orphaned active incidents/alerts.
    """
    from datetime import datetime, timezone
    manager = get_camera_manager()
    # Stop the worker first so it cannot read from an adapter being torn down.
    await get_worker_registry().stop_worker(camera_id)
    success = await manager.deregister_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )

    # Clean up active incidents and alerts for this camera to prevent orphaned states
    try:
        from backend.database import get_session_factory
        from backend.database.schema import Incident, Alert
        from sqlalchemy import select, and_
        factory = get_session_factory()
        async with factory() as session:
            inc_stmt = select(Incident).where(
                and_(
                    Incident.primary_camera_id == camera_id,
                    Incident.status.in_(["DETECTED", "ACTIVE", "ESCALATED"]),
                )
            )
            res = await session.execute(inc_stmt)
            active_incs = res.scalars().all()
            for inc in active_incs:
                inc.status = "RESOLVED"
                inc.resolved_at = datetime.now(timezone.utc)
                meta = dict(inc.meta or {})
                meta["resolution_notes"] = f"Camera {camera_id} decommissioned"
                inc.meta = meta
                # Resolve alerts
                alert_stmt = select(Alert).where(Alert.incident_id == inc.incident_id)
                a_res = await session.execute(alert_stmt)
                for a in a_res.scalars().all():
                    a.operator_status = "RESOLVED"
            await session.commit()
    except Exception as e:
        logger.warning(f"Error cleaning up incidents on camera deletion: {e}")

    # Remove from camera topology
    try:
        from backend.topology.service import get_topology
        topo = get_topology()
        adj = topo.get_adjacent_cameras(camera_id)
        for other in adj:
            topo.remove_edge(camera_id, other, remove_reverse=True)
    except Exception as e:
        logger.debug(f"Error updating topology on camera deletion: {e}")

    return {"camera_id": camera_id, "status": "deregistered", "removed": success}


@router.post("/{camera_id}/start")
async def start_camera(camera_id: str) -> Dict[str, Any]:
    """Open the source and start live perception for a registered camera."""
    manager = get_camera_manager()
    worker_reg = get_worker_registry()

    # Enforce strictly ONE active camera running perception at a time
    running_cams = manager.get_running_cameras()
    for other_id in running_cams:
        if other_id != camera_id:
            logger.info(f"Stopping active camera '{other_id}' before starting '{camera_id}'")
            await worker_reg.stop_worker(other_id)
            await manager.stop_camera(other_id)

    success = await manager.start_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start camera '{camera_id}'. Ensure camera is registered.",
        )
    await worker_reg.start_worker(camera_id)
    return {"camera_id": camera_id, "status": "started"}


@router.post("/{camera_id}/stop")
async def stop_camera(camera_id: str) -> Dict[str, Any]:
    """Stop live perception and release the camera's capture handle."""
    manager = get_camera_manager()
    await get_worker_registry().stop_worker(camera_id)
    success = await manager.stop_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to stop camera '{camera_id}'",
        )
    return {"camera_id": camera_id, "status": "stopped"}


@router.post("/{camera_id}/pause")
async def pause_camera_analysis(camera_id: str) -> Dict[str, Any]:
    """Pause perception inference for a camera without stopping the worker.
    The MJPEG stream stays alive (frozen on last frame) so the UI doesn't disconnect."""
    registry = get_worker_registry()
    ok = registry.pause_worker(camera_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active worker for camera '{camera_id}'",
        )
    return {"camera_id": camera_id, "status": "paused"}


@router.post("/{camera_id}/resume")
async def resume_camera_analysis(camera_id: str) -> Dict[str, Any]:
    """Resume perception inference for a paused camera."""
    registry = get_worker_registry()
    ok = registry.resume_worker(camera_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active worker for camera '{camera_id}'",
        )
    return {"camera_id": camera_id, "status": "resumed"}


@router.post("/{camera_id}/reconnect")
async def reconnect_camera(camera_id: str) -> Dict[str, Any]:
    """Attempt reconnection for a degraded or disconnected camera stream."""
    manager = get_camera_manager()
    success = await manager.reconnect_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reconnect camera '{camera_id}'",
        )
    await get_worker_registry().start_worker(camera_id)
    return {"camera_id": camera_id, "status": "reconnected"}


@router.get("/{camera_id}/diagnostics")
async def get_camera_diagnostics(camera_id: str):
    """
    Run real-time optical quality, lens tampering, and signal degradation diagnostics on camera stream.
    Detects lens spray, defocus, blinding glare, and illumination blackout.
    """
    from backend.ingestion.optical_diagnostics import diagnose_camera_stream
    diag = await diagnose_camera_stream(camera_id)
    if not diag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )
    return diag


@router.get("/{camera_id}/heatmap")
async def get_camera_spatial_heatmap(
    camera_id: str,
    grid_size: int = 16,
    limit: int = 500,
):
    """
    Generate normalized 2D spatial trajectory density grid and corridor breach hotspot matrix.
    Computes spatial coordinate frequencies from persistent SQLite WAL tracking logs.
    """
    from backend.zones.heatmap import get_heatmap_engine
    engine = get_heatmap_engine()
    return await engine.generate_heatmap(camera_id=camera_id, grid_size=grid_size, limit=limit)


@router.get("/{camera_id}/metrics")
async def get_single_camera_metrics(camera_id: str):
    """Return live FPS, inference latency, tracking latency, and encoding telemetry for camera."""
    worker = get_worker_registry().get_worker(camera_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No worker active for camera '{camera_id}'",
        )
    return worker.get_metrics()


@router.get("/fleet/metrics")
async def get_fleet_telemetry():
    """Return process-wide aggregate FPS and performance telemetry."""
    return get_worker_registry().aggregate_metrics()


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str) -> Dict[str, Any]:
    """
    Phase 24: Safely decommission/delete a camera.
    - Stops live worker and camera capture handle.
    - Resolves all active incidents/alerts to prevent orphaned alert cards.
    - Removes camera from topology.
    - Unregisters from CameraManager.
    """
    from datetime import datetime, timezone

    worker_reg = get_worker_registry()
    await worker_reg.stop_worker(camera_id)

    manager = get_camera_manager()
    removed = await manager.remove_camera(camera_id)

    # Clean up active incidents and alerts for this camera to prevent orphaned states
    try:
        from backend.database import get_session_factory
        from backend.database.schema import Incident, Alert
        from sqlalchemy import select, and_
        factory = get_session_factory()
        async with factory() as session:
            inc_stmt = select(Incident).where(
                and_(
                    Incident.primary_camera_id == camera_id,
                    Incident.status.in_(["DETECTED", "ACTIVE", "ESCALATED"]),
                )
            )
            res = await session.execute(inc_stmt)
            active_incs = res.scalars().all()
            for inc in active_incs:
                inc.status = "RESOLVED"
                inc.resolved_at = datetime.now(timezone.utc)
                meta = dict(inc.meta or {})
                meta["resolution_notes"] = f"Camera {camera_id} decommissioned"
                inc.meta = meta
                # Resolve alerts
                alert_stmt = select(Alert).where(Alert.incident_id == inc.incident_id)
                a_res = await session.execute(alert_stmt)
                for a in a_res.scalars().all():
                    a.operator_status = "RESOLVED"
            await session.commit()
    except Exception as e:
        logger.warning(f"Error cleaning up incidents on camera deletion: {e}")

    # Remove from camera topology
    try:
        from backend.topology.service import get_topology
        topo = get_topology()
        adj = topo.get_adjacent_cameras(camera_id)
        for other in adj:
            topo.remove_edge(camera_id, other, remove_reverse=True)
    except Exception as e:
        logger.debug(f"Error updating topology on camera deletion: {e}")

    return {
        "status": "success",
        "camera_id": camera_id,
        "removed": removed,
        "message": f"Camera '{camera_id}' decommissioned; active incidents and topology cleaned up",
    }

