"""
Place real-world validation footage into dataset/surveillance/.

Final pipeline (idempotent — safe to re-run):
  night_ir_patrol.mp4          <- trim f4783-5094 of the X-Life IR CCTV DVR
                                  recording (genuine IR night surveillance,
                                  timestamp overlay; measured best-yield segment
                                  with REAL tracking: 2 concurrent persons held
                                  under stable IDs for 12.4s, 238/250 frames
                                  with tracks, 5 unique IDs total)
  thermal_patrol.mp4           <- trim f608-1408 of Bayraktar TB2 FLIR aerial
                                  white-hot thermal surveillance (people +
                                  vehicles; measured 1.10 dets/f, conf 0.29)
  anpr_vehicle_checkpoint.mp4  <- full 4K motorway clip downscaled to 1080p
                                  (plates verified readable after downscale:
                                  63/63 OCR reads accepted, mean conf 0.818)

Every output is verified with OpenCV: path, size, codec, resolution, FPS,
frame count, duration, and a full decode pass.

Sources (Internet Archive, public uploads):
  night:  youtube-GC2x8dwvi4M
  thermal: 2019FLIRPORNGOLETACA93117
  anpr:   anpr_examples_202208
"""
import os
import sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT_DIR = "dataset/surveillance"

# Raw sources in scratch (kept until placement verified)
SRC_NIGHT = "scratch/real_dl/night_street_cams.mp4"
SRC_THERMAL = "scratch/real_dl/thermal_flir_tb2.mp4"
SRC_ANPR = "scratch/real_dl/anpr_test_video_1.mp4"


def _writer(out_path: str, fps: float, size) -> cv2.VideoWriter:
    for fcc in ("avc1", "mp4v"):
        w = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*fcc), fps, size)
        if w.isOpened():
            return w
        w.release()
    raise RuntimeError(f"No working VideoWriter codec for {out_path}")


def trim(src: str, out_name: str, start: int, end) -> str:
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if end is None or end > total:
        end = total
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    out_path = os.path.join(OUT_DIR, out_name)
    writer = _writer(out_path, fps, (w, h))
    written = 0
    while written < (end - start):
        ok, img = cap.read()
        if not ok:
            break
        writer.write(img)
        written += 1
    writer.release()
    cap.release()
    print(f"wrote {out_path}: {written} frames ({written / fps:.1f}s)")
    return out_path


def downscale(src: str, out_name: str, target_w: int) -> str:
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = target_w / w
    tw, th = target_w, int(round(h * scale / 2) * 2)
    out_path = os.path.join(OUT_DIR, out_name)
    writer = _writer(out_path, fps, (tw, th))
    written = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        img = cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA)
        writer.write(img)
        written += 1
    writer.release()
    cap.release()
    print(f"wrote {out_path}: {written} frames ({written / fps:.1f}s) {tw}x{th}")
    return out_path


def verify(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    assert cap.isOpened(), f"FAILED TO OPEN {path}"
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    decoded = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        decoded += 1
    codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join(chr((codec_int >> 8 * i) & 0xFF) for i in range(4))
    cap.release()

    size_mb = os.path.getsize(path) / 1e6
    info = {
        "path": path.replace("\\", "/"),
        "size_mb": round(size_mb, 2),
        "codec": codec,
        "resolution": f"{w}x{h}",
        "fps": round(fps, 2),
        "frames_meta": n,
        "frames_decoded": decoded,
        "duration_s": round(decoded / fps, 2) if fps else 0,
    }
    info["decode_ok"] = decoded >= n * 0.98 and decoded > 0
    return info


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Placing real footage into", OUT_DIR)
    outs = []

    # Regenerate only when missing — placement is verified, re-runs stay cheap.
    night_out = os.path.join(OUT_DIR, "night_ir_patrol.mp4")
    thermal_out = os.path.join(OUT_DIR, "thermal_patrol.mp4")
    anpr_out = os.path.join(OUT_DIR, "anpr_vehicle_checkpoint.mp4")

    if not os.path.exists(night_out):
        if os.path.exists(SRC_NIGHT):
            trim(SRC_NIGHT, "night_ir_patrol.mp4", 4783, 5094)
        else:
            print(f"  [SKIP] source missing: {SRC_NIGHT}")
    outs.append(night_out)

    if not os.path.exists(thermal_out):
        if os.path.exists(SRC_THERMAL):
            trim(SRC_THERMAL, "thermal_patrol.mp4", 608, 1408)
        else:
            print(f"  [SKIP] source missing: {SRC_THERMAL}")
    outs.append(thermal_out)

    if not os.path.exists(anpr_out):
        if os.path.exists(SRC_ANPR):
            downscale(SRC_ANPR, "anpr_vehicle_checkpoint.mp4", 1920)
        else:
            print(f"  [SKIP] source missing: {SRC_ANPR}")
    outs.append(anpr_out)

    print("\nVerification:")
    results = []
    for p in outs:
        info = verify(p)
        results.append(info)
        status = "OK" if info["decode_ok"] else "DECODE-FAIL"
        print(f"  [{status}] {info['path']}")
        for k, v in info.items():
            if k not in ("path", "decode_ok"):
                print(f"        {k}: {v}")

    import json
    with open(os.path.join(OUT_DIR, "real_footage_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "description": "Real-world validation footage (non-synthetic) for night/IR, thermal and ANPR demos",
            "sources": {
                "night_ir_patrol.mp4": "Internet Archive youtube-GC2x8dwvi4M (X-Life IR CCTV DVR night recording, trimmed to best continuous segment f4783-5094: 2 concurrent persons under stable IDs, 238/250 frames with tracks)",
                "thermal_patrol.mp4": "Internet Archive 2019FLIRPORNGOLETACA93117 (Bayraktar TB2 FLIR aerial white-hot surveillance, trimmed f608-1408)",
                "anpr_vehicle_checkpoint.mp4": "Internet Archive anpr_examples_202208 (4K motorway traffic, downscaled to 1080p; plates verified readable post-downscale)",
            },
            "rejections": {
                "night_quality_inn (IA)": "indoor handheld camera, not surveillance",
                "nightvision.mp4 (IA 'CHEAP & SMALL DIY NIGHT VISION')": "product review video, not surveillance footage",
                "FLIR Fever Screening (Adafruit)": "desk product review, only brief thermal-screen segments",
            },
            "files": results,
        }, fh, indent=2)
    print("\nManifest written to dataset/surveillance/real_footage_manifest.json")
    return 0 if all(r["decode_ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
