"""Phase J: Regression testing — verify all fixes, no breakage."""
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

def regression_test(path, label, mod, n=40):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"SKIP: {path}"); return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = min(n, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

    ids_set = set()
    dets_per_frame = []
    face_count = 0
    plate_dets = 0
    errors = []
    total_ms = []

    t0 = time.time()
    for fn in range(1, n + 1):
        ret, f = cap.read()
        if not ret: break

        ts = datetime.fromtimestamp(fn / fps, tz=timezone.utc)
        fd = FrameData(camera_id=label, image=f, frame_number=fn, fps=fps,
                       width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE, modality=mod)

        try:
            t_start = time.perf_counter()
            dets = det.detect(f)
            tracks = trk.update(dets, fd)
            total_ms.append((time.perf_counter() - t_start) * 1000)
        except Exception as e:
            errors.append(f"Frame {fn}: pipeline error: {e}")
            continue

        dets_per_frame.append(len(dets))
        for t in tracks:
            ids_set.add(t.track_id)
            if t.object_class == "person" and t.bounding_box:
                try:
                    fv = face.best_face_in_box(f, t.bounding_box, min_face_px=8)
                    if fv: face_count += 1
                except Exception as e:
                    errors.append(f"Frame {fn}: face error: {e}")
            if t.object_class in ("car", "truck", "bus") and t.bounding_box:
                try:
                    pd = plate.detect_in_vehicle(f, t.bounding_box)
                    if pd: plate_dets += 1
                except Exception as e:
                    errors.append(f"Frame {fn}: plate error: {e}")

    cap.release()
    el = time.time() - t0
    avg_dets = np.mean(dets_per_frame) if dets_per_frame else 0
    avg_ms = np.mean(total_ms) if total_ms else 0

    status = "PASS" if not errors else "FAIL"
    print(f"  {status} {label}: {w}x{h} {mod} | {len(dets_per_frame)}fr {len(dets_per_frame)/el:.1f}fps")
    print(f"    Dets: {avg_dets:.1f}/fr | IDs: {len(ids_set)} | Faces: {face_count} | Plates: {plate_dets}")
    print(f"    Avg frame: {avg_ms:.0f}ms | Errors: {len(errors)}")
    if errors:
        for e in errors[:3]:
            print(f"    ERROR: {e}")

    return {
        "status": status, "frames": len(dets_per_frame), "fps": len(dets_per_frame) / el,
        "dets_per_frame": float(avg_dets), "unique_ids": len(ids_set),
        "faces": face_count, "plates": plate_dets, "errors": len(errors),
        "avg_ms": float(avg_ms),
    }


print("=" * 60)
print("PHASE J: REGRESSION TESTING")
print("=" * 60)

R = {}
R["anpr"] = regression_test("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "anpr", "STANDARD")
R["night"] = regression_test("dataset/surveillance/night_ir_patrol.mp4", "night", "IR_NIGHT")
R["thermal"] = regression_test("dataset/surveillance/thermal_patrol.mp4", "thermal", "THERMAL")

import glob
tf = glob.glob("dataset/surveillance/thermal_real/ptb_tir_park1.mp4")
if tf: R["park1"] = regression_test(tf[0], "park1", "THERMAL")
tf2 = glob.glob("dataset/surveillance/thermal_real/ptb_tir_road2.mp4")
if tf2: R["road2"] = regression_test(tf2[0], "road2", "THERMAL")
nf = glob.glob("dataset/surveillance/night_real/nirped_*.mp4")
if nf: R["nirped"] = regression_test(nf[0], "nirped", "NIGHT_IR")

# Also test RGB VIRAT clip
clips = sorted(glob.glob("dataset/surveillance/CCTV 01/*.mp4"))
if clips:
    R["virat_rgb"] = regression_test(clips[0], "virat_rgb", "STANDARD")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
all_pass = all(r["status"] == "PASS" for r in R.values() if r)
print(f"Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
for k, v in R.items():
    if v:
        print(f"  {k}: {v['status']} ({v['errors']} errors, {v['fps']:.1f}fps)")

os.makedirs("scratch", exist_ok=True)
with open("scratch/regression_results.json", "w") as f:
    json.dump(R, f, indent=2, default=str)
print(f"\nSaved to scratch/regression_results.json")
