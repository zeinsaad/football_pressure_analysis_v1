"""
Best-effort integration with the pipeline's own `paths.py`.

If the pipeline project (containing paths.py) is importable -- either
because this app is run from inside it, or PIPELINE_ROOT below points at
it -- known cache/output paths are read directly from there instead of
requiring manual uploads every time.

We don't have the full contents of your real paths.py, so this only
assumes two attributes confirmed by your actual pipeline code
(main.py / the analysis notebook both reference them):

    PLAYER_FRAME_TABLE_CACHE_PATH
    BALL_FRAME_TABLE_CACHE_PATH

Two more are read too, but they're SUGGESTED new constants, not
confirmed ones -- add them to your real paths.py to get full
auto-detection everywhere:

    UI_EXPORT_PATH        # where the notebook's Section 20 cell should write
                           # pressure_analysis_export.json
    OUTPUT_VIDEO_PATH      # where render.RenderPipeline.render() writes the
                           # annotated video
    LLM_REPORT_PATH        # where team_pressure_llm_report.ipynb saves its
                           # generated tactical report (markdown)

Anything not found falls back to a default and the UI still lets you
type a path or upload a file manually -- this never hard-fails just
because paths.py isn't on the Python path.
"""

import importlib
import os
import sys

PIPELINE_ROOT = os.environ.get(
    "PIPELINE_ROOT",
    r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project",
)

_paths_module = None
_import_error = None
_tried = False


def _try_import(extra_root: str = "") -> None:
    global _paths_module, _import_error, _tried
    root = extra_root or PIPELINE_ROOT
    if root and root not in sys.path:
        sys.path.insert(0, root)
        _tried = False  # a new root means it's worth trying again

    if _tried:
        return
    _tried = True
    try:
        _paths_module = importlib.import_module("paths")
    except ImportError as e:
        _import_error = e


def available(extra_root: str = "") -> bool:
    _try_import(extra_root)
    return _paths_module is not None


def get(attr: str, default=None, extra_root: str = ""):
    """
    Read one attribute off the real paths.py, or return default if missing/unimportable.

    A relative path value is resolved against the folder paths.py itself lives in
    (not the caller's cwd) -- otherwise the exact same relative string in paths.py
    points at a different place depending on whether the notebook, a script, or
    Streamlit happens to be running it from.
    """
    _try_import(extra_root)
    if _paths_module is None:
        return default
    value = getattr(_paths_module, attr, default)
    if value is None or not isinstance(value, str) or os.path.isabs(value):
        return value
    module_dir = os.path.dirname(os.path.abspath(_paths_module.__file__))
    return os.path.normpath(os.path.join(module_dir, value))


CONFIRMED_ATTRS = ["PLAYER_FRAME_TABLE_CACHE_PATH", "BALL_FRAME_TABLE_CACHE_PATH"]
SUGGESTED_ATTRS = ["UI_EXPORT_PATH", "OUTPUT_VIDEO_PATH", "LLM_REPORT_PATH"]


def status(extra_root: str = "") -> dict:
    """For the sidebar: what got found vs. what's missing."""
    _try_import(extra_root)
    all_attrs = CONFIRMED_ATTRS + SUGGESTED_ATTRS
    return {
        "importable": _paths_module is not None,
        "import_error": str(_import_error) if _import_error else None,
        "module_file": getattr(_paths_module, "__file__", None) if _paths_module else None,
        "found": {a: get(a) for a in all_attrs if get(a) is not None},
        "missing": [a for a in all_attrs if get(a) is None],
    }
