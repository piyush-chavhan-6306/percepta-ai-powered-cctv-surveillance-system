"""Verify face detection fix — crop-based + lower threshold."""
import sys, time, cv2
sys.path.insert(0, '.')
from backend.detection.detector import get_detector
from backend.detection.evidence_detectors import get_face_detector

det = get_detector(); det.initialize()
face = get_face_detector()
print(f'Threshold: {face.score_threshold}')

# Test on VIRAT RGB footage (has people)
import glob
clips = sorted(glob.glob("dataset/surveillance/CCTV 01/*.mp4"))
if not clips:
    print("No VIRAT clips found"); exit()

cap = cv2.VideoCapture(clips[0])
fps = cap.get(cv2.CAP_PROP_FPS)
total = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 30)
w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f'Video: {clips[0]} ({w}x{h}, {fps} FPS, {total} frames)')

face_total = 0; crop_faces = 0; full_faces = 0
for fn in range(1, total+1):
    ret, f = cap.read()
    if not ret: break
    dets = det.detect(f)
    persons = [d.bounding_box for d in dets if d.class_name == 'person']
    for pb in persons:
        try:
            fv = face.best_face_in_box(f, pb, min_face_px=8)
            if fv:
                face_total += 1
                fb = fv['bbox']
                fw, fh = int(fb[2]-fb[0]), int(fb[3]-fb[1])
                if fn <= 3 or face_total <= 3:
                    print(f'  Fr{fn} face {fw}x{fh} conf={fv["confidence"]:.3f}')
        except Exception as e:
            print(f'  Error: {e}')
cap.release()
print(f'\nVIRAT RGB: {face_total} faces in {total} frames')

# Also test night IR
cap2 = cv2.VideoCapture('dataset/surveillance/night_ir_patrol.mp4')
fps2 = cap2.get(cv2.CAP_PROP_FPS)
w2, h2 = int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT))
total2 = min(int(cap2.get(cv2.CAP_PROP_FRAME_COUNT)), 30)
face_night = 0
for fn in range(1, total2+1):
    ret, f = cap2.read()
    if not ret: break
    dets = det.detect(f)
    persons = [d.bounding_box for d in dets if d.class_name == 'person']
    for pb in persons:
        try:
            fv = face.best_face_in_box(f, pb, min_face_px=8)
            if fv: face_night += 1
        except: pass
cap2.release()
print(f'Night IR: {face_night} faces in {total2} frames')

# Test thermal
cap3 = cv2.VideoCapture('dataset/surveillance/thermal_patrol.mp4')
fps3 = cap3.get(cv2.CAP_PROP_FPS)
w3, h3 = int(cap3.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap3.get(cv2.CAP_PROP_FRAME_HEIGHT))
total3 = min(int(cap3.get(cv2.CAP_PROP_FRAME_COUNT)), 30)
face_therm = 0
for fn in range(1, total3+1):
    ret, f = cap3.read()
    if not ret: break
    dets = det.detect(f)
    persons = [d.bounding_box for d in dets if d.class_name == 'person']
    for pb in persons:
        try:
            fv = face.best_face_in_box(f, pb, min_face_px=8)
            if fv: face_therm += 1
        except: pass
cap3.release()
print(f'Thermal: {face_therm} faces in {total3} frames')
print('DONE')
