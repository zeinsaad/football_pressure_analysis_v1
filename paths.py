"""
Single source of truth for every path used across the pipeline.

Fill these in for your environment (Kaggle/Colab/local) — nothing else in
the project should hardcode a path. Every module's config.py imports its
relevant subset from here.
"""

# ---- shared ----
VIDEO_PATH = "barca_atletico/clip.mkv"   # used by detector, homography, tracker, team_assigner, ball_tracker, render

# ---- detector ----
MULTI_MODEL_PATH = "models/yolov8x_football_ft2_best.pt"       # goalkeeper/player/referee model
BALL_MODEL_PATH = "models/best_ball_final.pt.pt"        # dedicated ball-only model
DETECTION_CACHE_PATH = "barca_atletico/cache/barca_atletico_detection_cache_final_v1.pkl"   # output of detector

# ---- homography ----
SEG_MODEL_PATH = "models/seg_model.pt"         # pitch-line segmentation model
POSE_MODEL_PATH = "models/pose_model.pt"        # pitch keypoint pose model
HOMOGRAPHY_CACHE_PATH = "barca_atletico/cache/homography_cache (5).pkl"  # output of homography

# ---- tracker ----
OSNET_WEIGHTS_PATH = "osnet_x1_0_sportsmot_best.pt"     # fine-tuned OSNet ReID weights
TRACKING_CACHE_PATH = "barca_atletico/cache/barca_atletico_tracking_cache_final_v1.pkl"    # output of tracker (input to team_assigner + ball_tracker + render)

# ---- team_assigner ----
TEAM_CACHE_PATH = "barca_atletico/cache/barca_atletico_team_assignment_final.pkl"        # output of team_assigner

# ---- ball_tracker ----
BALL_TRACKED_CACHE_PATH = "barca_atletico/cache/barca_atletico_ball_tracked_cache.pkl"    # output of the Kalman+RTS ball tracker (input to carrier assignment + render)
BALL_CARRIER_CACHE_PATH = "barca_atletico/cache/barca_atletico_ball_carrier_cache.pkl"    # output of carrier assignment (input to render)

# ---- render ----
OUTPUT_VIDEO_PATH = "barca_atletico/output/annotated_video.mp4"      # final annotated video

# ---- frame_table (stats join layer) ----
PLAYER_FRAME_TABLE_CACHE_PATH = "barca_atletico/cache/player_frame_table.parquet"
BALL_FRAME_TABLE_CACHE_PATH = "barca_atletico/cache/ball_frame_table.parquet"

# ---- passes (stats event module) ----
PASS_EVENTS_CACHE_PATH = "barca_atletico/cache/pass_events.parquet"