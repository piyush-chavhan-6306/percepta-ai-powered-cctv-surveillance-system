"""
COMPREHENSIVE PIPELINE DIAGNOSTIC
Traces ANPR, face detection, night/IR, thermal, and measures full performance.
Runs on ALL test videos in a single pass.
"""
import sys, os, json, time, logging, traceback
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("diag")
logger.setLevel(logging.INFO)

# Suppress noisy loggers
for name in ["backend.detection.evidence_detectors", "backend.detection.plate_aggregator",
             "backend.tracking.bytetrack_wrapper", "backend.tracking.pipeline",
             "backend.ingestion.sensor_adapter", "ultralytics"]:
    logging.getLogger(name).setLevel(logging.WARNING)


def make_frame_data(frame_bgr, camera_id, frame_num, fps, w, h, modality="STANDARD"):
    from backend.ingestion.adapter import FrameData
    from backend.events.schema import SourceType
    ts = datetime.fromtimestamp(frame_num / fps if fps > 0 else time.time(), tz=timezone.utc)
    return FrameData(
        camera_id=camera_id, image=frame_bgr, frame_number=frame_num,
        fps=fps, width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE,
        modality=modality,
    )


def trace_anpr(video_path, label, max_frames=302):
    """Phase C/D: Full ANPR pipeline trace."""
    print(f"\n{'='*60}")
    print(f"PHASE C/D: ANPR TRACE — {label}")
    print(f"{'='*60}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ERROR: Cannot open {video_path}")
        return None

    total_frames = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), max_frames)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  Video: {video_path} ({w}x{h}, {fps} FPS, {total_frames} frames)")

    from backend.detection.detector import get_detector
    from backend.detection.evidence_detectors import get_face_detector, get_plate_recognizer
    from backend.detection.plate_aggregator import get_plate_collector
    from backend.tracking.bytetrack_wrapper import ByteTrackTracker
    from backend.tracking.pipeline import TrackingPipeline
    from backend.events.store import EventStore
    from backend.zones.security_zone import ZoneMonitor

    detector = get_detector()
    detector.initialize()
    tracker = ByteTrackTracker()
    tracker.initialize()
    pipeline = TrackingPipeline(detector=detector, tracker=tracker)
    pipeline.initialize()

    plate_collector = get_plate_collector()
    face_det = get_face_detector()
    plate_rec = get_plate_recognizer()

    stats = {
        "total_frames": 0, "total_detections": 0, "total_tracks": 0,
        "vehicle_tracks": 0, "person_tracks": 0,
        "plate_detections": 0, "plate_reads": 0, "plate_uncertain": 0,
        "face_detections": 0, "face_crops": 0,
        "alerts": 0, "evidence_packages": 0,
        "det_ms_total": 0, "track_ms_total": 0, "evidence_ms_total": 0,
        "plate_details": [], "face_details": [], "perf_samples": [],
    }

    t_start = time.time()
    frame_num = 0

    while frame_num < total_frames:
        ret, frame_bgr = cap.read()
        if not ret:
            break
        frame_num += 1
        t_frame_start = time.perf_counter()

        frame_data = make_frame_data(frame_bgr, f"anpr_{label}", frame_num, fps, w, h)

        # Run pipeline
        t0 = time.perf_counter()
        result = pipeline.process_frame_sync(frame_data)
        t_total = (time.perf_counter() - t_frame_start) * 1000

        stats["total_frames"] = frame_num
        stats["total_detections"] += len(result.detections)
        stats["total_tracks"] += len(result.tracks)
        stats["alerts"] += len(result.alert_events)
        stats["det_ms_total"] += result.inference_latency_ms
        stats["track_ms_total"] += result.tracking_latency_ms
        stats["perf_samples"].append(t_total)

        # Count vehicle vs person tracks
        for t in result.tracks:
            if t.object_class in ("car", "truck", "bus", "motorcycle", "bicycle", "vehicle"):
                stats["vehicle_tracks"] += 1
            elif t.object_class == "person":
                stats["person_tracks"] += 1

        # ANPR: for each vehicle track, try plate detection
        t_ev_start = time.perf_counter()
        for track in result.tracks:
            if track.object_class not in ("car", "truck", "bus", "motorcycle", "bicycle", "vehicle"):
                continue
            if not track.bounding_box or len(track.bounding_box) < 4:
                continue

            # Try plate detection
            try:
                plate_det = plate_rec.detect_in_vehicle(frame_bgr, track.bounding_box)
                if plate_det is not None:
                    stats["plate_detections"] += 1
                    plate_bbox = plate_det["bbox"]
                    plate_crop = plate_det.get("crop")
                    plate_w = int(plate_bbox[2] - plate_bbox[0]) if plate_bbox else 0
                    plate_h = int(plate_bbox[3] - plate_bbox[1]) if plate_bbox else 0

                    # OCR
                    reading = plate_rec.read_plate(frame_bgr, plate_bbox)
                    plate_text = reading.get("text", "")
                    plate_conf = reading.get("confidence", 0.0)
                    plate_uncertain = reading.get("uncertain", True)

                    if plate_text:
                        stats["plate_reads"] += 1
                    if plate_uncertain:
                        stats["plate_uncertain"] += 1

                    # Temporal aggregation
                    track_key = f"anpr_{label}:{track.track_id}"
                    if plate_text:
                        plate_collector.add_observation(
                            track_key=track_key, text=plate_text, confidence=plate_conf,
                            frame_number=frame_num, timestamp=frame_data.timestamp,
                            vehicle_box=track.bounding_box, plate_box=plate_bbox,
                        )
                    consensus = plate_collector.get_best(track_key)

                    if frame_num <= 10 or (consensus and not consensus.uncertain):
                        stats["plate_details"].append({
                            "frame": frame_num, "track_id": track.track_id,
                            "plate_bbox_size": f"{plate_w}x{plate_h}",
                            "plate_text": plate_text, "plate_conf": round(plate_conf, 3),
                            "uncertain": plate_uncertain,
                            "consensus_text": consensus.text if consensus else None,
                            "consensus_conf": round(consensus.confidence, 3) if consensus else None,
                            "consensus_uncertain": consensus.uncertain if consensus else None,
                        })
            except Exception as e:
                pass

            # Face detection on person tracks near this vehicle (skip for ANPR test)
        
        # Face detection on person tracks
        for track in result.tracks:
            if track.object_class != "person":
                continue
            if not track.bounding_box or len(track.bounding_box) < 4:
                continue
            try:
                face = face_det.best_face_in_box(frame_bgr, track.bounding_box, min_face_px=8)
                if face is not None:
                    stats["face_detections"] += 1
                    fb = face["bbox"]
                    fc = face.get("confidence", 0)
                    fw = int(fb[2] - fb[0]) if fb else 0
                    fh = int(fb[3] - fb[1]) if fb else 0
                    if frame_num <= 5 or stats["face_detections"] <= 3:
                        stats["face_details"].append({
                            "frame": frame_num, "track_id": track.track_id,
                            "face_bbox_size": f"{fw}x{fh}", "face_conf": round(fc, 3),
                        })
            except Exception:
                pass

        t_ev_end = time.perf_counter()
        stats["evidence_ms_total"] += (t_ev_end - t_ev_start) * 1000

        if frame_num % 50 == 0:
            elapsed = time.time() - t_start
            print(f"  Frame {frame_num}/{total_frames} ({frame_num/elapsed:.1f} fps) "
                  f"dets={len(result.detections)} tracks={len(result.tracks)} "
                  f"plates={stats['plate_detections']} faces={stats['face_detections']}")

    cap.release()
    elapsed = time.time() - t_start

    # Summary
    avg_det_ms = stats["det_ms_total"] / max(stats["total_frames"], 1)
    avg_track_ms = stats["track_ms_total"] / max(stats["total_frames"], 1)
    avg_ev_ms = stats["evidence_ms_total"] / max(stats["total_frames"], 1)
    avg_frame_ms = sum(stats["perf_samples"]) / max(len(stats["perf_samples"]), 1)

    print(f"\n  --- ANPR RESULTS ---")
    print(f"  Frames: {stats['total_frames']}")
    print(f"  Total detections: {stats['total_detections']} ({stats['total_detections']/max(stats['total_frames'],1):.1f}/frame)")
    print(f"  Vehicle track-frames: {stats['vehicle_tracks']}")
    print(f"  Person track-frames: {stats['person_tracks']}")
    print(f"  Plate detections: {stats['plate_detections']}")
    print(f"  Plate reads (non-empty): {stats['plate_reads']}")
    print(f"  Plate uncertain: {stats['plate_uncertain']}")
    print(f"  Face detections: {stats['face_detections']}")
    print(f"  Processing FPS: {stats['total_frames']/elapsed:.1f}")
    print(f"  Avg frame latency: {avg_frame_ms:.1f} ms")
    print(f"  Avg detection: {avg_det_ms:.1f} ms")
    print(f"  Avg tracking: {avg_track_ms:.1f} ms")
    print(f"  Avg evidence: {avg_ev_ms:.1f} ms")

    if stats["plate_details"]:
        print(f"\n  Plate reads (first 10):")
        for pd in stats["plate_details"][:10]:
            print(f"    Frame {pd['frame']}: Track #{pd['track_id']} "
                  f"plate_size={pd['plate_bbox_size']} "
                  f"text='{pd['plate_text']}' conf={pd['plate_conf']} "
                  f"uncertain={pd['uncertain']} "
                  f"consensus='{pd['consensus_text']}' cconf={pd['consensus_conf']}")

    if stats["face_details"]:
        print(f"\n  Face detections (first 5):")
        for fd in stats["face_details"][:5]:
            print(f"    Frame {fd['frame']}: Track #{fd['track_id']} "
                  f"face_size={fd['face_bbox_size']} conf={fd['face_conf']}")

    return stats


