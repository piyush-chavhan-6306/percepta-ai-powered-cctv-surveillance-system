"""Phase I: Full performance measurement + Phase J: Regression."""
import sys, os, json, time, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import datetime, timezone
from backend.detection.detector import get_detector
from backend.detection.evidence_detectors import get_face_detector, get_plate_recognizer
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.ingestion.adapter import FrameData
from backend.events.schema import SourceType

det = get_detector(); det.initialize()
face = get_face_detector()
plate = get_plate_recognizer()
trk = ByteTrackTracker(); trk.initialize()

def perf_test(path, label, mod, n=40):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f'SKIP: {path}'); return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = min(n, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    decode_t, det_t, trk_t, face_t, plate_t, total_t = [], [], [], [], [], []
    ids_set = set()
    dets_per_frame = []
    t0 = time.time()

    for fn in range(1, n + 1):
        ts_start = time.perf_counter()
        ret, f = cap.read()
        if not ret: break
        decode_t.append((time.perf_counter() - ts_start) * 1000)

        ts = datetime.fromtimestamp(fn / fps, tz=timezone.utc)
        fd = FrameData(camera_id=label, image=f, frame_number=fn, fps=fps,
                       width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE, modality=mod)

        t1 = time.perf_counter()
        dets = det.detect(f)
        det_t.append((time.perf_counter() - t1) * 1000)

        t2 = time.perf_counter()
        tracks = trk.update(dets, fd)
        trk_t.append((time.perf_counter() - t2) * 1000)

        dets_per_frame.append(len(dets))
        for t in tracks:
            ids_set.add(t.track_id)

        if fn % 5 == 0:
            for t in tracks[:2]:
                if t.object_class == "person" and t.bounding_box:
                    t3 = time.perf_counter()
                    try:
                        face.best_face_in_box(f, t.bounding_box, min_face_px=8)
                    except: pass
                    face_t.append((time.perf_counter() - t3) * 1000)
                if t.object_class in ("car", "truck", "bus") and t.bounding_box:
                    t4 = time.perf_counter()
                    try:
                        plate.detect_in_vehicle(f, t.bounding_box)
                    except: pass
                    plate_t.append((time.perf_counter() - t4) * 1000)

        total_t.append((time.perf_counter() - ts_start) * 1000)

    cap.release()
    el = time.time() - t0

    def stat(a, name):
        if not a: return f"  {name}: N/A"
        a = np.array(a)
        return f"  {name}: mean={a.mean():.1f}ms p50={np.median(a):.1f}ms p95={np.percentile(a,95):.1f}ms max={a.max():.1f}ms"

    all_ms = {"Decode": np.mean(decode_t), "Det": np.mean(det_t), "Track": np.mean(trk_t),
              "Face": np.mean(face_t) if face_t else 0, "Plate": np.mean(plate_t) if plate_t else 0}
    bn = max(all_ms, key=all_ms.get)
    avg_dets = np.mean(dets_per_frame) if dets_per_frame else 0

    print(f"\n  {label}: {w}x{h} {mod} {len(dets_per_frame)}fr {len(dets_per_frame)/el:.1f}fps")
    print(stat(decode_t, "Decode"))
    print(stat(det_t, "Detection"))
    print(stat(trk_t, "Tracking"))
    print(stat(face_t, "Face"))
    print(stat(plate_t, "Plate"))
    print(stat(total_t, "Total"))
    print(f"  Unique IDs: {len(ids_set)} | Dets/frame: {avg_dets:.1f}")
    print(f"  BOTTLENECK: {bn} ({all_ms[bn]:.1f}ms)")

    return {
        "bottleneck": bn, "fps": len(dets_per_frame) / el,
        "det_ms": float(np.mean(det_t)), "trk_ms": float(np.mean(trk_t)),
        "total_ms": float(np.mean(total_t)), "unique_ids": len(ids_set),
        "dets_per_frame": float(avg_dets),
    }


print("=" * 60)
print("PHASE I: FULL PERFORMANCE MEASUREMENT")
print("=" * 60)
R = {}

R["anpr"] = perf_test("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "anpr", "STANDARD")
R["night"] = perf_test("dataset/surveillance/night_ir_patrol.mp4", "night", "IR_NIGHT")
R["thermal"] = perf_test("dataset/surveillance/thermal_patrol.mp4", "thermal", "THERMAL")

import glob
tf = glob.glob("dataset/surveillance/thermal_real/ptb_tir_park1.mp4")
if tf: R["park1"] = perf_test(tf[0], "park1", "THERMAL")
nf = glob.glob("dataset/surveillance/night_real/nirped_*.mp4")
if nf: R["nirped"] = perf_test(nf[0], "nirped", "NIGHT_IR")

os.makedirs("scratch", exist_ok=True)
with open("scratch/perf_results.json", "w") as f:
    json.dump(R, f, indent=2, default=str)
print(f"\nSaved to scratch/perf_results.json")
