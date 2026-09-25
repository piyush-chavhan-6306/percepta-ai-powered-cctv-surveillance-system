"""
PERCEPTA Pipeline Profiler — Measures every stage of the surveillance pipeline.

Run:  python -m backend.profiler

Produces a structured benchmark report without modifying any production code.
"""
import asyncio
import gc
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("profiler")
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────
# 1. SYSTEM INFO
# ─────────────────────────────────────────────
def gather_system_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "unknown",
        "cpu_count_logical": os.cpu_count(),
        "ram_total_gb": 0.0,
    }
    try:
        import psutil
        info["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
        info["ram_available_gb"] = round(psutil.virtual_memory().available / (1024**3), 2)
    except ImportError:
        pass

    # GPU info
    info["gpu_name"] = "none"
    info["vram_total_mb"] = 0
    info["cuda_available"] = False
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 4:
                info["gpu_name"] = parts[0]
                info["vram_total_mb"] = int(parts[1])
                info["vram_used_mb"] = int(parts[2])
                info["nvidia_driver"] = parts[3]
    except Exception:
        pass

    # ONNX Runtime
    try:
        import onnxruntime as ort
        info["onnxruntime_version"] = ort.__version__
        info["onnx_available_providers"] = ort.get_available_providers()
        info["cuda_available"] = "CUDAExecutionProvider" in ort.get_available_providers()
        info["tensorrt_available"] = "TensorrtExecutionProvider" in ort.get_available_providers()
    except Exception as e:
        info["onnxruntime_error"] = str(e)

    # OpenCV
    info["opencv_version"] = cv2.__version__
    info["opencv_build_info_ocl"] = "OpenCL" in cv2.getBuildInformation()

    return info


# ─────────────────────────────────────────────
# 2. STAGE TIMERS
# ─────────────────────────────────────────────
class StageTimer:
    """Accumulates timing samples for a named pipeline stage."""

    def __init__(self, name: str):
        self.name = name
        self.samples: List[float] = []

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_):
        elapsed_ms = (time.perf_counter() - self._t0) * 1000.0
        self.samples.append(elapsed_ms)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def mean_ms(self) -> float:
        return sum(self.samples) / max(len(self.samples), 1)

    @property
    def p50_ms(self) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        return s[len(s) // 2]

    @property
    def p95_ms(self) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        return s[int(len(s) * 0.95)]

    @property
    def p99_ms(self) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        return s[min(int(len(s) * 0.99), len(s) - 1)]

    @property
    def max_ms(self) -> float:
        return max(self.samples) if self.samples else 0.0

    def report(self) -> Dict[str, Any]:
        return {
            "stage": self.name,
            "samples": self.count,
            "mean_ms": round(self.mean_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "theoretical_fps": round(1000.0 / self.mean_ms, 1) if self.mean_ms > 0 else 0,
        }


# ─────────────────────────────────────────────
# 3. ONNX PROVIDER DIAGNOSIS
# ─────────────────────────────────────────────
def diagnose_providers() -> Dict[str, Any]:
    """Inspect why CUDA may not be available."""
    import onnxruntime as ort
    result = {
        "available_providers": ort.get_available_providers(),
        "cuda_provider_available": "CUDAExecutionProvider" in ort.get_available_providers(),
        "tensorrt_provider_available": "TensorrtExecutionProvider" in ort.get_available_providers(),
    }

    # Test CUDA provider initialization
    if result["cuda_provider_available"]:
        try:
            dummy_path = None
            # Find the model
            from backend.config import get_settings
            settings = get_settings()
            model_path = Path(settings.MODELS_DIR) / "detection" / "yolov8n.onnx"
            if model_path.exists():
                opts = ort.SessionOptions()
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
                sess = ort.InferenceSession(
                    str(model_path), opts,
                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                )
                active = sess.get_providers()
                result["cuda_session_test"] = {
                    "success": True,
                    "active_providers": active,
                    "actually_using_cuda": "CUDAExecutionProvider" in active,
                }
                del sess
        except Exception as e:
            result["cuda_session_test"] = {
                "success": False,
                "error": str(e),
            }
    else:
        # Check what package is installed
        result["onnxruntime_package"] = ort.__file__
        result["cuda_diagnosis"] = (
            "CUDAExecutionProvider not available. This typically means "
            "onnxruntime-gpu is not installed, or CUDA/cuDNN versions are incompatible. "
            "Install with: pip install onnxruntime-gpu"
        )

    return result


# ─────────────────────────────────────────────
# 4. PIPELINE BENCHMARK
# ─────────────────────────────────────────────
def benchmark_pipeline(
    video_path: Optional[str] = None,
    num_frames: int = 300,
    imgsz: int = 416,
) -> Dict[str, Any]:
    """Benchmark every stage of the pipeline independently."""

    # Find video
    if video_path is None:
        candidates = [
            "frontend/public/videos/virat_cctv.mp4",
            "dataset/demo_border_clip.mp4",
            "dataset/sample.mp4",
        ]
        for c in candidates:
            if Path(c).exists():
                video_path = c
                break
        if video_path is None:
            # Try to find ANY mp4/avi
            for ext in ("*.mp4", "*.avi"):
                found = list(Path("dataset").glob(ext)) if Path("dataset").exists() else []
                if found:
                    video_path = str(found[0])
                    break
    if video_path is None:
        return {"error": "No video file found for benchmarking"}

    logger.info(f"Benchmarking with: {video_path} ({num_frames} frames, imgsz={imgsz})")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video: {video_path}"}

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Initialize detector
    from backend.detection.onnx_detector import OnnxDetector
    from backend.config import get_settings
    settings = get_settings()
    model_path = str(Path(settings.MODELS_DIR) / "detection" / "yolov8n.onnx")

    detector = OnnxDetector(
        onnx_path=model_path,
        conf_threshold=settings.CONFIDENCE_THRESHOLD,
        iou_threshold=settings.IOU_THRESHOLD,
        imgsz=imgsz,
    )
    detector.initialize()

    # Initialize tracker
    from backend.tracking.bytetrack_wrapper import ByteTrackTracker
    tracker = ByteTrackTracker()

    # Stage timers
    t_decode = StageTimer("video_decode")
    t_preprocess = StageTimer("preprocess")
    t_inference = StageTimer("inference_only")
    t_postprocess = StageTimer("postprocess_nms")
    t_bytetrack = StageTimer("bytetrack")
    t_jpeg_encode = StageTimer("jpeg_encode")
    t_full_pipeline = StageTimer("full_pipeline")

    detection_counts = []
    track_counts = []
    confidence_scores = []

    # Warm up
    ret, frame = cap.read()
    if not ret:
        return {"error": "Cannot read first frame"}
    for _ in range(5):
        detector.detect(frame)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    gc.collect()

    # Benchmark loop
    for i in range(num_frames):
        with t_full_pipeline:
            # 1. Video decode
            with t_decode:
                ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break

            # 2. Preprocess
            with t_preprocess:
                blob = detector._preprocess(frame)

            # 3. Inference
            with t_inference:
                outputs = detector._session.run(None, {detector._input_name: blob})

            # 4. Postprocess
            h, w = frame.shape[:2]
            with t_postprocess:
                dets = detector._postprocess(outputs[0], h, w)

            detection_counts.append(len(dets))
            for d in dets:
                confidence_scores.append(d["confidence"])

            # 5. ByteTrack
            from backend.detection.detector import DetectionResult
            det_results = [
                DetectionResult(
                    class_id=d["class_id"],
                    class_name=d["class_name"],
                    confidence=d["confidence"],
                    bounding_box=d["bbox"],
                    normalized_box=d.get("norm", [0, 0, 0, 0]),
                )
                for d in dets
            ]
            from backend.ingestion.adapter import FrameData
            fd = FrameData(
                image=frame,
                frame_number=i,
                camera_id="BENCH",
                timestamp=time.time(),
                source=None,
            )
            with t_bytetrack:
                tracks = tracker.update(det_results, fd)
            track_counts.append(len(tracks))

            # 6. JPEG encode (simulating streaming)
            with t_jpeg_encode:
                cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])

    cap.release()
    detector.release()

    # Compute results
    results = {
        "video": {
            "path": video_path,
            "resolution": f"{width}x{height}",
            "source_fps": round(source_fps, 1),
            "frames_benchmarked": num_frames,
        },
        "model": {
            "path": model_path,
            "imgsz": imgsz,
            "device": detector.device,
            "active_provider": detector.active_provider,
            "conf_threshold": settings.CONFIDENCE_THRESHOLD,
            "iou_threshold": settings.IOU_THRESHOLD,
        },
        "stage_timings": {
            t.name: t.report()
            for t in [t_decode, t_preprocess, t_inference, t_postprocess,
                      t_bytetrack, t_jpeg_encode, t_full_pipeline]
        },
        "detection_stats": {
            "mean_detections_per_frame": round(sum(detection_counts) / max(len(detection_counts), 1), 2),
            "max_detections_per_frame": max(detection_counts) if detection_counts else 0,
            "mean_confidence": round(sum(confidence_scores) / max(len(confidence_scores), 1), 3) if confidence_scores else 0,
            "total_detections": sum(detection_counts),
        },
        "tracking_stats": {
            "mean_tracks_per_frame": round(sum(track_counts) / max(len(track_counts), 1), 2),
            "max_tracks_per_frame": max(track_counts) if track_counts else 0,
        },
    }

    # Compute effective FPS
    inf_ms = t_inference.mean_ms
    full_ms = t_full_pipeline.mean_ms
    results["effective_fps"] = {
        "inference_only_fps": round(1000.0 / inf_ms, 1) if inf_ms > 0 else 0,
        "full_pipeline_fps": round(1000.0 / full_ms, 1) if full_ms > 0 else 0,
    }

    # Bottleneck identification
    stages = [
        ("inference_only", t_inference.mean_ms),
        ("preprocess", t_preprocess.mean_ms),
        ("postprocess_nms", t_postprocess.mean_ms),
        ("bytetrack", t_bytetrack.mean_ms),
        ("video_decode", t_decode.mean_ms),
        ("jpeg_encode", t_jpeg_encode.mean_ms),
    ]
    stages.sort(key=lambda x: x[1], reverse=True)
    results["bottleneck_ranking"] = [
        {"stage": name, "mean_ms": round(ms, 2), "pct_of_total": round(ms / full_ms * 100, 1) if full_ms > 0 else 0}
        for name, ms in stages
    ]

    return results


