"""
Border Intelligence Frame Overlay Renderer.

Burns real detection/tracking geometry into the frame server-side so the browser
receives pixels that already agree with the model output. This removes any
possibility of client-side coordinate drift or "video plays but boxes are stale".

All coordinates consumed here are pixel coordinates in the source frame:
  - TrackedObject.bounding_box -> [x1, y1, x2, y2]
  - SecurityZone.polygon       -> [(x, y), ...]
  - VirtualBoundary.pt1/pt2    -> (x, y)
"""
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import cv2
import numpy as np

from backend.tracking.tracker import TrackedObject
from backend.zones.security_zone import SecurityZone, VirtualBoundary

# Tactical palette, expressed in OpenCV BGR to match the frontend design tokens.
C2_CYAN = (255, 229, 0)      # #00e5ff
C2_EMERALD = (118, 230, 0)   # #00e676
C2_AMBER = (0, 171, 255)     # #ffab00
C2_ORANGE = (0, 109, 255)    # #ff6d00
C2_CRIMSON = (68, 23, 255)   # #ff1744
C2_BLUE = (255, 121, 41)     # #2979ff
C2_WHITE = (245, 245, 245)

SEVERITY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "info": C2_CYAN,
    "warning": C2_AMBER,
    "restricted": C2_ORANGE,
    "critical": C2_CRIMSON,
}

# Person vs vehicle classes get distinct colors so the demo reads clearly.
_VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "train", "boat", "airplane"}

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _severity_color(severity) -> Tuple[int, int, int]:
    value = getattr(severity, "value", severity)
    return SEVERITY_COLORS.get(str(value).lower(), C2_ORANGE)


def _track_color(track: TrackedObject) -> Tuple[int, int, int]:
    if track.object_class in _VEHICLE_CLASSES:
        return C2_BLUE
    return C2_CYAN


def _dim(color: Tuple[int, int, int], factor: float = 0.55) -> Tuple[int, int, int]:
    return tuple(int(c * factor) for c in color)  # type: ignore[return-value]


