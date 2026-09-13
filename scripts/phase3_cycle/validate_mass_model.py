"""Phase 3 validation of the centrifugal design chain + bottom-up mass model against two real engines
that bracket our airflow: JetCat P400-PRO-LN (0.67 kg/s, PR 3.8, 98 000 rpm, 425 N, 148.4 mm,
390 mm, 4.01 kg incl. integrated ECU/pump) and AMT Nike (1.25 kg/s, PR 4.0, 61 500 rpm, 784 N,
201 mm, 524 mm, 9.15 kg engine only). Manufacturer data from data/microturbojet_database.csv.

Process identical to the trade: SLS cycle at fielded efficiencies (eta_c 0.70, eta_t 0.75, eta_b
0.95) with the published W and PR and T4 solved to give the published thrust; TurboFlow
centrifugal stage at the published rpm; TurboFlow stress-limited turbine at the published rpm;
theta-scaled combustor; engine_mass.engine(). Note: the combustor theta is calibrated on the
same reference set (includes both engines), so the DIAMETER check is not independent where the
combustor sets the diameter; the MASS and LENGTH checks are.
"""
import os, sys, json, numpy as np, pandas as pd
from scipy.optimize import brentq
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import cycle_model as cm, combustor_sizing as cs, engine_mass as em
from arch_trade import run_np1

REFS = [dict(model="JetCat P400-PRO-LN", W=0.67, PR=3.8, rpm=98000, F=425.0, D=148.4, L=390.0, m=4.01, note="incl. integrated ECU/pump"),
        dict(model="AMT Nike", W=1.25, PR=4.0, rpm=61500, F=784.0, D=201.0, L=524.0, m=9.15, note="engine only")]
prob, _ = cm.build(design_W='fixed')
rows = []
for r in REFS:
    def fnres(T4):
        cm.set_design(prob, 0.0, 0.0, r["PR"], T4, 0.70, 0.75, W_kgps=r["W"]); prob.run_model()
        return cm.read(prob, 'DESIGN', eta_b=0.95)["Fn_N"] - r["F"]
    try:
        T4 = brentq(fnres, 900, 1700, xtol=0.5)
    except ValueError:
        T4 = 1600.0
    fnres(T4); cyc = cm.read(prob, 'DESIGN', eta_b=0.95)
    tag = "val_" + r["model"].split()[1]
    comp = run_np1("centrifugal_design.py", dict(mdot=r["W"], T01=288.15, P01=101325.0, PR=r["PR"], rpm=r["rpm"], beta2b_deg=-30, Z=12,
                                                 tip_clearance=0.25e-3, R4R2=1.35), tag + "_cc")
    g = cyc.get("t_out_gamma", 1.325)
    turb = run_np1("turbine_design.py", dict(T04=cyc["Tt4_K"], P04=cyc["Pt4_kPa"] * 1e3, p_out=cyc["Pt5_kPa"] * 1e3 / (1 + 0.5 * (g - 1) * 0.2025) ** (g / (g - 1)),
                                              rpm=r["rpm"], mdot=r["W"] + cyc["Wf_kgps"] * 0.95, tip_clearance=0.30e-3), tag + "_tt")
    comb, _ = cs.combustor(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], r["W"])
    e = em.engine(cyc, "centrifugal", comp, turb, comb["mean"], r["rpm"])
    rows.append(dict(model=r["model"], T4_for_thrust=T4, D_pred=e["D_engine_mm"], D_pub=r["D"], D_comp=e["D_breakdown"]["compressor"],
                     D_comb=e["D_breakdown"]["combustor"], D_turb=e["D_breakdown"]["turbine"], L_pred=e["L_engine_mm"], L_pub=r["L"],
                     m_pred=e["dry_mass_kg"], m_pub=r["m"], m_err_pct=100 * (e["dry_mass_kg"] / r["m"] - 1), note=r["note"],
                     eta_c_tool=comp["turboflow"]["eta"], eta_t_tool=turb["overall"]["efficiency_tt"] / 100))
    print(rows[-1], flush=True)
    json.dump(dict(ref=r, cycle=cyc, engine=e), open(os.path.join(ROOT, "data", "phase3", f"{tag}_engine.json"), "w"), indent=1, default=float)
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase3_mass_model_validation.csv"), index=False)
pd.set_option("display.width", 220); print(df.round(3).to_string(index=False))