def trace_modality(video_path, label, modality, max_frames=200):
    """Phase F/G: Night/IR/Thermal pipeline trace."""
    print(f"\n{'='*60}")
    print(f"MODALITY TRACE: {label} (modality={modality})")
    print(f"{'='*60}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ERROR: Cannot open {video_path}")
        return None

    total_frames = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), max_frames)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  Video: {video_path} ({w}x{h}, {fps} FPS, {total_frames} frames)")

    from backend.detection.detector import get_detector
    from backend.tracking.bytetrack_wrapper import ByteTrackTracker
    from backend.tracking.pipeline import TrackingPipeline
    from backend.ingestion.sensor_adapter import SensorFrameAdapter

    detector = get_detector()
    detector.initialize()
    tracker = ByteTrackTracker()
    tracker.initialize()
    pipeline = TrackingPipeline(detector=detector, tracker=tracker)
    pipeline.initialize()

    stats = {
        "total_frames": 0, "total_detections": 0, "total_tracks": 0,
        "det_ms_total": 0, "track_ms_total": 0, "total_ms": 0,
        "alerts": 0, "detections_per_frame": [],
        "track_ids_set": set(), "unique_ids": 0,
        "modality": modality,
    }

    t_start = time.time()
    frame_num = 0

    while frame_num < total_frames:
        ret, frame_bgr = cap.read()
        if not ret:
            break
        frame_num += 1
        t_frame_start = time.perf_counter()

        # Check modality preprocessing
        norm = SensorFrameAdapter.normalize_frame(frame_bgr, modality=modality)

        frame_data = make_frame_data(frame_bgr, f"mod_{label}", frame_num, fps, w, h, modality=modality)
        result = pipeline.process_frame_sync(frame_data)
        t_total = (time.perf_counter() - t_frame_start) * 1000

        stats["total_frames"] = frame_num
        stats["total_detections"] += len(result.detections)
        stats["total_tracks"] += len(result.tracks)
        stats["alerts"] += len(result.alert_events)
        stats["det_ms_total"] += result.inference_latency_ms
        stats["track_ms_total"] += result.tracking_latency_ms
        stats["total_ms"] += t_total
        stats["detections_per_frame"].append(len(result.detections))

        for t in result.tracks:
            stats["track_ids_set"].add(t.track_id)

        if frame_num % 50 == 0:
            elapsed = time.time() - t_start
            print(f"  Frame {frame_num}/{total_frames} ({frame_num/elapsed:.1f} fps) "
                  f"dets={len(result.detections)} tracks={len(result.tracks)} "
                  f"alerts={len(result.alert_events)}")

    cap.release()
    elapsed = time.time() - t_start
    stats["unique_ids"] = len(stats["track_ids_set"])

    avg_det = stats["det_ms_total"] / max(stats["total_frames"], 1)
    avg_trk = stats["track_ms_total"] / max(stats["total_frames"], 1)
    avg_tot = stats["total_ms"] / max(stats["total_frames"], 1)
    avg_dets = sum(stats["detections_per_frame"]) / max(len(stats["detections_per_frame"]), 1)

    print(f"\n  --- {label} RESULTS ---")
    print(f"  Modality: {modality}")
    print(f"  Frames: {stats['total_frames']}")
    print(f"  Total detections: {stats['total_detections']} ({avg_dets:.1f}/frame)")
    print(f"  Total tracks: {stats['total_tracks']}")
    print(f"  Unique track IDs: {stats['unique_ids']}")
    print(f"  Alerts: {stats['alerts']}")
    print(f"  Processing FPS: {stats['total_frames']/elapsed:.1f}")
    print(f"  Avg detection: {avg_det:.1f} ms")
    print(f"  Avg tracking: {avg_trk:.1f} ms")
    print(f"  Avg total frame: {avg_tot:.1f} ms")

    # Modality-specific observations
    if modality in ("IR_NIGHT", "NIGHT_IR"):
        print(f"\n  Night/IR observations:")
        print(f"  - YOLOv8n is trained on RGB; night/IR detection quality depends on")
        print(f"    how well the thermal/IR imagery resembles training distribution")
        if avg_dets < 1.0:
            print(f"  - LOW detection rate ({avg_dets:.1f}/frame): model may struggle with this modality")
        elif avg_dets < 5.0:
            print(f"  - MODERATE detection rate ({avg_dets:.1f}/frame)")
        else:
            print(f"  - GOOD detection rate ({avg_dets:.1f}/frame)")
    elif modality == "THERMAL":
        print(f"\n  Thermal observations:")
        print(f"  - YOLOv8n is RGB-trained; thermal detection is expected to be limited")
        if avg_dets < 1.0:
            print(f"  - LOW detection rate ({avg_dets:.1f}/frame): expected for RGB model on thermal")
        else:
            print(f"  - Detection rate ({avg_dets:.1f}/frame): better than expected for RGB model")

    return stats


