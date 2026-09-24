"""Fast modality diagnostics — detection + tracking on all test videos."""
import sys, os, json, time, logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2, numpy as np
logging.basicConfig(level=logging.WARNING)

for n in ["backend.detection.evidence_detectors","backend.detection.plate_aggregator",
          "backend.tracking.bytetrack_wrapper","backend.tracking.pipeline",
          "ultralytics"]:
    logging.getLogger(n).setLevel(logging.ERROR)

def run_quick(video, label, modality="STANDARD", max_frames=80):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        print(f"  SKIP: {video}")
        return None
    total = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), max_frames)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    from backend.detection.detector import get_detector
    from backend.detection.evidence_detectors import get_face_detector
    from backend.tracking.bytetrack_wrapper import ByteTrackTracker
    from backend.ingestion.adapter import FrameData
    from backend.events.schema import SourceType
    
    det = get_detector(); det.initialize()
    face = get_face_detector()
    trk = ByteTrackTracker(); trk.initialize()
    
    dets_pf, face_count, total_dets = [], 0, 0
    det_ms, trk_ms, face_ms_arr = [], [], []
    all_ids = set()
    
    t0 = time.time()
    for fn in range(1, total+1):
        ret, fbgr = cap.read()
        if not ret: break
        ts = datetime.fromtimestamp(fn / fps if fps > 0 else time.time(), tz=timezone.utc)
        fd = FrameData(camera_id=label, image=fbgr, frame_number=fn, fps=fps,
                       width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE, modality=modality)
        
        t1 = time.perf_counter()
        dets = det.detect(fbgr)
        det_ms.append((time.perf_counter()-t1)*1000)
        
        t2 = time.perf_counter()
        tracks = trk.update(dets, fd)
        trk_ms.append((time.perf_counter()-t2)*1000)
        
        dets_pf.append(len(dets))
        total_dets += len(dets)
        for t in tracks:
            all_ids.add(t.track_id)
            if t.object_class == "person" and t.bounding_box:
                t3 = time.perf_counter()
                try:
                    f = face.best_face_in_box(fbgr, t.bounding_box, min_face_px=8)
                    if f: face_count += 1
                except: pass
                face_ms_arr.append((time.perf_counter()-t3)*1000)
        
        if fn % 20 == 0:
            el = time.time()-t0
            print(f"  {fn}/{total} ({fn/el:.1f}fps) dets={len(dets)} tracks={len(tracks)} faces={face_count}")
    
    cap.release()
    el = time.time()-t0
    avg_dets = np.mean(dets_pf) if dets_pf else 0
    print(f"\n  {label}: {w}x{h} | {modality} | {total} frames")
    print(f"  Dets: {total_dets} ({avg_dets:.1f}/frame) | IDs: {len(all_ids)} | Faces: {face_count}")
    print(f"  Det: {np.mean(det_ms):.1f}ms | Track: {np.mean(trk_ms):.1f}ms | Face: {np.mean(face_ms_arr) if face_ms_arr else 0:.1f}ms")
    print(f"  FPS: {total/el:.1f}")
    return {"frames": total, "dets_per_frame": avg_dets, "unique_ids": len(all_ids), 
            "faces": face_count, "det_ms": float(np.mean(det_ms)), "trk_ms": float(np.mean(trk_ms)),
            "fps": total/el}

R = {}
print("="*60 + "\nPHASE C: ANPR VIDEO\n" + "="*60)
R["anpr"] = run_quick("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "anpr")

print("\n" + "="*60 + "\nPHASE F: NIGHT/IR\n" + "="*60)
R["night"] = run_quick("dataset/surveillance/night_ir_patrol.mp4", "night", "IR_NIGHT")

print("\n" + "="*60 + "\nPHASE G: THERMAL\n" + "="*60)
R["thermal"] = run_quick("dataset/surveillance/thermal_patrol.mp4", "thermal", "THERMAL")

import glob
print("\n" + "="*60 + "\nPHASE G: REAL PTB-TIR (park1)\n" + "="*60)
tf = glob.glob("dataset/surveillance/thermal_real/ptb_tir_park1.mp4")
if tf: R["thermal_park1"] = run_quick(tf[0], "park1", "THERMAL")

print("\n" + "="*60 + "\nPHASE G: REAL PTB-TIR (road2)\n" + "="*60)
tf2 = glob.glob("dataset/surveillance/thermal_real/ptb_tir_road2.mp4")
if tf2: R["thermal_road2"] = run_quick(tf2[0], "road2", "THERMAL")

print("\n" + "="*60 + "\nPHASE F: NIRPED NIGHT\n" + "="*60)
nf = glob.glob("dataset/surveillance/night_real/nirped_*.mp4")
if nf: R["nirped"] = run_quick(nf[0], "nirped", "NIGHT_IR")

os.makedirs("scratch", exist_ok=True)
with open("scratch/quick_diagnostic.json", "w") as f:
    json.dump(R, f, indent=2, default=str)
print(f"\nSaved to scratch/quick_diagnostic.json")
