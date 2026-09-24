"""
PERCEPTA Defense — Camera Topology Service.

Maintains explicit camera relationships (adjacent, overlapping, sequential, entry/exit),
tracks expected transition times, and evaluates transition plausibility for
cross-camera Re-ID association and tactical visualization.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RelationshipType(str, Enum):
    ADJACENT = "adjacent"
    OVERLAPPING = "overlapping"
    SEQUENTIAL = "sequential"
    ENTRY_EXIT = "entry_exit"
    CUSTOM = "custom"


class TopologyEdge:
    """Represents a directed or bi-directional relationship between two cameras."""

    def __init__(
        self,
        from_camera: str,
        to_camera: str,
        relationship: RelationshipType = RelationshipType.ADJACENT,
        min_time_s: float = 1.0,
        max_time_s: float = 120.0,
        avg_time_s: float = 15.0,
        confidence_weight: float = 1.0,
        bidirectional: bool = True,
        is_configured: bool = False,
    ) -> None:
        self.from_camera = from_camera
        self.to_camera = to_camera
        self.relationship = relationship
        self.min_time_s = min_time_s
        self.max_time_s = max_time_s
        self.avg_time_s = avg_time_s
        self.confidence_weight = confidence_weight
        self.bidirectional = bidirectional
        self.is_configured = is_configured
        self.observed_transition_count = 0
        self.avg_observed_confidence = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_camera": self.from_camera,
            "to_camera": self.to_camera,
            "relationship": self.relationship.value if hasattr(self.relationship, "value") else str(self.relationship),
            "min_time_s": self.min_time_s,
            "max_time_s": self.max_time_s,
            "avg_time_s": self.avg_time_s,
            "confidence_weight": self.confidence_weight,
            "bidirectional": self.bidirectional,
            "is_configured": self.is_configured,
            "observed_transitions": self.observed_transition_count,
            "avg_confidence": round(self.avg_observed_confidence, 2),
        }


class CameraTopology:
    """
    Camera topology graph service.
    Combines operator-configured relationships and empirically observed transitions.
    """

    def __init__(self) -> None:
        self._edges: Dict[str, Dict[str, TopologyEdge]] = defaultdict(dict)
        self._last_rebuild: Optional[datetime] = None
        self._rebuild_interval_s = 300.0
        self._seed_default_topology()

    def _seed_default_topology(self) -> None:
        """Seed common default adjacency relationships."""
        defaults = [
            ("CAM-01", "CAM-02", RelationshipType.SEQUENTIAL, 2.0, 60.0, 10.0),
            ("CAM-02", "CAM-03", RelationshipType.SEQUENTIAL, 2.0, 60.0, 12.0),
            ("CAM-01", "CAM-03", RelationshipType.ADJACENT, 5.0, 120.0, 25.0),
            ("CAM-GATE", "CAM-PERIMETER", RelationshipType.ENTRY_EXIT, 1.0, 45.0, 8.0),
            ("ANPR-01", "CAM-01", RelationshipType.OVERLAPPING, 0.5, 30.0, 5.0),
        ]
        for src, dst, rel, t_min, t_max, t_avg in defaults:
            self.add_edge(src, dst, relationship=rel, min_time_s=t_min, max_time_s=t_max, avg_time_s=t_avg, is_configured=True)

    def add_edge(
        self,
        from_camera: str,
        to_camera: str,
        relationship: RelationshipType = RelationshipType.ADJACENT,
        min_time_s: float = 1.0,
        max_time_s: float = 120.0,
        avg_time_s: float = 15.0,
        confidence_weight: float = 1.0,
        bidirectional: bool = True,
        is_configured: bool = True,
    ) -> TopologyEdge:
        """Add or update an explicit relationship between two cameras."""
        edge = TopologyEdge(
            from_camera=from_camera,
            to_camera=to_camera,
            relationship=relationship,
            min_time_s=min_time_s,
            max_time_s=max_time_s,
            avg_time_s=avg_time_s,
            confidence_weight=confidence_weight,
            bidirectional=bidirectional,
            is_configured=is_configured,
        )
        self._edges[from_camera][to_camera] = edge
        if bidirectional:
            rev_edge = TopologyEdge(
                from_camera=to_camera,
                to_camera=from_camera,
                relationship=relationship,
                min_time_s=min_time_s,
                max_time_s=max_time_s,
                avg_time_s=avg_time_s,
                confidence_weight=confidence_weight,
                bidirectional=True,
                is_configured=is_configured,
            )
            self._edges[to_camera][from_camera] = rev_edge
        return edge

    def remove_edge(self, from_camera: str, to_camera: str, remove_reverse: bool = True) -> bool:
        """Remove relationship between two cameras."""
        removed = False
        if from_camera in self._edges and to_camera in self._edges[from_camera]:
            del self._edges[from_camera][to_camera]
            removed = True
        if remove_reverse and to_camera in self._edges and from_camera in self._edges[to_camera]:
            del self._edges[to_camera][from_camera]
            removed = True
        return removed

    def rebuild_if_stale(self) -> None:
        """Rebuild observed transitions from DB if stale."""
        now = datetime.now(timezone.utc)
        if self._last_rebuild and (now - self._last_rebuild).total_seconds() < self._rebuild_interval_s:
            return
        self._rebuild_from_db()

    def _rebuild_from_db(self) -> None:
        """Query camera_transitions table to update observed transition counts."""
        try:
            import sqlite3
            from backend.config import get_settings
            settings = get_settings()
            raw_url = settings.DATABASE_URL
            db_path = raw_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT from_camera_id, to_camera_id, association_confidence,
                       COUNT(*) as transition_count,
                       AVG(association_confidence) as avg_conf
                FROM camera_transitions
                GROUP BY from_camera_id, to_camera_id
            """).fetchall()
            conn.close()

            for r in rows:
                fc = r["from_camera_id"]
                tc = r["to_camera_id"]
                count = r["transition_count"]
                conf = r["avg_conf"]

                edge = self._edges[fc].get(tc)
                if not edge:
                    edge = self.add_edge(fc, tc, relationship=RelationshipType.ADJACENT, is_configured=False)
                edge.observed_transition_count = count
                edge.avg_observed_confidence = conf

            self._last_rebuild = datetime.now(timezone.utc)
        except Exception as e:
            logger.debug(f"CameraTopology._rebuild_from_db failed: {e}")

    def evaluate_transition_plausibility(
        self,
        from_camera: str,
        to_camera: str,
        elapsed_seconds: float,
    ) -> Tuple[bool, float, str]:
        """
        Evaluate if a transition between two cameras within elapsed_seconds is topologically plausible.
        Returns: (is_plausible: bool, topology_score: float [0.0-1.0], reason: str).
        """
        if from_camera == to_camera:
            return True, 1.0, "Same camera observation"

        self.rebuild_if_stale()
        edge = self._edges.get(from_camera, {}).get(to_camera)
        if not edge:
            # If from_camera has configured relationships to other cameras, but NOT to to_camera:
            if from_camera in self._edges and len(self._edges[from_camera]) > 0:
                if elapsed_seconds > 300.0:
                    return True, 0.25, f"Unlinked transition ({from_camera}->{to_camera}) plausible via long transit window (>5 min)"
                return False, 0.05, f"No topological relationship between {from_camera} and {to_camera}"
            # If camera pair has no configured topology, permit default candidate evaluation
            return True, 0.70, f"Unconfigured camera pair ({from_camera}->{to_camera}); permitted by default"

        # Plausibility checks based on travel time
        if elapsed_seconds < edge.min_time_s * 0.5:
            return False, 0.1, f"Transition too rapid ({elapsed_seconds:.1f}s < min {edge.min_time_s}s) - physical impossibility"

        if elapsed_seconds > edge.max_time_s * 2.0:
            return True, 0.4, f"Transition overdue ({elapsed_seconds:.1f}s > max {edge.max_time_s}s) - candidate only"

        # Within normal expected window
        time_diff = abs(elapsed_seconds - edge.avg_time_s)
        time_score = max(0.5, 1.0 - (time_diff / (edge.max_time_s + 1e-6)))
        final_score = min(1.0, time_score * edge.confidence_weight)
        return True, round(final_score, 2), f"Plausible transition ({edge.relationship.value}, {elapsed_seconds:.1f}s)"

    def get_adjacent_cameras(self, camera_id: str) -> List[str]:
        """Return cameras adjacent or linked to the given camera."""
        self.rebuild_if_stale()
        return list(self._edges.get(camera_id, {}).keys())

    def get_transition_info(self, from_camera: str, to_camera: str) -> Optional[Dict[str, Any]]:
        """Get transition edge info between two cameras."""
        self.rebuild_if_stale()
        edge = self._edges.get(from_camera, {}).get(to_camera)
        return edge.to_dict() if edge else None

    def is_valid_transition(self, from_camera: str, to_camera: str) -> bool:
        """Check if any relationship exists between two cameras."""
        self.rebuild_if_stale()
        return to_camera in self._edges.get(from_camera, {})

    def to_dict(self) -> Dict[str, Any]:
        """Export full topology graph as dict."""
        self.rebuild_if_stale()
        nodes = set()
        edges = []
        for fc, neighbors in self._edges.items():
            nodes.add(fc)
            for tc, edge in neighbors.items():
                nodes.add(tc)
                edges.append(edge.to_dict())

        return {
            "nodes": sorted(nodes),
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "last_rebuilt": self._last_rebuild.isoformat() if self._last_rebuild else None,
        }


global_topology = CameraTopology()


def get_topology() -> CameraTopology:
    return global_topology
