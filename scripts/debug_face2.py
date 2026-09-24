"""Debug face detection — check frame 150 and profile face detector."""
import sys, time, cv2
sys.path.insert(0, '.')
from backend.detection.detector import get_detector
from backend.detection.evidence_detectors import get_face_detector

det = get_detector(); det.initialize()
face = get_face_detector()

cap = cv2.VideoCapture('dataset/surveillance/anpr_vehicle_checkpoint.mp4')
fps = cap.get(cv2.CAP_PROP_FPS)
# Jump to frame 150 (middle of video)
cap.set(cv2.CAP_PROP_POS_FRAMES, 149)
ret, f = cap.read()
cap.release()

print(f'Frame 150: {f.shape}')

# YOLO detections
t0 = time.perf_counter()
dets = det.detect(f)
det_ms = (time.perf_counter() - t0) * 1000
person_boxes = [d.bounding_box for d in dets if d.class_name == 'person']
vehicle_boxes = [d.bounding_box for d in dets if d.class_name in ('car', 'truck', 'bus')]
print(f'YOLO: {len(dets)} dets ({det_ms:.0f}ms), {len(person_boxes)} persons, {len(vehicle_boxes)} vehicles')
for i, pb in enumerate(person_boxes[:5]):
    pw, ph = int(pb[2]-pb[0]), int(pb[3]-pb[1])
    print(f'  person {i}: {pw}x{ph} at ({int(pb[0])},{int(pb[1])})')

# Face detection on full frame
t0 = time.perf_counter()
faces_full = face.detect(f)
face_full_ms = (time.perf_counter() - t0) * 1000
print(f'\nFace (full frame): {len(faces_full)} faces ({face_full_ms:.0f}ms)')
for fc in faces_full[:5]:
    b = fc['bbox']
    print(f'  face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={fc["confidence"]:.3f}')

# Face detection on person crops (the FIX)
print('\n--- Face on person crops ---')
for i, pb in enumerate(person_boxes[:5]):
    pw, ph = int(pb[2]-pb[0]), int(pb[3]-pb[1])
    # Crop top 40% of person (likely head/face region)
    head_y2 = int(pb[1] + (pb[3]-pb[1])*0.40)
    crop = f[max(0,int(pb[1])):min(f.shape[0],head_y2), max(0,int(pb[0])):min(f.shape[1],int(pb[2]))]
    if crop.size == 0:
        continue
    ch, cw = crop.shape[:2]
    
    # Direct detect
    t0 = time.perf_counter()
    fc = face.detect(crop)
    ms = (time.perf_counter() - t0) * 1000
    print(f'  person {i} crop {cw}x{ch}: {len(fc)} faces ({ms:.0f}ms)')
    for ff in fc[:2]:
        b = ff['bbox']
        print(f'    face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={ff["confidence"]:.3f}')
    
    # 2x upscale
    if ch > 10 and cw > 10:
        up = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        t0 = time.perf_counter()
        fc2 = face.detect(up)
        ms2 = (time.perf_counter() - t0) * 1000
        print(f'    2x upscale {up.shape[1]}x{up.shape[0]}: {len(fc2)} faces ({ms2:.0f}ms)')
        for ff in fc2[:2]:
            b = ff['bbox']
            print(f'      face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={ff["confidence"]:.3f}')

# Also test with score_threshold lowered
print('\n--- With lower threshold (0.3) ---')
face_low = get_face_detector()
face_low.score_threshold = 0.3
face_low._detector = None  # Force reload
face_low._ensure_loaded()
t0 = time.perf_counter()
faces_low = face_low.detect(f)
ms_low = (time.perf_counter() - t0) * 1000
print(f'Faces (threshold 0.3): {len(faces_low)} ({ms_low:.0f}ms)')
for fc in faces_low[:10]:
    b = fc['bbox']
    print(f'  face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={fc["confidence"]:.3f}')
