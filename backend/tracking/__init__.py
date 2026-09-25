"""
Border Intelligence Tracking Package.
Provides multi-object tracking abstractions, native Kalman Filter, native ByteTrack implementation, movement analysis, and pipeline coordination.
"""
from backend.tracking.kalman_filter import KalmanFilterXYAH
from backend.tracking.byte_tracker import BYTETracker, STrack, TrackState
from backend.tracking.tracker import BaseTracker, TrackedObject
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.tracking.movement import MovementVector, calculate_movement_vector
from backend.tracking.pipeline import FrameProcessingResult, TrackingPipeline

__all__ = [
    "KalmanFilterXYAH",
    "BYTETracker",
    "STrack",
    "TrackState",
    "BaseTracker",
    "TrackedObject",
    "ByteTrackTracker",
    "MovementVector",
    "calculate_movement_vector",
    "FrameProcessingResult",
    "TrackingPipeline",
]
