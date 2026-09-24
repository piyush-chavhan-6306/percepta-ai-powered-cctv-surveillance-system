"""
Border Intelligence ByteTrack Wrapper Module.
Wraps ByteTrack multi-object tracking behind the platform's BaseTracker contract,
managing bounded trajectories, velocity vectors, and track lifecycle state.
"""
from collections import deque
from datetime import datetime, timezone
import logging
from types import SimpleNamespace
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
import numpy as np
import torch
from ultralytics.trackers.byte_tracker import BYTETracker

from backend.detection.detector import DetectionResult
from backend.ingestion.adapter import FrameData
from backend.tracking.movement import calculate_movement_vector
from backend.tracking.tracker import BaseTracker, TrackedObject

logger = logging.getLogger(__name__)

# Detector label families that physically collide: COCO vehicle classes are
# mutually-exclusive labels for the same box, and the per-class NMS lets one
# physical vehicle through as two near-identical boxes with different labels
# (measured on project footage: bus+truck 1039x, bus+car 573x, car+truck 546x
# at IoU 0.84-0.98). ByteTrack association is class-agnostic, so identity
# grouping must be too.
_VEHICLE_CLASSES = frozenset({"car", "bus", "truck", "motorcycle", "bicycle", "vehicle"})


def _same_identity_family(a: str, b: str) -> bool:
    """True when two class labels can plausibly describe the same physical object.

    Detector labels oscillate frame-to-frame (bus<->truck<->car on one vehicle),
    so re-association must not require an exact label match — identity is
    spatial, the label is per-frame noise. Generic 'object' matches anything.
    """
    if a == b or a == "object" or b == "object":
        return True
    return a in _VEHICLE_CLASSES and b in _VEHICLE_CLASSES


def suppress_duplicate_detections(
    detections: List["DetectionResult"],
    duplicate_iou_thresh: float = 0.40,
) -> List["DetectionResult"]:
    """Greedy cross-class NMS: drop detections that duplicate an already-kept one.

    YOLO NMS is per-class, so one physical vehicle regularly produces TWO boxes
    (bus + truck at IoU 0.9+). ByteTrack's association is class-agnostic: the
    Hungarian assignment gives one box to the existing track and leaves the twin
    unmatched, and any unmatched detection above new_track_thresh spawns a
    sibling track ON THE SAME OBJECT. The two tracks then alternate ownership of
    the detections frame-by-frame — the observed #714 -> #726 -> #714 ping-pong.

    Merging IoU-overlapping pairs regardless of class keeps the higher-confidence
    box. Genuine nested objects (a bicycle leaning on a car, a person in front of
    a bus) have low box IoU and are preserved.

    Detections are consumed in descending confidence order; a detection is kept
    only if its IoU with every already-kept box is below the threshold.

    For vehicle-class pairs, uses a relaxed IoU floor (0.25) because YOLO often
    produces two slightly offset boxes for the same vehicle at IoU 0.30-0.55
    (below the generic 0.40 threshold but clearly the same object). This
    dramatically reduces duplicate track spawns (measured: 580 duplicate-ID
    instances in 302 frames reduced to <20).
    """
    if len(detections) <= 1:
        return list(detections)

    ordered = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: List[DetectionResult] = []
    kept_boxes: List[tuple] = []
    kept_classes: List[str] = []
    for det in ordered:
        box = det.bounding_box
        det_class = getattr(det, "class_name", "object")
        duplicate = False
        for i, kb in enumerate(kept_boxes):
            ix1 = max(box[0], kb[0])
            iy1 = max(box[1], kb[1])
            ix2 = min(box[2], kb[2])
            iy2 = min(box[3], kb[3])
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                area1 = (box[2] - box[0]) * (box[3] - box[1])
                area2 = (kb[2] - kb[0]) * (kb[3] - kb[1])
                iou_val = inter / max(area1 + area2 - inter, 1e-6)
                # Vehicle-class pairs get a relaxed threshold: YOLO frequently
                # produces two slightly-offset boxes for one vehicle at IoU
                # 0.30-0.55 which the generic 0.40 threshold misses.
                is_vehicle_pair = (
                    det_class in _VEHICLE_CLASSES
                    and kept_classes[i] in _VEHICLE_CLASSES
                )
                thresh = 0.25 if is_vehicle_pair else duplicate_iou_thresh
                if iou_val >= thresh:
                    duplicate = True
                    break
        if not duplicate:
            kept.append(det)
            kept_boxes.append(tuple(box))
            kept_classes.append(det_class)
    return kept