def _dashed_line(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = 1,
    dash: int = 9,
) -> None:
    """Draw a dashed line segment (OpenCV has no native dashed stroke)."""
    x1, y1 = pt1
    x2, y2 = pt2
    length = int(np.hypot(x2 - x1, y2 - y1))
    if length == 0:
        return
    steps = max(1, length // dash)
    for i in range(steps):
        if i % 2:
            continue
        a = i / steps
        b = min(1.0, (i + 1) / steps)
        cv2.line(
            img,
            (int(x1 + (x2 - x1) * a), int(y1 + (y2 - y1) * a)),
            (int(x1 + (x2 - x1) * b), int(y1 + (y2 - y1) * b)),
            color,
            thickness,
            cv2.LINE_AA,
        )


def _dashed_rect(
    img: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: Tuple[int, int, int],
    thickness: int = 1,
) -> None:
    _dashed_line(img, (x1, y1), (x2, y1), color, thickness)
    _dashed_line(img, (x2, y1), (x2, y2), color, thickness)
    _dashed_line(img, (x2, y2), (x1, y2), color, thickness)
    _dashed_line(img, (x1, y2), (x1, y1), color, thickness)


def _label(
    img: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: Tuple[int, int, int],
    scale: float = 0.42,
) -> None:
    """Draw a compact filled label chip with dark text, clamped inside the frame."""
    h, w = img.shape[:2]
    (tw, th), baseline = cv2.getTextSize(text, _FONT, scale, 1)
    pad = 3
    box_h = th + baseline + pad
    top = y - box_h
    if top < 0:  # flip below the box when there is no room above
        top = y
    top = max(0, min(h - box_h, top))
    left = max(0, min(w - (tw + 2 * pad), x))
    cv2.rectangle(img, (left, top), (left + tw + 2 * pad, top + box_h), color, -1)
    cv2.putText(
        img,
        text,
        (left + pad, top + th + pad - 1),
        _FONT,
        scale,
        (12, 12, 12),
        1,
        cv2.LINE_AA,
    )


def draw_zones(
    img: np.ndarray,
    zones: Iterable[SecurityZone],
    boundaries: Iterable[VirtualBoundary],
) -> None:
    """Render configured geofence polygons and directional tripwires."""
    overlay = None
    for zone in zones:
        if not zone.is_active or not zone.polygon or len(zone.polygon) < 3:
            continue
        color = _severity_color(zone.severity)
        pts = np.array([[int(x), int(y)] for x, y in zone.polygon], dtype=np.int32)

        # Translucent fill, drawn on a scratch layer so alpha stays cheap.
        if overlay is None:
            overlay = img.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.polylines(img, [pts], True, color, 2, cv2.LINE_AA)
        _label(img, f"{zone.name} [{getattr(zone.severity, 'value', zone.severity)}]".upper(),
               int(pts[:, 0].min()), int(pts[:, 1].min()), color, 0.40)

    if overlay is not None:
        cv2.addWeighted(overlay, 0.16, img, 0.84, 0, dst=img)

    for boundary in boundaries:
        if not boundary.is_active:
            continue
        color = _severity_color(boundary.severity)
        p1 = (int(boundary.pt1[0]), int(boundary.pt1[1]))
        p2 = (int(boundary.pt2[0]), int(boundary.pt2[1]))
        cv2.line(img, p1, p2, color, 2, cv2.LINE_AA)
        # Endpoint pips plus a mid-segment normal arrow showing crossing direction.
        cv2.circle(img, p1, 4, color, -1, cv2.LINE_AA)
        cv2.circle(img, p2, 4, color, -1, cv2.LINE_AA)
        mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        norm = float(np.hypot(dx, dy)) or 1.0
        nx, ny = -dy / norm, dx / norm  # left-hand normal
        cv2.arrowedLine(
            img, mid, (int(mid[0] + nx * 26), int(mid[1] + ny * 26)),
            color, 2, cv2.LINE_AA, tipLength=0.35,
        )
        _label(img, f"{boundary.name}".upper(), p1[0], p1[1], color, 0.40)


def draw_tracks(
    img: np.ndarray,
    tracks: Sequence[TrackedObject],
    show_trails: bool = True,
) -> None:
    """Render tracked object boxes, stable IDs, confidence, and motion trails."""
    for track in tracks:
        box = track.bounding_box
        if not box or len(box) < 4:
            continue
        x1, y1, x2, y2 = (int(round(v)) for v in box[:4])
        predicted = track.provenance == "prediction"
        color = _track_color(track)

        if predicted:
            # Inferred position on a stride-skipped frame: dashed + dimmed so the
            # operator can tell measurement from extrapolation.
            _dashed_rect(img, x1, y1, x2, y2, _dim(color), 2)
        else:
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

        conf_pct = int(round(track.confidence * 100))
        suffix = " ~" if predicted else ""
        _label(img, f"{track.track_id} {track.object_class} {conf_pct}%{suffix}", x1, y1, color)

        if show_trails and len(track.trajectory) > 1:
            trail = np.array(
                [[int(cx), int(cy)] for cx, cy in track.trajectory[-28:]],
                dtype=np.int32,
            )
            cv2.polylines(img, [trail], False, _dim(color, 0.75), 1, cv2.LINE_AA)


def draw_hud(
    img: np.ndarray,
    camera_id: str,
    display_fps: float,
    track_count: int,
    inference_fps: Optional[float] = None,
    device: str = "cpu",
    stride: int = 1,
    degraded: bool = False,
) -> None:
    """Render a compact status strip along the bottom of the frame."""
    h, w = img.shape[:2]
    bar_h = 26
    top = h - bar_h
    strip = img[top:h, 0:w]
    cv2.addWeighted(strip, 0.25, np.zeros_like(strip), 0.75, 0, dst=strip)

    live_color = C2_AMBER if degraded else C2_EMERALD
    cv2.circle(img, (14, top + bar_h // 2), 4, live_color, -1, cv2.LINE_AA)

    left_text = f"{camera_id}   {display_fps:4.1f} FPS   TRACKS {track_count}"
    cv2.putText(img, left_text, (26, top + 18), _FONT, 0.46, C2_WHITE, 1, cv2.LINE_AA)

    right_bits: List[str] = [f"YOLOv8n {device.upper()}"]
    if inference_fps is not None:
        right_bits.append(f"{inference_fps:.1f} inf/s")
    right_bits.append(f"stride {stride}")
    right_text = "   ".join(right_bits)
    (tw, _), _ = cv2.getTextSize(right_text, _FONT, 0.42, 1)
    cv2.putText(img, right_text, (max(0, w - tw - 10), top + 18), _FONT, 0.42, C2_CYAN, 1, cv2.LINE_AA)


def draw_offline(img: np.ndarray, camera_id: str, message: str) -> None:
    """Render a clear signal-loss placeholder while a source is reconnecting."""
    h, w = img.shape[:2]
    cv2.putText(img, "SIGNAL LOSS", (int(w * 0.5) - 96, int(h * 0.5) - 8),
                _FONT, 0.9, C2_CRIMSON, 2, cv2.LINE_AA)
    cv2.putText(img, f"{camera_id} — {message}", (int(w * 0.5) - 150, int(h * 0.5) + 22),
                _FONT, 0.48, C2_WHITE, 1, cv2.LINE_AA)


def annotate_frame(
    image: np.ndarray,
    tracks: Sequence[TrackedObject],
    zones: Iterable[SecurityZone] = (),
    boundaries: Iterable[VirtualBoundary] = (),
    camera_id: str = "",
    display_fps: float = 0.0,
    inference_fps: Optional[float] = None,
    device: str = "cpu",
    stride: int = 1,
    show_hud: bool = True,
    degraded: bool = False,
    copy: bool = True,
) -> np.ndarray:
    """
    Composite every overlay onto a frame and return the annotated image.

    Draw order matters: zones sit underneath tracks so boxes stay readable, and
    the HUD is painted last so nothing occludes it.
    """
    canvas = image.copy() if copy else image
    draw_zones(canvas, zones, boundaries)
    draw_tracks(canvas, tracks)
    if show_hud:
        draw_hud(
            canvas,
            camera_id=camera_id,
            display_fps=display_fps,
            track_count=len(tracks),
            inference_fps=inference_fps,
            device=device,
            stride=stride,
            degraded=degraded,
        )
    return canvas


def encode_jpeg(image: np.ndarray, quality: int = 78) -> Optional[bytes]:
    """JPEG-encode a frame once for fan-out to all MJPEG clients."""
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None
    return buf.tobytes()
