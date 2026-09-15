"""Phase 3b axial-centrifugal compressor: n_ax axial stages (TurboDesigner geometry + Howell loss model,
same method and SAME CAVEAT as the pure axial: textbook loss system, verified only at conventional
scale, no micro-scale validation) feeding one centrifugal stage (TurboFlow, same settings as the
pure centrifugal: Oh losses, Wiesner slip, beta2b -30 deg, Z 12, tip clearance 0.25 mm, R4/R2 1.35).
Single spool: both run at the same rpm. The last axial stator is assumed to return the flow to
axial (alpha_in = 0 at the impeller eye); the transition duct between axial exit and impeller eye
is not loss-modelled (noted as a limitation, Phase 4).

Impeller stress, same criterion as the pure centrifugal: solid-disc peak (3+nu)/8 rho U2^2 in
Ti-6Al-4V vs 450 MPa. Fielded tip speed: the fielded stage needs more work for the same pressure
ratio -> U2_fielded = U2_tool * sqrt((T0_eye,f / T0_eye,t) * (eta_cc,tool / eta_cc,fielded)) with
eta_fielded = eta_tool * 0.882 (the Phase 3 ratio 0.70 / 0.794) for every stage.

Usage (screening):  python axicent_design.py screen <W> <T01> <P01> <tag>
"""
import os, sys, json, subprocess, itertools, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# shared module (arch_trade.py imports it), but the __main__ screen below is axial-centrifugal: its results live under axial/
AXROOT = os.path.join(ROOT, "axial")
sys.path.insert(0, HERE)
import axial_design as ad
NP1 = os.path.join(ROOT, ".venv-np1", "Scripts", "python.exe")
G, CP = 1.4, 1004.5
K_F = 0.70 / 0.794
SIG_TI, RHO_TI = 450e6, 4430.0

def best_axial_stages(W, T01, P01, pi_a, n_ax, rpm):
    best = None
    for ht in (0.40, 0.45, 0.50, 0.55, 0.60):
        for Cx in (160, 170, 185, 200):
            p = dict(mdot=W, T01=T01, P01=P01, PR=pi_a, rpm=rpm, N=n_ax, hub_tip=ht, Cx=Cx, clearance=0.25e-3)
            try:
                eta = 0.85
                for _ in range(12):
                    r = ad.evaluate(p, eta)
                    if abs(r["eta_is"] - eta) < 5e-4: break
                    eta = 0.5 * eta + 0.5 * r["eta_is"]
            except Exception:
                continue
            st = r["stages"]
            ok = (max(s["DF_rotor"] for s in st) <= 0.5 and min(s["deHaller_r"] for s in st) >= 0.72 and st[0]["M_rel_tip"] <= 1.35
                  and st[-1]["stator"]["h"] >= 0.010 and np.isfinite(r["eta_is"]))
            if ok and (best is None or r["eta_is"] > best[1]["eta_is"]):
                best = (p, r)
    if best is None: return None
    p, r = best
    r.update(input=p, D_casing_mm=2e3 * (r["r_tip_max"] + 0.25e-3 + 0.0025))
    T0a = T01 * (1 + (pi_a ** ((G - 1) / G) - 1) / r["eta_is"])
    return r, T0a, P01 * pi_a

def run_cc(W, T0, P0, PR, rpm, tag):
    fi = os.path.join(ROOT, "data", "phase3", f"{tag}_in.json"); fo = fi.replace("_in.json", "_out.json")
    json.dump(dict(mdot=W, T01=T0, P01=P0, PR=PR, rpm=rpm, beta2b_deg=-30, Z=12, tip_clearance=0.25e-3, R4R2=1.35), open(fi, "w"))
    r = subprocess.run([NP1, os.path.join(HERE, "centrifugal_design.py"), fi, fo], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(r.stderr[-600:])
    return json.load(open(fo))

def design(W, T01, P01, OPR, n_ax, pi_a, rpm, tag):
    a = best_axial_stages(W, T01, P01, pi_a, n_ax, rpm)
    if a is None: return None
    ax, T0a, P0a = a
    pi_c = OPR / pi_a
    cc = run_cc(W, T0a, P0a, pi_c, rpm, tag)
    eta_cc = cc["turboflow"]["eta"]
    T03 = T0a * (1 + (pi_c ** ((G - 1) / G) - 1) / eta_cc)
    eta_ov = (OPR ** ((G - 1) / G) - 1) / (T03 / T01 - 1)
    # fielded: every stage debited by K_F
    eta_ax_f, eta_cc_f = ax["eta_is"] * K_F, eta_cc * K_F
    T0a_f = T01 * (1 + (pi_a ** ((G - 1) / G) - 1) / eta_ax_f)
    T03_f = T0a_f * (1 + (pi_c ** ((G - 1) / G) - 1) / eta_cc_f)
    eta_ov_f = (OPR ** ((G - 1) / G) - 1) / (T03_f / T01 - 1)
    U2 = cc["U2"]; U2_f = U2 * np.sqrt((T0a_f / T0a) * (eta_cc / eta_cc_f))
    s = lambda U: (3 + 0.3) / 8 * RHO_TI * U ** 2
    return dict(n_ax=n_ax, pi_a=pi_a, pi_c=pi_c, OPR=OPR, rpm=rpm, eta_ax=ax["eta_is"], eta_cc=eta_cc, eta_overall=eta_ov,
                eta_overall_fielded=eta_ov_f, T0_eye=T0a, U2=U2, U2_fielded=U2_f, stress_MPa=s(U2) / 1e6, stress_fielded_MPa=s(U2_f) / 1e6,
                stress_factor=SIG_TI / s(U2), stress_factor_fielded=SIG_TI / s(U2_f), M1s_rel=cc["M1s_rel"], choked=cc["turboflow"]["choked"],
                D_axial_mm=ax["D_casing_mm"], D_diffuser_mm=cc["D_diffuser_mm"] + 6.0, D2_mm=cc["D_impeller_mm"], M_rel_tip_axial=ax["stages"][0]["M_rel_tip"],
                L_axial_mm=1e3 * ax["length"], ax_hub_tip=ax["input"]["hub_tip"], ax_Cx=ax["input"]["Cx"], axial=ax, centrifugal=cc)

if __name__ == "__main__" and sys.argv[1] == "screen":
    W, T01, P01 = (float(v) for v in sys.argv[2:5]); tag = sys.argv[5]
    rows = []
    splits = {1: (1.3, 1.4, 1.5), 2: (1.6, 1.8, 2.0)}
    NAX = tuple(int(v) for v in (sys.argv[6].split(",") if len(sys.argv) > 6 else ("1", "2")))
    for n_ax, OPR, rpm in itertools.product(NAX, (4.0, 4.5, 5.0), (65000, 75000, 85000)):
        for pi_a in splits[n_ax]:
            d = design(W, T01, P01, OPR, n_ax, pi_a, rpm, f"acs_{tag}_{n_ax}_{OPR:g}_{rpm}_{pi_a:g}")
            if d is None:
                rows.append(dict(n_ax=n_ax, pi_a=pi_a, OPR=OPR, rpm=rpm, note="no feasible axial stage(s)")); print(rows[-1], flush=True); continue
            rows.append({k: v for k, v in d.items() if k not in ("axial", "centrifugal")}); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
    json.dump(rows, open(os.path.join(ROOT, "data", "phase3", f"axicent_screen_{tag}.json"), "w"), indent=1, default=float)
    import pandas as pd
    df = pd.DataFrame(rows); df.to_csv(os.path.join(AXROOT, "data", f"phase3_axicent_screen_{tag}.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(df.round(3).to_string(index=False))
