"""Phase 3R screening of the single-stage centrifugal compressor (run in .venv; calls TurboFlow in .venv-np1).

For each OPR (dash cycle, Fn 500 N at M 1.02 / 5 km, T4 1150 K):
  1. dash cycle at the tool-level efficiency estimate (eta_c 0.79, eta_t 0.93) and at the fielded level (0.70 / 0.75)
  2. TurboFlow stage design (centrifugal_design.py, slip fixed) at the tool-level cycle for every spool speed x exit
     backsweep: 12 main + 12 splitter blades (Z_eff 18), effective exit width, 10 % choke margin, R4/R2 1.35
  3. the FIELDED impeller (the realistic case, A3.1): same pressure ratio at eta 0.70 needs more work, so
     U2_f = U2_tool sqrt(eta_TF / 0.70); r2_f = U2_f / omega; eye radius scaled with sqrt(W_f / W_tool) (as in the
     Phase 4 gate); effective exit width from continuity at the same phi2 (flow, radius, tip speed and exit density
     ratios); axial length 0.65 r2_f
  4. impeller_stress.evaluate on the fielded impeller at design speed: exducer root thickness sized for Fty at MCS
     (105 %), exit blockage -> physical exit width, boreless disc with thermal gradient, burst.
Output: data/phase3r/screen_<tag>.json per design, data/phase3r_cc_screen.csv
Usage: python cc_screen.py   (env CCS_OPR, CCS_RPM, CCS_BETA: comma lists)
"""
import os, sys, json, copy, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.environ.setdefault("P3_DATA", "phase3r")
sys.path.insert(0, HERE)
import arch_trade as at, dash_cycle as dc, impeller_stress as ist

OPRS = [float(v) for v in os.environ.get("CCS_OPR", "3.5,4.0,4.5").split(",")]
RPMS = [int(v) for v in os.environ.get("CCS_RPM", "75000,85000,95000").split(",")]
BETAS = [float(v) for v in os.environ.get("CCS_BETA", "0,-10,-20,-30").split(",")]
CC = dict(Z=12, Z_split=12, split_frac=0.5, effective_width=True, choke_margin=0.10, tip_clearance=0.25e-3, R4R2=1.35)
TOOL, FIELD = (0.79, 0.93), (0.70, 0.75)
G = 1.4; KX = G / (G - 1)

def fielded_scales(cc, cyc_t, cyc_f, PR, eta_f=0.70):
    """work-based fielded scaling of a centrifugal stage: exit radius with the tip speed the extra work needs (kU), exit
    width from continuity at the same phi2 (flow, radius, tip-speed and exit-density ratios), eye with sqrt(flow)."""
    eta = cc["turboflow"]["eta"]; kU = np.sqrt(eta / eta_f)
    Wr = cyc_f["W_kgps"] / cyc_t["W_kgps"]; tau = PR ** (1 / KX) - 1
    T02_ratio = (1 + tau / eta_f) / (1 + tau / eta)         # exit density falls with the extra work at equal PR
    return dict(kU=kU, kb=Wr / kU ** 2 * T02_ratio, ke=np.sqrt(Wr), Wr=Wr)

def fielded_impeller(cc, cyc_t, cyc_f, rpm, PR, eta_f=0.70):
    im = cc["geometry"]["impeller"]; k = fielded_scales(cc, cyc_t, cyc_f, PR, eta_f)
    U2f = cc["U2"] * k["kU"]; r2f = U2f / (rpm * np.pi / 30)
    return dict(U2=U2f, r2=r2f, b2_eff=im["width_out"] * k["kb"], r1s=im["radius_tip_in"] * k["ke"], r1h=im["radius_hub_in"] * k["ke"], L=0.65 * r2f)

