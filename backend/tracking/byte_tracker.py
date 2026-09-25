"""
Border Intelligence Native BYTETracker Module.
Implements the BYTETrack multi-object tracking algorithm (Zhang et al., ECCV 2022)
with two-stage association (high-confidence + low-confidence detections),
IoU matching, and Kalman Filter state management.
"""
from __future__ import annotations
from enum import IntEnum
from typing import Any, List, Optional, Tuple
import numpy as np

from backend.tracking.kalman_filter import KalmanFilterXYAH


class TrackState(IntEnum):
    New = 0
    Tracked = 1
    Lost = 2
    Removed = 3


def bbox_ious(atlbr: np.ndarray, btlbr: np.ndarray) -> np.ndarray:
    """
    Compute pairwise IoU between two sets of boxes [x1, y1, x2, y2].
    """
    if len(atlbr) == 0 or len(btlbr) == 0:
        return np.zeros((len(atlbr), len(btlbr)), dtype=np.float32)

    atlbr = np.ascontiguousarray(atlbr, dtype=np.float32)
    btlbr = np.ascontiguousarray(btlbr, dtype=np.float32)

    ious = np.zeros((len(atlbr), len(btlbr)), dtype=np.float32)

    for i, a in enumerate(atlbr):
        area_a = max(0.0, (a[2] - a[0])) * max(0.0, (a[3] - a[1]))
        for j, b in enumerate(btlbr):
            area_b = max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1]))
            xx1 = max(a[0], b[0])
            yy1 = max(a[1], b[1])
            xx2 = min(a[2], b[2])
            yy2 = min(a[3], b[3])
            w = max(0.0, xx2 - xx1)
            h = max(0.0, yy2 - yy1)
            inter = w * h
            union = area_a + area_b - inter
            ious[i, j] = inter / union if union > 0 else 0.0

    return ious


