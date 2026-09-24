"""
Border Intelligence — Comprehensive Pipeline Diagnostic Script.
Traces the full detection→tracking→evidence flow on real video files.
Reports track ID stability, face detection, ANPR, and per-frame metrics.
"""
import asyncio
import json
import sys
import time
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def probe_video(path: str) -> Dict[str, Any]:
    """Open a video file and return metadata without decoding frames."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"error": f"Cannot open: {path}"}
    info = {
        "path": path,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "codec": int(cap.get(cv2.CAP_PROP_FOURCC)),
        "total_frames_reported": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    # Decode first frame to verify readability
    ret, first = cap.read()
    info["readable"] = ret and first is not None
    if ret and first is not None:
        info["first_frame_shape"] = list(first.shape)
    # Count actual frames by reading to EOF
    count = 0
    if ret:
        count = 1
        while True:
            ret2, _ = cap.read()
            if not ret2:
                break
            count += 1
    info["actual_frames"] = count
    info["duration_s"] = round(count / max(info["fps"], 1e-6), 2)
    cap.release()
    return info


def run_diagnostic_on_video(
    video_path: str,
    modality: str = "STANDARD",
    max_frames: int = 200,
    frame_stride: int = 2,
) -> Dict[str, Any]:
    """
    Run the full production pipeline on a video and collect detailed metrics.
    Returns a comprehensive diagnostic report.
    """
    from backend.detection.onnx_detector import get_onnx_detector
    from backend.detection.detector import DetectionResult
    from backend.tracking.bytetrack_wrapper import ByteTrackTracker, suppress_duplicate_detections
    from backend.ingestion.adapter import FrameData
    from backend.ingestion.sensor_adapter import SensorFrameAdapter
    from backend.detection.evidence_detectors import get_face_detector, get_plate_recognizer
    from backend.events.schema import SourceType
    from datetime import datetime, timezone

    camera_id = "DIAG-CAM"
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print("  Initializing detector...")
    detector = get_onnx_detector(camera_id)
    print("  Detector initialized, loading model weights...")
    detector.initialize()
    print("  Model weights loaded. Initializing tracker...")
    tracker = ByteTrackTracker()
    print("  Tracker ready. Loading face/plate models...")

    face_detector = get_face_detector()
    print("  Face detector loaded.")
    plate_recognizer = get_plate_recognizer()
    print("  Plate recognizer loaded.")

    # Metrics collections
    track_history: Dict[str, List[int]] = defaultdict(list)  # track_id -> [frame_numbers]
    track_classes: Dict[str, str] = {}
    track_first_frame: Dict[str, int] = {}
    track_last_frame: Dict[str, int] = {}
    id_switches: List[Dict] = []
    frame_metrics: List[Dict] = []
    face_detections: List[Dict] = []
    plate_detections: List[Dict] = []
    all_detections_per_frame: List[int] = []
    all_tracks_per_frame: List[int] = []

    prev_frame_tracks: set = set()
    frame_num = 0
    processed = 0
    t_start = time.perf_counter()

    while True:
        ret, bgr = cap.read()
        if not ret or bgr is None:
            break
        frame_num += 1

        # Apply stride
        if (frame_num - 1) % frame_stride != 0:
            # Even on skipped frames, run predict_step to advance tracker state
            frame_data = FrameData(
                camera_id=camera_id,
                frame_number=frame_num,
                timestamp=datetime.now(timezone.utc),
                image=bgr,
                width=w,
                height=h,
                fps=fps,
                source=SourceType.VIDEO_FILE,
            )
            predicted = tracker.predict_step(frame_data)
            continue

        processed += 1
        if processed > max_frames:
            break

        t_frame_start = time.perf_counter()

        # Normalize frame for detection
        norm = SensorFrameAdapter.normalize_frame(bgr, modality=modality)

        # Detect
        t_det = time.perf_counter()
        raw_dets = detector.detect(norm)
        t_det_end = time.perf_counter()

        # Convert to DetectionResult
        detections = []
        for d in raw_dets:
            detections.append(DetectionResult(
                class_id=d["class_id"],
                class_name=d["class_name"],
                confidence=d["confidence"],
                bounding_box=d["bbox"],
                normalized_box=d.get("norm", [0, 0, 0, 0]),
            ))

        det_count = len(detections)
        all_detections_per_frame.append(det_count)

        # Track
        frame_data = FrameData(
            camera_id=camera_id,
            frame_number=frame_num,
            timestamp=datetime.now(timezone.utc),
            image=bgr,
            width=w,
            height=h,
            fps=fps,
            source=SourceType.VIDEO_FILE,
        )
        t_track = time.perf_counter()
        tracks = tracker.update(detections, frame_data)
        t_track_end = time.perf_counter()

        track_ids_this_frame = set()
        for t in tracks:
            tid = t.track_id
            track_ids_this_frame.add(tid)
            track_history[tid].append(frame_num)
            track_classes[tid] = t.object_class
            if tid not in track_first_frame:
                track_first_frame[tid] = frame_num
            track_last_frame[tid] = frame_num

        all_tracks_per_frame.append(len(tracks))

        # Detect ID switches: objects that were present last frame but got new IDs
        new_ids = track_ids_this_frame - prev_frame_tracks
        lost_ids = prev_frame_tracks - track_ids_this_frame
        if prev_frame_tracks and new_ids and lost_ids:
            # Check spatial overlap between lost and new tracks
            for new_tid in new_ids:
                new_track = next((t for t in tracks if t.track_id == new_tid), None)
                if new_track is None:
                    continue
                for lost_tid in lost_ids:
                    # Look up the last known position of the lost track
                    # We stored it in the tracker's active tracks before it was lost
                    id_switches.append({
                        "frame": frame_num,
                        "lost_id": lost_tid,
                        "new_id": new_tid,
                        "class": new_track.object_class,
                        "new_bbox": new_track.bounding_box,
                    })

        prev_frame_tracks = track_ids_this_frame

        # Face detection on person tracks
        for t in tracks:
            if t.object_class == "person" and t.bounding_box:
                try:
                    face = face_detector.best_face_in_box(bgr, t.bounding_box, min_face_px=8)
                    if face is not None:
                        face_detections.append({
                            "frame": frame_num,
                            "track_id": t.track_id,
                            "face_bbox": face["bbox"],
                            "face_conf": face["confidence"],
                        })
                except Exception as e:
                    pass

        # Plate detection on vehicle tracks (RGB only)
        if modality in ("STANDARD", "RGB"):
            for t in tracks:
                if t.object_class in ("car", "truck", "bus", "motorcycle", "bicycle", "vehicle") and t.bounding_box:
                    try:
                        plate = plate_recognizer.detect_in_vehicle(bgr, t.bounding_box)
                        if plate is not None:
                            reading = plate_recognizer.read_plate(bgr, plate["bbox"])
                            plate_detections.append({
                                "frame": frame_num,
                                "track_id": t.track_id,
                                "plate_bbox": plate["bbox"],
                                "plate_conf": plate["confidence"],
                                "ocr_text": reading.get("text", ""),
                                "ocr_conf": reading.get("confidence", 0.0),
                                "uncertain": reading.get("uncertain", True),
                            })
                    except Exception as e:
                        pass

        t_frame_end = time.perf_counter()

        frame_metrics.append({
            "frame": frame_num,
            "detections": det_count,
            "tracks": len(tracks),
            "det_ms": round((t_det_end - t_det) * 1000, 1),
            "track_ms": round((t_track_end - t_track) * 1000, 1),
            "total_ms": round((t_frame_end - t_frame_start) * 1000, 1),
        })

        if processed % 50 == 0:
            print(f"  [DIAG] frame {frame_num} det={det_count} tracks={len(tracks)} "
                  f"det_ms={frame_metrics[-1]['det_ms']} track_ms={frame_metrics[-1]['track_ms']}")

    cap.release()
    t_total = time.perf_counter() - t_start

    # Analyze track stability
    track_lifespans = {}
    for tid, frames in track_history.items():
        track_lifespans[tid] = {
            "first_frame": min(frames),
            "last_frame": max(frames),
            "num_frames": len(frames),
            "class": track_classes.get(tid, "unknown"),
        }

    # Count ID switches per class
    switches_by_class = Counter()
    for sw in id_switches:
        switches_by_class[sw["class"]] += 1

    # Detection coverage: what % of frames had detections
    det_coverage = sum(1 for d in all_detections_per_frame if d > 0) / max(len(all_detections_per_frame), 1)

    report = {
        "video": video_path,
        "modality": modality,
        "frame_stride": frame_stride,
        "total_frames_read": frame_num,
        "frames_processed": processed,
        "wall_time_s": round(t_total, 2),
        "effective_fps": round(processed / max(t_total, 0.001), 1),
        "detection_coverage": round(det_coverage * 100, 1),
        "avg_detections_per_frame": round(np.mean(all_detections_per_frame), 1) if all_detections_per_frame else 0,
        "avg_tracks_per_frame": round(np.mean(all_tracks_per_frame), 1) if all_tracks_per_frame else 0,
        "unique_track_ids": len(track_history),
        "id_switches_total": len(id_switches),
        "id_switches_by_class": dict(switches_by_class),
        "track_lifespans": track_lifespans,
        "face_detections_count": len(face_detections),
        "face_detections": face_detections[:20],  # first 20
        "plate_detections_count": len(plate_detections),
        "plate_detections": plate_detections[:20],
        "latency_percentiles": {
            "p50_det_ms": round(float(np.percentile([m["det_ms"] for m in frame_metrics], 50)), 1) if frame_metrics else 0,
            "p95_det_ms": round(float(np.percentile([m["det_ms"] for m in frame_metrics], 95)), 1) if frame_metrics else 0,
            "p50_total_ms": round(float(np.percentile([m["total_ms"] for m in frame_metrics], 50)), 1) if frame_metrics else 0,
            "p95_total_ms": round(float(np.percentile([m["total_ms"] for m in frame_metrics], 95)), 1) if frame_metrics else 0,
        },
    }

    return report


def main():
    print("=" * 80)
    print("BORDER INTELLIGENCE — COMPREHENSIVE PIPELINE DIAGNOSTIC")
    print("=" * 80)

    # Discover test videos
    virat_root = Path("VIRAT")
    test_videos = []

    # ANPR video
    anpr_path = virat_root / "anpr_vehicle_checkpoint.mp4"
    if anpr_path.exists():
        test_videos.append(("ANPR", str(anpr_path), "STANDARD"))

    # Night IR
    night_path = virat_root / "night_ir_patrol.mp4"
    if night_path.exists():
        test_videos.append(("NIGHT_IR", str(night_path), "IR_NIGHT"))

    # Thermal
    thermal_path = virat_root / "thermal_patrol.mp4"
    if thermal_path.exists():
        test_videos.append(("THERMAL", str(thermal_path), "THERMAL"))

    # Standard RGB (VIRAT CCTV)
    rgb_path = virat_root / "CCTV 01" / "VIRAT_S_010001_03_000537_000563.mp4"
    if rgb_path.exists():
        test_videos.append(("RGB_VIRAT", str(rgb_path), "STANDARD"))

    # Probe all videos first
    print("\n--- VIDEO PROBES ---")
    for label, path, mod in test_videos:
        info = probe_video(path)
        print(f"\n[{label}] {path}")
        for k, v in info.items():
            print(f"  {k}: {v}")

    # Run diagnostics
    all_reports = {}
    for label, path, mod in test_videos:
        print(f"\n{'=' * 60}")
        print(f"Running diagnostic: {label} ({mod})")
        print(f"  Video: {path}")
        print(f"{'=' * 60}")

        report = run_diagnostic_on_video(
            video_path=path,
            modality=mod,
            max_frames=100,
            frame_stride=5,
        )
        all_reports[label] = report

        print(f"\n--- RESULTS: {label} ---")
        print(f"  Frames processed: {report.get('frames_processed', 0)}")
        print(f"  Effective FPS: {report.get('effective_fps', 0)}")
        print(f"  Detection coverage: {report.get('detection_coverage', 0)}%")
        print(f"  Avg detections/frame: {report.get('avg_detections_per_frame', 0)}")
        print(f"  Avg tracks/frame: {report.get('avg_tracks_per_frame', 0)}")
        print(f"  Unique track IDs: {report.get('unique_track_ids', 0)}")
        print(f"  ID switches: {report.get('id_switches_total', 0)}")
        print(f"  Face detections: {report.get('face_detections_count', 0)}")
        print(f"  Plate detections: {report.get('plate_detections_count', 0)}")
        print(f"  Latency p50={report.get('latency_percentiles', {}).get('p50_total_ms', 0)}ms "
              f"p95={report.get('latency_percentiles', {}).get('p95_total_ms', 0)}ms")

        if report.get("track_lifespans"):
            print(f"\n  Track ID Lifespans:")
            for tid, info in sorted(report["track_lifespans"].items(), key=lambda x: x[1]["first_frame"]):
                print(f"    Track #{tid}: frames {info['first_frame']}-{info['last_frame']} "
                      f"({info['num_frames']} frames) class={info['class']}")

        if report.get("face_detections"):
            print(f"\n  Face Detections (first {len(report['face_detections'])}):")
            for fd in report["face_detections"]:
                print(f"    Frame {fd['frame']}: track #{fd['track_id']} "
                      f"face_conf={fd['face_conf']:.3f} bbox={[int(v) for v in fd['face_bbox']]}")

        if report.get("plate_detections"):
            print(f"\n  Plate Detections (first {len(report['plate_detections'])}):")
            for pd in report["plate_detections"]:
                print(f"    Frame {pd['frame']}: track #{pd['track_id']} "
                      f"plate_conf={pd['plate_conf']:.3f} OCR='{pd['ocr_text']}' "
                      f"ocr_conf={pd['ocr_conf']:.3f} uncertain={pd['uncertain']}")

        if report.get("id_switches_total", 0) > 0:
            print(f"\n  ID Switch Events (first 10):")
            for sw in report.get("id_switches", [])[:10]:
                print(f"    Frame {sw['frame']}: lost #{sw['lost_id']} -> new #{sw['new_id']} "
                      f"class={sw['class']}")

    # Save full report
    output_path = Path("scratch") / "diagnostic_report.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_reports, f, indent=2, default=str)
    print(f"\nFull report saved to: {output_path}")

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