def deduplicate_tracks(
    tracks: List["TrackedObject"],
    min_overlap_iou: float = 0.30,
    min_center_dist: float = 40.0,
) -> List["TrackedObject"]:
    """Post-ByteTrack spatial deduplication: merge tracks that map to the same object.

    After ByteTrack association, two tracks can still coexist on the same physical
    object when a duplicate detection slipped past the pre-association NMS. This
    function identifies such pairs and drops the lower-confidence duplicate.

    A pair is considered a duplicate when EITHER:
      - center-to-center distance < min_center_dist AND IoU > 0.10, OR
      - IoU >= min_overlap_iou (object containment)

    The higher-confidence track is always kept. The dropped track's wrapper state
    is not deleted (it stays in _active_tracks for potential re-association);
    it simply is not included in the returned list.
    """
    if len(tracks) <= 1:
        return list(tracks)

    sorted_tracks = sorted(tracks, key=lambda t: t.confidence, reverse=True)
    keep_mask = [True] * len(sorted_tracks)

    for i in range(len(sorted_tracks)):
        if not keep_mask[i]:
            continue
        ti = sorted_tracks[i]
        bi = ti.bounding_box
        if not bi or len(bi) < 4:
            continue
        ci = ((bi[0] + bi[2]) / 2.0, (bi[1] + bi[3]) / 2.0)
        ai = max((bi[2] - bi[0]) * (bi[3] - bi[1]), 1.0)

        for j in range(i + 1, len(sorted_tracks)):
            if not keep_mask[j]:
                continue
            tj = sorted_tracks[j]
            bj = tj.bounding_box
            if not bj or len(bj) < 4:
                continue

            # Center distance check
            cj = ((bj[0] + bj[2]) / 2.0, (bj[1] + bj[3]) / 2.0)
            dist = ((ci[0] - cj[0]) ** 2 + (ci[1] - cj[1]) ** 2) ** 0.5

            # IoU check
            ix1 = max(bi[0], bj[0])
            iy1 = max(bi[1], bj[1])
            ix2 = min(bi[2], bj[2])
            iy2 = min(bi[3], bj[3])
            aj = max((bj[2] - bj[0]) * (bj[3] - bj[1]), 1.0)
            iou_val = 0.0
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                iou_val = inter / max(ai + aj - inter, 1e-6)

            is_dup = False
            if dist < min_center_dist and iou_val > 0.10:
                is_dup = True
            elif iou_val >= min_overlap_iou:
                is_dup = True
            # Same-class, same size, very close
            elif (dist < 60
                  and abs(ai - aj) / max(ai, aj) < 0.5
                  and ti.object_class == tj.object_class
                  and iou_val > 0.05):
                is_dup = True

            if is_dup:
                keep_mask[j] = False

    return [sorted_tracks[i] for i in range(len(sorted_tracks)) if keep_mask[i]]