def linear_assignment(cost_matrix: np.ndarray, thresh: float) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """
    Hungarian linear sum assignment with cost threshold.
    Uses greedy matching as robust pure-NumPy baseline with zero external C-dependencies.
    """
    if cost_matrix.size == 0:
        return [], list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

    try:
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matches = []
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] <= thresh:
                matches.append((int(r), int(c)))
        matched_rows = {r for r, _ in matches}
        matched_cols = {c for _, c in matches}
        unmatched_a = [i for i in range(cost_matrix.shape[0]) if i not in matched_rows]
        unmatched_b = [j for j in range(cost_matrix.shape[1]) if j not in matched_cols]
        return matches, unmatched_a, unmatched_b
    except ImportError:
        pass

    # Greedy linear assignment fallback
    matches = []
    unmatched_a = set(range(cost_matrix.shape[0]))
    unmatched_b = set(range(cost_matrix.shape[1]))

    # Flatten indices sorted by cost ascending
    sorted_indices = np.argsort(cost_matrix, axis=None)
    num_cols = cost_matrix.shape[1]

    for idx in sorted_indices:
        r = int(idx // num_cols)
        c = int(idx % num_cols)
        if cost_matrix[r, c] > thresh:
            break
        if r in unmatched_a and c in unmatched_b:
            matches.append((r, c))
            unmatched_a.remove(r)
            unmatched_b.remove(c)

    return matches, sorted(list(unmatched_a)), sorted(list(unmatched_b))


class STrack:
    """Single tracked object state with Kalman filter."""
    shared_kalman = KalmanFilterXYAH()
    _count = 0

    def __init__(self, tlwh: np.ndarray, score: float, cls: Any = 0):
        # tlwh: [top, left, width, height]
        self._tlwh = np.asarray(tlwh, dtype=np.float32)
        self.kalman_filter: Optional[KalmanFilterXYAH] = None
        self.mean: Optional[np.ndarray] = None
        self.covariance: Optional[np.ndarray] = None
        self.is_activated = False

        self.score = float(score)
        self.tracklet_len = 0
        self.cls = cls
        self.track_id = 0
        self.state = TrackState.New
        self.frame_id = 0
        self.start_frame = 0

    @classmethod
    def next_id(cls) -> int:
        cls._count += 1
        return cls._count

    @property
    def tlwh(self) -> np.ndarray:
        if self.mean is None:
            return self._tlwh.copy()
        ret = self.mean[:4].copy()
        ret[2] *= ret[3]
        ret[:2] -= ret[2:] / 2
        return ret

    @property
    def tlbr(self) -> np.ndarray:
        ret = self.tlwh.copy()
        ret[2:] += ret[:2]
        return ret

    @staticmethod
    def tlwh_to_xyah(tlwh: np.ndarray) -> np.ndarray:
        ret = np.asarray(tlwh).copy()
        ret[:2] += ret[2:] / 2
        ret[2] /= ret[3] if ret[3] > 0 else 1.0
        return ret

    def to_xyah(self) -> np.ndarray:
        return self.tlwh_to_xyah(self.tlwh)

    def activate(self, kalman_filter: KalmanFilterXYAH, frame_id: int) -> None:
        self.kalman_filter = kalman_filter
        self.track_id = self.next_id()
        self.mean, self.covariance = self.kalman_filter.initiate(self.to_xyah())
        self.tracklet_len = 0
        self.state = TrackState.Tracked
        if frame_id == 1:
            self.is_activated = True
        self.frame_id = frame_id
        self.start_frame = frame_id

    def re_activate(self, new_track: STrack, frame_id: int, new_id: bool = False) -> None:
        if self.kalman_filter is None:
            self.kalman_filter = KalmanFilterXYAH()
        self.mean, self.covariance = self.kalman_filter.update(
            self.mean, self.covariance, self.tlwh_to_xyah(new_track.tlwh)
        )
        self.tracklet_len = 0
        self.state = TrackState.Tracked
        self.is_activated = True
        self.frame_id = frame_id
        if new_id:
            self.track_id = self.next_id()
        self.score = new_track.score
        self.cls = new_track.cls

    def update(self, new_track: STrack, frame_id: int) -> None:
        self.frame_id = frame_id
        self.tracklet_len += 1
        new_tlwh = new_track.tlwh
        if self.kalman_filter is None:
            self.kalman_filter = KalmanFilterXYAH()
        self.mean, self.covariance = self.kalman_filter.update(
            self.mean, self.covariance, self.tlwh_to_xyah(new_tlwh)
        )
        self.state = TrackState.Tracked
        self.is_activated = True
        self.score = new_track.score
        self.cls = new_track.cls

    def predict(self) -> None:
        mean_state = self.mean.copy()
        if self.state != TrackState.Tracked:
            mean_state[7] = 0
        if self.kalman_filter is None:
            self.kalman_filter = KalmanFilterXYAH()
        self.mean, self.covariance = self.kalman_filter.predict(mean_state, self.covariance)

    def mark_lost(self) -> None:
        self.state = TrackState.Lost

    def mark_removed(self) -> None:
        self.state = TrackState.Removed


class BYTETracker:
    """
    BYTETrack: Multi-Object Tracking by Associating Every Detection Box.
    """

    def __init__(
        self,
        args: Any = None,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
        frame_rate: int = 30,
    ) -> None:
        if args is not None:
            self.track_thresh = getattr(args, "track_high_thresh", getattr(args, "track_thresh", track_thresh))
            self.track_low_thresh = getattr(args, "track_low_thresh", 0.04)
            self.new_track_thresh = getattr(args, "new_track_thresh", self.track_thresh)
            self.match_thresh = getattr(args, "match_thresh", match_thresh)
            self.track_buffer = getattr(args, "track_buffer", track_buffer)
            self.frame_rate = getattr(args, "frame_rate", frame_rate)
        else:
            self.track_thresh = track_thresh
            self.track_low_thresh = 0.04
            self.new_track_thresh = track_thresh
            self.match_thresh = match_thresh
            self.track_buffer = track_buffer
            self.frame_rate = frame_rate

        self.tracked_stracks: List[STrack] = []
        self.lost_stracks: List[STrack] = []
        self.removed_stracks: List[STrack] = []

        self.frame_id = 0
        self.max_time_lost = int(self.frame_rate / 30.0 * self.track_buffer)
        self.kalman_filter = KalmanFilterXYAH()

    def update(self, output_results: Any, *args: Any, **kwargs: Any) -> np.ndarray:
        """
        Process detections for current frame and return active tracked targets as:
        [x1, y1, x2, y2, track_id, score, cls, idx]
        """
        self.frame_id += 1
        activated_stracks: List[STrack] = []
        refind_stracks: List[STrack] = []
        lost_stracks: List[STrack] = []
        removed_stracks: List[STrack] = []

        if hasattr(output_results, "xyxy"):
            xyxy = output_results.xyxy.cpu().numpy() if hasattr(output_results.xyxy, "cpu") else np.asarray(output_results.xyxy)
            conf = output_results.conf.cpu().numpy() if hasattr(output_results.conf, "cpu") else np.asarray(output_results.conf)
            cls = output_results.cls.cpu().numpy() if hasattr(output_results.cls, "cpu") else np.asarray(output_results.cls)
            if len(xyxy) > 0:
                output_results = np.column_stack([xyxy, conf, cls])
            else:
                output_results = np.zeros((0, 6))
        elif hasattr(output_results, "cpu"):
            output_results = output_results.cpu().numpy()
        output_results = np.asarray(output_results)

        scores = output_results[:, 4] if len(output_results) > 0 else np.array([])
        bboxes = output_results[:, :4] if len(output_results) > 0 else np.array([])
        classes = output_results[:, 5] if len(output_results) > 0 and output_results.shape[1] > 5 else np.zeros(len(scores))

        remain_inds = scores > self.track_thresh
        inds_low = scores > 0.1
        inds_high = remain_inds
        inds_second = np.logical_and(inds_low, np.logical_not(remain_inds))

        # Split detections into D_high and D_low
        dets_second = bboxes[inds_second]
        scores_second = scores[inds_second]
        cls_second = classes[inds_second]

        dets = bboxes[inds_high]
        scores_keep = scores[inds_high]
        cls_keep = classes[inds_high]

        # Convert [x1, y1, x2, y2] to [x1, y1, w, h]
        def to_tlwh(boxes):
            if len(boxes) == 0:
                return []
            res = boxes.copy()
            res[:, 2] -= res[:, 0]
            res[:, 3] -= res[:, 1]
            return res

        tlwh_first = to_tlwh(dets)
        detections = [STrack(tlwh_first[i], scores_keep[i], cls_keep[i]) for i in range(len(dets))]

        # Predict current locations with Kalman Filter
        unconfirmed = []
        tracked_stracks = []
        for track in self.tracked_stracks:
            if not track.is_activated:
                unconfirmed.append(track)
            else:
                tracked_stracks.append(track)

        strack_pool = tracked_stracks + self.lost_stracks
        for track in strack_pool:
            track.predict()

        # Association Step 1: Match D_high with Tracked & Lost tracks
        if len(strack_pool) > 0 and len(detections) > 0:
            track_boxes = np.array([t.tlbr for t in strack_pool])
            det_boxes = np.array([d.tlbr for d in detections])
            ious = bbox_ious(track_boxes, det_boxes)
            dists = 1.0 - ious
            matches, u_track, u_detection = linear_assignment(dists, thresh=self.match_thresh)
        else:
            matches = []
            u_track = list(range(len(strack_pool)))
            u_detection = list(range(len(detections)))

        for itracked, idet in matches:
            track = strack_pool[itracked]
            det = detections[idet]
            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        # Association Step 2: Match D_low with remaining unmatched tracks
        tlwh_second = to_tlwh(dets_second)
        detections_second = [STrack(tlwh_second[i], scores_second[i], cls_second[i]) for i in range(len(dets_second))]
        r_tracked_stracks = [strack_pool[i] for i in u_track if strack_pool[i].state == TrackState.Tracked]

        if len(r_tracked_stracks) > 0 and len(detections_second) > 0:
            track_boxes = np.array([t.tlbr for t in r_tracked_stracks])
            det_boxes = np.array([d.tlbr for d in detections_second])
            ious = bbox_ious(track_boxes, det_boxes)
            dists = 1.0 - ious
            matches, u_track_second, _ = linear_assignment(dists, thresh=0.5)
        else:
            matches = []
            u_track_second = list(range(len(r_tracked_stracks)))

        for itracked, idet in matches:
            track = r_tracked_stracks[itracked]
            det = detections_second[idet]
            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        for it in u_track_second:
            track = r_tracked_stracks[it]
            if track.state != TrackState.Lost:
                track.mark_lost()
                lost_stracks.append(track)

        # Association Step 3: Match remaining unconfirmed tracks with unmatched high detections
        detections_post = [detections[i] for i in u_detection]
        if len(unconfirmed) > 0 and len(detections_post) > 0:
            track_boxes = np.array([t.tlbr for t in unconfirmed])
            det_boxes = np.array([d.tlbr for d in detections_post])
            ious = bbox_ious(track_boxes, det_boxes)
            dists = 1.0 - ious
            matches, u_unconfirmed, u_detection_final = linear_assignment(dists, thresh=0.7)
        else:
            matches = []
            u_unconfirmed = list(range(len(unconfirmed)))
            u_detection_final = list(range(len(detections_post)))

        for itracked, idet in matches:
            unconfirmed[itracked].update(detections_post[idet], self.frame_id)
            activated_stracks.append(unconfirmed[itracked])

        for it in u_unconfirmed:
            track = unconfirmed[it]
            track.mark_removed()
            removed_stracks.append(track)

        # Initialize new tracks from unmatched high detections
        for inew in u_detection_final:
            track = detections_post[inew]
            if track.score < self.track_thresh:
                continue
            track.activate(self.kalman_filter, self.frame_id)
            activated_stracks.append(track)

        # Update state pools
        for track in self.lost_stracks:
            if self.frame_id - track.frame_id > self.max_time_lost:
                track.mark_removed()
                removed_stracks.append(track)

        self.tracked_stracks = [t for t in self.tracked_stracks if t.state == TrackState.Tracked]
        self.tracked_stracks = list(dict.fromkeys(self.tracked_stracks + activated_stracks + refind_stracks))
        self.lost_stracks = [t for t in self.lost_stracks if t.state == TrackState.Lost]
        self.lost_stracks.extend(lost_stracks)
        self.removed_stracks.extend(removed_stracks)

        output_stracks = [t for t in self.tracked_stracks if t.is_activated]
        outputs = []
        for t in output_stracks:
            box = t.tlbr
            outputs.append([box[0], box[1], box[2], box[3], t.track_id, t.score, t.cls, getattr(t, "idx", 0)])
        return np.asarray(outputs, dtype=np.float32) if outputs else np.zeros((0, 8), dtype=np.float32)
