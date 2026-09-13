"""Phase 2: statistical engine mass / envelope from the sourced micro-turbojet database.

Input : data/microturbojet_database.csv (26 engines, 160-1250 N, manufacturer data sheets;
        every row carries its source URL).
Method: power-law fits y = a F^b (log-log least squares) of dry mass, diameter, length and
        airflow vs max SLS thrust; residual scatter reported as 1-sigma in log space.
        Accessory mass (ECU + pump + valves + battery + thermocouple + straps) from the three
        engines whose manufacturer publishes BOTH engine-only and "system airborne" mass (AMT).
Query : the D1.1 engine: derived SLS thrust 665 N (pyCycle), static airflow 1.166 kg/s.
Output: data/phase2_engine_fit.csv, data/engine_envelope.json (read by airframe_model.Config),
        plots/phase2_engine_database.png
"""
import os, json, re, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
db = pd.read_csv(os.path.join(ROOT, "data", "microturbojet_database.csv"))
F_Q, W_Q = 665.3, 1.166           # D1.1 engine: SLS thrust [N], SLS airflow [kg/s] (pyCycle, Phase 1/2)

def fit(x, y):
    m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    b, la = np.polyfit(np.log(x[m]), np.log(y[m]), 1)
    s = np.std(np.log(y[m] / (np.exp(la) * x[m] ** b)), ddof=2)
    return np.exp(la), b, s, int(m.sum())

rows, fits = [], {}
F = db.max_thrust_N.values.astype(float)
for col, lab in [("engine_mass_kg", "mass"), ("diameter_mm", "diameter"), ("length_mm", "length"), ("mass_flow_kgps", "airflow")]:
    a, b, s, n = fit(F, db[col].values.astype(float))
    pred = a * F_Q ** b
    fits[col] = (a, b, s)
    rows.append(dict(quantity=col, a=a, b=b, sigma_log=s, n=n, query_F_N=F_Q, prediction=pred,
                     lo_1sigma=pred * np.exp(-s), hi_1sigma=pred * np.exp(s)))
# mass vs airflow (subset with airflow published)
a, b, s, n = fit(db.mass_flow_kgps.values.astype(float), db.engine_mass_kg.values.astype(float))
rows.append(dict(quantity="engine_mass_kg vs airflow", a=a, b=b, sigma_log=s, n=n, query_F_N=np.nan, prediction=a * W_Q ** b,
                 lo_1sigma=a * W_Q ** b * np.exp(-s), hi_1sigma=a * W_Q ** b * np.exp(s)))
a, b, s, n = fit(db.mass_flow_kgps.values.astype(float), db.diameter_mm.values.astype(float))
rows.append(dict(quantity="diameter_mm vs airflow", a=a, b=b, sigma_log=s, n=n, query_F_N=np.nan, prediction=a * W_Q ** b,
                 lo_1sigma=a * W_Q ** b * np.exp(-s), hi_1sigma=a * W_Q ** b * np.exp(s)))
res = pd.DataFrame(rows)

# accessories: AMT publishes engine-only and system-airborne mass
acc = []
for _, r in db[db.manufacturer.str.contains("AMT")].iterrows():
    m = re.search(r"system airborne weight (\d+) g", str(r.mass_includes))
    if m:
        sysm = float(m.group(1)) / 1000
        acc.append(dict(model=r.model, F=r.max_thrust_N, engine=r.engine_mass_kg, system=sysm, accessories=sysm - r.engine_mass_kg,
                        frac=(sysm - r.engine_mass_kg) / r.engine_mass_kg))
acc = pd.DataFrame(acc)
acc_frac = acc.frac.mean()

# specific thrust / SFC of vendors vs the placeholder cycle
db["spec_thrust"] = db.max_thrust_N / db.mass_flow_kgps
pd.set_option("display.width", 200)
print(res.round(4).to_string(index=False))
print("\nAMT accessories:\n", acc.round(3).to_string(index=False), f"\nmean accessory fraction = {acc_frac:.3f} of engine mass")
print("\nvendor specific thrust [m/s] (airflow published):", db.dropna(subset=["mass_flow_kgps"])[["model", "spec_thrust", "pressure_ratio"]].round(0).to_string(index=False))
print(f"placeholder cycle (Phase 1/2): SLS specific thrust {F_Q / W_Q:.0f} m/s")

mfit = res.set_index("quantity")
env = dict(source="scripts/phase2_airframe/engine_database_fit.py (statistical, 26 engines)", F_SLS_N=F_Q,
           engine_mass_kg=float(mfit.loc["engine_mass_kg", "prediction"]),
           engine_mass_hi_kg=float(mfit.loc["engine_mass_kg", "hi_1sigma"]),
           accessory_frac=float(acc_frac),
           D_engine_m=float(mfit.loc["diameter_mm", "prediction"]) / 1000, D_engine_hi_m=float(mfit.loc["diameter_mm", "hi_1sigma"]) / 1000,
           L_engine_m=float(mfit.loc["length_mm", "prediction"]) / 1000)
res.to_csv(os.path.join(ROOT, "data", "phase2_engine_fit.csv"), index=False)
json.dump(env, open(os.path.join(ROOT, "data", "engine_envelope.json"), "w"), indent=1)
print("\nengine_envelope.json:", json.dumps(env, indent=1))

fig, ax = plt.subplots(1, 4, figsize=(16, 4))
xx = np.linspace(150, 1300, 60)
for a_, (col, lab) in zip(ax, [("engine_mass_kg", "dry mass [kg]"), ("diameter_mm", "diameter [mm]"), ("length_mm", "length [mm]"), ("mass_flow_kgps", "airflow [kg/s]")]):
    a_.scatter(db.max_thrust_N, db[col], c="k", s=14, zorder=3)
    for _, r in db.dropna(subset=[col]).iterrows():
        a_.annotate(r.model.split(" ")[0], (r.max_thrust_N, r[col]), fontsize=5.5, xytext=(2, 2), textcoords="offset points")
    a, b, s = fits[col]
    a_.plot(xx, a * xx ** b, "--", label=f"{a:.3g} F^{b:.2f}  (1-sigma {100*s:.0f} %)")
    a_.fill_between(xx, a * xx ** b * np.exp(-s), a * xx ** b * np.exp(s), alpha=.15)
    a_.axvline(F_Q, color="r", alpha=.5); a_.set_xlabel("max SLS thrust [N]"); a_.set_ylabel(lab); a_.grid(alpha=.3); a_.legend(fontsize=7)
fig.suptitle("Micro-turbojet database (26 engines, manufacturer data) with power-law fits; red = D1.1 engine derived SLS thrust 665 N", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase2_engine_database.png"), dpi=130)
print("saved")
