from dataclasses import dataclass, field


# Shared ball tracker constants.
# These are runtime values, not file paths, so they stay here instead of paths.py.
PX_PER_METER = 10.0
FPS = 25.0


# Cache rebuild controls.
# Set True when a stage must run again even if its cache already exists.
FORCE_REBUILD_BALL_TRACKER = False
FORCE_REBUILD_CARRIER = False


@dataclass
class BallTrackerConfig:
    # Kalman filter noise parameters.
    # Higher values make the filter trust predictions less and detections more.
    base_process_noise_pos: float = 15.0
    base_process_noise_vel: float = 40.0
    measurement_noise: float = 25.0

    # Increase uncertainty when the ball is missing.
    # Allows the tracker to search a larger area after lost detections.
    gap_inflation_per_frame: float = 1.15
    max_gap_inflation: float = 25.0

    # Maximum allowed prediction-to-detection distance using covariance.
    mahalanobis_gate: float = 9.21

    # Detection confidence handling.
    min_detection_conf: float = 0.15
    low_conf_flag: float = 0.25

    # Track lifecycle settings.
    max_track_gap_frames: int = 38
    min_frames_to_confirm_track: int = 2

    # Video coordinate conversion.
    px_per_meter: float = PX_PER_METER
    fps: float = FPS

    # Reject physically impossible ball movements.
    # Prevents loose Kalman uncertainty from accepting false detections.
    max_ball_speed_mps: float = 35.0


    # Increase confidence requirement when multiple players are close.
    # Helps remove false ball detections during tackles and crowded situations.
    crowd_min_conf: float = 0.50
    crowd_radius_px: float = 60.0
    crowd_min_players: int = 2



@dataclass
class CarrierConfig:
    # Distance margin around a player bbox considered as ball contact.
    bbox_overlap_margin_px: float = 15.0

    # Maximum distance fallback when assigning the ball carrier.
    max_carrier_distance_m: float = 2.5

    # Number of consecutive frames needed before changing carrier.
    # Prevents rapid carrier switching caused by noisy detections.
    min_frames_to_switch: int = 10

    # Remove the carrier when no player is close to the ball.
    clear_on_no_candidate: bool = True

    # Keep previous carrier briefly when the ball is temporarily ambiguous.
    no_candidate_grace_frames: int = 8


    # Avoid choosing a carrier when two players are almost equally close.
    # The best candidate must clearly beat the second candidate.
    candidate_margin_ratio: float = 0.7


    # Verify carrier changes using ball movement.
    # A real touch usually changes ball speed or direction.
    velocity_check_window: int = 4
    min_speed_change_mps: float = 2.0
    min_angle_change_deg: float = 20.0

    fps: float = FPS


    # Allowed ball position sources used by the carrier logic.
    decision_sources: set = field(
        default_factory=lambda: {"detected", "smoothed"}
    )

    # Sources allowed for visualization/output.
    display_sources: set = field(
        default_factory=lambda: {"detected", "smoothed"}
    )