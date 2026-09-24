"""Face detection test on VIRAT footage and downloaded videos."""
import sys, os, json, time, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import datetime, timezone
from backend.detection.detector import get_detector
from backend.detection.evidence_detectors import get_face_detector
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.ingestion.adapter import FrameData
from backend.events.schema import SourceType

det = get_detector(); det.initialize()
face = get_face_detector()
trk = ByteTrackTracker(); trk.initialize()

def test_face_detection(video_path, label, n=60):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"SKIP: {video_path}"); return None
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = min(n, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    
    face_count = 0
    face_sizes = []
    face_confs = []
    person_tracks = 0
    face_ms = []
    det_ms = []
    track_ms = []
    all_ids = set()
    t0 = time.time()
    
    for fn in range(1, n + 1):
        ret, f = cap.read()
        if not ret: break
        
        # Detection
        t1 = time.perf_counter()
        dets = det.detect(f)
        det_ms.append((time.perf_counter() - t1) * 1000)
        
        # Tracking
        ts = datetime.fromtimestamp(fn / fps, tz=timezone.utc)
        fd = FrameData(camera_id=label, image=f, frame_number=fn, fps=fps,
                       width=w, height=h, timestamp=ts, source=SourceType.VIDEO_FILE)
        t2 = time.perf_counter()
        tracks = trk.update(dets, fd)
        track_ms.append((time.perf_counter() - t2) * 1000)
        
        for t in tracks:
            all_ids.add(t.track_id)
            if t.object_class == "person":
                person_tracks += 1
                if t.bounding_box and len(t.bounding_box) >= 4:
                    t3 = time.perf_counter()
                    try:
                        fv = face.best_face_in_box(f, t.bounding_box, min_face_px=8)
                        if fv:
                            face_count += 1
                            fb = fv["bbox"]
                            fw, fh = int(fb[2] - fb[0]), int(fb[3] - fb[1])
                            face_sizes.append((fw, fh))
                            face_confs.append(fv["confidence"])
                    except Exception as e:
                        pass
                    face_ms.append((time.perf_counter() - t3) * 1000)
    
    cap.release()
    elapsed = time.time() - t0
    
    avg_det = np.mean(det_ms) if det_ms else 0
    avg_trk = np.mean(track_ms) if track_ms else 0
    avg_fc = np.mean(face_ms) if face_ms else 0
    avg_w = np.mean([s[0] for s in face_sizes]) if face_sizes else 0
    avg_h = np.mean([s[1] for s in face_sizes]) if face_sizes else 0
    avg_conf = np.mean(face_confs) if face_confs else 0
    
    print(f"\n{'='*60}")
    print(f"FACE DETECTION TEST: {label}")
    print(f"{'='*60}")
    print(f"Video: {video_path}")
    print(f"Resolution: {w}x{h} | FPS: {fps} | Frames: {n}")
    print(f"Elapsed: {elapsed:.1f}s ({n/elapsed:.1f} processing FPS)")
    print(f"")
    print(f"Detection: {avg_det:.1f}ms/frame")
    print(f"Tracking: {avg_trk:.1f}ms/frame")
    print(f"Face detection: {avg_fc:.1f}ms/frame")
    print(f"")
    print(f"Person track-frames: {person_tracks}")
    print(f"Unique track IDs: {len(all_ids)}")
    print(f"Face detections: {face_count}")
    print(f"Face rate: {face_count/max(person_tracks,1):.1%} of person tracks")
    print(f"")
    if face_sizes:
        print(f"Face sizes: avg {avg_w:.0f}x{avg_h:.0f}px")
        print(f"Face confidence: avg {avg_conf:.3f}")
        widths = [s[0] for s in face_sizes]
        heights = [s[1] for s in face_sizes]
        print(f"Smallest face: {min(widths)}x{min(heights)}px")
        print(f"Largest face: {max(widths)}x{max(heights)}px")
    
    return {
        "video": video_path, "resolution": f"{w}x{h}", "frames": n,
        "fps": round(n/elapsed, 1), "det_ms": round(avg_det, 1),
        "track_ms": round(avg_trk, 1), "face_ms": round(avg_fc, 1),
        "person_tracks": person_tracks, "face_detections": face_count,
        "face_rate": round(face_count/max(person_tracks,1), 3),
        "avg_face_size": f"{avg_w:.0f}x{avg_h:.0f}",
        "avg_face_conf": round(avg_conf, 3),
    }

results = []

# Test 1: VIRAT RGB footage (known to have people)
import glob
virat_clips = sorted(glob.glob("dataset/surveillance/CCTV 01/*.mp4"))
if virat_clips:
    for clip in virat_clips[:3]:
        r = test_face_detection(clip, os.path.basename(clip), n=60)
        if r: results.append(r)

# Test 2: VIRAT ANPR video (has vehicles + some people)
if os.path.exists("dataset/surveillance/anpr_vehicle_checkpoint.mp4"):
    r = test_face_detection("dataset/surveillance/anpr_vehicle_checkpoint.mp4", "ANPR", n=60)
    if r: results.append(r)

# Test 3: OpenCV test videos
for v in ["Megamind.avi", "vtest.avi"]:
    path = f"dataset/surveillance/face_detection/{v}"
    if os.path.exists(path):
        r = test_face_detection(path, v, n=60)
        if r: results.append(r)

# Test 4: Night IR (no faces expected - YuNet is RGB only)
if os.path.exists("dataset/surveillance/night_ir_patrol.mp4"):
    r = test_face_detection("dataset/surveillance/night_ir_patrol.mp4", "Night IR", n=30)
    if r: results.append(r)

# Test 5: Thermal (no faces expected)
if os.path.exists("dataset/surveillance/thermal_patrol.mp4"):
    r = test_face_detection("dataset/surveillance/thermal_patrol.mp4", "Thermal", n=30)
    if r: results.append(r)

# Save results
os.makedirs("scratch", exist_ok=True)
with open("scratch/face_detection_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Print summary table
print(f"\n{'='*60}")
print("SUMMARY TABLE")
print(f"{'='*60}")
print(f"{'Video':<30} {'Res':<12} {'FPS':<8} {'Faces':<8} {'Rate':<8} {'Size':<12}")
print("-" * 78)
for r in results:
    print(f"{r['video']:<30} {r['resolution']:<12} {r['fps']:<8} {r['face_detections']:<8} {r['face_rate']:<8} {r['avg_face_size']:<12}")

print(f"\nResults saved to scratch/face_detection_results.json")
