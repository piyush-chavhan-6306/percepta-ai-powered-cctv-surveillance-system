"""
Generate real YOLOv8 + ByteTrack Kalman tracking telemetry for virat_cctv.mp4.
Extracts real target bounding boxes, track IDs, velocities, and confidence for every frame/interval
so that offline and Vercel modes have bit-for-bit real perception matching the video.
"""
import json
import os
import cv2
import numpy as np

from backend.detection.detector import ObjectDetector
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.ingestion.adapter import FrameData
from backend.events.schema import SourceType
from datetime import datetime, timezone

def main():
    video_path = os.path.join("frontend", "public", "videos", "virat_cctv.mp4")
    out_json = os.path.join("frontend", "public", "data", "virat_perception_track.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    if not os.path.exists(video_path):
        print(f"Error: {video_path} does not exist")
        return

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {width}x{height} @ {fps:.1f} FPS, {total_frames} frames")

    # Initialize real detector and tracker
    detector = ObjectDetector(model_name="yolov8n.pt", conf_threshold=0.20, device="cpu")
    tracker = ByteTrackTracker(track_high_thresh=0.20, track_low_thresh=0.08, new_track_thresh=0.25, fps=fps)
    tracker.initialize()
    frame_idx = 0
    records = []

    # Process consecutive frames for continuous Kalman association
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        timestamp_sec = round(frame_idx / fps, 2)
        frame_data = FrameData(
            camera_id="CAM-01",
            frame_number=frame_idx,
            timestamp=datetime.now(timezone.utc),
            image=frame,
            width=width,
            height=height,
            fps=fps,
            source=SourceType.VIDEO_FILE
        )

        detections = detector.detect(frame_data.image)
        tracks = tracker.update(detections, frame_data)

        frame_tracks = []
        for t in tracks:
            # normalized coordinates in percentage (0 to 100)
            x1, y1, x2, y2 = t.bounding_box
            pct_x = round((x1 / width) * 100, 2)
            pct_y = round((y1 / height) * 100, 2)
            pct_w = round(((x2 - x1) / width) * 100, 2)
            pct_h = round(((y2 - y1) / height) * 100, 2)
            cx = round((t.center_x / width) * 100, 2)
            cy = round((t.center_y / height) * 100, 2)

            frame_tracks.append({
                "track_id": t.track_id,
                "class_name": t.object_class,
                "confidence": round(t.confidence, 2),
                "box": [pct_x, pct_y, pct_w, pct_h],
                "center": [cx, cy],
                "velocity": [round(t.velocity[0], 2), round(t.velocity[1], 2)],
                "speed": round(t.speed_px_per_frame, 2),
                "heading": t.cardinal_heading,
                "is_breached": cx > 50.0  # crossing mid-perimeter
            })

        records.append({
            "frame": frame_idx,
            "timestamp": timestamp_sec,
            "targets": frame_tracks
        })

        if frame_idx % 60 == 0:
            print(f"Processed frame {frame_idx}/{total_frames} ({timestamp_sec:.1f}s) - {len(frame_tracks)} tracks")

    cap.release()

    output_payload = {
        "metadata": {
            "source": "virat_cctv.mp4",
            "fps": fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "algorithm": "YOLOv8n + Native ByteTrack Kalman"
        },
        "frames": records
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"Saved real telemetry to {out_json} with {len(records)} sample points.")

if __name__ == "__main__":
    main()
