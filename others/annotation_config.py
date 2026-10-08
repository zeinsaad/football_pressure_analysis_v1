# ============================================================================================
# annotation_config.py -- everything you may want to change for the annotated video.
# The renderer (annotate_pro.py) imports this file; no settings live in the renderer itself.
# Colours are BGR (OpenCV order): (blue, green, red).
# ============================================================================================

# ---- paths ----------------------------------------------------------------------------------
VIDEO_PATH    = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\clip.mkv"
TRACKING_PATH = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\barca_atletico_match_cache.pkl"
BALL_CACHE_PATH    = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\barca_atletico_first_half_ball_tracked_cache.pkl"
CARRIER_CACHE_PATH = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\barca_atletico_first_half_ball_carrier_named.pkl"   # from compute_carrier.py (NEW ids)
OUTPUT_PATH   = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\annotated_pro.mp4"
PREVIEW_DIR   = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\preview"

# ---- teams ----------------------------------------------------------------------------------
TEAMS = {
    "BAR": {"name": "FC Barcelona",       "short": "BAR",
            "color": (152, 77, 0),        # Barça blue  (#004D98)
            "accent": (68, 0, 165),       # garnet      (#A50044)
            "gk_color": (0, 190, 255)},   # goalkeeper ring / badge (amber)
    "ATM": {"name": "Atlético de Madrid", "short": "ATM",
            "color": (36, 53, 203),       # Atleti red  (#CB3524)
            "accent": (97, 46, 39),       # navy        (#272E61)
            "gk_color": (80, 200, 60)},   # goalkeeper ring / badge (green)
}

# ---- roster: (team, shirt number) -> display name + position ---------------------------------
# The cache already carries team + number on every box; this table only decides what is SHOWN.
ROSTER = {
    # FC Barcelona
    ("BAR", 13): {"name": "Peña",        "pos": "GK"},
    ("BAR", 3):  {"name": "Balde",       "pos": "LB"},
    ("BAR", 5):  {"name": "I. Martínez", "pos": "CB"},
    ("BAR", 2):  {"name": "Cubarsí",     "pos": "CB"},
    ("BAR", 23): {"name": "Koundé",      "pos": "RB"},
    ("BAR", 17): {"name": "Casadó",      "pos": "CM"},
    ("BAR", 8):  {"name": "Pedri",       "pos": "CM"},
    ("BAR", 6):  {"name": "Gavi",        "pos": "CM"},
    ("BAR", 11): {"name": "Raphinha",    "pos": "RW"},
    ("BAR", 9):  {"name": "Lewandowski", "pos": "ST"},
    ("BAR", 16): {"name": "Fermín",      "pos": "LW"},
    # Atlético de Madrid
    ("ATM", 13): {"name": "Oblak",       "pos": "GK"},
    ("ATM", 21): {"name": "Galán",       "pos": "LB"},
    ("ATM", 15): {"name": "Lenglet",     "pos": "CB"},
    ("ATM", 2):  {"name": "Giménez",     "pos": "CB"},
    ("ATM", 14): {"name": "Llorente",    "pos": "RB"},
    ("ATM", 4):  {"name": "Gallagher",   "pos": "LM"},
    ("ATM", 8):  {"name": "Barrios",     "pos": "CM"},
    ("ATM", 5):  {"name": "De Paul",     "pos": "CM"},
    ("ATM", 22): {"name": "Simeone",     "pos": "RM"},
    ("ATM", 19): {"name": "Álvarez",     "pos": "ST"},
    ("ATM", 7):  {"name": "Griezmann",   "pos": "ST"},
}

# ---- officials ------------------------------------------------------------------------------
REFEREE_COLOR = (25, 25, 25)            # black ring + badge
REFEREE_LABEL = "REF"
ASSISTANT_LABEL = "AR"

# ---- what the label shows ---------------------------------------------------------------------
SHOW_NUMBER_BADGE = True                # coloured square with the shirt number
SHOW_NAME         = False               # False = numbers only on everybody (clean); names on hover in the viewer
SHOW_POSITION     = False               # small "CB" tag after the name
CARRIER_SHOWS_NAME = False              # True = the ball carrier gets number + name (+ position)
NAME_UPPERCASE    = False

# ---- look -----------------------------------------------------------------------------------
FONT_PATHS = [                          # first one found is used (bold sans works best)
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
]
LABEL_FONT_PX     = 12                  # number size at 1080p (scaled with video height)
LABEL_PLACEMENT   = "fixed"             # "fixed" = always centred above the head (never moves); "avoid" = shifts to avoid overlaps
LABEL_BG_COLOR    = (28, 22, 18)        # dark label background
LABEL_BG_ALPHA    = 0.82
LABEL_TEXT_COLOR  = (255, 255, 255)
POSITION_COLOR    = (190, 190, 190)
LABEL_GAP_PX      = 6                   # gap between the head and the label
LEADER_LINE       = True                # thin line from a moved label to its player
RING_FILL_ALPHA   = 0.28                # translucent ground ellipse
RING_THICKNESS    = 2
SMOOTHING         = 0.55                # 0 = raw boxes, closer to 1 = smoother (less jitter, a bit of lag)

# ---- what is drawn --------------------------------------------------------------------------
DRAW_DUPLICATES   = False               # second box on an already drawn person (same person twice)
DRAW_OFFPITCH     = True                # bench / staff / ball boys: faint grey ring, no label
OFFPITCH_COLOR    = (150, 150, 150)
DRAW_BALL         = True
BALL_COLOR        = (0, 255, 255)       # yellow circle ON the ball
BALL_DRAW_SOURCES = ("detected",)       # only real detections are drawn (add "smoothed" to also show filled-in frames)
BALL_CIRCLE_RADIUS = 8                  # px at 1080p when the detection box is not available
BALL_CIRCLE_THICKNESS = 2
CARRIER_TRIANGLE_COLOR = (0, 165, 255)  # small flipped triangle above the carrier's head (orange)
CARRIER_TRIANGLE_SIZE  = 9              # half-width in px at 1080p
CARRIER_LABEL_ICON = False              # True = also a small ball icon on the carrier's label
SHOW_POSSESSION   = True                # "Ball: BAR · Pedri" row in the HUD

# ---- viewer (match_viewer.py) ----------------------------------------------------------------
VIEWER_WIDTH = 1600                     # window width in px; hover is mapped exactly at any size
SHOW_HUD          = True                # team legend + match clock, top-left
CLOCK_OFFSET_S    = 0.0                 # match time at frame 0 (e.g. 0 for kick-off)

# ---- preview (run: python annotate_pro.py preview) -------------------------------------------
PREVIEW_FRAMES       = "auto"           # "auto" or a list, e.g. [1200, 5400, 30250]
PREVIEW_N_EVEN       = 3                # auto: evenly spaced frames ...
PREVIEW_N_CROWDED    = 3                # ... + the most crowded frames (hardest for labels)
PREVIEW_SEARCH_RANGE = (0, 15000)       # auto picks frames in this range (sequential read up to the end of it)

# ---- full render (run: python annotate_pro.py render) ----------------------------------------
START_FRAME = 0
END_FRAME   = 999                       # first check: frames 0-999 (40 s); None = to the end of the video
CODEC       = "mp4v"