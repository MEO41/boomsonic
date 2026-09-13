"""Import ROSS 2.3.0 in the project .venv (plotly 7.0.0, numba 0.67.0). Two compatibility work-arounds,
neither of which touches the FE matrices or eigen-solution:
1. ROSS's plotly theme uses the 'scattermapbox' template key that plotly 7 removed -> the import fails.
   The template is created with skip_invalid=True (plot styling only).
2. ROSS's numba-jitted mode-shape orbit helper (results._init_orbit) calls np.argmax on a complex array,
   which numba 0.67 cannot type -> run_modal fails. NUMBA_DISABLE_JIT=1 runs that helper as plain NumPy
   (same code path, slower)."""
import os
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
import plotly.graph_objects as go
_orig = go.layout.Template.__init__
def _init(self, *a, **k):
    k.setdefault("skip_invalid", True); _orig(self, *a, **k)
go.layout.Template.__init__ = _init
import ross as rs  # noqa: E402
go.layout.Template.__init__ = _orig
