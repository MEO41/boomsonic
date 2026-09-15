"""Bracketing check: the same engine match (dash design point, TurboFlow turbine map, design nozzle) with pyCycle's
NPSS AXI5 compressor map (a 5-stage, PR 5.2 axial map shipped with pyCycle; provenance/variable-geometry schedule
undocumented) instead of the stage-stacking map. Reports where the SLS steady running line meets the AXI5 stall line.
Usage: python running_line_axi5.py <trade tag>"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
TAG = sys.argv[1] if len(sys.argv) > 1 else "ax0_opr5_t1150_cap_blk"
sys.argv = [sys.argv[0], TAG]; sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE)
import operability as op
import pycycle.api as pyc
prob, mp, d = op.build("N", [(0.0, 0.0)], pyc.AXI5)
pt = mp.od_names[0]; Nd = op.g(prob, "DESIGN.Nmech", "rpm")
prob.set_val(pt + ".fc.MN", 1e-6); prob.set_val(pt + ".fc.alt", 0.0, units="m"); prob.set_val(pt + ".inlet.ram_recovery", 1.0)
rows = []
for N in [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35]:
    prob.set_val(pt + ".Nmech", N * Nd, units="rpm"); prob.run_model()
    r = op.read_od(prob, pt, Nd)
    if not r["conv"]: prob.run_model(); r = op.read_od(prob, pt, Nd)
    try: r["SMN"] = op.g(prob, pt + ".comp.SMN")
    except Exception: r["SMN"] = np.nan
    rows.append(r)
    print(f"  AXI5 SLS N {100*N:5.1f}%: conv {r['conv']} Fn {r['Fn_N']:7.1f} W {r['W_kgps']:.3f} PR {r['comp_PR']:.3f} eta {r['comp_eff']:.3f} T4 {r['Tt4_K']:6.1f} Rline {r['comp_RlineMap']:.3f} Nc {r['comp_NcMap']:.3f} SMN {r['SMN']:+.1f} %", flush=True)
pd.DataFrame(rows).to_csv(os.path.join(AXROOT, "data", f"phase4_running_line_axi5_{TAG}.csv"), index=False)
