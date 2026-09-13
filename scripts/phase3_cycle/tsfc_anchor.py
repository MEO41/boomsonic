"""Phase 3: anchor the cycle 'technology level' on the one robust vendor observable, SLS TSFC.

Vendor (W, PR, Fn, Wf) sets are mutually inconsistent with the published EGT limits
(vendor_calibration.py: matching all four needs T4 1330-1450 K, T5 1180-1300 K vs EGT limits
1023-1148 K), so published airflow is treated as nominal. Thrust and fuel flow are measured
on the vendors' test stands, so SLS TSFC is robust: 0.145-0.167 kg/(N h) for P220..Nike.
Here: SLS, PR 3.8, T4 = 1150 / 1250 K, grid of (eta_c, eta_t), eta_b 0.95 and 0.90 ->
TSFC and specific thrust. Output: data/phase3_tsfc_anchor.csv
"""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cycle_model as cm
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
prob, mp = cm.build(design_W='fixed')
rows = []
for T4 in (1150.0, 1250.0):
    for ec in (0.66, 0.70, 0.74, 0.78):
        for et in (0.70, 0.75, 0.80, 0.85):
            cm.set_design(prob, 0.0, 0.0, 3.8, T4, ec, et, W_kgps=1.0)
            prob.run_model(); d = cm.read(prob, 'DESIGN', eta_b=1.0)
            for eb in (0.95, 0.90):
                rows.append(dict(T4_K=T4, eta_c=ec, eta_t=et, eta_b=eb, TSFC=d["TSFC_kgpNh"] / eb, spec_thrust=d["Fn_N"] / d["W_kgps"],
                                 T5_K=d["Tt5_K"], ok=d["res"] < 1e-4))
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase3_tsfc_anchor.csv"), index=False)
pd.set_option("display.width", 200)
for (T4, eb), g in df.groupby(["T4_K", "eta_b"]):
    print(f"\nT4 = {T4:.0f} K, eta_b = {eb}: TSFC [kg/N/h]  (rows eta_c, cols eta_t)")
    print(g.pivot_table(index="eta_c", columns="eta_t", values="TSFC").round(3).to_string())
    print("   specific thrust [m/s]:"); print(g.pivot_table(index="eta_c", columns="eta_t", values="spec_thrust").round(0).to_string())
print("\nvendor measured TSFC band 0.145-0.167 (P220, P300, P400, Olympus, Titan, Nike)")
