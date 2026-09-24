"""
Global Identity Manager — multi-camera person Re-ID layer.

Sits ABOVE the per-camera ByteTrack trackers (which stay untouched and keep
their local IDs). Each camera periodically embeds crops of its stable person
tracks; this module compares those embeddings against known global identities
and maintains the mapping:

    CAM-01 local #42  ─┐
                       ├──> Global Person #G102
    CAM-02 local  #7  ─┘

Design constraints (deliberate):
  * Person appearance Re-ID ONLY — this is NOT face recognition, not a
    watchlist, and not biometric identification. No face crops, no identity DB.
  * Conservative matching: below-threshold similarity is UNKNOWN, never forced.
    Two people in similar clothes must NOT merge (min margin against the best
    competing identity, multi-observation confirmation for new links).
  * Explainability: every match decision records score, threshold, margin and
    the reason it matched or didn't.
  * Session-scoped identity state (in-memory). Global IDs do NOT persist across
    backend restarts: restarting resets perception, and stale identities must
    not silently attach to new footage. Event HISTORY keeps whatever global id
    was assigned at the time.
  * Bounded memory: per-identity embedding history and per-camera/track caches
    are capped; identities expire after `identity_ttl_seconds`.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model metadata (documented per requirement §2 / §16)
# ---------------------------------------------------------------------------
def _get_reid_weights_path() -> str:
    """Resolve ReID model path from centralized config."""
    try:
        from pathlib import Path
        from backend.config import get_settings
        return str(Path(get_settings().MODELS_DIR) / "reid" / "osnet_x0_25_msmt17.onnx")
    except Exception:
        return "models/reid/osnet_x0_25_msmt17.onnx"

REID_MODEL_INFO = {
    "model": "OSNet-x0.25 (Omni-Scale Network)",
    "weights": _get_reid_weights_path(),
    "trained_on": "MSMT17 (person re-identification, 15 cameras)",
    "source": "https://huggingface.co/anriha/osnet_x0_25_msmt17",
    "license": "MIT (model export); OSNet code BSD-3 (KaiyangZhou/deep-person-reid)",
    "size_bytes": 907_171,
    "params": "~0.24M (x0.25 width variant)",
    "input": "NCHW float32, 1x3x256x128 (H=256, W=128), RGB, /255 normalized",
    "embedding_dim": 512,
    "cpu_latency_ms_measured": 4.2,
}


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(np.dot(a, b))


@dataclass
class MatchDecision:
    """Explainable result of an association attempt."""
    global_id: Optional[str]
    matched: bool
    score: float            # best similarity (or 0.0)
    margin: float           # best minus second-best competing similarity
    reason: str
    candidate_count: int = 0


@dataclass
class _Observation:
    embedding: np.ndarray
    camera_id: str
    ts: float


@dataclass
class GlobalIdentity:
    global_id: str
    embeddings: List[_Observation] = field(default_factory=list)  # capped ring
    last_camera: str = ""
    last_seen_ts: float = 0.0
    first_seen_ts: float = 0.0
    confirmed: bool = False            # confirmed cross-camera identity?
    local_ids: Dict[str, str] = field(default_factory=dict)  # camera -> last local id

    def mean_embedding(self, max_obs: int = 16) -> np.ndarray:
        obs = self.embeddings[-max_obs:]
        return np.mean([o.embedding for o in obs], axis=0)


@dataclass
class _TrackState:
    """Per (camera, local track) embedding cache."""
    embeddings: List[_Observation] = field(default_factory=list)  # capped
    global_id: Optional[str] = None
    confirmed: bool = False       # link confirmed by >= confirm_observations matches?
    match_streak: int = 0
    last_ts: float = 0.0


class GlobalIdentityManager:
    """
    One instance per backend process. Thread-safe (workers embed on their own
    threads; zone/event threads read labels).
    """

    def __init__(
        self,
        similarity_threshold: float = 0.62,     # conservative MSMT17-cosine gate
        margin_threshold: float = 0.08,          # must beat 2nd-best by this much
        confirm_observations: int = 3,           # consecutive matches to confirm link
        max_embeddings_per_identity: int = 24,
        max_embeddings_per_track: int = 8,
        identity_ttl_seconds: float = 15 * 60.0, # expire identities after 15 min
        track_cache_ttl_seconds: float = 3 * 60.0,
        min_time_between_embeddings_s: float = 0.9,  # Re-ID sampling rate per track
        crop_min_height_px: int = 40,            # reject tiny/unusable person crops
        crop_min_sharpness: float = 12.0,        # Laplacian variance quality gate
        transition_window_seconds: float = 45.0, # cross-camera gap must be < this
        same_camera_lock_seconds: float = 8.0,   # identities of OTHER live tracks
        topology: Optional[Any] = None,
        use_topology: bool = True,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.margin_threshold = margin_threshold
        self.confirm_observations = confirm_observations
        self.max_embeddings_per_identity = max_embeddings_per_identity
        self.max_embeddings_per_track = max_embeddings_per_track
        self.identity_ttl_seconds = identity_ttl_seconds
        self.track_cache_ttl_seconds = track_cache_ttl_seconds
        self.min_time_between_embeddings_s = min_time_between_embeddings_s
        self.crop_min_height_px = crop_min_height_px
        self.crop_min_sharpness = crop_min_sharpness
        self.transition_window_seconds = transition_window_seconds
        self.same_camera_lock_seconds = same_camera_lock_seconds
        self.use_topology = use_topology
        if topology is not None:
            self.topology = topology
        else:
            try:
                from backend.topology.service import get_topology
                self.topology = get_topology()
            except Exception:
                self.topology = None

        self._identities: "OrderedDict[str, GlobalIdentity]" = OrderedDict()
        self._track_state: Dict[Tuple[str, str], _TrackState] = {}
        self._next_global_num = 1
        self._lock = threading.RLock()
        self._last_embed_ts: Dict[Tuple[str, str], float] = {}

        # metrics
        self.metrics = {
            "embeddings_computed": 0,
            "embeddings_skipped_quality": 0,
            "embeddings_skipped_rate": 0,
            "match_attempts": 0,
            "matches_new_identity": 0,
            "matches_linked": 0,
            "matches_unknown": 0,
            "matches_low_margin": 0,
            "links_confirmed": 0,
        }

    # ------------------------------------------------------------- embedding
    def _load_session(self):
        import os
        import onnxruntime as ort
        weights = REID_MODEL_INFO["weights"]
        if not os.path.exists(weights):
            return None
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1  # tiny model; keep footprint minimal
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return ort.InferenceSession(weights, opts, providers=["CPUExecutionProvider"])

    def initialize(self) -> None:
        """Load the ONNX Re-ID session (idempotent, safe to call at boot)."""
        with self._lock:
            if getattr(self, "_session", None) is not None:
                return
            try:
                self._session = self._load_session()
                if self._session is not None:
                    logger.info(
                        f"Re-ID model loaded: {REID_MODEL_INFO['model']} "
                        f"({REID_MODEL_INFO['size_bytes'] // 1024} KB, "
                        f"dim={REID_MODEL_INFO['embedding_dim']})"
                    )
            except Exception as err:
                logger.warning(f"Re-ID model failed to load (Re-ID disabled): {err}")
                self._session = None

    @property
    def enabled(self) -> bool:
        return getattr(self, "_session", None) is not None

    def compute_embedding(self, image_bgr: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Embed a person crop. Returns None if the crop is too small / blurry —
        the caller must treat that as 'no observation', never as evidence of
        anything. Quality gates keep embeddings explainable and bounded.
        """
        if not self.enabled or image_bgr is None or image_bgr.size == 0:
            return None
        try:
            import cv2
            h_img, w_img = image_bgr.shape[:2]
            x1, y1, x2, y2 = bbox
            x1 = max(0, int(x1)); y1 = max(0, int(y1))
            x2 = min(w_img, int(x2)); y2 = min(h_img, int(y2))
            if x2 - x1 < 12 or y2 - y1 < self.crop_min_height_px:
                self.metrics["embeddings_skipped_quality"] += 1
                return None
            crop = image_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                self.metrics["embeddings_skipped_quality"] += 1
                return None
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            if sharpness < self.crop_min_sharpness:
                self.metrics["embeddings_skipped_quality"] += 1
                return None

            h, w = crop.shape[:2]
            target_h, target_w = 256, 128
            scale = max(target_w / w, target_h / h)
            crop = cv2.resize(crop, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                              interpolation=cv2.INTER_LINEAR)
            top = (crop.shape[0] - target_h) // 2
            left = (crop.shape[1] - target_w) // 2
            crop = crop[top:top + target_h, left:left + target_w]

            blob = crop[:, :, ::-1].astype(np.float32) / 255.0       # BGR->RGB, /255
            blob = np.transpose(blob, (2, 0, 1))[None]               # HWC->CHW, N=1
            out = self._session.run(None, {self._session.get_inputs()[0].name: blob})[0]
            emb = out[0]
            self.metrics["embeddings_computed"] += 1
            return emb
        except Exception as err:
            logger.debug(f"Re-ID embedding failed: {err}")
            return None

    # ------------------------------------------------------- bookkeeping
    def _expire(self, now: float) -> None:
        dead_ids = [gid for gid, gi in self._identities.items()
                    if now - gi.last_seen_ts > self.identity_ttl_seconds]
        for gid in dead_ids:
            del self._identities[gid]
        dead_tracks = [k for k, st in self._track_state.items()
                       if now - st.last_ts > self.track_cache_ttl_seconds]
        for k in dead_tracks:
            del self._track_state[k]

    def _new_global_id(self) -> str:
        gid = f"G{self._next_global_num}"
        self._next_global_num += 1
        return gid

    # ------------------------------------------------------- association
    def observe(
        self,
        camera_id: str,
        track_id: str,
        embedding: np.ndarray,
        ts: Optional[float] = None,
    ) -> MatchDecision:
        """
        Feed one embedding observation for a (camera, local track). Returns the
        (possibly newly created) global identity with an explainable decision.
        """
        now = time.time() if ts is None else ts
        with self._lock:
            self._expire(now)
            key = (str(camera_id), str(track_id))
            state = self._track_state.get(key)
            if state is None:
                state = _TrackState(last_ts=now)
                self._track_state[key] = state

            state.last_ts = now
            state.embeddings.append(_Observation(embedding, str(camera_id), now))
            if len(state.embeddings) > self.max_embeddings_per_track:
                state.embeddings = state.embeddings[-self.max_embeddings_per_track:]

            self.metrics["match_attempts"] += 1

            # ---- Step 1: continuity on the SAME (camera, track) -------------
            # If this local track is already linked to an identity, similarity
            # with THAT identity decides first. This is what keeps a person on
            # one camera under one global id without any cross-camera logic and
            # prevents the same-camera lock below from exploding identities.
            if state.global_id is not None:
                gi = self._identities.get(state.global_id)
                if gi is not None:
                    score = cosine_similarity(embedding, gi.mean_embedding())
                    if score >= self.similarity_threshold:
                        state.match_streak += 1
                        state.confirmed = state.match_streak >= self.confirm_observations
                        gi.embeddings.append(_Observation(embedding, str(camera_id), now))
                        if len(gi.embeddings) > self.max_embeddings_per_identity:
                            gi.embeddings = gi.embeddings[-self.max_embeddings_per_identity:]
                        gi.last_camera = str(camera_id)
                        gi.last_seen_ts = now
                        gi.local_ids[str(camera_id)] = str(track_id)
                        if not gi.confirmed and state.confirmed:
                            gi.confirmed = True
                            self.metrics["links_confirmed"] += 1
                        self.metrics["matches_linked"] += 1
                        return MatchDecision(
                            gi.global_id, True, float(score), 0.0,
                            f"continuity on {camera_id}#{track_id}: cosine={score:.3f}"
                            f", streak={state.match_streak}/{self.confirm_observations}"
                            f"{', CONFIRMED' if gi.confirmed else ''}",
                            len(self._identities),
                        )
                    # fell below threshold with its own identity: treat as a
                    # changed appearance; search for a better candidate below
                    # (the old link stays until something better confirms).

            # ---- Step 2: cross-camera candidate search ----------------------
            # Exclusion rule (same-camera lock), refined for respawn: an
            # identity last seen on THIS camera is excluded only while its last
            # local track here is STILL BEING OBSERVED (another live person on
            # this camera). If that track has gone quiet, the identity is the
            # same person whose local track ByteTrack just respawned (occlusion,
            # detector dropout) — matching it is exactly what preserves one
            # identity across a local ID change.
            best_gid, best_score, second_score, best_reason = None, -1.0, -1.0, ""
            current_gid = state.global_id
            for gid, gi in self._identities.items():
                if gi.last_camera == str(camera_id):
                    last_local_track = gi.local_ids.get(str(camera_id))
                    other_state = self._track_state.get((str(camera_id), str(last_local_track))) \
                        if last_local_track else None
                    other_alive = (
                        other_state is not None
                        and last_local_track != str(track_id)
                        and now - other_state.last_ts < self.same_camera_lock_seconds
                    )
                    if other_alive:
                        continue
                ref = gi.mean_embedding()
                score = cosine_similarity(embedding, ref)
                gap = now - gi.last_seen_ts
                confirmed_here = gi.last_camera == str(camera_id) and gi.confirmed
                if gap > self.transition_window_seconds and not confirmed_here:
                    continue

                # Topological plausibility gate for cross-camera transitions
                topo_factor = 1.0
                if gi.last_camera != str(camera_id) and self.use_topology and self.topology is not None:
                    is_plausible, topo_factor, _ = self.topology.evaluate_transition_plausibility(
                        gi.last_camera, str(camera_id), gap
                    )
                    if not is_plausible:
                        # Reject candidates that violate physical topology / transition constraints
                        continue
                    # Scale score with topology factor (80% appearance, 20% topological plausibility)
                    score = score * (0.80 + 0.20 * topo_factor)

                # Sticky confirmed links: a track with a CONFIRMED identity may
                # only switch when a candidate decisively beats it. This kills
                # mid-track identity flips caused by one noisy observation.
                if (
                    current_gid is not None
                    and current_gid == self._track_state.get(key).global_id
                    and self._track_state.get(key).confirmed
                    and gid != current_gid
                ):
                    cur_gi = self._identities.get(current_gid)
                    if cur_gi is not None:
                        cur_score = cosine_similarity(embedding, cur_gi.mean_embedding())
                        if score < cur_score + self.margin_threshold:
                            continue
                if score > best_score:
                    second_score = best_score
                    best_score, best_gid = score, gid
                    best_reason = f"cosine={score:.3f} (topo={topo_factor:.2f}) vs mean of {len(gi.embeddings)} obs"
                elif score > second_score:
                    second_score = score

            margin = (best_score - second_score) if best_gid is not None else 0.0

            # ---- decision ----------------------------------------------------
            if best_gid is None or best_score < self.similarity_threshold:
                gid = self._new_global_id()
                gi = GlobalIdentity(global_id=gid, last_camera=str(camera_id),
                                    last_seen_ts=now, first_seen_ts=now,
                                    local_ids={str(camera_id): str(track_id)})
                gi.embeddings.append(_Observation(embedding, str(camera_id), now))
                self._identities[gid] = gi
                state.global_id = gid
                state.match_streak = 1
                self.metrics["matches_new_identity"] += 1
                return MatchDecision(gid, False, float(max(best_score, 0.0)), 0.0,
                                     "no candidate above threshold; created new identity",
                                     len(self._identities))

            if margin < self.margin_threshold and best_score < 0.80:
                # Ambiguous: two identities look almost as similar. Conservative
                # behavior is to NOT link (still report the best candidate id as
                # unconfirmed candidate via decision, but don't merge).
                self.metrics["matches_low_margin"] += 1
                gi = self._identities[best_gid]
                return MatchDecision(
                    best_gid, False, float(best_score), float(margin),
                    f"ambiguous: best={best_score:.3f} margin={margin:.3f} "
                    f"< margin_threshold={self.margin_threshold}; identity NOT updated",
                    len(self._identities),
                )

            # ---- confirmed match path ------------------------------------
            gi = self._identities[best_gid]
            state.global_id = best_gid
            state.match_streak += 1
            state.confirmed = state.match_streak >= self.confirm_observations
            gi.embeddings.append(_Observation(embedding, str(camera_id), now))
            if len(gi.embeddings) > self.max_embeddings_per_identity:
                gi.embeddings = gi.embeddings[-self.max_embeddings_per_identity:]
            gi.last_camera = str(camera_id)
            gi.last_seen_ts = now
            gi.local_ids[str(camera_id)] = str(track_id)
            if not gi.confirmed and state.confirmed:
                gi.confirmed = True
                self.metrics["links_confirmed"] += 1
            self.metrics["matches_linked"] += 1
            reason = (
                f"linked to {best_gid}: {best_reason}, margin={margin:.3f}, "
                f"streak={state.match_streak}/{self.confirm_observations}"
                f"{', CONFIRMED' if gi.confirmed else ''}"
            )
            return MatchDecision(best_gid, True, float(best_score), float(margin), reason,
                                 len(self._identities))

    # ------------------------------------------------------- sampled entry
    def observe_if_due(
        self,
        camera_id: str,
        track_id: str,
        image_bgr: np.ndarray,
        bbox: List[float],
        frame_number: int = 0,
        ts: Optional[float] = None,
    ) -> Optional[MatchDecision]:
        """
        Sampling wrapper: embeds the track's crop only when this (camera, track)
        is due for its next Re-ID observation (>= min_time_between_embeddings_s).
        Returns None when skipped (rate limit / quality gate) — callers must
        treat None as 'no new information', not as 'no identity'.

        This is the ONLY method the perception workers call, so duplicate
        embedding computation for the same track/frame is impossible and Re-ID
        cost is bounded by tracks * (1 / min_time_between_embeddings_s).

        `ts` is the observation clock in epoch seconds. Live sources leave it
        None (wall clock). Video-file sources pass MEDIA time (frame_number /
        fps): a looping or faster-than-realtime replay must not expire
        identities by wall time — temporal windows are defined in footage time.
        """
        if not self.enabled:
            return None
        now = float(ts) if ts is not None else time.time()
        key = (str(camera_id), str(track_id))
        with self._lock:
            last = self._last_embed_ts.get(key, 0.0)
            if now - last < self.min_time_between_embeddings_s:
                self.metrics["embeddings_skipped_rate"] += 1
                return None
            self._last_embed_ts[key] = now
        emb = self.compute_embedding(image_bgr, bbox)
        if emb is None:
            return None
        return self.observe(camera_id, track_id, emb, now)

    # ------------------------------------------------------- lookups
    def get_global_id(self, camera_id: str, track_id: str) -> Optional[str]:
        with self._lock:
            st = self._track_state.get((str(camera_id), str(track_id)))
            return st.global_id if st else None

    def get_identity_summary(self, global_id: str) -> Optional[dict]:
        with self._lock:
            gi = self._identities.get(global_id)
            if gi is None:
                return None
            return {
                "global_id": gi.global_id,
                "confirmed": gi.confirmed,
                "last_camera": gi.last_camera,
                "last_seen_ts": gi.last_seen_ts,
                "first_seen_ts": gi.first_seen_ts,
                "observations": len(gi.embeddings),
                "cameras": sorted(gi.local_ids.keys()),
                "local_ids": dict(gi.local_ids),
            }

    def identity_label(self, camera_id: str, track_id: str) -> str:
        """Overlay label fragment: 'G12' if linked, '' otherwise."""
        gid = self.get_global_id(camera_id, track_id)
        return gid if gid else ""

    def active_identities(self) -> List[dict]:
        """All identities not yet expired. Expiry uses the OBSERVATION clock
        (wall time for live sources, media time for video replays), so this
        intentionally does NOT re-filter by wall clock: a video-file session
        observed in media time would otherwise report an empty list."""
        with self._lock:
            return [self.get_identity_summary(gid) for gid in list(self._identities.keys())]

    def reset(self) -> None:
        """Session reset (worker restarts). Global IDs intentionally do NOT persist."""
        with self._lock:
            self._identities.clear()
            self._track_state.clear()
            self._last_embed_ts.clear()


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------
_global_manager: Optional[GlobalIdentityManager] = None


def get_reid_manager() -> GlobalIdentityManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = GlobalIdentityManager()
    return _global_manager
