"""Screen the Phase 3 axial design space with the corrected TurboDesigner blockage (0.02 / 0.04) at the
Phase 3 tool-level cycle point (W 1.052 kg/s, OPR 5); prints feasibility and the binding limits."""
import os, sys, json, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import axial_design as ad
rpms = [int(a) for a in sys.argv[1].split(",")] if len(sys.argv) > 1 else [50000, 55000, 60000, 65000, 70000, 75000, 80000, 85000]
p0 = dict(mdot=1.052167931905524, T01=308.90466137184205, P01=101701.5430887929, PR=5.0, clearance=0.25e-3)
rows = []
for rpm in rpms:
    for N in (4, 5, 6, 7):
        for ht in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
            for Cx in (150, 170, 185, 200):
                p = dict(p0, rpm=rpm, N=N, hub_tip=ht, Cx=Cx)
                try:
                    eta = 0.80
                    for _ in range(12):
                        r = ad.evaluate(p, eta)
                        if abs(r["eta_is"] - eta) < 5e-4: break
                        eta = 0.5 * eta + 0.5 * r["eta_is"]
                except Exception as e:
                    continue
                st = r["stages"]
                lim = dict(DF=max(s["DF_rotor"] for s in st), dH=min(s["deHaller_r"] for s in st), M=st[0]["M_rel_tip"], h=st[-1]["stator"]["h"] * 1e3)
                ok = lim["DF"] <= 0.5 and lim["dH"] >= 0.72 and lim["M"] <= 1.35 and lim["h"] >= 10.0 and np.isfinite(r["eta_is"])
                rows.append(dict(rpm=rpm, N=N, ht=ht, Cx=Cx, eta=r["eta_is"], ok=ok, D=2e3 * (r["r_tip_max"] + 0.25e-3 + 0.0025), L=r["length"] * 1e3, **lim))
import pandas as pd
df = pd.DataFrame(rows); pd.set_option("display.width", 200)
print("feasible:", int(df.ok.sum()), "of", len(df))
print(df[df.ok].sort_values("eta", ascending=False).head(15).round(3).to_string(index=False))
print("best infeasible by eta (limits):")
print(df[~df.ok].sort_values("eta", ascending=False).head(10).round(3).to_string(index=False))
df.to_csv(os.path.join(ROOT, "data", "phase4_axial_blockage_screen.csv"), index=False)
