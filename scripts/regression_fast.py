"""Phase J: Fast regression — pipeline stability only (skip slow evidence)."""
import sys, os, json, time, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import datetime, timezone
from backend.detection.detector import get_detector
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.ingestion.adapter import FrameData
from backend.events.schema import SourceType

det = get_detector(); det.initialize()
trk = ByteTrackTracker(); trk.initialize()

def quick_test(path, label, mod, n=30):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"SKIP: {path}"); return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = min(n, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    ids = set(); dets_list = []; ms_list = []; err = 0
    t0 = time.time()
    for fn in range(1, n + 1):
        ret, f = cap.read()
        if not ret: break
        try:
            ts = datetime.fromtimestamp(fn / fps, tz=timezone.utc)
            fd = FrameData(camera_id=label, image=f, frame_number=fn, fps=fps,
                           width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE, modality=mod)
            t1 = time.perf_counter()
            dets = det.detect(f)
            tracks = trk.update(dets, fd)
            ms_list.append((time.perf_counter() - t1) * 1000)
            dets_list.append(len(dets))
            for t in tracks: ids.add(t.track_id)
        except Exception as e:
            err += 1
            print(f"  ERROR fr{fn}: {e}")
    cap.release()
    el = time.time() - t0
    avg_d = np.mean(dets_list) if dets_list else 0
    avg_ms = np.mean(ms_list) if ms_list else 0
    status = "PASS" if err == 0 else "FAIL"
    print(f"  {status} {label}: {w}x{h} {mod} | {len(dets_list)}fr {len(dets_list)/el:.1f}fps | "
          f"dets={avg_d:.1f}/fr ids={len(ids)} | avg={avg_ms:.0f}ms | err={err}")
    return {"status": status, "fps": len(dets_list)/el, "err": err, "ids": len(ids), "dets": float(avg_d)}

print("=" * 60)
print("PHASE J: REGRESSION TESTING (fast)")
print("=" * 60)
R = {}
R["anpr"] = quick_test("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "anpr", "STANDARD")
R["night"] = quick_test("dataset/surveillance/night_ir_patrol.mp4", "night", "IR_NIGHT")
R["thermal"] = quick_test("dataset/surveillance/thermal_patrol.mp4", "thermal", "THERMAL")
import glob
tf = glob.glob("dataset/surveillance/thermal_real/ptb_tir_park1.mp4")
if tf: R["park1"] = quick_test(tf[0], "park1", "THERMAL")
tf2 = glob.glob("dataset/surveillance/thermal_real/ptb_tir_road2.mp4")
if tf2: R["road2"] = quick_test(tf2[0], "road2", "THERMAL")
nf = glob.glob("dataset/surveillance/night_real/nirped_*.mp4")
if nf: R["nirped"] = quick_test(nf[0], "nirped", "NIGHT_IR")
clips = sorted(glob.glob("dataset/surveillance/CCTV 01/*.mp4"))
if clips: R["virat_rgb"] = quick_test(clips[0], "virat_rgb", "STANDARD")

print("\nSUMMARY:")
all_pass = all(r["status"] == "PASS" for r in R.values() if r)
print(f"Overall: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")
os.makedirs("scratch", exist_ok=True)
with open("scratch/regression.json", "w") as f: json.dump(R, f, indent=2)
print("Saved to scratch/regression.json")
