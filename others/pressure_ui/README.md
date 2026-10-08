# Team Pressure Analysis — Streamlit UI

A modular Streamlit app for the pressing-metrics pipeline. Reads the JSON
export produced by the notebook's Section 20 cell and renders it as a
dashboard, a pitch heatmap, a match timeline, a pass map, and (optionally)
an annotated video.

## Project layout

```
pressure_ui/
├── app.py                    # entry point: nav, theme toggle, page routing
├── requirements.txt
├── .streamlit/config.toml    # fallback dark theme (app.py toggles at runtime)
├── data/
│   └── pressure_analysis_export.json   # <- put the notebook's export here
├── modules/
│   ├── data_loader.py        # cached JSON loading + small helpers
│   ├── pipeline_paths.py     # best-effort import of your real paths.py
│   ├── theme.py               # dark/light CSS + plotly template
│   ├── overview.py            # KPI cards, profile table, zone/PPDA/shape charts
│   ├── heatmap.py             # pitch pressure heatmap
│   ├── timeline.py            # pressure events, intensity bins, turnovers
│   ├── passmap.py             # pass release map + outcome taxonomy
│   └── video.py                # output-video viewer
└── utils/
    └── pitch.py                # shared Plotly pitch-drawing helper
```

## Setup

```bash
cd pressure_ui
pip install -r requirements.txt
```

1. Run the notebook's **Section 20** export cell (`team_pressure_analysis_v30.ipynb`).
2. Either:
   - **Auto-detect (recommended):** add a `UI_EXPORT_PATH` constant to your pipeline's `paths.py`
     pointing at where you want the export written, and a `RENDER_OUTPUT_PATH` constant pointing
     at where `render.RenderPipeline.render()` writes its annotated video. The notebook and this
     app both read `paths.py` when it's importable (see `modules/pipeline_paths.py`) — no manual
     copying needed.
   - **Manual:** copy `pressure_analysis_export.json` into `data/`, and use the "Upload a file"
     option on the Annotated Video page.
3. Run the app:

```bash
streamlit run app.py
```

If `paths.py` isn't on the Python path (e.g. this app lives outside your pipeline's project
folder), set the **pipeline root** in the sidebar's "Data source" panel — it's just the folder
that contains `paths.py`, and gets added to `sys.path` at runtime. Same effect as setting a
`PIPELINE_ROOT` environment variable before launching.

`PLAYER_FRAME_TABLE_CACHE_PATH` and `BALL_FRAME_TABLE_CACHE_PATH` are the only two `paths.py`
attributes this integration assumes exist (confirmed from your actual `main.py` and notebook).
`UI_EXPORT_PATH` and `RENDER_OUTPUT_PATH` are suggested additions — without them, the app falls
back to `data/pressure_analysis_export.json` and manual video upload respectively, and tells you
exactly which constants are missing in the sidebar.

## Sections

- **Overview** — KPI cards per team (pressing intensity, PPDA, regain rate), zone breakdown,
  turnover rate by zone, and defensive-shape comparison (resting vs. actively pressing).
- **Pressure heatmap** — the notebook's binned pressure grid (Section 20) drawn over a pitch,
  side-by-side or one team at a time.
- **Match timeline** — pressure events as a Gantt-style strip, the 5-minute pressing-intensity
  timeline, and a turnovers/press-response table.
- **Pass map & outcomes** — pass release locations colored by outcome, the pressured-action
  outcome taxonomy by team, and disruption/turnover rate by zone.
- **Output video** — plays the video your pipeline's own `render.RenderPipeline` already
  produced (tracking dots, team colors — main.py Step 9), auto-located via
  `paths.OUTPUT_VIDEO_PATH`. Doesn't process or re-annotate anything; just finds and displays it.

## Notes

- The dark/light toggle is applied at runtime via CSS injection (`modules/theme.py`) since
  Streamlit doesn't support switching its native theme mid-session; Plotly figures pick up the
  matching `plotly_dark` / `plotly_white` template automatically.
- Team colors are centralized in `data_loader.team_color()` so every chart in the app stays
  consistent.
- `pressure_analysis_export.json` is expected to match the shape written by the notebook's
  Section 20 cell (`meta` / `team` / `events` top-level keys). If your export's field names
  differ, the modules that read them will raise a clear error rather than fail silently.
