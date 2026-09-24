"""
Ingestion performance profiler — measures EVERY stage of the perception path
with the real components (no mocks), reporting per-stage ms and throughput FPS.

Stages:
  1. VideoCapture open
  2. Time to first frame
  3. Frame decode (cap.read)
  4. Preprocessing (SensorFrameAdapter.normalize_frame)
  5. ONNX inference (OnnxDetector.detect)
  6. ByteTrack update
  7. Re-ID embed/observe (as invoked per cadence)
  8. Zone evaluation
  9. Evidence capture (alert frames only, measured separately)
 10. Annotation render
 11. JPEG encode
 12. End-to-end single-frame latency + ingestion/inference/display FPS

Usage:
  venv/Scripts/python -X utf8 scripts/profile_ingestion.py <video> [modality] [frames] [stride]
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from backend.detection.onnx_detector import OnnxDetector
from backend.ingestion.sensor_adapter import SensorFrameAdapter
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.tracking.overlay import annotate_frame, encode_jpeg
from backend.ingestion.adapter import FrameData
from backend.events.schema import SourceType
from backend.detection.detector import DetectionResult


def to_detection_results(raw: list) -> list:
    """Map OnnxDetector dicts to the DetectionResult dataclass the tracker expects."""
    return [
        DetectionResult(
            class_id=d["class_id"],
            class_name=d["class_name"],
            confidence=d["confidence"],
            bounding_box=d["bbox"],
            normalized_box=d["norm"],
        )
        for d in raw
    ]


def profile(video: str, modality: str = "STANDARD", n_frames: int = 120, stride: int = 2) -> dict:
    res = {"video": video, "modality": modality, "requested_frames": n_frames, "stride": stride}

    # --- 1. VideoCapture open --------------------------------------------
    t0 = time.perf_counter()
    cap = cv2.VideoCapture(video)
    opened = cap.isOpened()
    res["open_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    if not opened:
        res["error"] = "cannot open"
        return res

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    res["resolution"] = f"{w}x{h}"
    res["fps"] = round(fps, 2)

    # --- 2. Time to first frame ------------------------------------------
    t0 = time.perf_counter()
    ok, first = cap.read()
    res["ttff_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    if not ok:
        res["error"] = "no first frame"
        return res

    det = OnnxDetector(conf_threshold=0.15, imgsz=416)
    t0 = time.perf_counter()
    det.initialize()
    res["onnx_init_ms_incl_warmup"] = round((time.perf_counter() - t0) * 1000, 2)

    tracker = ByteTrackTracker(fps=fps)
    tracker.initialize()

    stage_ms = {k: 0.0 for k in
                ("read", "preprocess", "inference", "tracking", "reid", "zones", "annotate", "jpeg")}
    n_read = n_inf = n_tracks_frames = 0
    track_ids = set()
    latencies = []

    frame_img = first
    fi = 0
    displayed = 0
    while displayed < n_frames:
        # --- 3. read -------------------------------------------------------
        t0 = time.perf_counter()
        if fi > 0:
            ok, frame_img = cap.read()
            if not ok:
                break
        stage_ms["read"] += (time.perf_counter() - t0) * 1000
        n_read += 1
        fi += 1

        # build FrameData (media-time consistent)
        fd = FrameData(
            camera_id="CAM-PROFILE",
            frame_number=fi,
            timestamp=datetime.now(timezone.utc),
            image=frame_img,
            width=w, height=h,
            fps=fps,
            source=SourceType.VIDEO_FILE,
            modality=modality,
        )

        is_det_frame = (fi - 1) % stride == 0

        # --- 4. preprocess --------------------------------------------------
        t0 = time.perf_counter()
        norm = SensorFrameAdapter.normalize_frame(fd.image, modality=modality)
        stage_ms["preprocess"] += (time.perf_counter() - t0) * 1000

        dets = []
        if is_det_frame:
            # --- 5. inference -------------------------------------------------
            t0 = time.perf_counter()
            dets = to_detection_results(det.detect(norm))
            stage_ms["inference"] += (time.perf_counter() - t0) * 1000
            n_inf += 1

        # --- 6. tracking (every displayed frame: update or predict) ----------
        t0 = time.perf_counter()
        if is_det_frame:
            tracks = tracker.update(dets, fd)
        else:
            tracks = tracker.predict_step(fd)
        stage_ms["tracking"] += (time.perf_counter() - t0) * 1000
        if tracks:
            n_tracks_frames += 1
            track_ids.update(t.track_id for t in tracks)

        # --- 7. Re-ID (cadence-sampled as in pipeline: >=0.9s per track) -----
        t0 = time.perf_counter()
        from backend.tracking.reid_manager import get_reid_manager
        mgr = get_reid_manager()
        mgr.initialize()
        if mgr.enabled:
            media_ts = fi / fps
            for t in tracks:
                if t.object_class == "person":
                    mgr.observe_if_due("CAM-PROFILE", t.track_id, frame_img, t.bounding_box, ts=media_ts)
        stage_ms["reid"] += (time.perf_counter() - t0) * 1000

        # --- 8. zone evaluation ------------------------------------------
        t0 = time.perf_counter()
        # ZoneMonitor needs event store; use a lightweight no-store instance
        if not hasattr(profile, "_zm"):
            from backend.zones.security_zone import ZoneMonitor
            profile._zm = ZoneMonitor()
        zone_events, alert_events = profile._zm.evaluate_tracks(
            tracks=tracks, camera_id="CAM-PROFILE", source=SourceType.VIDEO_FILE)
        stage_ms["zones"] += (time.perf_counter() - t0) * 1000

        # --- evidence: measured separately (alert frames only) — reported as zero here
        # --- 10. annotation ------------------------------------------------
        t0 = time.perf_counter()
        render = frame_img.copy()
        if render.shape[1] > 1280:
            sc = 1280.0 / render.shape[1]
            render = cv2.resize(render, None, fx=sc, fy=sc, interpolation=cv2.INTER_LINEAR)
        annotated = annotate_frame(render, tracks, camera_id="CAM-PROFILE",
                                   display_fps=0.0, inference_fps=0.0, device="cpu",
                                   stride=stride, modality=modality)
        stage_ms["annotate"] += (time.perf_counter() - t0) * 1000

        # --- 11. JPEG ------------------------------------------------------
        t0 = time.perf_counter()
        encode_jpeg(annotated, quality=60)
        stage_ms["jpeg"] += (time.perf_counter() - t0) * 1000

        displayed += 1
        latencies.append(sum(stage_ms.values()) / max(displayed, 1))  # running mean proxy

    cap.release()

    total_frames = max(displayed, 1)
    per_stage = {k: round(v / total_frames, 3) for k, v in stage_ms.items()}
    per_stage_det_only = {
        "inference_per_det_frame": round(stage_ms["inference"] / max(n_inf, 1), 2),
    }
    e2e = round(sum(stage_ms.values()) / total_frames, 2)
    res.update({
        "frames_displayed": displayed,
        "frames_inferred": n_inf,
        "per_frame_ms": per_stage,
        **per_stage_det_only,
        "e2e_per_displayed_frame_ms": e2e,
        "ingestion_fps_theoretical": round(1000.0 / max(e2e, 0.01), 2),
        "unique_tracks": len(track_ids),
        "frames_with_tracks_pct": round(100 * n_tracks_frames / total_frames, 1),
    })
    return res


if __name__ == "__main__":
    video = sys.argv[1] if len(sys.argv) > 1 else "dataset/surveillance/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4"
    modality = sys.argv[2] if len(sys.argv) > 2 else "STANDARD"
    n_frames = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    stride = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    import json
    print(json.dumps(profile(video, modality, n_frames, stride), indent=2))
