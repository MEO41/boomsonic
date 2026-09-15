"""Phase 4: overboard handling/start bleed after stage 3 of the 6-stage axial (fixed IGV, design nozzle):
stage-stacking map rebuilt with the bleed (rear stages see (1-f) of the flow), pyCycle bleed port removes the
same flow fraction. frac_P / frac_work of the port from the design-point stage-3 exit (stacking model).
Usage: python bleed_sweep.py <trade tag>"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
TAG = sys.argv[1] if len(sys.argv) > 1 else "ax0_opr5_t1150_cap_blk"
ARGS = sys.argv[:]; sys.argv = [sys.argv[0], TAG]; sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE)
import operability as op, axial_map as am
dp = op.c.point(1.0, op.c.W_d, detail=True)
K = 3
P3 = np.prod([r["PR"] for r in dp["rows"][:K]]); frac_P = (P3 - 1) / (dp["PR"] - 1)
frac_work = sum(r["dT0"] for r in dp["rows"][:K]) / sum(r["dT0"] for r in dp["rows"])
print(f"bleed port after stage {K}: frac_P {frac_P:.3f}, frac_work {frac_work:.3f}", flush=True)
Ns = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35]
rows = []
for f in [float(v) for v in ARGS[2].split(",")] if len(ARGS) > 2 else (0.10, 0.20, 0.30):
    lines_b = am.build_compressor_lines(op.c, bleed_sched=lambda N, f=f: (K, f) if N <= op.BLEED_CLOSE + 1e-9 else None)
    cmap_b, _ = am.compressor_mapdata(lines_b, op.c.W_d, op.c.T01, op.c.P01)
    r, _ = op.sweep_speed(0.0, 0.0, Ns, f"SLS_bleed{int(f*100)}", cmap_=cmap_b, lines_=lines_b, bleed=(K, f, frac_P, frac_work)); rows += r
pd.DataFrame(rows).to_csv(os.path.join(AXROOT, "data", f"phase4_bleed_sweep_{TAG}" + (("_" + ARGS[2].replace(",", "-")) if len(ARGS) > 2 else "") + ".csv"), index=False)
