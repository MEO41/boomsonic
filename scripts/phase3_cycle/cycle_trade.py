"""Phase 3 cycle-parameter trade at the dash design point (pyCycle): OPR x T4 x nozzle type, at the two
technology levels, Fn = 500 N at M1.02 / 5 km. Engine size follows airflow; the theta-scaled
combustor diameter (combustor_sizing.py) is reported because it sets the engine diameter.
Outputs: data/phase3_cycle_trade.csv, plots/phase3_cycle_trade.png
"""
import os, sys, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import dash_cycle as dc, cycle_model as cm, combustor_sizing as cs

LEVELS = {"tool (TurboFlow-level)": (0.79, 0.93), "fielded (vendor-TSFC level)": (0.70, 0.75)}
rows = []
probs = {nz: cm.build(design_W='Fn', nozz_type=nz)[0] for nz in ("CV", "CD")}
for lvl, (ec, et) in LEVELS.items():
    for nz in ("CV", "CD"):
        for T4 in (1150.0, 1250.0):
            for OPR in (3.0, 3.5, 4.0, 4.5, 5.0, 6.0):
                try:
                    d, _ = dc.design(OPR, T4, ec, et, nozz=nz, prob=probs[nz])
                except Exception as e:
                    continue
                if d["res"] > 1e-3: continue
                comb, _ = cs.combustor(d["Pt3_kPa"] * 1e3, d["Tt3_K"], d["W_kgps"])
                rows.append(dict(level=lvl, nozzle=nz, T4=T4, OPR=OPR, W=d["W_kgps"], spec_thrust=d["spec_thrust"], TSFC=d["TSFC_kgpNh"],
                                 T5=d["Tt5_K"], T3=d["Tt3_K"], P3_kPa=d["Pt3_kPa"], NPR=d["NPR"], comb_OD_mm=comb["mean"]["OD_mm"],
                                 comp_power_kW=d["comp_pwr_kW"], duct_dPqP=float(d["duct"]["dPqP"])))
                print(rows[-1], flush=True)
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase3_cycle_trade.csv"), index=False)
fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
for (lvl, nz, T4), g in df.groupby(["level", "nozzle", "T4"]):
    ls = "-" if nz == "CV" else "--"; c = "tab:blue" if lvl.startswith("tool") else "tab:red"; mk = "o" if T4 == 1150 else "s"
    lab = f"{lvl.split()[0]}, {nz}, T4 {T4:.0f}"
    ax[0].plot(g.OPR, g.W, ls, c=c, marker=mk, ms=4, label=lab); ax[1].plot(g.OPR, g.TSFC, ls, c=c, marker=mk, ms=4); ax[2].plot(g.OPR, g.comb_OD_mm, ls, c=c, marker=mk, ms=4)
ax[0].set_ylabel("airflow for 500 N at M1.02/5 km [kg/s]"); ax[1].set_ylabel("TSFC [kg/(N h)]"); ax[2].set_ylabel("theta-scaled combustor OD [mm]")
for a in ax: a.set_xlabel("compressor pressure ratio"); a.grid(alpha=.3)
ax[0].legend(fontsize=6.5)
fig.suptitle("Phase 3 cycle trade at the dash design point (pyCycle, duct loss included, eta_b 0.95)", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase3_cycle_trade.png"), dpi=130)
pd.set_option("display.width", 220)
print(df.round(3).to_string(index=False))
