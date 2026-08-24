"""
Border Intelligence Camera Management REST API.
Provides endpoints to list registered cameras, query stream status, and manage camera lifecycles.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.ingestion.camera_manager import CameraManager, get_camera_manager

router = APIRouter(prefix="/api/cameras", tags=["Cameras"])


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
    source_type: str = "video_file"  # "video_file", "rtsp", "simulation"
    source_url: Optional[str] = None  # path to video or RTSP URL
    location_label: str = "Sector Border Post"
    loop: bool = True
    fps: Optional[float] = 30.0


@router.post("/register", response_model=CameraResponse)
async def register_camera(request: RegisterCameraRequest) -> CameraResponse:
    """Register a new surveillance camera (video file, RTSP, or simulation)."""
    from backend.events.schema import SourceType
    from backend.ingestion.rtsp_adapter import RTSPAdapter
    from backend.ingestion.simulation_adapter import SimulationAdapter
    from backend.ingestion.video_adapter import VideoFileAdapter

    manager = get_camera_manager()
    src_type = request.source_type.lower()

    if src_type == "rtsp":
        if not request.source_url:
            raise HTTPException(status_code=400, detail="RTSP camera requires 'source_url'")
        adapter = RTSPAdapter(
            camera_id=request.camera_id,
            rtsp_url=request.source_url,
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
        video_path = request.source_url or "VIRAT/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4"
        adapter = VideoFileAdapter(
            camera_id=request.camera_id,
            video_path=video_path,
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
    return CameraResponse(**record.to_dict())


@router.delete("/{camera_id}")
async def deregister_camera(camera_id: str) -> Dict[str, Any]:
    """Deregister and stop a camera feed."""
    manager = get_camera_manager()
    success = await manager.deregister_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )
    return {"camera_id": camera_id, "status": "deregistered"}


@router.post("/{camera_id}/start")
async def start_camera(camera_id: str) -> Dict[str, Any]:
    """Start ingestion for a specific registered camera."""
    manager = get_camera_manager()
    success = await manager.start_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start camera '{camera_id}'. Ensure camera is registered.",
        )
    return {"camera_id": camera_id, "status": "started"}


@router.post("/{camera_id}/stop")
async def stop_camera(camera_id: str) -> Dict[str, Any]:
    """Stop ingestion for a specific registered camera."""
    manager = get_camera_manager()
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
