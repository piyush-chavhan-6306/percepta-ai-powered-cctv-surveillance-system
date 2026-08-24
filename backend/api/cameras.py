"""
Border Intelligence Camera Management REST API.
Provides endpoints to register cameras (video file, upload, webcam, RTSP), start
and stop live perception on them, and query stream status and diagnostics.
"""
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

DEFAULT_DEMO_CLIP = "VIRAT/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4"
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".webm"}
MAX_UPLOAD_BYTES = 2 * (1 << 30)  # 2 GB
# Directories scanned when the UI asks what footage is available locally.
VIDEO_SEARCH_ROOTS = ("VIRAT", "videos", "frontend/public/videos", "storage/uploads")


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


class CameraListResponse(BaseModel):
    count: int
    cameras: List[CameraResponse]


@router.get("", response_model=CameraListResponse)
async def list_cameras() -> CameraListResponse:
    """List all registered surveillance cameras and their operational statuses."""
    manager = get_camera_manager()
    cams = manager.list_cameras()
    return CameraListResponse(count=len(cams), cameras=cams)


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


class RegisterCameraRequest(BaseModel):
    camera_id: str
    name: Optional[str] = None
    source_type: str = "video_file"  # "video_file", "webcam", "rtsp", "simulation"
    source_url: Optional[str] = None  # video path, RTSP URL, or webcam device index
    location_label: str = "Sector Border Post"
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
        video_path = request.source_url or DEFAULT_DEMO_CLIP
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
        )
        src_enum = SourceType.VIDEO_FILE

    record = manager.register_camera(
        camera_id=request.camera_id,
        adapter=adapter,
        name=request.name or f"Camera {request.camera_id}",
        location_label=request.location_label,
        source_type=src_enum,
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
) -> CameraResponse:
    """
    Accept an uploaded video file and register it as a live camera.

    Lets an operator (or a judge at a demo) drop in arbitrary footage and get
    real tracking on it without touching the filesystem or restarting anything.
    """
    from backend.events.schema import SourceType
    from backend.ingestion.video_adapter import VideoFileAdapter

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_SUFFIXES))}",
        )

    manager = get_camera_manager()
    cam_id = (camera_id or "").strip() or f"CAM-UP-{uuid.uuid4().hex[:6].upper()}"
    if manager.get_camera(cam_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera '{cam_id}' is already registered",
        )

    upload_dir = Path(get_settings().STORAGE_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{cam_id}{suffix}"

    # Stream to disk in chunks; a full read would hold an entire video in RAM.
    bytes_written = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1 << 20):
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeds the {MAX_UPLOAD_BYTES // (1 << 20)} MB limit",
                    )
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if bytes_written == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file was empty")

    adapter = VideoFileAdapter(
        camera_id=cam_id,
        video_path=str(dest),
        loop=loop,
    )
    record = manager.register_camera(
        camera_id=cam_id,
        adapter=adapter,
        name=name or Path(file.filename or cam_id).stem,
        location_label=location_label,
        source_type=SourceType.VIDEO_FILE,
    )

    if not await manager.start_camera(cam_id):
        error = record.last_error or "unreadable video"
        await manager.deregister_camera(cam_id)
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not decode uploaded video: {error}",
        )

    await get_worker_registry().start_worker(cam_id)
    return CameraResponse(**record.to_dict())


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

    return {"count": len(clips), "default": DEFAULT_DEMO_CLIP, "videos": clips}


@router.delete("/{camera_id}")
async def deregister_camera(camera_id: str) -> Dict[str, Any]:
    """Stop perception, release the capture, and remove the camera."""
    manager = get_camera_manager()
    # Stop the worker first so it cannot read from an adapter being torn down.
    await get_worker_registry().stop_worker(camera_id)
    success = await manager.deregister_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )
    return {"camera_id": camera_id, "status": "deregistered"}


@router.post("/{camera_id}/start")
async def start_camera(camera_id: str) -> Dict[str, Any]:
    """Open the source and start live perception for a registered camera."""
    manager = get_camera_manager()
    success = await manager.start_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start camera '{camera_id}'. Ensure camera is registered.",
        )
    await get_worker_registry().start_worker(camera_id)
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
