"""Phase 3 robustness check: both finalists at EQUAL fielded compressor efficiency (0.66 / 0.70 / 0.74,
eta_t 0.75), and with the +1 sigma combustor size. Answers: does the axial's margin advantage survive
if its compressor is no better than the centrifugal's? Output: data/phase3_efficiency_sensitivity.csv"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import arch_trade as at
rows = []
CASES = [(c.split(":")[0], float(c.split(":")[1])) for c in os.environ["P3_SENS_CASES"].split(",")] if "P3_SENS_CASES" in os.environ     else (("ce85000_opr4_t1150", 4.0), ("ax0_opr5_t1150_cap", 5.0))
for tag, opr in CASES:
    at.OPR = opr
    case = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{tag}_tool.json")))["case"]
    for ec in (0.66, 0.70, 0.74):
        at.FIELDED["eta_c_centrifugal"] = ec
        case["eta_c_centrifugal_ref"] = case["eta_c"] * 0.70 / ec if case["kind"] == "axial" else 0.794
        if case["kind"] == "axial":  # evaluate() applies eta_axial = eta_tool * FIELDED / ref -> force eta_axial = ec
            case["eta_c_centrifugal_ref"] = case["eta_c"] * ec / ec; at.FIELDED["eta_c_centrifugal"] = ec
            case["eta_c_centrifugal_ref"] = case["eta_c"]
        ev = at.evaluate(case, "fielded")
        if ev is None:
            rows.append(dict(case=tag, eta_c=ec, note="cycle does not close")); continue
        for comb in ("mean", "hi"):
            ev2 = dict(ev); ev2["engine"] = ev["engine"] if comb == "mean" else ev["engine_comb_hi"]
            af = at.airframe(ev2)
            rows.append(dict(case=tag, eta_c=ev["eta_c"], combustor=comb, W=ev["cycle"]["W_kgps"], D_mm=ev2["engine"]["D_engine_mm"],
                             dry_raw=ev2["engine"]["dry_mass_kg"], dry_cal=1.24 * ev2["engine"]["dry_mass_kg"], L_cal=1.22 * ev2["engine"]["L_engine_mm"],
                             margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"],
                             TOGW_cal=af["TOGW_kg"] + 0.24 * ev2["engine"]["dry_mass_kg"]))
            print({k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in rows[-1].items()}, flush=True)
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", f"phase3_efficiency_sensitivity{os.environ.get('P3_OUT_SUFFIX', '')}.csv"), index=False)
pd.set_option("display.width", 200); print(df.round(3).to_string(index=False))
