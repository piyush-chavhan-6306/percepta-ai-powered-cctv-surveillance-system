"""
Border Intelligence Model Weight Downloader.
Pre-downloads and caches YOLOv8 detection weights into ./models/ for offline deployment.

Also stages the evidence-detection models (idempotent — skips files already present):
  - models/anpr/plate_yolov8n.onnx       YOLOv8n single-class license-plate detector
  - models/anpr/en_PP-OCRv3_rec_infer.onnx  PP-OCRv3 English CTC recognition head
  - models/anpr/en_dict.txt              PaddleOCR charset for CTC decoding
  - models/face/face_detection_yunet_2023mar.onnx  OpenCV YuNet face detector
All four run through ONNX Runtime / OpenCV DNN on CPU — no PyTorch-only deps.
"""
import sys
import urllib.request
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.detection.model_loader import ModelLoader

EVIDENCE_MODELS = {
    "models/anpr/plate_yolov8n.onnx":
        "https://huggingface.co/ml-debi/yolov8-license-plate-detection/resolve/main/best.onnx",
    "models/anpr/en_PP-OCRv3_rec_infer.onnx":
        "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv3/en_PP-OCRv3_rec_infer.onnx",
    "models/anpr/en_dict.txt":
        "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/en_dict.txt",
    "models/face/face_detection_yunet_2023mar.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
}


def stage_evidence_models() -> None:
    print("--- Evidence models (plate / OCR / face) ---")
    for rel, url in EVIDENCE_MODELS.items():
        target = Path(rel)
        if target.exists():
            print(f"[OK] {rel} already cached")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"[DOWNLOADING] {rel} ...")
        try:
            urllib.request.urlretrieve(url, target)
            print(f"[OK] cached {rel}")
        except Exception as err:
            print(f"[WARN] could not fetch {rel}: {err}")
            print("       ANPR/face evidence will degrade gracefully (detectors report unavailable).")


def main():
    print("=== Border Intelligence Model Weight Caching Script ===")
    models_dir = Path("./models")
    loader = ModelLoader(models_dir=str(models_dir))

    target_weights = ["yolov8n.pt"]
    for weight in target_weights:
        target_path = loader.get_model_path(weight)
        if target_path.exists():
            print(f"[OK] Model {weight} already cached at: {target_path}")
        else:
            print(f"[DOWNLOADING] Downloading {weight} to local cache...")
            loader.load_model(weight)
            print(f"[OK] Successfully cached {weight} at: {target_path}")

    stage_evidence_models()

    print("\nAll model weights ready for offline execution.")


if __name__ == "__main__":
    main()
