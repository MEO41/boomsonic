"""Phase 3R sensitivities of the recommended engine's dash thrust margin (run in .venv).
  * diameter: compressor-set OD calibrated to the AMT Nike (the one validation engine whose diameter the compressor
    sets: predicted 212 vs published 201 mm, x 0.946), bounded below by the combustor
  * fielded compressor efficiency 0.66 / 0.74 (mean combustor), with the impeller re-sized at each level
Usage: python cc_sensitivity.py <tag>     output data/phase3r_sensitivity_<tag>.csv
"""
import os, sys, json, copy, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import cc_trade as ct
at = ct.at
TAG = sys.argv[1]
d = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{TAG}.json"))); at.OPR = d["OPR"]; at.CAP = True
v = pd.read_csv(os.path.join(ROOT, "data", "phase3_mass_model_validation_3r.csv")); nike = v[v.model.str.contains("Nike")].iloc[0]
k_D = nike.D_pub / nike.D_pred
rows = []
L = d["levels"]["fielded"]; ev = copy.deepcopy(L["eval"]); ev["engine"] = copy.deepcopy(L["engine_cal"])
e = ev["engine"]; D0 = e["D_engine_mm"]
for lab, D in (("baseline", D0), (f"compressor OD x {k_D:.3f} (Nike)", max(e["D_breakdown"]["compressor"] * k_D, e["D_breakdown"]["combustor"], e["D_breakdown"]["turbine"]))):
    e["D_engine_mm"] = D; af = at.airframe(ev)
    rows.append(dict(case=lab, eta_c=0.70, D_mm=D, margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"], TOGW=af["TOGW_kg"]))
for ec in (0.66, 0.74):
    s, _ = ct.stress_for(d["case"], "fielded", eta_f=ec)
    ev2 = ct.evaluate3r(ct.with_blades(d["case"], s), "fielded", eta_f=ec, tag=TAG)
    if ev2.get("failed"):
        rows.append(dict(case=f"eta_c {ec}", eta_c=ec, note="not converged")); continue
    af = at.airframe(ct.calibrated(ev2, d["calibration"]))
    rows.append(dict(case=f"eta_c {ec}", eta_c=ec, D_mm=ev2["engine"]["D_engine_mm"], U2=s["U2_design"], t_root_mm=s["blade"]["t_root_mm"], stress_ok=s["ok"],
                     margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"], TOGW=af["TOGW_kg"]))
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", f"phase3r_sensitivity_{TAG}.csv"), index=False)
pd.set_option("display.width", 200); print(df.round(3).to_string(index=False))
