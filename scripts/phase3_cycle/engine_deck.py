"""Phase 3 off-design deck of a chosen engine (pyCycle), max throttle = min(RPM-limited, T4-limited).

Design point = the Phase 3 dash design (M1.02 / 5 km, Fn 500 N, given OPR, T4, eta_c, eta_t, duct
loss). Off-design uses pyCycle's scaled NPSS maps (AXI5 / LPT2269) -> PLACEHOLDER map shapes until
Phase 4 produces the real compressor/turbine maps (flagged in the output).
Usage: python engine_deck.py OPR T4 eta_c eta_t duct_dPqP tag
Output: data/phase3_deck_<tag>.csv
"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import cycle_model as cm, dash_cycle as dc

OPR, T4, EC, ET, DUCT = (float(v) for v in sys.argv[1:6]); TAG = sys.argv[6]
MACHS = [0.0, 0.3, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0, 1.02, 1.05]
ALTS = [0.0, 1000.0, 2500.0, 4000.0, 5000.0, 6000.0]

def snake():
    p = []
    for i, h in enumerate(ALTS):
        p += [(m, h) for m in (MACHS if i % 2 == 0 else MACHS[::-1])]
    return p

res = {}
for mode in ("N", "T4"):
    prob, mp = cm.build(od_points=[(1.02, 5000.0)], od_mode=mode)
    rec = dc.normal_shock_recovery(dc.M_DASH)
    cm.set_design(prob, dc.M_DASH, dc.H_DASH, OPR, T4, EC, ET, Fn_N=500.0, duct_dPqP=DUCT, ram_recovery=rec, od_names=mp.od_names, od_mode=mode)
    pt = mp.od_names[0]; grp = prob.model._get_subsystem(pt)
    prob.run_model()
    Nd = float(np.ravel(prob.get_val('DESIGN.Nmech', units='rpm'))[0])
    for (m, h) in snake():
        prob.set_val(pt + '.fc.MN', max(m, 1e-6)); prob.set_val(pt + '.fc.alt', h, units='m')
        prob.set_val(pt + '.inlet.ram_recovery', dc.normal_shock_recovery(m))
        prob.run_model()
        ok = float(grp._residuals.get_norm()) < 1e-4
        d = cm.read(prob, pt, eta_b=dc.ETA_B); d["converged"] = ok; d["N_pct"] = 100 * d["Nmech"] / Nd
        res[(mode, m, h)] = d
rows = []
for h in ALTS:
    for m in MACHS:
        a, b = res[("N", m, h)], res[("T4", m, h)]
        c = [x for x in (a, b) if x["converged"] and (x is a or x["N_pct"] <= 100.5)]
        best = min(c, key=lambda x: x["Fn_N"]) if c else None
        rows.append(dict(MN=m, alt_m=h, Fn_N=best["Fn_N"] if best else np.nan, Wf_kgps=best["Wf_kgps"] if best else np.nan,
                         W_kgps=best["W_kgps"] if best else np.nan, T4_K=best["Tt4_K"] if best else np.nan, N_pct=best["N_pct"] if best else np.nan,
                         binding=("N" if best is a else "T4") if best else "none", Fn_Nmode=a["Fn_N"], Fn_T4mode=b["Fn_N"], conv_N=a["converged"], conv_T4=b["converged"],
                         maps="PLACEHOLDER scaled NPSS maps"))
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", f"phase3_deck_{TAG}.csv"), index=False)
pd.set_option("display.width", 200)
print(df[["MN", "alt_m", "Fn_N", "binding", "N_pct", "T4_K", "W_kgps", "conv_N", "conv_T4"]].round(3).to_string(index=False))
