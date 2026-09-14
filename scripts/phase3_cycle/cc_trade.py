"""Phase 3R full-chain trade of single-stage centrifugal designs (run in .venv; calls TurboFlow in .venv-np1).

  python cc_trade.py run OPR:rpm:beta2b [OPR:rpm:beta2b ...]     one full evaluation per case (run cases in parallel)
  python cc_trade.py compile                                      summary table + plot from the per-case JSON files

Chain per case (unchanged Phase 3 method, arch_trade.py, with the Phase 3R compressor conventions):
  1. dash cycle <-> TurboFlow compressor (slip fixed, 12 + 12 splitters, effective width, 10 % choke margin, R4/R2 1.35)
     <-> TurboFlow turbine (same shaft speed, 350 MPa blade-root limit, tip capped at the engine envelope), iterated on
     the tool efficiencies ('tool' level); fielded level eta_c 0.70 / eta_t 0.75 with geometry scaled by sqrt(W) (A3.6)
  2. impeller stress-sized at each level (impeller_stress.py): exducer root thickness for Fty at MCS 105 %, blockage ->
     physical exit width and blade mass, boreless disc with thermal gradient, burst at MCS
  3. theta-scaled combustor (mean and +1 sigma), bottom-up engine mass x the Phase 3R calibration (P400 / Nike re-run
     with the slip fix, data/phase3_mass_model_validation_3r.csv), length x its calibration
  4. Phase 2 airframe drag at M 1.02 / 5 km with the calibrated engine diameter, length and mass; margin = Fn / drag - 1
     (nominal and pessimistic wave drag); TOGW
  5. worst corner (fielded): eta_c 0.66, combustor +1 sigma, pessimistic drag; impeller stress also re-sized there
Outputs: data/phase3r/cct_<tag>.json, data/phase3r_cc_trade.csv, plots/phase3r_cc_trade.png
"""
import os, sys, json, copy, glob, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.environ.setdefault("P3_DATA", "phase3r"); os.environ["P3_TURB_CAP"] = "1"
sys.path.insert(0, HERE)
import arch_trade as at, impeller_stress as ist, combustor_sizing as cs, engine_mass as em
from cc_screen import CC, fielded_impeller, fielded_scales

def calibration():
    v = pd.read_csv(os.path.join(ROOT, "data", "phase3_mass_model_validation_3r.csv"))
    km = v.m_pub / v.m_pred; kl = v.L_pub / v.L_pred
    return dict(K_M=float(km.mean()), K_M_lo=float(km.min()), K_M_hi=float(km.max()), K_L=float(kl.mean()))

def stress_for(case, level, eta_f=0.70):
    """size the impeller at this level; returns (stress result, geometry used)."""
    cc, rpm, beta = case["comp"], case["rpm"], case["cc_opts"]["beta2b_deg"]
    im = cc["geometry"]["impeller"]
    if level == "tool":
        geo = dict(U2=cc["U2"], r2=cc["r2"], b2_eff=im["width_out"], r1s=im["radius_tip_in"], r1h=im["radius_hub_in"], L=im["length_axial"])
        Te, Tx = case["cycle"]["Tt2_K"], case["cycle"]["Tt3_K"]
    else:
        cf, _ = at.dc.design(at.OPR, 1150.0, eta_f, at.FIELDED["eta_t"])
        geo = fielded_impeller(cc, case["cycle"], cf, rpm, at.OPR, eta_f)
        Te, Tx = cf["Tt2_K"], cf["Tt3_K"]
    s = ist.evaluate(rpm, geo["r2"], geo["b2_eff"], geo["r1s"], geo["r1h"], geo["L"], beta, Te, Tx)
    return s, geo

def scale_cc(comp, k):
    """fielded centrifugal geometry, work-based (replaces the Phase 3 sqrt(W) scaling A3.6 for the compressor): radii from
    the impeller exit outward and axial/meridional lengths x kU, exit and diffuser widths x kb, eye radii x ke."""
    c = copy.deepcopy(comp); im = c["geometry"]["impeller"]
    im["radius_out"] *= k["kU"]; im["width_out"] *= k["kb"]; im["length_axial"] *= k["kU"]; im["length_meridional"] *= k["kU"]
    im["radius_tip_in"] *= k["ke"]; im["radius_hub_in"] *= k["ke"]
    for sec in ("vaneless_diffuser", "vaned_diffuser"):
        g = c["geometry"][sec]
        for key in list(g):
            if key.startswith("radius") or key == "opening": g[key] *= k["kU"]
            elif key.startswith("width"): g[key] *= k["kb"]
    return c