# ─────────────────────────────────────────────
# 5. RESOLUTION COMPARISON
# ─────────────────────────────────────────────
def benchmark_resolutions(video_path: Optional[str] = None) -> Dict[str, Any]:
    """Compare inference at different input resolutions."""
    results = {}
    for imgsz in [320, 416, 512, 640]:
        logger.info(f"Benchmarking imgsz={imgsz}...")
        res = benchmark_pipeline(video_path=video_path, num_frames=100, imgsz=imgsz)
        if "error" in res:
            results[str(imgsz)] = res
        else:
            results[str(imgsz)] = {
                "imgsz": imgsz,
                "inference_ms": res["stage_timings"]["inference_only"]["mean_ms"],
                "inference_fps": res["effective_fps"]["inference_only_fps"],
                "full_pipeline_fps": res["effective_fps"]["full_pipeline_fps"],
                "mean_detections": res["detection_stats"]["mean_detections_per_frame"],
                "mean_confidence": res["detection_stats"]["mean_confidence"],
                "preprocess_ms": res["stage_timings"]["preprocess"]["mean_ms"],
                "postprocess_ms": res["stage_timings"]["postprocess_nms"]["mean_ms"],
            }
    return results


# ─────────────────────────────────────────────
# 6. MEMORY PROFILE
# ─────────────────────────────────────────────
def memory_profile() -> Dict[str, Any]:
    result = {}
    try:
        import psutil
        proc = psutil.Process()
        result["process_rss_mb"] = round(proc.memory_info().rss / (1024**2), 1)
        result["process_vms_mb"] = round(proc.memory_info().vms / (1024**2), 1)
        vm = psutil.virtual_memory()
        result["system_ram_used_pct"] = vm.percent
        result["system_ram_available_gb"] = round(vm.available / (1024**3), 2)
    except ImportError:
        result["note"] = "psutil not installed"

    # GPU memory
    try:
        import subprocess
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0:
            parts = res.stdout.strip().split(", ")
            result["gpu_vram_used_mb"] = int(parts[0])
            result["gpu_vram_total_mb"] = int(parts[1])
            result["gpu_utilization_pct"] = int(parts[2])
    except Exception:
        pass
    return result


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 70)
    print("  PERCEPTA PIPELINE PROFILER")
    print("=" * 70)

    report: Dict[str, Any] = {}

    # 1. System Info
    print("\n[1/6] Gathering system info...")
    report["system"] = gather_system_info()
    print(f"  CPU: {report['system']['cpu']}")
    print(f"  RAM: {report['system'].get('ram_total_gb', '?')} GB")
    print(f"  GPU: {report['system']['gpu_name']}")
    print(f"  ONNX Providers: {report['system'].get('onnx_available_providers', [])}")

    # 2. Provider Diagnosis
    print("\n[2/6] Diagnosing ONNX execution providers...")
    report["provider_diagnosis"] = diagnose_providers()
    cuda_status = "AVAILABLE" if report["provider_diagnosis"]["cuda_provider_available"] else "NOT AVAILABLE"
    print(f"  CUDA Provider: {cuda_status}")
    if "cuda_session_test" in report["provider_diagnosis"]:
        test = report["provider_diagnosis"]["cuda_session_test"]
        print(f"  CUDA Session Test: {'✅ SUCCESS' if test['success'] else '❌ FAILED'}")
        if test.get("success"):
            print(f"  Actually using CUDA: {test.get('actually_using_cuda', False)}")
        else:
            print(f"  Error: {test.get('error', 'unknown')}")

    # 3. Memory baseline
    print("\n[3/6] Memory baseline...")
    report["memory_baseline"] = memory_profile()
    print(f"  Process RSS: {report['memory_baseline'].get('process_rss_mb', '?')} MB")

    # 4. Pipeline benchmark (default resolution)
    print("\n[4/6] Pipeline benchmark (imgsz=416)...")
    report["pipeline_416"] = benchmark_pipeline(num_frames=300, imgsz=416)
    if "error" not in report["pipeline_416"]:
        timings = report["pipeline_416"]["stage_timings"]
        print(f"  Video: {report['pipeline_416']['video']['resolution']} @ {report['pipeline_416']['video']['source_fps']} fps")
        print(f"  Provider: {report['pipeline_416']['model']['active_provider']}")
        print(f"  Inference: {timings['inference_only']['mean_ms']:.1f}ms (p95: {timings['inference_only']['p95_ms']:.1f}ms)")
        print(f"  Preprocess: {timings['preprocess']['mean_ms']:.1f}ms")
        print(f"  Postprocess: {timings['postprocess_nms']['mean_ms']:.1f}ms")
        print(f"  ByteTrack: {timings['bytetrack']['mean_ms']:.1f}ms")
        print(f"  JPEG encode: {timings['jpeg_encode']['mean_ms']:.1f}ms")
        print(f"  Full pipeline: {timings['full_pipeline']['mean_ms']:.1f}ms")
        print(f"  → Inference FPS: {report['pipeline_416']['effective_fps']['inference_only_fps']}")
        print(f"  → Full Pipeline FPS: {report['pipeline_416']['effective_fps']['full_pipeline_fps']}")
        print(f"  Bottleneck: {report['pipeline_416']['bottleneck_ranking'][0]['stage']} "
              f"({report['pipeline_416']['bottleneck_ranking'][0]['pct_of_total']:.0f}% of total)")
    else:
        print(f"  ERROR: {report['pipeline_416']['error']}")

    # 5. Resolution comparison
    print("\n[5/6] Resolution comparison benchmark...")
    report["resolution_comparison"] = benchmark_resolutions()
    for sz, data in report["resolution_comparison"].items():
        if "error" not in data:
            print(f"  imgsz={sz}: inference={data['inference_ms']:.1f}ms → {data['inference_fps']} FPS "
                  f"(detections={data['mean_detections']:.1f}, conf={data['mean_confidence']:.3f})")

    # 6. Memory after benchmark
    print("\n[6/6] Memory after benchmark...")
    report["memory_after"] = memory_profile()
    print(f"  Process RSS: {report['memory_after'].get('process_rss_mb', '?')} MB")

    # Save report
    report_path = Path("runtime") / "benchmark_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n{'=' * 70}")
    print(f"  Report saved to: {report_path}")
    print(f"{'=' * 70}")

    return report


if __name__ == "__main__":
    main()
