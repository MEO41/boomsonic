"""Phase 4: effect of a larger (variable-area) exhaust nozzle on the sea-level-static running line of the
axial engine (fixed IGV map). A8_scale = throat area / dash-design throat area.
Usage: python nozzle_sweep.py <trade tag>"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TAG = sys.argv[1] if len(sys.argv) > 1 else "ax0_opr5_t1150_cap_blk"
ARGS = sys.argv[:]; sys.argv = [sys.argv[0], TAG]; sys.path.insert(0, HERE)
import operability as op
Ns = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3]
rows = []
for a8 in [float(v) for v in ARGS[2].split(",")] if len(ARGS) > 2 else (1.15, 1.3, 1.5, 1.75, 2.0):
    r, _ = op.sweep_speed(0.0, 0.0, Ns, f"SLS_A8x{a8:g}", a8=a8); rows += r
pd.DataFrame(rows).to_csv(os.path.join(ROOT, "data", f"phase4_nozzle_sweep_{TAG}" + (("_" + ARGS[2].replace(",", "-")) if len(ARGS) > 2 else "") + ".csv"), index=False)