def fielded_turbine(cyc, comp, rpm, tag):
    """TurboFlow turbine designed AT the fielded cycle (same speed, 350 MPa blade-root limit, envelope cap). Replaces the
    sqrt(W) scaling of the tool-level turbine, which pushed the tip ~11 % past its stress limit (found in Phase 3R).
    Cached: re-used when the input is unchanged."""
    tin = dict(T04=cyc["Tt4_K"], P04=cyc["Pt4_kPa"] * 1e3, p_out=at.turb_pout(cyc), rpm=rpm, mdot=cyc["W_kgps"] + cyc["Wf_kgps"] * at.dc.ETA_B,
               tip_clearance=0.30e-3, r_tip_cap=at.envelope_cap("centrifugal", comp, cyc))
    fo = os.path.join(at.OUT, f"{tag}_out.json")
    if os.path.exists(fo):
        old = json.load(open(fo))
        if all(abs(old["input"].get(k, np.nan) - v) <= 1e-6 * max(1.0, abs(v)) for k, v in tin.items()):
            return old
    return at.run_np1("turbine_design.py", tin, tag)

def evaluate3r(case, level, eta_f=0.70, tag=None):
    """arch_trade.evaluate with the work-based fielded compressor geometry and a turbine re-designed at the fielded cycle."""
    if level == "tool":
        return at.evaluate(case, "tool")
    cyc, _ = at.dc.design(at.OPR, 1150.0, eta_f, at.FIELDED["eta_t"])
    if cyc["res"] > 1e-3 or abs(cyc["Fn_N"] - 500.0) > 1.0 or not np.isfinite(cyc["TSFC_kgpNh"]):
        return dict(failed=True, res=cyc["res"], Fn_N=cyc["Fn_N"])
    k = fielded_scales(case["comp"], case["cycle"], cyc, at.OPR, eta_f)
    comp = scale_cc(case["comp"], k)
    turb = fielded_turbine(cyc, comp, case["rpm"], f"{tag}_ttf{int(round(eta_f * 100))}")
    comb_all, _ = cs.combustor(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], cyc["W_kgps"])
    e = em.engine(cyc, "centrifugal", comp, turb, comb_all["mean"], case["rpm"])
    e_hi = em.engine(cyc, "centrifugal", comp, turb, comb_all["hi"], case["rpm"])
    return dict(level=level, eta_c=eta_f, eta_t=at.FIELDED["eta_t"], cycle=cyc, engine=e, engine_comb_hi=e_hi, combustor=comb_all, scales=k,
                turbine=dict(eta_tt_tool=turb["overall"]["efficiency_tt"] / 100, r_tip_mm=turb["r_tip_max"] * 1e3, r_tip_stress_limit_mm=turb["r_tip_stress_limit"] * 1e3,
                             r_tip_cap_mm=turb["r_tip_limit"] * 1e3, success=turb["success"]))

def with_blades(case, s):
    c = copy.deepcopy(case)
    c["comp"]["Z_eff"] = c["comp"]["geometry"]["impeller"]["number_of_blades"]
    c["comp"]["t_blade_mean"] = s["blade"]["t_mean_mm"] / 1e3
    c["comp"]["b2_geo_ratio"] = 1.0 / (1.0 - s["blade"]["B2"])
    return c

def calibrated(ev, cal, comb="mean"):
    e = copy.deepcopy(ev["engine"] if comb == "mean" else ev["engine_comb_hi"])
    e["dry_mass_raw_kg"] = e["dry_mass_kg"]; e["L_raw_mm"] = e["L_engine_mm"]
    e["dry_mass_kg"] *= cal["K_M"]; e["L_engine_mm"] *= cal["K_L"]
    ev2 = dict(ev); ev2["engine"] = e
    return ev2

def run_case(spec):
    opr, rpm, beta = float(spec.split(":")[0]), int(spec.split(":")[1]), float(spec.split(":")[2])
    at.OPR = opr; at.CAP = True
    tag = f"ce{rpm}_opr{opr:g}_t1150_b{abs(beta):g}_cap"
    case = at.design_case("centrifugal", rpm, tag, cc_opts=dict(CC, beta2b_deg=beta))
    evaluate_all(case, tag, opr, rpm, beta)

