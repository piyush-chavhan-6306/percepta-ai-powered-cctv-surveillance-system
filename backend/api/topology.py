"""
PERCEPTA Defense — Camera Topology API.

Provides camera relationship visualization, topology queries, edge management,
and transition plausibility evaluation.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, status

from backend.topology.service import RelationshipType, get_topology

router = APIRouter(prefix="/api/topology", tags=["Camera Topology"])


class AddEdgeRequest(BaseModel):
    from_camera: str = Field(..., description="Source camera ID")
    to_camera: str = Field(..., description="Destination camera ID")
    relationship: RelationshipType = Field(default=RelationshipType.ADJACENT, description="Relationship type")
    min_time_s: float = Field(default=1.0, ge=0.1, description="Minimum travel time in seconds")
    max_time_s: float = Field(default=120.0, ge=1.0, description="Maximum travel time in seconds")
    avg_time_s: float = Field(default=15.0, ge=0.5, description="Expected average travel time in seconds")
    confidence_weight: float = Field(default=1.0, ge=0.1, le=1.0, description="Confidence multiplier")
    bidirectional: bool = Field(default=True, description="Whether relationship is two-way")


@router.get("", response_model=Dict[str, Any])
@router.get("/graph", response_model=Dict[str, Any])
async def get_topology_graph() -> Dict[str, Any]:
    """Get full camera topology graph (nodes + edges)."""
    topo = get_topology()
    return topo.to_dict()


@router.post("/edges", response_model=Dict[str, Any])
async def add_or_update_edge(req: AddEdgeRequest) -> Dict[str, Any]:
    """Add or update an explicit topological relationship between two cameras."""
    topo = get_topology()
    edge = topo.add_edge(
        from_camera=req.from_camera,
        to_camera=req.to_camera,
        relationship=req.relationship,
        min_time_s=req.min_time_s,
        max_time_s=req.max_time_s,
        avg_time_s=req.avg_time_s,
        confidence_weight=req.confidence_weight,
        bidirectional=req.bidirectional,
        is_configured=True,
    )
    return {
        "status": "success",
        "message": f"Topology relationship created: {req.from_camera} <-> {req.to_camera}",
        "edge": edge.to_dict(),
    }


@router.delete("/edges")
async def delete_edge(
    from_camera: str = Query(...),
    to_camera: str = Query(...),
    bidirectional: bool = Query(True),
) -> Dict[str, Any]:
    """Remove a relationship between two cameras."""
    topo = get_topology()
    removed = topo.remove_edge(from_camera, to_camera, remove_reverse=bidirectional)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge between {from_camera} and {to_camera} not found",
        )
    return {
        "status": "success",
        "message": f"Edge removed between {from_camera} and {to_camera}",
    }


@router.get("/adjacent/{camera_id}")
async def get_adjacent_cameras(camera_id: str) -> Dict[str, Any]:
    """Get cameras adjacent to a given camera."""
    topo = get_topology()
    adjacent = topo.get_adjacent_cameras(camera_id)
    return {
        "camera_id": camera_id,
        "adjacent_cameras": adjacent,
        "count": len(adjacent),
    }


@router.get("/transition")
async def get_transition_info(
    from_camera: str = Query(..., description="Source camera ID"),
    to_camera: str = Query(..., description="Destination camera ID"),
) -> Dict[str, Any]:
    """Get transition info between two cameras."""
    topo = get_topology()
    info = topo.get_transition_info(from_camera, to_camera)
    if info is None:
        return {
            "from_camera": from_camera,
            "to_camera": to_camera,
            "exists": False,
            "message": "No recorded transitions between these cameras",
        }
    return {
        "from_camera": from_camera,
        "to_camera": to_camera,
        "exists": True,
        **info,
    }


class EvaluateTransitionRequest(BaseModel):
    from_camera: str = Field(..., description="Source camera ID")
    to_camera: str = Field(..., description="Destination camera ID")
    elapsed_seconds: float = Field(..., ge=0.0, description="Elapsed time in seconds")


@router.post("/evaluate")
async def evaluate_transition_post(req: EvaluateTransitionRequest) -> Dict[str, Any]:
    """Evaluate whether a camera transition is topologically plausible (POST)."""
    topo = get_topology()
    is_plausible, score, reason = topo.evaluate_transition_plausibility(
        from_camera=req.from_camera,
        to_camera=req.to_camera,
        elapsed_seconds=req.elapsed_seconds,
    )
    return {
        "from_camera": req.from_camera,
        "to_camera": req.to_camera,
        "elapsed_seconds": req.elapsed_seconds,
        "is_plausible": is_plausible,
        "topology_score": score,
        "reason": reason,
    }


@router.get("/evaluate")
async def evaluate_transition(
    from_camera: str = Query(..., description="Source camera"),
    to_camera: str = Query(..., description="Destination camera"),
    elapsed_seconds: float = Query(..., ge=0.0, description="Elapsed time in seconds"),
) -> Dict[str, Any]:
    """Evaluate whether a camera transition is topologically plausible (GET)."""
    topo = get_topology()
    is_plausible, score, reason = topo.evaluate_transition_plausibility(
        from_camera=from_camera,
        to_camera=to_camera,
        elapsed_seconds=elapsed_seconds,
    )
    return {
        "from_camera": from_camera,
        "to_camera": to_camera,
        "elapsed_seconds": elapsed_seconds,
        "is_plausible": is_plausible,
        "topology_score": score,
        "reason": reason,
    }
