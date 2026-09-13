"""Sweep axial-compressor design space (TurboDesigner geometry + loss model), keep designs that
meet the limits: rotor/stator DF <= 0.50, de Haller >= 0.72, first-rotor tip M_rel <= 1.35,
last blade height >= 10 mm (clearance/height and manufacturability). Usage: mdot T01 P01 PR tag"""
import sys, os, json, itertools, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import axial_design as ad
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
mdot, T01, P01, PR = [float(v) for v in sys.argv[1:5]]; tag = sys.argv[5]
rows = []
for rpm, N, ht, Cx in itertools.product([55000, 65000, 75000, 85000], [4, 5, 6, 7], [0.45, 0.55, 0.65], [160, 185, 210]):
    p = dict(mdot=mdot, T01=T01, P01=P01, PR=PR, rpm=rpm, N=N, hub_tip=ht, Cx=Cx, clearance=0.25e-3)
    try:
        eta = 0.80
        for _ in range(12):
            r = ad.evaluate(p, eta)
            if abs(r["eta_is"] - eta) < 5e-4: break
            eta = 0.5 * eta + 0.5 * r["eta_is"]
    except Exception as e:
        continue
    st = r["stages"]
    d = dict(rpm=rpm, N=N, hub_tip=ht, Cx=Cx, eta_is=r["eta_is"], eta_poly=r["eta_poly"], D_casing_mm=2e3 * (r["r_tip_max"] + 0.25e-3 + 0.0025),
             DFr=max(s["DF_rotor"] for s in st), DFs=max(s["DF_stator"] for s in st), deH=min(s["deHaller_r"] for s in st),
             Mt1=st[0]["M_rel_tip"], h_last_mm=1e3 * st[-1]["stator"]["h"], length_mm=1e3 * r["length"], n_blades=r["n_blades"],
             U_mean=st[0]["U_mean"], inlet_M=r["inlet_M"])
    d["feasible"] = bool(d["DFr"] <= 0.5 and d["DFs"] <= 0.5 and d["deH"] >= 0.72 and d["Mt1"] <= 1.35 and d["h_last_mm"] >= 10 and np.isfinite(d["eta_is"]))
    rows.append(d)
json.dump(rows, open(os.path.join(ROOT, "data", "phase3", f"ax_sweep_{tag}.json"), "w"), indent=1)
import pandas as pd
df = pd.DataFrame(rows); pd.set_option("display.width", 220)
f = df[df.feasible]
print(f"{len(df)} designs, {len(f)} feasible")
print("best efficiency per casing-diameter band (feasible):")
f = f.assign(Dband=(f.D_casing_mm // 10) * 10)
print(f.sort_values("eta_is", ascending=False).groupby("Dband").head(1).sort_values("Dband").round(3).to_string(index=False))
