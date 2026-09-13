"""Phase 2: zero-lift drag-area table D/q(S_wing, Mach, altitude) for the baseline configuration
family (fuselage fixed by the engine envelope; wing + tails scale with S_wing), plus lift-curve
slope and induced-drag factor. Consumed by the ADRpy constraint script (NumPy-1 env) and the
mission integration. Output: data/phase2_drag_table.csv, data/phase2_baseline_breakdown.csv"""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from airframe_model import Config, ROOT

S_GRID = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.80]
M_GRID = [0.05, 0.2, 0.4, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 1.0, 1.02, 1.05]
H_GRID = [0.0, 2500.0, 5000.0]
rows = []
for S in S_GRID:
    c = Config(S_wing=S)
    for h in H_GRID:
        for M in M_GRID:
            E_nom = max(1.8, c.E_geom())
            for tag, E in [("nom", None), ("lo", min(1.4, E_nom)), ("hi", max(3.0, E_nom))]:
                d = c.drag_breakdown(M, h, E_WD=E)
                rows.append(dict(S_wing=S, alt_m=h, MN=M, E_case=tag, CDS_m2=sum(d.values()), wave_m2=d["wave"],
                                 E_WD=c._wave_info["E_WD_used"], E_geom=c._wave_info["E_geom"], k=c.k_induced(M), CLa=c.CL_alpha(M),
                                 CD0=sum(d.values()) / S))
df = pd.DataFrame(rows)
df.to_csv(os.path.join(ROOT, "data", "phase2_drag_table.csv"), index=False)
c = Config()
bd = []
for M, h in [(0.3, 0), (0.7, 300), (0.9, 5000), (1.0, 5000), (1.02, 5000), (1.05, 5000)]:
    d = c.drag_breakdown(M, h); d = {k: v * 1e4 for k, v in d.items()}; d.update(MN=M, alt_m=h, total_cm2=sum(d.values())); bd.append(d)
bd = pd.DataFrame(bd); bd.to_csv(os.path.join(ROOT, "data", "phase2_baseline_breakdown.csv"), index=False)
pd.set_option("display.width", 200)
print(pd.Series(c.summary()).to_string())
print("E_geom =", round(c.E_geom(), 3), "| D_fus =", c.D_fus)
print(bd.round(1).to_string(index=False))
sub = df[(df.alt_m == 5000) & (df.MN == 1.02)].pivot_table(index="S_wing", columns="E_case", values="CDS_m2") * 1e4
print("\nCD*S [cm2] at M1.02 / 5 km vs wing area and E_WD case:\n", sub.round(1).to_string())