def one(opr, rpm, beta, cyc_t, cyc_f):
    tag = f"scr_opr{opr:g}_{rpm // 1000}k_b{abs(beta):g}"
    try:
        cc = at.run_np1("centrifugal_design.py", dict(mdot=cyc_t["W_kgps"], T01=cyc_t["Tt2_K"], P01=cyc_t["Pt2_kPa"] * 1e3, PR=opr, rpm=rpm,
                                                      beta2b_deg=beta, **CC), tag)
    except Exception as e:
        return dict(OPR=opr, rpm=rpm, beta2b=beta, note=f"TurboFlow failed: {str(e)[-200:]}")
    tfr = cc["turboflow"]
    row = dict(OPR=opr, rpm=rpm, beta2b=beta, PR_TF=tfr["PR"], eta_TF=tfr["eta"], converged=tfr["success"], M1s_rel=cc["M1s_rel"],
               M_rel_in_TF=tfr["M_rel_in"], U2_tool=cc["U2"], D2_tool_mm=cc["D_impeller_mm"], D_diff_tool_mm=cc["D_diffuser_mm"],
               b2_r2_tool=cc["geometry"]["impeller"]["width_out"] / cc["r2"], ATR=cc["area_throat_ratio"],
               choke_margin_ok=(cc["choke_check"] or {}).get("unchoked_at_margin"), alpha2_deg=np.degrees(np.arctan2(cc["meanline"]["Ct2"], cc["meanline"]["Cm2"])))
    f = fielded_impeller(cc, cyc_t, cyc_f, rpm, opr)
    s = ist.evaluate(rpm, f["r2"], f["b2_eff"], f["r1s"], f["r1h"], f["L"], beta, cyc_f["Tt2_K"], cyc_f["Tt3_K"])
    row.update(U2_fielded=f["U2"], D2_fielded_mm=2e3 * f["r2"], D_diff_fielded_mm=2e3 * 1.35 * f["r2"] + 6.0,
               t_root_mm=s["blade"]["t_root_mm"], sigma_root_MCS=s["blade"]["sigma_root_MCS_MPa"], B2=s["blade"]["B2"], blade_ok=s["blade"]["ok"],
               b2_geo_r2=s["blade"]["b2_geo"] / f["r2"], inducer_MCS=s["inducer_root_MCS_MPa"],
               disc_vm_MCS=s["disc"]["vm_thermal_MCS_MPa"], disc_yield_MS=s["disc"]["yield_MS"], burst_MCS=s["disc"]["burst_ratio_MCS"],
               impeller_FE_mass_kg=s["disc"]["mass_kg"], stress_ok=s["ok"])
    json.dump(dict(row=row, cc=cc, fielded=f, stress=s), open(os.path.join(at.OUT, f"screen_{tag}.json"), "w"), indent=1, default=float)
    print({k: (round(v, 3) if isinstance(v, (float, np.floating)) else v) for k, v in row.items()}, flush=True)
    return row

if __name__ == "__main__":
    cycles = {}
    for opr in OPRS:
        at.OPR = opr
        ct, _ = dc.design(opr, 1150.0, *TOOL); cf, _ = dc.design(opr, 1150.0, *FIELD)
        cycles[opr] = (ct, cf)
        print(f"OPR {opr}: tool W {ct['W_kgps']:.3f} Tt3 {ct['Tt3_K']:.0f} | fielded W {cf['W_kgps']:.3f} Tt3 {cf['Tt3_K']:.0f}", flush=True)
    jobs = [(o, r, b) for o in OPRS for r in RPMS for b in BETAS]
    tf_rows = {}
    def tf_only(j):
        o, r, b = j; ct, cf = cycles[o]
        tag = f"scr_opr{o:g}_{r // 1000}k_b{abs(b):g}"
        try:
            return j, at.run_np1("centrifugal_design.py", dict(mdot=ct["W_kgps"], T01=ct["Tt2_K"], P01=ct["Pt2_kPa"] * 1e3, PR=o, rpm=r, beta2b_deg=b, **CC), tag)
        except Exception as e:
            return j, e
    with ThreadPoolExecutor(max_workers=12) as ex:
        for j, cc in ex.map(tf_only, jobs):
            tf_rows[j] = cc
    rows = []
    for j in jobs:                                           # stress runs serially (fast); TurboFlow results are cached on disk
        o, r, b = j; cc = tf_rows[j]
        if isinstance(cc, Exception):
            rows.append(dict(OPR=o, rpm=r, beta2b=b, note=f"TurboFlow failed: {str(cc)[-200:]}")); print(rows[-1], flush=True); continue
        at_run = at.run_np1
        at.run_np1 = lambda *a, _cc=cc, **k: _cc                # reuse the parallel result
        try: rows.append(one(o, r, b, *cycles[o]))
        finally: at.run_np1 = at_run
    df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase3r_cc_screen.csv"), index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
    cols = ["OPR", "rpm", "beta2b", "eta_TF", "PR_TF", "M1s_rel", "alpha2_deg", "U2_tool", "U2_fielded", "D_diff_fielded_mm", "t_root_mm", "B2",
            "sigma_root_MCS", "disc_vm_MCS", "burst_MCS", "stress_ok", "choke_margin_ok"]
    print(df[[c for c in cols if c in df.columns]].round(3).to_string(index=False))
