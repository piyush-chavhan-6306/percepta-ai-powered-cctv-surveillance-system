"""
Border Intelligence Kalman Filter Module for Multi-Object Tracking.
Implements the 8D state Kalman Filter (x, y, a, h, vx, vy, va, vh) in image space,
used by BYTETrack to model constant velocity motion and predict/smooth bounding boxes.
"""
from __future__ import annotations
import numpy as np


class KalmanFilterXYAH:
    """
    8-dimensional Kalman filter for tracking bounding boxes in image coordinate space.
    
    State vector: [x, y, a, h, vx, vy, va, vh]
      - (x, y): center coordinates of bounding box
      - a: aspect ratio (w / h)
      - h: height of bounding box
      - (vx, vy, va, vh): respective instantaneous velocities
    """

    def __init__(self) -> None:
        ndim, dt = 4, 1.0

        # Construct state transition motion matrix F (8x8)
        self._motion_mat = np.eye(2 * ndim, 2 * ndim)
        for i in range(ndim):
            self._motion_mat[i, ndim + i] = dt

        # Construct measurement observation matrix H (4x8)
        self._update_mat = np.eye(ndim, 2 * ndim)

        # Motion and measurement uncertainty scaling
        self._std_weight_position = 1.0 / 20
        self._std_weight_velocity = 1.0 / 160

    def initiate(self, measurement: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Create a new track state from an unassociated measurement [x, y, a, h].
        """
        measurement = np.asarray(measurement, dtype=np.float64)
        mean_pos = measurement
        mean_vel = np.zeros_like(mean_pos)
        mean = np.r_[mean_pos, mean_vel]

        h = measurement[3]
        std = [
            2 * self._std_weight_position * h,
            2 * self._std_weight_position * h,
            1e-2,
            2 * self._std_weight_position * h,
            10 * self._std_weight_velocity * h,
            10 * self._std_weight_velocity * h,
            1e-5,
            10 * self._std_weight_velocity * h,
        ]
        covariance = np.diag(np.square(std))
        return mean, covariance

    def predict(self, mean: np.ndarray, covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Run the Kalman filter prediction step forward by 1 frame.
        """
        h = mean[3]
        std_pos = [
            self._std_weight_position * h,
            self._std_weight_position * h,
            1e-2,
            self._std_weight_position * h,
        ]
        std_vel = [
            self._std_weight_velocity * h,
            self._std_weight_velocity * h,
            1e-5,
            self._std_weight_velocity * h,
        ]
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))

        mean = np.dot(mean, self._motion_mat.T)
        covariance = np.linalg.multi_dot((self._motion_mat, covariance, self._motion_mat.T)) + motion_cov
        return mean, covariance

    def project(self, mean: np.ndarray, covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Project state distribution to 4D measurement space [x, y, a, h].
        """
        h = mean[3]
        std = [
            self._std_weight_position * h,
            self._std_weight_position * h,
            1e-1,
            self._std_weight_position * h,
        ]
        innovation_cov = np.diag(np.square(std))

        mean = np.dot(self._update_mat, mean)
        covariance = np.linalg.multi_dot((self._update_mat, covariance, self._update_mat.T))
        return mean, covariance + innovation_cov

    def multi_predict(self, mean: np.ndarray, covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Vectorized prediction for multiple tracks simultaneously.
        """
        if len(mean) == 0:
            return mean, covariance
        std_pos = [
            self._std_weight_position * mean[:, 3],
            self._std_weight_position * mean[:, 3],
            1e-2 * np.ones_like(mean[:, 3]),
            self._std_weight_position * mean[:, 3],
        ]
        std_vel = [
            self._std_weight_velocity * mean[:, 3],
            self._std_weight_velocity * mean[:, 3],
            1e-5 * np.ones_like(mean[:, 3]),
            self._std_weight_velocity * mean[:, 3],
        ]
        sqr = np.square(np.r_[std_pos, std_vel]).T

        motion_cov = np.empty((len(mean), 8, 8))
        for i, s in enumerate(sqr):
            motion_cov[i] = np.diag(s)

        mean = np.dot(mean, self._motion_mat.T)
        left = np.dot(self._motion_mat, covariance).transpose((1, 0, 2))
        covariance = np.dot(left, self._motion_mat.T) + motion_cov
        return mean, covariance

    def update(self, mean: np.ndarray, covariance: np.ndarray, measurement: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Run the Kalman filter correction / update step with incoming detection measurement.
        """
        projected_mean, projected_cov = self.project(mean, covariance)

        # Solve for Kalman Gain K = P * H^T * S^(-1)
        chol_factor, lower = np.linalg.cholesky(projected_cov), True
        try:
            kalman_gain = np.linalg.solve(projected_cov, np.dot(covariance, self._update_mat.T).T).T
        except np.linalg.LinAlgError:
            kalman_gain = np.dot(np.dot(covariance, self._update_mat.T), np.linalg.pinv(projected_cov))

        innovation = measurement - projected_mean
        new_mean = mean + np.dot(innovation, kalman_gain.T)
        new_covariance = covariance - np.linalg.multi_dot((kalman_gain, projected_cov, kalman_gain.T))
        return new_mean, new_covariance
