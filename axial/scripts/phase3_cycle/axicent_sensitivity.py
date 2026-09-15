"""Phase 3b robustness of the axial-centrifugal variants, same corners as efficiency_sensitivity.py:
overall fielded compressor efficiency 0.66 / 0.70 / 0.74 (eta_t 0.75), combustor mean and +1 sigma.
Also reports the fielded impeller tip speed and stress factor at each efficiency (same criterion as
the pure centrifugal: U2 ~ eta^-1/2 at fixed pressure ratio; Ti solid-disc stress vs 450 MPa).
Output: data/phase3_axicent_sensitivity.csv"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, HERE)
import arch_trade as at
rows = []
for tag, opr in (("ax68000_opr4_t1150_ax2_pa2_cap", 4.0), ("ax68000_opr5_t1150_ax2_pa2_cap", 5.0), ("ax68000_opr4_t1150_ax1_pa1.5_cap", 4.0)):
    at.OPR = opr
    case = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{tag}_tool.json")))["case"]
    c = case["comp"]
    for ec in (0.66, 0.70, 0.74):
        case["comp"]["eta_overall_fielded"] = ec
        ev = at.evaluate(case, "fielded")
        if ev is None:
            rows.append(dict(case=tag, eta_c=ec, note="cycle does not close")); continue
        # impeller stage efficiency scales with the overall one: U2 ~ sqrt(eta_cc_tool / eta_cc_f)
        U2 = c["U2"] * np.sqrt(c["eta_overall"] / ec); st = 3.3 / 8 * 4430 * U2 ** 2
        for comb in ("mean", "hi"):
            ev2 = dict(ev); ev2["engine"] = ev["engine"] if comb == "mean" else ev["engine_comb_hi"]
            af = at.airframe(ev2)
            rows.append(dict(case=tag, eta_c=ec, combustor=comb, W=ev["cycle"]["W_kgps"], D_mm=ev2["engine"]["D_engine_mm"],
                             dry_cal=1.24 * ev2["engine"]["dry_mass_kg"], L_cal=1.22 * ev2["engine"]["L_engine_mm"], U2=U2, stress_factor=450e6 / st,
                             margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"], TOGW_cal=af["TOGW_kg"] + 0.24 * ev2["engine"]["dry_mass_kg"]))
            print({k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in rows[-1].items()}, flush=True)
df = pd.DataFrame(rows); df.to_csv(os.path.join(AXROOT, "data", "phase3_axicent_sensitivity.csv"), index=False)
pd.set_option("display.width", 220); print(df.round(3).to_string(index=False))
