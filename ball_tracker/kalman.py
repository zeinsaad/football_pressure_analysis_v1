from __future__ import annotations

import numpy as np

from .config import BallTrackerConfig


class BallKalmanTracker:
    """
    Constant-velocity Kalman filter for ball tracking.

    This performs only the forward filtering pass:
    - predict where the ball should be
    - compare with detections
    - update the state when a detection is accepted

    The offline RTS smoother can later use this output to refine
    the trajectory using future frames.
    """

    def __init__(self, cfg: BallTrackerConfig):
        self.cfg = cfg

        # State vector:
        # [x_position, y_position, x_velocity, y_velocity]
        self.x = None

        # State uncertainty matrix.
        self.P = None

        # Number of consecutive frames without a detection.
        self.gap_frames = 0

        self.initialized = False


        # Constant velocity motion model:
        # next_position = current_position + velocity
        # velocity stays approximately constant.
        self.F = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=float)


        # Measurement model:
        # The detector only observes the ball position (x,y),
        # not its velocity.
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=float)


    def _process_noise_Q(self):
        """
        Defines how much uncertainty is added during prediction.

        Higher noise means the tracker allows faster changes
        in ball movement.
        """
        q_pos = self.cfg.base_process_noise_pos
        q_vel = self.cfg.base_process_noise_vel

        return np.diag([
            q_pos,
            q_pos,
            q_vel,
            q_vel
        ])


    def _gap_inflation(self):
        """
        Increases uncertainty when detections are missing.

        A longer detection gap means the prediction becomes
        less reliable, so the search area becomes larger.
        """
        factor = self.cfg.gap_inflation_per_frame ** self.gap_frames

        return min(
            factor,
            self.cfg.max_gap_inflation
        )


    def init(self, x, y):
        """
        Initialize the tracker with the first detected ball position.

        Initial velocity is unknown, so it starts at zero.
        """
        self.x = np.array([
            x,
            y,
            0.0,
            0.0
        ])

        self.P = np.diag([
            self.cfg.measurement_noise,
            self.cfg.measurement_noise,
            100.0,
            100.0
        ])

        self.gap_frames = 0
        self.initialized = True


    def predict(self):
        """
        Predict ball position in the next frame.

        Returns:
            predicted position (x,y)
            predicted position uncertainty
        """

        if not self.initialized:
            return None, None

        # Move state using constant velocity assumption.
        self.x = self.F @ self.x

        # Increase uncertainty if detections were missed.
        inflation = self._gap_inflation()

        self.P = (
            self.F @ self.P @ self.F.T
            + self._process_noise_Q() * inflation
        )

        return (
            self.x[:2].copy(),
            self.P[:2, :2].copy()
        )


    def mahalanobis(self, meas_xy):
        """
        Measure how far a detection is from the prediction.

        Used as a gate:
        - small value -> detection matches prediction
        - large value -> likely false detection
        """

        pred_xy = self.x[:2]

        S = (
            self.P[:2, :2]
            + np.eye(2) * self.cfg.measurement_noise
        )

        diff = np.array(meas_xy) - pred_xy

        try:
            S_inv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return np.inf

        return float(
            diff @ S_inv @ diff.T
        )


    def update(self, meas_xy):
        """
        Correct the prediction using a real ball detection.

        The Kalman gain decides how much to trust:
        - prediction
        - detection
        """

        R = np.eye(2) * self.cfg.measurement_noise

        S = (
            self.H @ self.P @ self.H.T
            + R
        )

        K = (
            self.P
            @ self.H.T
            @ np.linalg.inv(S)
        )

        # Difference between measured and predicted position.
        y = (
            np.array(meas_xy)
            - self.H @ self.x
        )

        # Correct state.
        self.x = self.x + K @ y

        # Reduce uncertainty after receiving a detection.
        self.P = (
            np.eye(4) - K @ self.H
        ) @ self.P

        self.gap_frames = 0


    def mark_missed(self):
        """
        Called when no valid ball detection is available.

        The tracker keeps predicting but increases uncertainty.
        """
        self.gap_frames += 1