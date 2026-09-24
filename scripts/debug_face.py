"""Debug face detection — why 0 faces found."""
import sys, time, cv2
sys.path.insert(0, '.')
from backend.detection.detector import get_detector
from backend.detection.evidence_detectors import get_face_detector

det = get_detector(); det.initialize()
face = get_face_detector()

cap = cv2.VideoCapture('dataset/surveillance/anpr_vehicle_checkpoint.mp4')
ret, f = cap.read()
cap.release()

print(f'Frame: {f.shape}')

# Direct face detection on full frame
t0 = time.time()
faces = face.detect(f)
print(f'Full frame faces: {len(faces)} ({(time.time()-t0)*1000:.0f}ms)')
for fac in faces[:5]:
    b = fac['bbox']
    fw, fh = int(b[2]-b[0]), int(b[3]-b[1])
    print(f'  face {fw}x{fh} conf={fac["confidence"]:.3f}')

# YOLO detections
dets = det.detect(f)
person_boxes = [d.bounding_box for d in dets if d.class_name == 'person']
print(f'\nPerson boxes from YOLO: {len(person_boxes)}')
for i, pb in enumerate(person_boxes[:5]):
    pw, ph = int(pb[2]-pb[0]), int(pb[3]-pb[1])
    print(f'  person {i}: {pw}x{ph} at ({int(pb[0])},{int(pb[1])})')

# Face detection on first person crop
if person_boxes:
    pb = person_boxes[0]
    crop = f[max(0,int(pb[1])):min(f.shape[0],int(pb[3])), max(0,int(pb[0])):min(f.shape[1],int(pb[2]))]
    if crop.size > 0:
        print(f'\nPerson crop: {crop.shape}')
        fc = face.detect(crop)
        print(f'Faces in crop: {len(fc)}')
        for ff in fc:
            b = ff['bbox']
            print(f'  face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={ff["confidence"]:.3f}')

        # 3x upscale
        up = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        print(f'\nUpscaled 3x: {up.shape}')
        fc2 = face.detect(up)
        print(f'Faces in upscaled: {len(fc2)}')
        for ff in fc2:
            b = ff['bbox']
            print(f'  face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={ff["confidence"]:.3f}')

# Also try the face_detector's detect on head region
if person_boxes:
    pb = person_boxes[0]
    head_y2 = int(pb[1] + (pb[3]-pb[1])*0.35)
    head_crop = f[max(0,int(pb[1])):min(f.shape[0],head_y2), max(0,int(pb[0])):min(f.shape[1],int(pb[2]))]
    if head_crop.size > 0:
        print(f'\nHead crop: {head_crop.shape}')
        fh = face.detect(head_crop)
        print(f'Faces in head crop: {len(fh)}')
        for ff in fh:
            b = ff['bbox']
            print(f'  face {int(b[2]-b[0])}x{int(b[3]-b[1])} conf={ff["confidence"]:.3f}')

# Test on a known-good image (download a test face)
print('\n--- YuNet model check ---')
print(f'Model path: {face.model_path}')
print(f'Available: {face.available}')
print(f'Input size: {face.input_size}')
print(f'Score threshold: {face.score_threshold}')

# Create a synthetic test image with a white rectangle (won't detect as face, but validates pipeline)
import numpy as np
test_img = np.zeros((320, 320, 3), dtype=np.uint8)
test_img[50:150, 80:200] = 200  # bright rectangle
tfc = face.detect(test_img)
print(f'\nSynthetic test (bright rect): {len(tfc)} faces (expected 0)')

# Test with face detector on the person track using best_face_in_box
if person_boxes:
    pb = person_boxes[0]
    best = face.best_face_in_box(f, pb, min_face_px=8)
    print(f'\nbest_face_in_box result: {best}')
    
    # Try with lower min_face_px
    best2 = face.best_face_in_box(f, pb, min_face_px=4)
    print(f'best_face_in_box (min_face_px=4): {best2}')
    
    # Try without person_box constraint
    best3 = face.best_face_in_box(f, None, min_face_px=8)
    print(f'best_face_in_box (no person_box): {best3}')
