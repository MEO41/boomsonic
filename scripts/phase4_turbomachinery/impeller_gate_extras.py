"""Supplementary load cases for the impeller stress gate (impeller_stress_gate.py):
1. Thermal gradient in the hub/disc added to the centrifugal load. Metal temperature assumed equal to
   the local air total temperature: eye ~309 K (T0 at M 1.02 / 5 km: 255.7 K x (1 + 0.2 M^2)) to
   ~520 K at the impeller exit (Phase 3 fielded dash cycle). dT = 211 K x (r / r2)^n, n = 1 or 2
   (bounding shapes; axial gradient ignored). Ti-6Al-4V at ~250 C from the ATI Grade 5 data sheet
   charts: E ~14.2 Msi (98 GPa), mean CTE ~5.1e-6 /F (9.2e-6 /K). Thermal FE verified in
   verify_axisym_fe.py-style check (thin disc, parabolic T: centre and rim within 0.4 %).
2. Exducer blade-root stress vs backsweep angle beta2 and vs the radius where backsweep begins
   (sensitivity only; the aerodynamic consequence of changing beta2 is NOT evaluated here).
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import impeller_stress_gate as g
import axisym_fe as fe

T_EYE = 255.7 * (1 + 0.2 * 1.02 ** 2); T_EXIT = 520.0; DT = T_EXIT - T_EYE
E_HOT, ALPHA = 98e9, 9.2e-6

def hub_thermal(r_bore, t_rim, A, p, n):
    # re-run analyse_hub with the thermal field (E matters now)
    dT = lambda r, z: DT * np.clip(r / g.R2, 0, 1) ** n
    orig = fe.solve_rotating
    def patched(*a, **k):
        k.update(E=E_HOT, alpha=ALPHA, dT=dT); k.pop("dT", None); k["dT"] = dT
        return orig(*a, **k)
    fe.solve_rotating = patched
    try:
        return g.analyse_hub(r_bore, t_rim, A, p)
    finally:
        fe.solve_rotating = orig

if __name__ == "__main__":
    out = dict(T_eye_K=T_EYE, T_exit_K=T_EXIT, E_GPa=E_HOT / 1e9, alpha=ALPHA, thermal=[], blade_beta=[], blade_ri=[])
    for r_bore, t_rim, A, p in ((0.006, 0.003, 0.018, 2.0), (0.006, 0.003, 0.012, 2.0), (0.0, 0.003, 0.018, 2.0), (0.0, 0.003, 0.012, 2.0)):
        base = g.analyse_hub(r_bore, t_rim, A, p)
        row = dict(r_bore_mm=r_bore * 1e3, A_mm=A * 1e3, p=p, vm_mech=base["vm_peak_MPa"], burst_mech=base["burst_ratio"])
        for n in (1, 2):
            d = hub_thermal(r_bore, t_rim, A, p, n)
            row[f"vm_n{n}"] = d["vm_peak_MPa"]; row[f"st_bore_n{n}"] = d["st_bore_MPa"]; row[f"yieldMS_n{n}"] = d["yield_MS"]
            row[f"vm_loc_n{n}"] = (round(d["vm_peak_r_mm"], 1), round(d["vm_peak_z_mm"], 1))
        out["thermal"].append(row); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    for beta in (10.0, 20.0, 30.0, 40.0):
        for tr in (2.5e-3, 3.5e-3):
            b = g.plate_root(tr, beta2=beta)
            out["blade_beta"].append(dict(beta2=beta, t_root_mm=tr * 1e3, sig_Kt_MPa=b["sig_root_Kt"] / 1e6))
            print(out["blade_beta"][-1], flush=True)
    for ri in (0.5, 0.85):
        b = g.plate_root(3.5e-3, r_i_frac=ri)
        out["blade_ri"].append(dict(r_i_frac=ri, t_root_mm=3.5, sig_Kt_MPa=b["sig_root_Kt"] / 1e6)); print(out["blade_ri"][-1])
    json.dump(out, open(os.path.join(ROOT, "data", "phase4_impeller_gate_extras.json"), "w"), indent=1, default=float)