def evaluate_all(case, tag, opr, rpm, beta):
    at.OPR = opr; at.CAP = True; cal = calibration()
    out = dict(tag=tag, OPR=opr, rpm=rpm, beta2b=beta, calibration=cal, case=case, levels={})
    for level in ("tool", "fielded"):
        s, geo = stress_for(case, level)
        ev = evaluate3r(with_blades(case, s), level, tag=tag)
        if ev is None or ev.get("failed"):
            out["levels"][level] = dict(note="cycle not converged", detail=ev); continue
        evc = calibrated(ev, cal); af = at.airframe(evc)
        evh = calibrated(ev, cal, "hi"); afh = at.airframe(evh)
        out["levels"][level] = dict(stress=s, stress_geo=geo, eval=ev, engine_cal=evc["engine"], airframe=af, airframe_comb_hi=afh)
    # worst corner: fielded eta_c 0.66, combustor +1 sigma, pessimistic drag; impeller re-sized at the higher tip speed
    s66, geo66 = stress_for(case, "fielded", eta_f=0.66)
    ev66 = evaluate3r(with_blades(case, s66), "fielded", eta_f=0.66, tag=tag)
    if ev66.get("failed"):
        out["worst_corner"] = dict(note="pyCycle design did not converge at eta_c 0.66", detail=ev66, stress=s66)
    else:
        afw = at.airframe(calibrated(ev66, cal, "hi"))
        out["worst_corner"] = dict(stress=s66, margin_hi=afw["dash"]["hi"]["margin"], D_mm=ev66["engine_comb_hi"]["D_engine_mm"], TOGW=afw["TOGW_kg"])
    json.dump(out, open(os.path.join(at.OUT, f"cct_{tag}.json"), "w"), indent=1, default=float)
    f = out["levels"].get("fielded", {})
    if "airframe" in f:
        print(f"{tag}: fielded D {f['engine_cal']['D_engine_mm']:.0f} mm, m {f['engine_cal']['dry_mass_kg']:.2f} kg, margin "
              f"{100*f['airframe']['dash']['nom']['margin']:+.0f} / {100*f['airframe']['dash']['hi']['margin']:+.0f} %, worst "
              f"{100*out.get('worst_corner', {}).get('margin_hi', np.nan):+.0f} %, stress ok {f['stress']['ok']}", flush=True)