def measure_performance(video_path, label, max_frames=150):
    """Phase I: Detailed per-stage performance measurement."""
    print(f"\n{'='*60}")
    print(f"PHASE I: PERFORMANCE — {label}")
    print(f"{'='*60}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ERROR: Cannot open {video_path}")
        return None

    total_frames = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), max_frames)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    from backend.detection.detector import get_detector
    from backend.detection.evidence_detectors import get_face_detector, get_plate_recognizer
    from backend.tracking.bytetrack_wrapper import ByteTrackTracker
    from backend.ingestion.sensor_adapter import SensorFrameAdapter

    detector = get_detector()
    detector.initialize()
    face_det = get_face_detector()
    plate_rec = get_plate_recognizer()
    tracker = ByteTrackTracker()
    tracker.initialize()

    decode_times = []
    det_times = []
    nms_times = []
    track_times = []
    face_times = []
    plate_times = []
    total_times = []

    t_start = time.time()
    frame_num = 0

    while frame_num < total_frames:
        t_total_start = time.perf_counter()

        t_dec_start = time.perf_counter()
        ret, frame_bgr = cap.read()
        if not ret:
            break
        t_dec_end = time.perf_counter()
        decode_times.append((t_dec_end - t_dec_start) * 1000)
        frame_num += 1

        # Detection
        t_det_start = time.perf_counter()
        norm = SensorFrameAdapter.normalize_frame(frame_bgr, modality="STANDARD")
        detections = detector.detect(norm)
        t_det_end = time.perf_counter()
        det_times.append((t_det_end - t_det_start) * 1000)

        # Tracking
        t_trk_start = time.perf_counter()
        from backend.ingestion.adapter import FrameData
        from backend.events.schema import SourceType
        ts = datetime.fromtimestamp(frame_num / fps, tz=timezone.utc)
        fd = FrameData(camera_id="perf", image=frame_bgr, frame_number=frame_num,
                       fps=fps, width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE)
        tracks = tracker.update(detections, fd)
        t_trk_end = time.perf_counter()
        track_times.append((t_trk_end - t_trk_start) * 1000)

        # Face detection (sample every 10th frame)
        if frame_num % 10 == 0:
            t_face_start = time.perf_counter()
            for t in tracks[:3]:  # Limit to 3 tracks for perf
                if t.object_class == "person" and t.bounding_box:
                    try:
                        face_det.best_face_in_box(frame_bgr, t.bounding_box, min_face_px=8)
                    except:
                        pass
            t_face_end = time.perf_counter()
            face_times.append((t_face_end - t_face_start) * 1000)

        # Plate detection (sample every 10th frame)
        if frame_num % 10 == 0:
            t_plate_start = time.perf_counter()
            for t in tracks[:3]:
                if t.object_class in ("car", "truck", "bus") and t.bounding_box:
                    try:
                        plate_rec.detect_in_vehicle(frame_bgr, t.bounding_box)
                    except:
                        pass
            t_plate_end = time.perf_counter()
            plate_times.append((t_plate_end - t_plate_start) * 1000)

        t_total_end = time.perf_counter()
        total_times.append((t_total_end - t_total_start) * 1000)

        if frame_num % 50 == 0:
            elapsed = time.time() - t_start
            print(f"  Frame {frame_num}/{total_frames} ({frame_num/elapsed:.1f} fps)")

    cap.release()
    elapsed = time.time() - t_start

    def stats(arr, name):
        if not arr:
            return f"  {name}: no samples"
        a = np.array(arr)
        return (f"  {name}: mean={a.mean():.1f}ms p50={np.median(a):.1f}ms "
                f"p95={np.percentile(a,95):.1f}ms p99={np.percentile(a,99):.1f}ms "
                f"max={a.max():.1f}ms")

    print(f"\n  --- PERFORMANCE RESULTS ---")
    print(f"  Frames: {frame_num}")
    print(f"  Resolution: {w}x{h}")
    print(f"  Wall time: {elapsed:.1f}s ({frame_num/elapsed:.1f} fps)")
    print(stats(decode_times, "Decode"))
    print(stats(det_times, "Detection"))
    print(stats(track_times, "Tracking"))
    print(stats(face_times, "Face detection"))
    print(stats(plate_times, "Plate detection"))
    print(stats(total_times, "Total frame"))

    # Find bottleneck
    all_stages = {
        "Decode": np.mean(decode_times) if decode_times else 0,
        "Detection": np.mean(det_times) if det_times else 0,
        "Tracking": np.mean(track_times) if track_times else 0,
        "Face": np.mean(face_times) if face_times else 0,
        "Plate": np.mean(plate_times) if plate_times else 0,
    }
    bottleneck = max(all_stages, key=all_stages.get)
    print(f"\n  BOTTLENECK: {bottleneck} ({all_stages[bottleneck]:.1f} ms/frame)")
    print(f"  Breakdown: {', '.join(f'{k}={v:.1f}ms' for k,v in sorted(all_stages.items(), key=lambda x: -x[1]))}")

    return {
        "decode_ms": np.mean(decode_times) if decode_times else 0,
        "det_ms": np.mean(det_times) if det_times else 0,
        "track_ms": np.mean(track_times) if track_times else 0,
        "face_ms": np.mean(face_times) if face_times else 0,
        "plate_ms": np.mean(plate_times) if plate_times else 0,
        "total_ms": np.mean(total_times) if total_times else 0,
        "bottleneck": bottleneck,
        "fps": frame_num / elapsed,
    }