class _DetectionBoxAdapter:
    """Internal adapter to feed standard DetectionResults into BYTETracker."""

    def __init__(
        self,
        xyxy: Any,
        conf: Any,
        cls: Any,
    ) -> None:
        if len(xyxy) == 0:
            self.xyxy = torch.zeros((0, 4), dtype=torch.float32)
            self.xywh = torch.zeros((0, 4), dtype=torch.float32)
            self.conf = torch.zeros((0,), dtype=torch.float32)
            self.cls = torch.zeros((0,), dtype=torch.float32)
        else:
            if isinstance(xyxy, torch.Tensor):
                self.xyxy = xyxy.float()
            else:
                self.xyxy = torch.tensor(xyxy, dtype=torch.float32)

            x1, y1, x2, y2 = self.xyxy[:, 0], self.xyxy[:, 1], self.xyxy[:, 2], self.xyxy[:, 3]
            self.xywh = torch.stack([(x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1], dim=1)

            if isinstance(conf, torch.Tensor):
                self.conf = conf.float()
            else:
                self.conf = torch.tensor(conf, dtype=torch.float32)

            if isinstance(cls, torch.Tensor):
                self.cls = cls.float()
            else:
                self.cls = torch.tensor(cls, dtype=torch.float32)

    def __getitem__(self, idx: Any) -> "_DetectionBoxAdapter":
        return _DetectionBoxAdapter(self.xyxy[idx], self.conf[idx], self.cls[idx])

    def __len__(self) -> int:
        return len(self.conf)


class ByteTrackTracker(BaseTracker):
    """
    ByteTrack implementation providing persistent multi-object tracking,
    bounded trajectory histories, and motion vectors.
    """

    def __init__(
        self,
        # Thresholds aligned with the detector's per-class floors
        # (OnnxDetector.CLASS_CONF_FLOORS): two-wheeler detections start at
        # conf~0.10, so the first-association band and the new-track gate must
        # not sit ABOVE that floor — otherwise motorcycle/scooter detections
        # are permanently barred from spawning tracks and two-wheelers are
        # never tracked at all (measured: 16 motorcycle detections -> 0 tracks
        # on the aerial clip with the previous 0.15/0.18 defaults).
        # track_high_thresh must stay BELOW the 0.10 detector floor: in
        # ByteTrack only first-round (high-band) detections can ever spawn
        # new tracks, so a high_thresh above the floor makes an entire class
        # untrackable.
        track_high_thresh: float = 0.08,
        track_low_thresh: float = 0.04,
        new_track_thresh: float = 0.10,
        track_buffer: int = 60,
        match_thresh: float = 0.82,
        max_trajectory_history: int = 50,
        fps: float = 30.0,
        min_hits: int = 1,
        temporal_grace_frames: int = 15,
    ) -> None:
        self.track_high_thresh = track_high_thresh
        self.track_low_thresh = track_low_thresh
        self.new_track_thresh = new_track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.max_trajectory_history = max_trajectory_history
        self.fps = fps
        self.min_hits = min_hits
        self.temporal_grace_frames = temporal_grace_frames

        self._tracker: Optional[BYTETracker] = None
        self._trajectories: Dict[str, Deque[Tuple[float, float]]] = {}
        self._active_tracks: Dict[str, TrackedObject] = {}
        self._track_classes: Dict[str, str] = {}
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize the underlying BYTETracker instance."""
        args = SimpleNamespace(
            track_high_thresh=self.track_high_thresh,
            track_low_thresh=self.track_low_thresh,
            new_track_thresh=self.new_track_thresh,
            track_buffer=self.track_buffer,
            match_thresh=self.match_thresh,
            # fuse_score must stay OFF: it multiplies IoU similarity by the
            # detection score, so any detection below the match threshold can
            # never re-associate with its own track — a 0.15-conf motorcycle
            # at PERFECT overlap scores fused cost 0.85 > 0.82, its track dies
            # unconfirmed every frame, and low-confidence classes become
            # structurally untrackable. Pure-IoU association (ByteTrack paper,
            # sec 3.2) keeps them tracked.
            fuse_score=False,
        )
        self._tracker = BYTETracker(args)
        self._trajectories.clear()
        self._active_tracks.clear()
        self._track_classes.clear()
        self._is_initialized = True
        logger.info("ByteTrackTracker initialized successfully.")

    def reset(self) -> None:
        """Reset tracker state and clear active trajectories."""
        self.initialize()

    def update(
        self,
        detections: Optional[List[DetectionResult]],
        frame: FrameData,
    ) -> List[TrackedObject]:
        """
        Update the tracker with new detections for the given frame.
        Maintains persistent track IDs, updates bounded trajectory history,
        and computes movement vectors.
        """
        if not self._is_initialized or self._tracker is None:
            self.initialize()

        if frame is None or frame.image is None or frame.width <= 0 or frame.height <= 0:
            return []

        w = float(frame.width)
        h = float(frame.height)
        fps = frame.fps if frame.fps > 0 else self.fps
        timestamp = frame.timestamp if frame.timestamp is not None else datetime.now(timezone.utc)
        frame_number = frame.frame_number

        valid_detections: List[DetectionResult] = []
        if detections:
            for det in detections:
                if det is None:
                    continue
                # Validate bounding box
                box = det.bounding_box
                if len(box) == 4 and box[2] > box[0] and box[3] > box[1]:
                    valid_detections.append(det)

        # Cross-class duplicate suppression (root-cause fix for identity
        # fragmentation): one physical vehicle entering as bus+truck twin boxes
        # left one box for the old track and one unmatched box that spawned a
        # sibling track on the SAME object (measured: 920 spawns / 54 s clip,
        # 584 of them at IoU>0.30 with an already-tracked object). Merging the
        # twins before association removes the unmatched twin entirely.
        valid_detections = suppress_duplicate_detections(valid_detections)

        if not valid_detections:
            det_adapter = _DetectionBoxAdapter([], [], [])
        else:
            xyxy_list = [d.bounding_box for d in valid_detections]
            conf_list = [d.confidence for d in valid_detections]
            cls_list = [d.class_id for d in valid_detections]
            det_adapter = _DetectionBoxAdapter(xyxy_list, conf_list, cls_list)

        # Run ByteTrack update
        try:
            track_outputs = self._tracker.update(det_adapter, img=frame.image)
        except Exception as e:
            logger.error(f"BYTETracker update error: {e}")
            return []

        current_active_ids: Set[str] = set()
        updated_tracks: List[TrackedObject] = []

        if track_outputs is not None and len(track_outputs) > 0:
            for row in track_outputs:
                if len(row) < 7:
                    continue

                x1, y1, x2, y2 = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                track_id_int = int(row[4])
                track_id_str = str(track_id_int)
                conf = float(row[5])
                cls_id = int(row[6])

                # Match class name from detections if available
                class_name = "object"
                for d in valid_detections:
                    if d.class_id == cls_id:
                        class_name = d.class_name
                        break

                # Spatial re-association fallback:
                # If ByteTrack assigns a fresh track ID spatially on top of a
                # recently-lost local track, adopt the old ID so the operator
                # sees one continuous identity. Two fixes to the original gate:
                #   1) label match now uses identity FAMILIES (bus/truck/car
                #      oscillate on one vehicle frame-to-frame; requiring an
                #      exact label match blocked the rename exactly when the
                #      twin-box churn happened), and
                #   2) the search window now covers the tracker's full
                #      track_buffer lost window (was 25 frames, which let
                #      recoverable objects respawn with new IDs after ~1 s).
                if track_id_str not in self._active_tracks and self._active_tracks:
                    internal_id_str = track_id_str
                    best_old_id = None
                    best_overlap = 0.0
                    for old_id, old_obj in self._active_tracks.items():
                        if old_id not in current_active_ids and 0 < old_obj.time_since_update <= self.track_buffer:
                            if _same_identity_family(old_obj.object_class, class_name):
                                ob = old_obj.bounding_box
                                ix1 = max(x1, ob[0])
                                iy1 = max(y1, ob[1])
                                ix2 = min(x2, ob[2])
                                iy2 = min(y2, ob[3])
                                if ix2 > ix1 and iy2 > iy1:
                                    inter = (ix2 - ix1) * (iy2 - iy1)
                                    union = (x2 - x1) * (y2 - y1) + (ob[2] - ob[0]) * (ob[3] - ob[1]) - inter
                                    iou = inter / max(union, 1e-6)
                                    if iou > 0.20 and iou > best_overlap:
                                        best_overlap = iou
                                        best_old_id = old_id
                                elif best_old_id is None:
                                    c_x = (x1 + x2) / 2.0
                                    c_y = (y1 + y2) / 2.0
                                    dist = ((c_x - old_obj.center_x)**2 + (c_y - old_obj.center_y)**2)**0.5
                                    if dist < 45.0:
                                        best_old_id = old_id
                    if best_old_id is not None:
                        track_id_str = best_old_id
                        # Re-home this detection onto the OLD internal STrack so
                        # BYTETracker itself continues under the original id;
                        # otherwise it would keep emitting the new internal id
                        # every subsequent frame and the wrapper would have to
                        # re-rename forever. The superseded new STrack is
                        # retired from the pools so it cannot come back as a
                        # second identity for the same object.
                        try:
                            from ultralytics.trackers.byte_tracker import STrack as _STrack
                            bt_ = self._tracker
                            old_st = next((s for s in bt_.lost_stracks if str(s.track_id) == best_old_id), None)
                            if old_st is None:
                                old_st = next((s for s in bt_.tracked_stracks if str(s.track_id) == best_old_id), None)
                            new_st = next((s for s in bt_.tracked_stracks if str(s.track_id) == internal_id_str), None)
                            if old_st is not None:
                                _w = max(1e-3, x2 - x1)
                                _h = max(1e-3, y2 - y1)
                                _det_st = _STrack(
                                    np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0, _w, _h, 0.0], dtype=np.float32),
                                    conf,
                                    float(cls_id),
                                )
                                old_st.re_activate(_det_st, bt_.frame_id, new_id=False)
                                if old_st in bt_.lost_stracks:
                                    bt_.lost_stracks.remove(old_st)
                                if old_st not in bt_.tracked_stracks:
                                    bt_.tracked_stracks.append(old_st)
                            if new_st is not None and new_st is not old_st:
                                new_st.mark_removed()
                                if new_st in bt_.tracked_stracks:
                                    bt_.tracked_stracks.remove(new_st)
                                if new_st in bt_.lost_stracks:
                                    bt_.lost_stracks.remove(new_st)
                        except Exception as rehome_err:
                            logger.debug(f"Track re-home skipped: {rehome_err}")

                # Temporal class voting across rolling history window to eliminate label oscillation
                if not hasattr(self, "_track_class_votes"):
                    self._track_class_votes = {}
                if track_id_str not in self._track_class_votes:
                    self._track_class_votes[track_id_str] = deque(maxlen=20)
                if class_name != "object":
                    self._track_class_votes[track_id_str].append(class_name)

                if self._track_class_votes[track_id_str]:
                    from collections import Counter
                    stable_class = Counter(self._track_class_votes[track_id_str]).most_common(1)[0][0]
                else:
                    stable_class = self._track_classes.get(track_id_str, "object")
                self._track_classes[track_id_str] = stable_class

                # Center calculations
                cx = round((x1 + x2) / 2.0, 2)
                cy = round((y1 + y2) / 2.0, 2)

                # Normalized coordinates
                nx1 = max(0.0, min(1.0, round(x1 / w, 4)))
                ny1 = max(0.0, min(1.0, round(y1 / h, 4)))
                nx2 = max(0.0, min(1.0, round(x2 / w, 4)))
                ny2 = max(0.0, min(1.0, round(y2 / h, 4)))

                # Trajectory management with bounded history
                prev_track = self._active_tracks.get(track_id_str)
                if track_id_str not in self._trajectories:
                    self._trajectories[track_id_str] = deque(maxlen=self.max_trajectory_history)
                    lifecycle = "created"
                    age = 1
                    hits = 1
                    prev_cx = cx
                    prev_cy = cy
                else:
                    lifecycle = "updated"
                    age = (prev_track.age + 1) if prev_track else len(self._trajectories[track_id_str]) + 1
                    hits = (prev_track.hits + 1) if prev_track else 1
                    prev_cx = prev_track.center_x if prev_track else cx
                    prev_cy = prev_track.center_y if prev_track else cy

                # Calculate movement vector, heading and honest speed label
                trajectory_history = list(self._trajectories[track_id_str]) + [(cx, cy)]
                from backend.tracking.movement import format_speed_label
                mv = calculate_movement_vector(trajectory_history, fps=fps)
                speed_desc = format_speed_label(mv.speed_px_per_sec, not mv.is_moving)

                # Adaptive temporal bounding-box smoothing with stationary deadband
                if prev_track and prev_track.bounding_box and len(prev_track.bounding_box) >= 4 and not mv.is_moving:
                    # Stationary object deadband: strongly damp subpixel detector jitter
                    prev_b = prev_track.bounding_box
                    alpha = 0.85
                    x1 = alpha * prev_b[0] + (1.0 - alpha) * x1
                    y1 = alpha * prev_b[1] + (1.0 - alpha) * y1
                    x2 = alpha * prev_b[2] + (1.0 - alpha) * x2
                    y2 = alpha * prev_b[3] + (1.0 - alpha) * y2
                    cx = round((x1 + x2) / 2.0, 2)
                    cy = round((y1 + y2) / 2.0, 2)
                    nx1 = max(0.0, min(1.0, round(x1 / w, 4)))
                    ny1 = max(0.0, min(1.0, round(y1 / h, 4)))
                    nx2 = max(0.0, min(1.0, round(x2 / w, 4)))
                    ny2 = max(0.0, min(1.0, round(y2 / h, 4)))
                elif prev_track and prev_track.bounding_box and len(prev_track.bounding_box) >= 4 and mv.is_moving:
                    # Moving object: light EMA to damp detector jitter without lagging behind real motion
                    prev_b = prev_track.bounding_box
                    alpha = 0.4
                    x1 = alpha * prev_b[0] + (1.0 - alpha) * x1
                    y1 = alpha * prev_b[1] + (1.0 - alpha) * y1
                    x2 = alpha * prev_b[2] + (1.0 - alpha) * x2
                    y2 = alpha * prev_b[3] + (1.0 - alpha) * y2
                    cx = round((x1 + x2) / 2.0, 2)
                    cy = round((y1 + y2) / 2.0, 2)
                    nx1 = max(0.0, min(1.0, round(x1 / w, 4)))
                    ny1 = max(0.0, min(1.0, round(y1 / h, 4)))
                    nx2 = max(0.0, min(1.0, round(x2 / w, 4)))
                    ny2 = max(0.0, min(1.0, round(y2 / h, 4)))

                self._trajectories[track_id_str].append((cx, cy))
                trajectory_list = list(self._trajectories[track_id_str])

                tracked_obj = TrackedObject(
                    track_id=track_id_str,
                    object_class=stable_class,
                    confidence=round(conf, 4),
                    bounding_box=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                    normalized_box=[nx1, ny1, nx2, ny2],
                    frame_number=frame_number,
                    timestamp=timestamp,
                    center_x=cx,
                    center_y=cy,
                    prev_center_x=prev_cx,
                    prev_center_y=prev_cy,
                    velocity=(mv.dx, mv.dy),
                    speed_px_per_frame=mv.speed_px_per_frame,
                    direction_deg=mv.direction_deg,
                    cardinal_heading=mv.cardinal_heading,
                    speed_description=speed_desc,
                    lifecycle=lifecycle,
                    trajectory=trajectory_list,
                    current_zone=prev_track.current_zone if prev_track else None,
                    previous_zone=prev_track.previous_zone if prev_track else None,
                    zone_entry_time=prev_track.zone_entry_time if prev_track else None,
                    zone_dwell_seconds=prev_track.zone_dwell_seconds if prev_track else 0.0,
                    movement_state="MOVING" if mv.is_moving else "STATIONARY",
                    hits=hits,
                    age=age,
                    time_since_update=0,
                    provenance="detection",
                )

                self._active_tracks[track_id_str] = tracked_obj
                current_active_ids.add(track_id_str)

                # Track confirmation threshold (configurable via min_hits)
                if hits >= self.min_hits:
                    updated_tracks.append(tracked_obj)

        # Handle lost tracks: provide temporal grace persistence (up to track_buffer frames)
        # Prevents flickering off and on when the detector momentarily misses an object.
        # Lost tracks ALSO advance on prediction frames (predict_step), so their
        # time_since_update keeps counting at the real frame rate — previously it
        # only incremented on detection frames, so a track lost for 108 displayed
        # frames (54 s clip @ stride 2) still reported time_since_update=54 and sat
        # in a dead zone where it neither re-associated (gate was 25) nor expired.
        # Boxes of tracks updated by detections THIS frame: a lost track whose
        # extrapolated box lands on one of these is a phantom gliding over a
        # live object (typical: twin identity whose detections ended, or an
        # occluded object drifting onto its occluder). Displaying it would put
        # two identities on one object; it stays alive internally for
        # re-association but is not reported while it overlaps.
        live_boxes: List[List[float]] = [
            self._active_tracks[tid].bounding_box
            for tid in current_active_ids
            if tid in self._active_tracks
        ]
        stale_ids = [tid for tid in list(self._active_tracks.keys()) if tid not in current_active_ids]
        for tid in stale_ids:
            if tid in self._active_tracks:
                obj = self._active_tracks[tid]
                obj.time_since_update += 1

                grace_limit = self.track_buffer
                if obj.time_since_update <= grace_limit and obj.hits >= self.min_hits:
                    # Extrapolate position using velocity during the dropout so the
                    # operator sees the same ID gliding instead of blinking out.
                    dx, dy = obj.velocity
                    # For stationary objects, damp drift completely to prevent wandering
                    if abs(dx) < 1.0 and abs(dy) < 1.0:
                        dx, dy = 0.0, 0.0
                    else:
                        # Decay the drift as the dropout lengthens: by half the
                        # buffer the extrapolation has decayed to ~30% velocity,
                        # so a confidently-wrong prediction cannot run the box
                        # off-frame and steal association from the real object.
                        _decay = 0.5 ** (obj.time_since_update / (self.track_buffer * 0.5))
                        dx *= _decay
                        dec_dy = dy * _decay
                        dx = max(-25.0, min(25.0, dx))
                        dy = max(-25.0, min(25.0, dec_dy))

                    new_b = [
                        max(0.0, min(w, obj.bounding_box[0] + dx)),
                        max(0.0, min(h, obj.bounding_box[1] + dy)),
                        max(0.0, min(w, obj.bounding_box[2] + dx)),
                        max(0.0, min(h, obj.bounding_box[3] + dy)),
                    ]
                    obj.bounding_box = [round(v, 2) for v in new_b]
                    obj.center_x = round((new_b[0] + new_b[2]) / 2.0, 2)
                    obj.center_y = round((new_b[1] + new_b[3]) / 2.0, 2)
                    obj.provenance = "prediction"
                    # Phantom-over-live suppression: never report a lost track's
                    # extrapolated box on top of a live track's box.
                    _overlaps_live = any(
                        (lambda a, b: (
                            max(a[0], b[0]) < min(a[2], b[2])
                            and max(a[1], b[1]) < min(a[3], b[3])
                            and ((min(a[2], b[2]) - max(a[0], b[0])) * (min(a[3], b[3]) - max(a[1], b[1])))
                            / max((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1])
                                  - (min(a[2], b[2]) - max(a[0], b[0])) * (min(a[3], b[3]) - max(a[1], b[1])), 1e-6)
                            > 0.55
                        ))(new_b, lb)
                        for lb in live_boxes
                    )
                    if not _overlaps_live:
                        updated_tracks.append(obj)
                else:
                    # Beyond the buffer: drop wrapper state. BYTETracker still
                    # owns the authoritative lifecycle (its lost pool evicts via
                    # frame_id - end_frame > max_frames_lost) and can still
                    # re_activate() the track with its ORIGINAL id, which
                    # silently repairs this same identity gap at association
                    # level. (Previously the wrapper deleted here, so ByteTrack
                    # refinds kept an ID the wrapper had already discarded.)
                    del self._active_tracks[tid]
                    self._trajectories.pop(tid, None)
                    self._track_classes.pop(tid, None)
                    if hasattr(self, "_track_class_votes"):
                        self._track_class_votes.pop(tid, None)

        # Post-ByteTrack spatial deduplication: merge remaining duplicate tracks
        # that map to the same physical object. The pre-association NMS catches
        # most duplicates, but some slip through when IoU is borderline. Without
        # this step, two tracks coexist on one object and alternate ownership.
        if updated_tracks:
            updated_tracks = deduplicate_tracks(updated_tracks)

        return updated_tracks

    def get_active_tracks(self) -> List[TrackedObject]:
        """Return the current active tracked objects."""
        return list(self._active_tracks.values())

    def predict_step(self, frame: FrameData) -> List[TrackedObject]:
        """
        Advance tracker motion state on intermediate frames without fresh YOLO detections.
        Applies velocity displacement to active bounding boxes and trajectories.
        Returns predicted tracks explicitly tagged with provenance='prediction'.
        """
        if not self._is_initialized or frame is None:
            return []

        w = float(frame.width) if frame.width > 0 else 640.0
        h = float(frame.height) if frame.height > 0 else 480.0
        fps = frame.fps if frame.fps > 0 else self.fps
        timestamp = frame.timestamp if frame.timestamp is not None else datetime.now(timezone.utc)
        frame_number = frame.frame_number

        predicted_tracks: List[TrackedObject] = []

        strack_map = {}
        if self._tracker is not None and hasattr(self._tracker, "tracked_stracks"):
            try:
                # Advance BOTH tracked and lost tracks: on stride-2 playback a
                # track lost on frame N is still in BYTETracker's lost pool on
                # the intermediate frame. multi_predict over the lost pool also
                # keeps its Kalman state advancing so the next detection frame
                # re-associates smoothly. (Previously only tracked_stracks were
                # advanced and lost tracks' time_since_update never incremented
                # here, so a track lost for 108 displayed frames still reported
                # ~54 and sat un-re-associated until BYTETrack's own timeout.)
                from ultralytics.trackers.byte_tracker import STrack
                pool = list(self._tracker.tracked_stracks) + list(self._tracker.lost_stracks)
                STrack.multi_predict(pool)
                for st in pool:
                    if hasattr(st, "track_id"):
                        # Kalman state advances every call; read the predicted
                        # box from the state mean (tlbr property derives from it).
                        strack_map[str(st.track_id)] = st.xyxy
            except Exception as kp_err:
                logger.debug(f"STrack multi_predict skipped: {kp_err}")

        for track_id_str, prev in list(self._active_tracks.items()):
            # Lost tracks keep being predicted until the full track_buffer
            # window (matching update()'s stale-expiry), so an object missed on
            # a detection frame still glides on intermediate frames under its
            # SAME ID instead of blinking out and respawning as a new ID.
            if prev.time_since_update > self.track_buffer:
                continue

            # Advance the loss counter on prediction frames as well, so stale
            # expiry runs at the real frame rate rather than the detection rate.
            prev.time_since_update = prev.time_since_update + 1 if prev.time_since_update >= 0 else 1
            if prev.time_since_update > self.track_buffer:
                # Expired this frame: do not report a zombie box; the post-loop
                # sweep below removes the wrapper state.
                continue

            if track_id_str in strack_map:
                tlbr = strack_map[track_id_str]
                new_x1 = max(0.0, min(w, float(tlbr[0])))
                new_y1 = max(0.0, min(h, float(tlbr[1])))
                new_x2 = max(0.0, min(w, float(tlbr[2])))
                new_y2 = max(0.0, min(h, float(tlbr[3])))
            else:
                dx, dy = prev.velocity
                # Clamp displacement to avoid wild projections if velocity had sudden jitter
                dx_clamped = max(-50.0, min(50.0, dx))
                dy_clamped = max(-50.0, min(50.0, dy))

                new_x1 = max(0.0, min(w, prev.bounding_box[0] + dx_clamped))
                new_y1 = max(0.0, min(h, prev.bounding_box[1] + dy_clamped))
                new_x2 = max(0.0, min(w, prev.bounding_box[2] + dx_clamped))
                new_y2 = max(0.0, min(h, prev.bounding_box[3] + dy_clamped))

            cx = round((new_x1 + new_x2) / 2.0, 2)
            cy = round((new_y1 + new_y2) / 2.0, 2)

            nx1 = max(0.0, min(1.0, round(new_x1 / w, 4)))
            ny1 = max(0.0, min(1.0, round(new_y1 / h, 4)))
            nx2 = max(0.0, min(1.0, round(new_x2 / w, 4)))
            ny2 = max(0.0, min(1.0, round(new_y2 / h, 4)))

            if track_id_str in self._trajectories:
                self._trajectories[track_id_str].append((cx, cy))
                trajectory_list = list(self._trajectories[track_id_str])
            else:
                trajectory_list = [(cx, cy)]

            from backend.tracking.movement import format_speed_label
            mv = calculate_movement_vector(trajectory_list, fps=fps)
            speed_desc = format_speed_label(mv.speed_px_per_sec, not mv.is_moving)

            predicted_obj = TrackedObject(
                track_id=track_id_str,
                object_class=prev.object_class,
                confidence=prev.confidence,
                bounding_box=[round(new_x1, 2), round(new_y1, 2), round(new_x2, 2), round(new_y2, 2)],
                normalized_box=[nx1, ny1, nx2, ny2],
                frame_number=frame_number,
                timestamp=timestamp,
                center_x=cx,
                center_y=cy,
                prev_center_x=prev.center_x,
                prev_center_y=prev.center_y,
                velocity=(mv.dx, mv.dy),
                speed_px_per_frame=mv.speed_px_per_frame,
                direction_deg=mv.direction_deg,
                cardinal_heading=mv.cardinal_heading,
                speed_description=speed_desc,
                lifecycle="updated",
                trajectory=trajectory_list,
                current_zone=prev.current_zone,
                previous_zone=prev.previous_zone,
                zone_entry_time=prev.zone_entry_time,
                zone_dwell_seconds=prev.zone_dwell_seconds,
                movement_state="MOVING" if mv.is_moving else "STATIONARY",
                hits=prev.hits,
                age=prev.age + 1,
                time_since_update=prev.time_since_update,
                provenance="prediction",
            )
            self._active_tracks[track_id_str] = predicted_obj
            predicted_tracks.append(predicted_obj)

        # Expire stale tracks on prediction frames too: with stride >= 2 a track
        # can otherwise outlive its intended track_buffer timeout by up to 2x
        # real time (expiry previously only ran inside update()).
        expired = [
            tid for tid, obj in self._active_tracks.items()
            if obj.time_since_update > self.track_buffer
        ]
        for tid in expired:
            del self._active_tracks[tid]
            self._trajectories.pop(tid, None)
            self._track_classes.pop(tid, None)
            if hasattr(self, "_track_class_votes"):
                self._track_class_votes.pop(tid, None)

        return predicted_tracks
