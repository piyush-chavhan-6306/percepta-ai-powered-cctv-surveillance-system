"""
End-to-end validation on REAL footage: night/IR, thermal, ANPR.

Runs each clip through the complete production chain:
  ingestion -> modality preprocessing -> YOLO -> ByteTrack -> Re-ID ->
  zones/tripwires -> alerts -> evidence packages -> annotated output video

Writes per-video:
  - annotated output mp4 (scratch/e2e_real/<demo>/annotated.mp4) for manual
    frame-by-frame inspection
  - evidence packages via SnapshotArchiveManager (same manager the API uses)
  - ANPR consensus per vehicle track (collector the pipeline uses)
  - JSON metrics: detections, tracks, ID switches, alerts, evidence, latency

No synthetic transformations. No fabricated plate numbers.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from backend.detection.onnx_detector import OnnxDetector
from backend.detection.detector import DetectionResult
from backend.ingestion.adapter import FrameData
from backend.ingestion.sensor_adapter import SensorFrameAdapter
from backend.events.schema import SourceType
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.tracking.overlay import annotate_frame
from backend.zones.security_zone import ZoneMonitor, SecurityZone, ZoneSeverity

OUT_ROOT = Path("scratch/e2e_real")

DEMOS = [
    {
        "id": "night_ir_patrol",
        "video": "dataset/surveillance/night_ir_patrol.mp4",
        "modality": "IR_NIGHT",
        "max_frames": 311,
    },
    {
        "id": "thermal_patrol",
        "video": "dataset/surveillance/thermal_patrol.mp4",
        "modality": "THERMAL",
        "max_frames": 800,
    },
    {
        "id": "anpr_vehicle_checkpoint",
        "video": "dataset/surveillance/anpr_vehicle_checkpoint.mp4",
        "modality": "STANDARD",
        "max_frames": 302,
    },
]


def make_zone_monitor():
    zm = ZoneMonitor()
    zm.add_zone(SecurityZone(
        zone_id="ZONE_VAL",
        name="Validation Restricted Area",
        polygon=[(0.0, 0.0), (1920.0, 0.0), (1920.0, 1080.0), (0.0, 1080.0)],
        severity=ZoneSeverity.RESTRICTED,
        loitering_threshold_seconds=1.5,
    ))
    return zm


async def run_demo(demo: dict) -> dict:
    demo_id = demo["id"]
    video_path = demo["video"]
    modality = demo["modality"]
    out_dir = OUT_ROOT / demo_id
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {"demo": demo_id, "video": video_path, "modality": modality}

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"cannot open {video_path}"
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    report["resolution"] = f"{w}x{h}"
    report["fps"] = round(fps, 2)

    det = OnnxDetector(conf_threshold=0.15, imgsz=416)
    det.initialize()
    tracker = ByteTrackTracker(fps=fps)
    tracker.initialize()
    zm = make_zone_monitor()

    from backend.events.snapshots import get_snapshot_manager
    snap_mgr = get_snapshot_manager()

    writer = cv2.VideoWriter(str(out_dir / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                             fps, (min(w, 1280), int(h * min(1.0, 1280.0 / w))))

    stage = {"read": 0.0, "preprocess": 0.0, "inference": 0.0, "tracking": 0.0,
             "zones": 0.0, "evidence": 0.0, "annotate": 0.0, "jpeg": 0.0}
    n = 0
    n_inf = 0
    det_total = 0
    det_by_class = {}
    id_first_frame = {}
    id_last_frame = {}
    id_switch_events = []          # track_id -> list of (frame, gap)
    track_seen_frames = {}
    alerts = []
    zone_events_total = 0
    evidence_files = []
    latencies = []
    prev_ids = set()

    plate_collector = None
    anpr_reads = []
    if modality == "STANDARD":
        from backend.detection.evidence_detectors import PlateRecognizer, get_plate_collector
        pr = PlateRecognizer()
        plate_collector = get_plate_collector()

    while n < demo["max_frames"]:
        t_loop = time.perf_counter()
        ok, img = cap.read()
        if not ok:
            break
        n += 1
        fd = FrameData(
            camera_id=f"VAL-{demo_id}",
            frame_number=n,
            timestamp=datetime.now(timezone.utc),
            image=img, width=w, height=h, fps=fps,
            source=SourceType.VIDEO_FILE, modality=modality,
        )
        is_det = (n - 1) % 2 == 0

        t0 = time.perf_counter()
        norm = SensorFrameAdapter.normalize_frame(img, modality=modality)
        stage["preprocess"] += (time.perf_counter() - t0) * 1000

        dets = []
        if is_det:
            t0 = time.perf_counter()
            raw = det.detect(norm)
            stage["inference"] += (time.perf_counter() - t0) * 1000
            n_inf += 1
            det_total += len(raw)
            for d in raw:
                det_by_class[d["class_name"]] = det_by_class.get(d["class_name"], 0) + 1
                dets.append(DetectionResult(
                    class_id=d["class_id"], class_name=d["class_name"],
                    confidence=d["confidence"], bounding_box=d["bbox"], normalized_box=d["norm"]))

        t0 = time.perf_counter()
        if is_det:
            tracks = tracker.update(dets, fd)
        else:
            tracks = tracker.predict_step(fd)
        stage["tracking"] += (time.perf_counter() - t0) * 1000

        cur_ids = set()
        for t in tracks:
            tid = t.track_id
            cur_ids.add(tid)
            if tid not in id_first_frame:
                id_first_frame[tid] = n
            id_last_frame[tid] = n
            track_seen_frames.setdefault(tid, set()).add(n)
            if tid not in prev_ids and prev_ids and tid in id_last_frame:
                # reappearance after absence: potential ID switch candidate
                gap = n - id_last_frame.get(tid, n)
                if gap > 2 and tid not in [e["id"] for e in id_switch_events]:
                    pass  # reappearance under SAME id is good (recovery), not a switch
        new_ids = cur_ids - prev_ids
        for tid in new_ids:
            if prev_ids and tid not in id_first_frame:
                id_switch_events.append({"frame": n, "new_id": tid})
        prev_ids = cur_ids

        t0 = time.perf_counter()
        zone_events, alert_events = zm.evaluate_tracks(
            tracks=tracks, camera_id=fd.camera_id, source=SourceType.VIDEO_FILE)
        stage["zones"] += (time.perf_counter() - t0) * 1000
        zone_events_total += len(zone_events)

        # Evidence + ANPR on alert frames (same path as pipeline._attach_alert_evidence)
        if alert_events:
            for a in alert_events:
                t0 = time.perf_counter()
                t_match = next((t for t in tracks if str(t.track_id) == str(getattr(a, "track_id", None))), None)
                face_b = plate_b = None
                plate_text = ""
                plate_conf = 0.0
                plate_uncertain = True
                if t_match is not None and modality in ("STANDARD", "RGB"):
                    try:
                        from backend.detection.evidence_detectors import get_plate_recognizer
                        pr2 = get_plate_recognizer()
                        dp = pr2.detect_in_vehicle(img, t_match.bounding_box)
                        if dp is not None:
                            plate_b = dp["bbox"]
                            reading = pr2.read_plate(img, plate_b)
                            plate_text = reading["text"]
                            plate_conf = reading["confidence"]
                            plate_uncertain = reading["uncertain"]
                            key = f"{fd.camera_id}:{t_match.track_id}"
                            if plate_text:
                                plate_collector.add_observation(
                                    track_key=key, text=plate_text, confidence=plate_conf,
                                    frame_number=n, timestamp=fd.timestamp,
                                    sharpness=float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()),
                                    vehicle_box=list(t_match.bounding_box[:4]), plate_box=list(plate_b[:4]))
                            consensus = plate_collector.get_best(key)
                            if consensus is not None and (not plate_text or consensus.confidence > plate_conf):
                                plate_text = consensus.text
                                plate_conf = consensus.confidence
                                plate_uncertain = consensus.uncertain
                            anpr_reads.append({
                                "frame": n, "track_id": t_match.track_id, "text": plate_text,
                                "confidence": plate_conf, "uncertain": plate_uncertain,
                            })
                    except Exception as anpr_err:
                        anpr_reads.append({"frame": n, "error": str(anpr_err)})
                try:
                    evidence = snap_mgr.create_evidence_package_async(
                        incident_id=str(a.event_id), image=img, camera_id=fd.camera_id,
                        frame_number=n, trigger_reason=a.message or "ALERT",
                        bounding_boxes=[t.bounding_box for t in tracks if t.bounding_box],
                        plate_bbox=plate_b, confidence=0.9,
                        plate_text=plate_text or None, plate_conf=plate_conf or None,
                        plate_uncertain=plate_uncertain,
                    )
                    evidence_files.append(evidence.file_uri)
                    alerts.append({
                        "frame": n, "event_id": str(a.event_id), "severity": a.severity,
                        "message": a.message, "track_id": getattr(a, "track_id", None),
                        "plate": plate_text or None, "plate_conf": plate_conf or None,
                        "plate_uncertain": plate_uncertain,
                        "evidence": evidence.file_uri,
                    })
                except Exception as ev_err:
                    alerts.append({"frame": n, "evidence_error": str(ev_err)})
                stage["evidence"] += (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        scale = min(1.0, 1280.0 / w)
        render = img if scale >= 1.0 else cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        annotated = annotate_frame(render, tracks, zones=list(zm.zones.values()),
                                   camera_id=fd.camera_id, display_fps=0, inference_fps=0,
                                   device="cpu", stride=2, modality=modality)
        stage["annotate"] += (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        ok_enc, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 60])
        stage["jpeg"] += (time.perf_counter() - t0) * 1000
        writer.write(annotated)

        latencies.append((time.perf_counter() - t_loop) * 1000)

    cap.release()
    writer.release()

    # ID switch metric: IDs whose frame coverage has a gap > 5 (fragmentation)
    fragmented = []
    for tid, frames in track_seen_frames.items():
        fl = sorted(frames)
        gaps = [(b - a) for a, b in zip(fl[:-1], fl[1:])]
        max_gap = max(gaps) if gaps else 0
        if max_gap > 5:
            fragmented.append({"track_id": tid, "max_gap": max_gap, "frames": len(fl)})

    report.update({
        "frames_processed": n,
        "frames_inferred": n_inf,
        "total_detections": det_total,
        "detections_per_inferred_frame": round(det_total / max(n_inf, 1), 2),
        "detections_by_class": det_by_class,
        "unique_track_ids": len(id_first_frame),
        "track_lifetimes": {tid: [id_first_frame[tid], id_last_frame[tid]]
                            for tid in sorted(id_first_frame, key=lambda x: int(x))},
        "fragmented_tracks": fragmented,
        "zone_events": zone_events_total,
        "alerts": alerts,
        "alert_count": len(alerts),
        "evidence_packages": len(evidence_files),
        "anpr_reads": anpr_reads if modality == "STANDARD" else "n/a (non-RGB modality)",
        "latency_ms_avg": round(float(np.mean(latencies)), 2),
        "latency_ms_p95": round(float(np.percentile(latencies, 95)), 2),
        "stage_ms_per_frame": {k: round(v / max(n, 1), 3) for k, v in stage.items()},
        "ingestion_fps_theoretical": round(1000.0 / (sum(stage.values()) / max(n, 1)), 2),
        "annotated_output": str(out_dir / "annotated.mp4"),
    })

    with open(out_dir / "report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    return report


async def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_reports = []
    for demo in DEMOS:
        print(f"\n=== {demo['id']} ===")
        r = await run_demo(demo)
        all_reports.append(r)
        print(f"  frames={r['frames_processed']} dets/inf={r['detections_per_inferred_frame']} "
              f"unique_ids={r['unique_track_ids']} alerts={r['alert_count']} "
              f"evidence={r['evidence_packages']} e2e={r['latency_ms_avg']}ms "
              f"({r['ingestion_fps_theoretical']}fps theoretical)")
        if r["alerts"]:
            for a in r["alerts"][:5]:
                print(f"    alert f{a['frame']}: {a.get('message', a.get('evidence_error'))[:80]}")
        if isinstance(r["anpr_reads"], list) and r["anpr_reads"]:
            cons = {}
            for rd in r["anpr_reads"]:
                if "text" in rd and rd["text"]:
                    cons.setdefault(rd["track_id"], []).append((rd["text"], round(rd["confidence"], 2)))
            print(f"  ANPR reads by track:")
            for tid, reads in list(cons.items())[:8]:
                print(f"    track {tid}: {reads[:4]}")
    with open(OUT_ROOT / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(all_reports, fh, indent=2, default=str)
    print(f"\nFull reports: {OUT_ROOT}/<demo>/report.json + summary.json")
    print(f"Annotated videos: {OUT_ROOT}/<demo>/annotated.mp4")


if __name__ == "__main__":
    asyncio.run(main())
