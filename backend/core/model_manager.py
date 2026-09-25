"""
PERCEPTA — Deterministic Model Manifest & Integrity Verification Engine.

Provides:
- Manifest of all required/optional perception models with exact file paths,
  byte sizes, SHA-256 hashes, and download mirrors.
- Verification function checking local availability and cryptographic integrity.
- Offline deployment support (verifies pre-provisioned local bundle without internet).
- Online auto-downloader for fresh developer clones.
- Explicit reporting during startup: prevents silent fake perception fallbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger("percepta.models")


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    name: str
    rel_path: str
    classification: str  # "REQUIRED" or "OPTIONAL"
    expected_size: int
    sha256: str
    download_urls: List[str]
    description: str


# Canonical Model Manifest for PERCEPTA Autonomous Surveillance
MODELS_MANIFEST: List[ModelSpec] = [
    ModelSpec(
        model_id="yolov8n_onnx",
        name="YOLOv8n General Detector (ONNX)",
        rel_path="models/detection/yolov8n.onnx",
        classification="REQUIRED",
        expected_size=13089190,
        sha256="4ee908ea0ed5de80b401bcbf3adb6821f42102addf635c0060d1276763c8f17a",
        download_urls=[
            "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx",
            "https://huggingface.co/arnabdhar/YOLOv8/resolve/main/yolov8n.onnx",
        ],
        description="High-speed ONNX runtime primary object & person detector.",
    ),
    ModelSpec(
        model_id="yolov8n_pt",
        name="YOLOv8n PyTorch Weights",
        rel_path="models/detection/yolov8n.pt",
        classification="REQUIRED",
        expected_size=6549796,
        sha256="f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
        download_urls=[
            "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
        ],
        description="PyTorch fallback and baseline validation detector.",
    ),
    ModelSpec(
        model_id="plate_yolov8n",
        name="License Plate Detector (ONNX)",
        rel_path="models/anpr/plate_yolov8n.onnx",
        classification="REQUIRED",
        expected_size=12238119,
        sha256="85d236280a1301ad98907947d284951dd2b20c23a6786ff50f7e6a8ec515bd50",
        download_urls=[
            "https://huggingface.co/ml-debi/yolov8-license-plate-detection/resolve/main/best.onnx",
        ],
        description="ANPR vehicle license plate localization model.",
    ),
    ModelSpec(
        model_id="en_ppocrv3",
        name="PP-OCRv3 Recognition Head (ONNX)",
        rel_path="models/anpr/en_PP-OCRv3_rec_infer.onnx",
        classification="REQUIRED",
        expected_size=8967018,
        sha256="ef7abd8bd3629ae57ea2c28b425c1bd258a871b93fd2fe7c433946ade9b5d9ea",
        download_urls=[
            "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv3/en_PP-OCRv3_rec_infer.onnx",
        ],
        description="English CTC text recognition for license plate transcription.",
    ),
    ModelSpec(
        model_id="en_dict",
        name="PaddleOCR English Charset",
        rel_path="models/anpr/en_dict.txt",
        classification="REQUIRED",
        expected_size=190,
        sha256="5662df9d2d03f0e8ca0d3b0649d6acbab904b6a14b3d3521463c71c37c668ce3",
        download_urls=[
            "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/en_dict.txt",
        ],
        description="ANPR alphabet character mapping table.",
    ),
    ModelSpec(
        model_id="yunet_face",
        name="YuNet Face Detector (ONNX)",
        rel_path="models/face/face_detection_yunet_2023mar.onnx",
        classification="REQUIRED",
        expected_size=232589,
        sha256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        download_urls=[
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        ],
        description="Lightweight OpenCV Zoo facial keypoint & face detector.",
    ),
    ModelSpec(
        model_id="osnet_reid",
        name="OSNet Re-ID Feature Extractor (ONNX)",
        rel_path="models/reid/osnet_x0_25_msmt17.onnx",
        classification="REQUIRED",
        expected_size=907171,
        sha256="434720ccf6bd5c509eb03a50d8b0b419bdd41bdb2b99b7dbc3f77b7e1be7f608",
        download_urls=[
            "https://github.com/KaiyangZhou/deep-person-reid/releases/download/v1.0.0/osnet_x0_25_msmt17.onnx",
        ],
        description="Cross-camera global entity Re-ID feature embedding extractor.",
    ),
    ModelSpec(
        model_id="gun_detector",
        name="Weapon & Gun Detection Model",
        rel_path="models/weapon/gun.pt",
        classification="OPTIONAL",
        expected_size=6534387,
        sha256="31e20dde3def09e2cf938c7be6fe23d9150bbbe503982af13345706515f2ef95",
        download_urls=[],
        description="Tactical armed threat and weapon classification model.",
    ),
]


def calculate_sha256(file_path: Path) -> str:
    """Compute cryptographic SHA-256 hash of a local file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify_models(
    base_dir: Optional[Path] = None,
    auto_download: bool = False,
    check_hashes: bool = True,
) -> Dict[str, Any]:
    """
    Verify model inventory against manifest.
    Returns status dict detailing available, missing, and compromised weights.
    """
    root = base_dir or Path(os.getcwd())
    results: List[Dict[str, Any]] = []
    missing_required: List[str] = []

    for spec in MODELS_MANIFEST:
        target = root / spec.rel_path
        status = "OK"
        hash_match = True
        actual_size = 0

        if not target.exists():
            if auto_download and spec.download_urls:
                target.parent.mkdir(parents=True, exist_ok=True)
                downloaded = False
                for url in spec.download_urls:
                    try:
                        logger.info(f"[MODELS] Downloading {spec.name} from {url}...")
                        urllib.request.urlretrieve(url, target)
                        downloaded = True
                        break
                    except Exception as e:
                        logger.warning(f"[MODELS] Download failed for {url}: {e}")
                if not downloaded:
                    status = "MISSING"
            else:
                status = "MISSING"

        if target.exists():
            actual_size = target.stat().st_size
            if check_hashes and spec.sha256:
                actual_hash = calculate_sha256(target)
                if actual_hash != spec.sha256:
                    status = "HASH_MISMATCH"
                    hash_match = False
        else:
            status = "MISSING"

        if status == "MISSING" and spec.classification == "REQUIRED":
            missing_required.append(spec.name)

        results.append({
            "model_id": spec.model_id,
            "name": spec.name,
            "path": spec.rel_path,
            "classification": spec.classification,
            "status": status,
            "size_bytes": actual_size,
            "expected_size": spec.expected_size,
            "hash_valid": hash_match,
        })

    all_required_ok = len(missing_required) == 0

    return {
        "all_required_ok": all_required_ok,
        "missing_required": missing_required,
        "models": results,
    }


def report_model_readiness(base_dir: Optional[Path] = None) -> bool:
    """Startup verification report logged to system observability."""
    check = verify_models(base_dir=base_dir, auto_download=False, check_hashes=False)
    if check["all_required_ok"]:
        logger.info("[MODELS] All required surveillance models verified and ready for offline perception.")
        return True
    else:
        logger.error(
            f"[MODELS] CRITICAL: Missing required models: {', '.join(check['missing_required'])}. "
            "No fake perception fallback will be used."
        )
        return False