def compile_():
    rows = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "data", "phase3r", "cct_*.json"))):
        d = json.load(open(fn))
        for level, L in d["levels"].items():
            if "eval" not in L: continue
            ev, e, af, afh, s = L["eval"], L["engine_cal"], L["airframe"], L["airframe_comb_hi"], L["stress"]
            cyc = ev["cycle"]; im = d["case"]["comp"]
            rows.append(dict(tag=d["tag"], OPR=d["OPR"], rpm=d["rpm"], beta2b=d["beta2b"], level=level, eta_c=ev["eta_c"], eta_t=ev["eta_t"],
                             eta_c_tool=d["case"]["eta_c"], eta_t_tool=d["case"]["eta_t"], W=cyc["W_kgps"], TSFC_dash=cyc["TSFC_kgpNh"], Wf_dash=cyc["Wf_kgps"],
                             Tt3=cyc["Tt3_K"], U2=s["U2_design"], t_root_mm=s["blade"]["t_root_mm"], B2=s["blade"]["B2"], sigma_root_MCS=s["blade"]["sigma_root_MCS_MPa"],
                             disc_vm_MCS=s["disc"]["vm_thermal_MCS_MPa"], burst_MCS=s["disc"]["burst_ratio_MCS"], stress_ok=s["ok"],
                             M1s_rel=im["M1s_rel"], D_engine_mm=e["D_engine_mm"], D_comp=e["D_breakdown"]["compressor"], D_comb=e["D_breakdown"]["combustor"],
                             D_turb=e["D_breakdown"]["turbine"], D_comb_hi_engine=L["eval"]["engine_comb_hi"]["D_engine_mm"],
                             L_cal_mm=e["L_engine_mm"], dry_raw=e["dry_mass_raw_kg"], dry_cal=e["dry_mass_kg"],
                             dry_cal_lo=e["dry_mass_raw_kg"] * d["calibration"]["K_M_lo"], dry_cal_hi=e["dry_mass_raw_kg"] * d["calibration"]["K_M_hi"],
                             CDS_nom=af["dash"]["nom"]["CDS_cm2"], CDS_hi=af["dash"]["hi"]["CDS_cm2"], drag_nom=af["dash"]["nom"]["drag_N"], drag_hi=af["dash"]["hi"]["drag_N"],
                             margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"], margin_hi_comb_hi=afh["dash"]["hi"]["margin"],
                             worst_corner=d.get("worst_corner", {}).get("margin_hi", np.nan) if level == "fielded" else np.nan,
                             worst_stress_ok=d.get("worst_corner", {}).get("stress", {}).get("ok", None) if level == "fielded" else None,
                             TOGW=af["TOGW_kg"], fuel=af["fuel_kg"], turb_rtip_mm=L["eval"]["engine"]["turb_geo"]["r_tip"] * 1e3,
                             turb_rtip_stress_limit_mm=(L["eval"].get("turbine") or {}).get("r_tip_stress_limit_mm", d["case"]["turb"]["r_tip_stress_limit"] * 1e3),
                             turb_eta_tool_at_fielded_flow=(L["eval"].get("turbine") or {}).get("eta_tt_tool", np.nan)))
    df = pd.DataFrame(rows).sort_values(["level", "OPR", "rpm", "beta2b"])
    # trailing-edge blockage dump loss (TurboFlow sees no blade thickness): sudden expansion of the meridional velocity
    # from Cm2 / (1 - B2) to Cm2 behind the blades (Borda-Carnot), dh = 0.5 Cm2^2 (B2 / (1 - B2))^2, Cm2 = phi2 U2,
    # as a fraction of the stage work at the level's efficiency -> efficiency debit (reported, not fed back)
    work = 1004.5 * 309.0 * (df.OPR ** (0.4 / 1.4) - 1) / df.eta_c
    df["dEta_TE_pts"] = 100 * 0.5 * (0.28 * df.U2) ** 2 * (df.B2 / (1 - df.B2)) ** 2 / work    # d(eta) = dh_loss / actual work
    df.to_csv(os.path.join(ROOT, "data", "phase3r_cc_trade.csv"), index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 50)
    cols = ["tag", "level", "eta_c", "eta_t", "W", "TSFC_dash", "U2", "t_root_mm", "B2", "dEta_TE_pts", "stress_ok", "D_engine_mm", "D_comp", "D_comb", "L_cal_mm", "dry_cal",
            "drag_nom", "drag_hi", "margin_nom", "margin_hi", "worst_corner", "TOGW"]
    print(df[cols].round(3).to_string(index=False))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    f = df[df.level == "fielded"]
    fig, ax = plt.subplots(1, 4, figsize=(18, 4.8))
    for a, (col, lab) in zip(ax, [("D_engine_mm", "engine OD [mm]"), ("dry_cal", "engine dry mass, calibrated [kg]"),
                                  ("margin_hi", "dash margin, pessimistic drag [%]"), ("worst_corner", "worst corner margin [%]")]):
        x = np.arange(len(f)); y = f[col] * (100 if "margin" in col or "worst" in col else 1)
        a.bar(x, y, color=["tab:green" if ok else "tab:grey" for ok in f.stress_ok], alpha=.85)
        if col == "dry_cal":
            a.errorbar(x, f[col], yerr=[f[col] - f.dry_cal_lo, f.dry_cal_hi - f[col]], fmt="none", ecolor="k", capsize=2)
        if "margin" in col or "worst" in col: a.axhline(25, c="k", ls="--", lw=1)
        a.set_xticks(x); a.set_xticklabels([f"OPR {r.OPR:g}, {r.rpm/1000:g}k, {abs(r.beta2b):g}°" for r in f.itertuples()], fontsize=7, rotation=60, ha="right")
        a.set_ylabel(lab); a.grid(alpha=.3, axis="y")
    fig.suptitle("Phase 3R single-stage centrifugal trade, fielded level (Fn 500 N at M 1.02 / 5 km, T4 1150 K); green = impeller stress-feasible", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase3r_cc_trade.png"), dpi=130)

if __name__ == "__main__":
    if sys.argv[1] == "run":
        for spec in sys.argv[2:]: run_case(spec)
    elif sys.argv[1] == "reeval":                      # re-evaluate saved designs (no TurboFlow re-design)
        files = sys.argv[2:] or sorted(glob.glob(os.path.join(ROOT, "data", "phase3r", "cct_*.json")))
        for fn in files:
            d = json.load(open(fn)); evaluate_all(d["case"], d["tag"], d["OPR"], d["rpm"], d["beta2b"])
            f = json.load(open(fn))["levels"].get("fielded", {})
            if "airframe" in f:
                print(f"{d['tag']}: fielded D {f['engine_cal']['D_engine_mm']:.0f} mm, margin {100*f['airframe']['dash']['nom']['margin']:+.0f} / "
                      f"{100*f['airframe']['dash']['hi']['margin']:+.0f} %", flush=True)
    else:
        compile_()
