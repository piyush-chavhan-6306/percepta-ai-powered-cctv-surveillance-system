import cv2, os, json, hashlib, numpy as np, time

img_dir = "D:/temp/nirped/val_images"
imgs = sorted([f for f in os.listdir(img_dir) if f.endswith(".png")])

print(f"NIRPed validation images: {len(imgs)}")
sample = cv2.imread(os.path.join(img_dir, imgs[0]))
h, w = sample.shape[:2]
print(f"Sample: {imgs[0]}, shape={sample.shape}, dtype={sample.dtype}")
print(f"Min pixel: {sample.min()}, Max pixel: {sample.max()}, Mean: {sample.mean():.1f}")

# Check if grayscale stored as BGR
if len(sample.shape) == 3 and sample.shape[2] == 3:
    diff_01 = np.std(sample[:,:,0].astype(float) - sample[:,:,1].astype(float))
    diff_12 = np.std(sample[:,:,1].astype(float) - sample[:,:,2].astype(float))
    print(f"Channel diff 0-1: {diff_01:.2f}, 1-2: {diff_12:.2f}")
    if diff_01 < 2.0 and diff_12 < 2.0:
        print("Modality: GRAYSCALE stored as BGR (NIR)")
    else:
        print("Modality: COLOR")

# Check annotation structure
with open("D:/temp/nirped/val_mini.json") as f:
    ann = json.load(f)
print(f"\nAnnotation keys: {list(ann.keys())}")
if "annotations" in ann:
    print(f"Number of annotations: {len(ann['annotations'])}")
    if ann["annotations"]:
        print(f"Sample annotation: {json.dumps(ann['annotations'][0], indent=2)[:300]}")
if "images" in ann:
    print(f"Number of images: {len(ann['images'])}")
    if ann["images"]:
        print(f"Sample image entry: {json.dumps(ann['images'][0], indent=2)[:300]}")

# Convert to MP4
out_path = "D:/SIH   border cctv/dataset/surveillance/night_real/nirped_val_sequence.mp4"
fps = 10
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

print(f"\nConverting to MP4 ({len(imgs)} frames, {w}x{h}, {fps} FPS)...")
t0 = time.time()
for i, fname in enumerate(imgs):
    frame = cv2.imread(os.path.join(img_dir, fname))
    if frame is not None:
        writer.write(frame)
    if (i+1) % 40 == 0:
        print(f"  {i+1}/{len(imgs)} frames written")
writer.release()
elapsed = time.time() - t0

file_size = os.path.getsize(out_path)
with open(out_path, "rb") as f:
    md5 = hashlib.md5(f.read()).hexdigest()

cap = cv2.VideoCapture(out_path)
actual_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
actual_fps = cap.get(cv2.CAP_PROP_FPS)
cap.release()

print(f"Output: {out_path}")
print(f"Size: {file_size/1e6:.1f} MB, Frames: {actual_frames}, FPS: {actual_fps}, Time: {elapsed:.1f}s")
print(f"MD5: {md5}")