if __name__ == "__main__":
    results = {}

    # Phase C/D: ANPR
    results["anpr"] = trace_anpr("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "anpr")

    # Phase E already covered in ANPR trace (face detection on person tracks)
    # Also run on RGB VIRAT footage for face-focused analysis
    results["face_rgb"] = trace_anpr("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "face_rgb")

    # Phase F: Night/IR
    results["night"] = trace_modality("dataset/surveillance/night_ir_patrol.mp4", "night_ir", "IR_NIGHT")

    # Phase G: Thermal (original)
    results["thermal_orig"] = trace_modality("dataset/surveillance/thermal_patrol.mp4", "thermal_orig", "THERMAL")

    # Phase G: Real PTB-TIR thermal
    import glob as globmod
    thermal_files = sorted(globmod.glob("dataset/surveillance/thermal_real/ptb_tir_*.mp4"))
    for tf in thermal_files[:2]:
        name = os.path.splitext(os.path.basename(tf))[0]
        results[f"thermal_{name}"] = trace_modality(tf, name, "THERMAL")

    # Phase F: Real NIRPed night
    night_files = sorted(globmod.glob("dataset/surveillance/night_real/nirped_*.mp4"))
    for nf in night_files[:1]:
        name = os.path.splitext(os.path.basename(nf))[0]
        results[f"night_{name}"] = trace_modality(nf, name, "NIGHT_IR")

    # Phase I: Performance on ANPR
    results["perf_anpr"] = measure_performance("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "anpr")
    results["perf_night"] = measure_performance("dataset/surveillance/night_ir_patrol.mp4", "night")

    # Save all results
    os.makedirs("scratch", exist_ok=True)
    with open("scratch/comprehensive_diagnostic.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nFull results saved to scratch/comprehensive_diagnostic.json")
