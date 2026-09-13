"""Phase 3: excess thrust through the transonic acceleration (level, 5 km, M 0.70 -> 1.05) for a candidate
engine: thrust from its pyCycle off-design deck (data/phase3_deck_<tag>.csv, RPM-limited, placeholder maps),
drag from the Phase 2 airframe model with the candidate's real engine diameter. Usage: deck_tag D_engine_mm mass_kg"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))
import airframe_model as am
from aero_utils import isa, G0
tag, D, m = sys.argv[1], float(sys.argv[2]) / 1e3, float(sys.argv[3])
deck = pd.read_csv(os.path.join(ROOT, "data", f"phase3_deck_{tag}.csv")); d5 = deck[deck.alt_m == 5000.0].sort_values("MN")
c = am.Config(S_wing=0.30); c.D_engine = D
rows = []
for _, r in d5[d5.MN >= 0.7].iterrows():
    M = r.MN; q = 0.7 * isa(5000.0)[1] * M * M; CL = m * G0 / (q * 0.30)
    for tag2, E in (("nom", None), ("hi", max(3.0, max(1.8, c.E_geom())))):
        Dr = q * c.CDS(M, 5000.0, E_WD=E) + q * 0.30 * c.k_induced(M) * CL ** 2
        rows.append(dict(MN=M, case=tag2, thrust_N=r.Fn_N, drag_N=Dr, excess_N=r.Fn_N - Dr, margin=r.Fn_N / Dr - 1, T4_K=r.T4_K))
df = pd.DataFrame(rows); pd.set_option("display.width", 200)
print(df.pivot_table(index="MN", columns="case", values=["thrust_N", "drag_N", "margin"]).round(3).to_string())
df.to_csv(os.path.join(ROOT, "data", f"phase3_pinch_{tag}.csv"), index=False)
