"""
Regression tests for the ByteTrack identity-stability fix.

Locks in the root-cause fixes for the #714 -> #726 -> #714 fragmentation:
  1. cross-class duplicate detection suppression (bus+truck twin boxes on one
     vehicle must not spawn two tracks),
  2. identity-family re-association fallback (label oscillation must not block
     the rename; the superseded internal track must be retired),
  3. lost tracks advance and expire on prediction frames too,
  4. one object keeps ONE id across detection + prediction frames, and
  5. stale tracks disappear only after track_buffer.
"""
import numpy as np
import pytest

from backend.detection.detector import DetectionResult
from backend.ingestion.adapter import FrameData
from backend.tracking.bytetrack_wrapper import (
    ByteTrackTracker,
    _same_identity_family,
    suppress_duplicate_detections,
)


def _det(cls_id, cls_name, conf, box):
    return DetectionResult(
        class_id=cls_id,
        class_name=cls_name,
        confidence=conf,
        bounding_box=list(box),
        normalized_box=[0.0, 0.0, 0.0, 0.0],
    )


def _frame(fn, fps=30.0):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    return FrameData(
        camera_id="T", frame_number=fn,
        timestamp=None, image=img, width=640, height=480, fps=fps,
    )


def _feed(tracker, detections, fn):
    return tracker.update(detections, _frame(fn))


class TestDuplicateSuppression:
    def test_cross_class_twin_boxes_merged(self):
        # one physical bus: twin bus+truck boxes at IoU ~0.9
        dets = [
            _det(5, "bus", 0.35, [100, 100, 260, 300]),
            _det(7, "truck", 0.30, [104, 98, 264, 302]),
        ]
        kept = suppress_duplicate_detections(dets)
        assert len(kept) == 1
        assert kept[0].class_name == "bus"  # higher confidence kept

    def test_distinct_objects_preserved(self):
        # two spatially separate cars
        dets = [
            _det(2, "car", 0.6, [10, 10, 60, 40]),
            _det(2, "car", 0.5, [300, 200, 400, 260]),
        ]
        kept = suppress_duplicate_detections(dets)
        assert len(kept) == 2

    def test_nested_vehicle_person_pairs_survive(self):
        # person next to a car: low IoU, both must survive
        dets = [
            _det(2, "car", 0.7, [10, 10, 200, 160]),
            _det(0, "person", 0.5, [210, 60, 240, 150]),
        ]
        kept = suppress_duplicate_detections(dets)
        assert len(kept) == 2

    def test_same_object_keeps_single_track_despite_twin_boxes(self):
        tracker = ByteTrackTracker()
        tracker.initialize()
        # frame 1: bus twin boxes -> must produce ONE track, not two
        tracks = _feed(tracker, [
            _det(5, "bus", 0.35, [100, 100, 260, 300]),
            _det(7, "truck", 0.30, [104, 98, 264, 302]),
        ], 1)
        assert len(tracks) == 1
        first_id = tracks[0].track_id
        # frame 3: label flips to truck; same box -> same track id
        tracks = _feed(tracker, [
            _det(7, "truck", 0.42, [102, 100, 262, 300]),
        ], 3)
        assert len(tracks) == 1
        assert tracks[0].track_id == first_id


class TestIdentityFamily:
    def test_vehicle_labels_same_family(self):
        assert _same_identity_family("bus", "truck")
        assert _same_identity_family("car", "bus")
        assert _same_identity_family("truck", "car")
        assert _same_identity_family("motorcycle", "car")

    def test_person_not_in_vehicle_family(self):
        assert not _same_identity_family("person", "car")
        assert not _same_identity_family("person", "bus")

    def test_object_generic_matches(self):
        assert _same_identity_family("object", "car")
        assert _same_identity_family("person", "object")


class TestLostTrackLifecycle:
    def test_lost_track_predicted_until_buffer_then_dropped(self):
        tracker = ByteTrackTracker(track_buffer=5)
        tracker.initialize()
        # create a track
        tracks = _feed(tracker, [_det(2, "car", 0.8, [100, 100, 180, 180])], 1)
        assert len(tracks) == 1
        tid = tracks[0].track_id
        # starve the tracker: no detections for track_buffer frames,
        # WITH prediction frames in between (stride-2 pattern)
        reported_last = None
        for fn in range(2, 14):
            if (fn - 1) % 2 != 0:
                tracker.predict_step(_frame(fn))
                continue
            out = _feed(tracker, [], fn)
            active_ids = [t.track_id for t in out]
            if fn - 1 <= 5:  # within buffer: may still be reported
                reported_last = fn
        # after buffer is exceeded the track must be gone
        active = [t.track_id for t in tracker.get_active_tracks()]
        assert tid not in active

    def test_no_duplicate_ids_for_one_object(self):
        tracker = ByteTrackTracker()
        tracker.initialize()
        ids_seen = set()
        # object drifting slowly right, detection every 2nd frame,
        # occasional dropouts (every 5th detection frame missed)
        box = [100.0, 100.0, 180.0, 180.0]
        for fn in range(1, 61):
            if (fn - 1) % 2 != 0:
                tracker.predict_step(_frame(fn))
                continue
            if fn % 10 == 0:
                out = _feed(tracker, [], fn)  # dropout
            else:
                box = [box[0] + 1.0, box[1], box[2] + 1.0, box[3]]
                out = _feed(tracker, [_det(2, "car", 0.7, box)], fn)
            for t in out:
                ids_seen.add(t.track_id)
        # exactly ONE id for the whole sequence (dropout gaps bridged)
        assert len(ids_seen) == 1

    def test_stale_expiry_happens_after_buffer_not_before(self):
        tracker = ByteTrackTracker(track_buffer=4)
        tracker.initialize()
        _feed(tracker, [_det(2, "car", 0.8, [100, 100, 180, 180])], 1)
        tid = tracker.get_active_tracks()[0].track_id
        # ByteTrack semantics: a track survives EXACTLY track_buffer lost
        # frames and is removed when time_since_update exceeds the buffer —
        # counting BOTH detection and prediction frames (the stride case).
        last_reported_fn = None
        gone_at = None
        for fn in range(2, 20):
            if (fn - 1) % 2 != 0:
                out = tracker.predict_step(_frame(fn))
            else:
                out = _feed(tracker, [], fn)
            if any(t.track_id == tid for t in out):
                last_reported_fn = fn
            active = [t.track_id for t in tracker.get_active_tracks()]
            if tid not in active and gone_at is None:
                gone_at = fn
        # lost frames are fn 2..5 (tsu 1..4 == buffer): still reported through
        # fn 5, removed on the 5th lost frame (tsu 5 > 4)
        assert last_reported_fn == 5
        assert gone_at == 6
