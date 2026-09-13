"""Phase 2 design-point outputs: drag polar plots, area distribution, thrust-vs-drag at the dash
altitude, and the per-segment thrust requirement table at the chosen design point
(S = 0.30 m2, take-off mass from the mass-budget iteration).
Outputs: plots/phase2_drag_polar.png, plots/phase2_area_distribution.png,
         data/phase2_design_point_segments.csv, data/phase2_design_point.json
"""
import os, sys, json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from airframe_model import Config, ROOT
from aero_utils import isa, G0
import mission_drag_polar as mdp

S_DES = 0.30
mb = pd.read_csv(os.path.join(ROOT, "data", "phase2_mass_budget.csv"))
row = mb[(mb.S_wing == S_DES) & (mb.engine_case == "nom") & (mb.E_case == "nom")].iloc[0]
TOGW = float(row.TOGW_kg)
c = Config(S_wing=S_DES)
E_hi = max(3.0, max(1.8, c.E_geom()))

# ---- per-segment thrust requirement at the design point ----
segs = []
for tag, E in (("nominal drag", None), (f"pessimistic drag (E_WD {E_hi:.1f})", E_hi)):
    for mass_tag, M0 in (("design TOGW", TOGW), ("25 kg ceiling", 25.0)):
        s, seg = mdp.run(S_DES, E_WD=E, M0=M0)
        for d in seg:
            d.update(drag_case=tag, mass_case=mass_tag, TOGW_kg=M0); segs.append(d)
sd = pd.DataFrame(segs)
sd.to_csv(os.path.join(ROOT, "data", "phase2_design_point_segments.csv"), index=False)
pd.set_option("display.width", 220)
print(sd[["drag_case", "mass_case", "segment", "time_s", "fuel_kg", "Treq_max_N", "Tavail_min_N", "excess_min_N"]].round(2).to_string(index=False))

# ---- drag polar vs Mach ----
Ms = np.array([0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.05])
fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
for S, ls in ((0.25, ":"), (0.30, "-"), (0.35, "--")):
    cc = Config(S_wing=S)
    ax[0].plot(Ms, [cc.CDS(m, 5000.0) * 1e4 for m in Ms], ls, c="k", label=f"S = {S} m2, E_WD nominal ({max(1.8, cc.E_geom()):.2f})")
lo = [c.CDS(m, 5000.0, E_WD=1.4) * 1e4 for m in Ms]; hi = [c.CDS(m, 5000.0, E_WD=E_hi) * 1e4 for m in Ms]
ax[0].fill_between(Ms, lo, hi, alpha=.2, label=f"S = 0.30: E_WD 1.4 - {E_hi:.1f}")
ax[0].axhline(132, c="r", ls="--", lw=1, label="Phase 1 budget 132 cm2"); ax[0].axhline(99, c="orange", ls="--", lw=1, label="Phase 1 target 99 cm2")
ax[0].axvline(1.02, c="gray", lw=.8)
ax[0].set_xlabel("Mach"); ax[0].set_ylabel("zero-lift drag area CD*S [cm2] at 5 km"); ax[0].grid(alpha=.3); ax[0].legend(fontsize=7)
ax[0].set_title("Drag build-up (Raymer friction/form + area-rule wave drag)", fontsize=9)
# thrust vs drag at 5 km, design mass
W = (TOGW - 0.85) * G0
def D(M, E=None):
    q = 0.7 * isa(5000.0)[1] * M ** 2; CL = W / (q * S_DES)
    return q * c.CDS(M, 5000.0, E_WD=E) + q * S_DES * c.k_induced(M) * CL ** 2
T = [0.97 * float(mdp.Fn_i((m, 5000.0))) for m in Ms]
ax[1].plot(Ms, T, "k-", lw=2, label="thrust available (max throttle, installed)")
ax[1].plot(Ms, [0.75 * t for t in T], "k:", label="75 % of available (25 % margin line)")
ax[1].plot(Ms, [D(m) for m in Ms], "b-", label="drag, nominal E_WD")
ax[1].plot(Ms, [D(m, E_hi) for m in Ms], "b--", label=f"drag, E_WD {E_hi:.1f}")
ax[1].axvline(1.02, c="gray", lw=.8)
ax[1].set_xlabel("Mach"); ax[1].set_ylabel("force [N]"); ax[1].grid(alpha=.3); ax[1].legend(fontsize=7)
ax[1].set_title(f"5 km, S = {S_DES} m2, mass {TOGW - 0.85:.1f} kg (at dash)", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase2_drag_polar.png"), dpi=130)

# ---- area distribution ----
x, A = c.area_distribution()
m = A > 1e-6; l = x[m][-1] - x[m][0]; xi = np.clip((x - x[m][0]) / l, 0, 1)
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(x, A * 1e4, "k", lw=2, label="equivalent body: external area - inlet stream-tube (+ jet plume)")
for k_, s_ in c.surfaces().items():
    ax.plot(x, s_.area_distribution(x, c.r_fus if not s_.vertical else 0.0) * 1e4, "--", label=k_)
ax.plot(x, A.max() * 1e4 * (4 * xi * (1 - xi)) ** 1.5, ":", c="gray", label="Sears-Haack, same A_max and length")
ax.set_xlabel("x [m]"); ax.set_ylabel("area [cm2]"); ax.grid(alpha=.3); ax.legend(fontsize=7)
ax.set_title(f"M = 1 normal-cut area distribution, S = {S_DES} m2: A_max {A.max()*1e4:.0f} cm2, l {l:.2f} m, E_geom {c.E_geom():.2f}", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase2_area_distribution.png"), dpi=130)

dp = dict(S_wing_m2=S_DES, TOGW_kg=TOGW, WS_TO_Pa=TOGW * G0 / S_DES, geometry={k: (float(v) if not isinstance(v, str) else v) for k, v in c.summary().items()},
          CDS_M1p02_5km_cm2=c.CDS(1.02, 5000.0) * 1e4, CDS_M1p02_5km_hi_cm2=c.CDS(1.02, 5000.0, E_WD=E_hi) * 1e4,
          E_geom=c.E_geom(), E_WD_nominal=max(1.8, c.E_geom()), E_WD_hi=E_hi, D_fus_m=c.D_fus, D_engine_m=c.D_engine)
json.dump(dp, open(os.path.join(ROOT, "data", "phase2_design_point.json"), "w"), indent=1)
print(json.dumps(dp, indent=1))
