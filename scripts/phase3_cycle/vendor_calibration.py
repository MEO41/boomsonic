"""Phase 3: what component efficiencies do real engines of this class achieve?

For each database engine with manufacturer-published airflow W, pressure ratio PR, max SLS
thrust Fn and max fuel flow Wf (data/microturbojet_database.csv), solve the pyCycle design
point (SLS, W and PR fixed) for the two unknowns (T4, eta_t) that reproduce BOTH Fn and Wf,
at assumed compressor efficiencies eta_c = 0.70 / 0.74 / 0.78 and combustion efficiency
eta_b = 0.95 (sensitivity 0.90). Output: data/phase3_vendor_calibration.csv
Fuel: ml/min converted with Jet-A density 0.80 kg/L; g/min used as published.
This uses catalog data to CALIBRATE EFFICIENCY LEVELS, not to look up engine mass.
"""
import os, re, sys, numpy as np, pandas as pd
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cycle_model as cm

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
db = pd.read_csv(os.path.join(ROOT, "data", "microturbojet_database.csv"))

def fuel_kgps(s):
    s = str(s)
    m = re.search(r"([\d.]+)\s*g/min", s)
    if m: return float(m.group(1)) / 1000 / 60
    m = re.search(r"([\d.]+)\s*ml/min", s)
    if m: return float(m.group(1)) * 0.80 / 1000 / 60
    return np.nan

db["Wf_kgps"] = db.fuel_consumption_at_max.map(fuel_kgps)
eng = db.dropna(subset=["mass_flow_kgps", "pressure_ratio", "Wf_kgps"])
prob, mp = cm.build(design_W='fixed')
rows = []
for _, e in eng.iterrows():
    for eta_c in (0.70, 0.74, 0.78):
        for eta_b in (0.95, 0.90):
            def resid(x):
                T4, eta_t = x
                cm.set_design(prob, 0.0, 0.0, e.pressure_ratio, T4, eta_c, eta_t, W_kgps=e.mass_flow_kgps,
                              burner_dPqP=0.05, duct_dPqP=0.0, ram_recovery=1.0, Cv=0.98)
                prob.run_model()
                d = cm.read(prob, 'DESIGN', eta_b=eta_b)
                resid.d = d
                return [(d["Fn_N"] - e.max_thrust_N) / e.max_thrust_N, (d["Wf_kgps"] - e.Wf_kgps) / e.Wf_kgps]
            try:
                sol = least_squares(resid, x0=[1100.0, 0.80], bounds=([800, 0.5], [1600, 0.98]), x_scale=[100, 0.05], diff_step=[1e-3, 1e-3])
                d = resid.d; ok = np.max(np.abs(sol.fun)) < 2e-3
            except Exception as ex:
                sol = None; d = {}; ok = False
            rows.append(dict(model=e.model, F_N=e.max_thrust_N, W=e.mass_flow_kgps, PR=e.pressure_ratio, Wf_gps=e.Wf_kgps * 1000,
                             EGT_max_C=e.EGT_max_C, eta_c=eta_c, eta_b=eta_b, T4_K=sol.x[0] if sol is not None else np.nan,
                             eta_t=sol.x[1] if sol is not None else np.nan, T5_K=d.get("Tt5_K", np.nan),
                             TSFC=d.get("TSFC_kgpNh", np.nan), spec_thrust=e.max_thrust_N / e.mass_flow_kgps, matched=ok))
            print(rows[-1])
out = pd.DataFrame(rows)
out.to_csv(os.path.join(ROOT, "data", "phase3_vendor_calibration.csv"), index=False)
pd.set_option("display.width", 200)
print(out.round(3).to_string(index=False))
