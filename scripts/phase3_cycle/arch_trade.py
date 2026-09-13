"""Phase 3 architecture trade orchestrator (run in .venv; calls TurboFlow tools in .venv-np1).

For each candidate (centrifugal at a given spool speed, or the best feasible axial design):
  1. dash cycle (pyCycle, M1.02 / 5 km, Fn 500 N, OPR 4.0, T4 1150 K, intake duct loss inside)
  2. compressor design at the cycle's W, Tt2, Pt2, PR (TurboFlow centrifugal / TurboDesigner+loss model)
  3. turbine design at T4, P4, exit static, W + Wf, SAME spool speed, blade-stress-limited tip radius
  4. repeat 1-3 with the tool efficiencies until eta_c, eta_t change < 0.003  -> 'tool' level
  5. 'fielded' level: component efficiencies set to the level that reproduces commercial micro-
     turbojet TSFC (tsfc_anchor.py: eta_c 0.70 centrifugal, eta_t 0.75; axial compressor debited by the
     same ratio as the centrifugal), cycle re-sized, compressor/turbine radii scaled by sqrt(W ratio)
  6. combustor (theta-scaled), engine envelope + bottom-up dry mass (engine_mass.py)
  7. airframe drag at M1.02 / 5 km with the real engine diameter and length (Phase 2 airframe model),
     thrust margin = installed Fn / drag - 1 for nominal and pessimistic wave drag; TOGW.
Outputs data/phase3/trade_<case>.json and data/phase3_arch_trade.csv
"""
import os, sys, json, subprocess, copy, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))
import dash_cycle as dc, cycle_model as cm, combustor_sizing as cs, engine_mass as em, axial_design as ad
NP1 = os.path.join(ROOT, ".venv-np1", "Scripts", "python.exe")
OUT = os.path.join(ROOT, "data", "phase3")
OPR, T4 = float(os.environ.get("P3_OPR", 4.0)), float(os.environ.get("P3_T4", 1150.0))
FIELDED = dict(eta_c_centrifugal=0.70, eta_t=0.75)

def run_np1(script, payload, tag):
    fi = os.path.join(OUT, f"{tag}_in.json"); fo = os.path.join(OUT, f"{tag}_out.json")
    json.dump(payload, open(fi, "w"))
    r = subprocess.run([NP1, os.path.join(HERE, script), fi, fo], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(f"{script} failed: {r.stderr[-800:]}")
    return json.load(open(fo))

def turb_pout(cyc):
    g = cyc.get("t_out_gamma", 1.325); M = 0.45
    return cyc["Pt5_kPa"] * 1e3 / (1 + 0.5 * (g - 1) * M * M) ** (g / (g - 1))

def best_axial(cyc):
    best = None
    for rpm in (40000, 45000, 50000, 55000, 60000, 65000):
        for N in (4, 5, 6, 7):
            for ht in (0.40, 0.45, 0.50, 0.55):
                for Cx in (170, 185, 200):
                    p = dict(mdot=cyc["W_kgps"], T01=cyc["Tt2_K"], P01=cyc["Pt2_kPa"] * 1e3, PR=OPR, rpm=rpm, N=N, hub_tip=ht, Cx=Cx, clearance=0.25e-3)
                    try:
                        eta = 0.80
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
    p, r = best
    r.update(input=p, D_casing_mm=2e3 * (r["r_tip_max"] + 0.25e-3 + 0.0025))
    return p["rpm"], r

CAP = os.environ.get("P3_TURB_CAP", "0") == "1"    # cap turbine tip radius at the compressor/combustor envelope

def envelope_cap(kind, comp, cyc):
    comb, _ = cs.combustor(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], cyc["W_kgps"])
    Dc = comp["D_casing_mm"] if kind == "axial" else 2e3 * (comp["geometry"]["vaned_diffuser"]["radius_out"] + 3e-3)
    return (max(Dc, comb["mean"]["OD_mm"]) / 2e3) - 2.3e-3

def design_case(kind, rpm=None, tag="x"):
    eta_c, eta_t = 0.78, 0.88
    hist = []
    for it in range(4):
        cyc, _ = dc.design(OPR, T4, eta_c, eta_t)
        if kind == "centrifugal":
            comp = run_np1("centrifugal_design.py", dict(mdot=cyc["W_kgps"], T01=cyc["Tt2_K"], P01=cyc["Pt2_kPa"] * 1e3, PR=OPR, rpm=rpm,
                                                         beta2b_deg=-30, Z=12, tip_clearance=0.25e-3, R4R2=1.35), f"{tag}_cc")
            eta_c_new = comp["turboflow"]["eta"]
        else:
            rpm, comp = best_axial(cyc); eta_c_new = comp["eta_is"]
        tin = dict(T04=cyc["Tt4_K"], P04=cyc["Pt4_kPa"] * 1e3, p_out=turb_pout(cyc), rpm=rpm, mdot=cyc["W_kgps"] + cyc["Wf_kgps"] * dc.ETA_B, tip_clearance=0.30e-3)
        if CAP: tin["r_tip_cap"] = envelope_cap(kind, comp, cyc)
        turb = run_np1("turbine_design.py", tin, f"{tag}_tt")
        eta_t_new = turb["overall"]["efficiency_tt"] / 100
        hist.append(dict(it=it, eta_c=eta_c, eta_t=eta_t, eta_c_tool=eta_c_new, eta_t_tool=eta_t_new, W=cyc["W_kgps"]))
        print(f"  [{tag}] it{it}: W {cyc['W_kgps']:.4f}  eta_c {eta_c:.3f}->{eta_c_new:.3f}  eta_t {eta_t:.3f}->{eta_t_new:.3f}  rpm {rpm}", flush=True)
        done = abs(eta_c_new - eta_c) < 0.003 and abs(eta_t_new - eta_t) < 0.003
        eta_c, eta_t = eta_c_new, eta_t_new
        if done: break
    cyc, _ = dc.design(OPR, T4, eta_c, eta_t)
    return dict(kind=kind, rpm=rpm, cycle=cyc, comp=comp, turb=turb, eta_c=eta_c, eta_t=eta_t, hist=hist)

def scaled_comp(kind, comp, s):
    c = copy.deepcopy(comp)
    if kind == "centrifugal":
        for sec in c["geometry"].values():
            for k in list(sec):
                if k.startswith("radius") or k.startswith("width") or k.startswith("length") or k == "opening": sec[k] *= s
    else:
        for st in c["stages"]:
            for row in ("rotor", "stator"):
                for k in ("r_hub", "r_tip", "h", "chord"): st[row][k] *= s
        c["r_tip_max"] *= s; c["length"] *= s
    return c

def evaluate(case, level):
    kind, rpm = case["kind"], case["rpm"]
    if level == "tool":
        cyc, comp, s_turb = case["cycle"], case["comp"], 1.0
        eta_c, eta_t = case["eta_c"], case["eta_t"]
    else:
        ref_c = case.get("eta_c_centrifugal_ref", case["eta_c"])
        eta_c = FIELDED["eta_c_centrifugal"] if kind == "centrifugal" else case["eta_c"] * FIELDED["eta_c_centrifugal"] / ref_c
        eta_t = FIELDED["eta_t"]
        cyc, _ = dc.design(OPR, T4, eta_c, eta_t)
        if cyc["res"] > 1e-3 or abs(cyc["Fn_N"] - 500.0) > 1.0 or not np.isfinite(cyc["TSFC_kgpNh"]):
            return None                                  # cycle does not close at this technology level (turbine cannot drive the compressor)
        s = np.sqrt(cyc["W_kgps"] / case["cycle"]["W_kgps"]); comp = scaled_comp(kind, case["comp"], s); s_turb = s
    comb_all, _ = cs.combustor(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], cyc["W_kgps"])
    e = em.engine(cyc, kind, comp, case["turb"], comb_all["mean"], rpm, turb_scale=s_turb)
    e_hi = em.engine(cyc, kind, comp, case["turb"], comb_all["hi"], rpm, turb_scale=s_turb)
    return dict(level=level, eta_c=eta_c, eta_t=eta_t, cycle=cyc, engine=e, engine_comb_hi=e_hi, combustor=comb_all)

def airframe(ev):
    import airframe_model as am, mass_budget as mb
    from aero_utils import isa, G0
    D_e, L_e = ev["engine"]["D_engine_mm"] / 1e3, ev["engine"]["L_engine_mm"] / 1e3
    c = am.Config(S_wing=0.30); c.D_engine = D_e; c.L_engine = L_e
    items = mb.bottom_up(c); af = sum(items.values())
    fuel = 1.58 * ev["cycle"]["Wf_kgps"] / 0.0190                                          # Phase 2 sortie fuel scaled by dash fuel flow
    togw = ev["engine"]["dry_mass_kg"] + 1.60 + af * 1.15 + fuel
    m_dash = togw - 0.32 * fuel                                                           # Phase 2: 32 % of sortie fuel burnt at the start of the dash
    q = 0.7 * isa(5000.0)[1] * 1.02 ** 2
    out = {}
    for tag, E in (("nom", None), ("hi", max(3.0, max(1.8, c.E_geom())))):
        CDS = c.CDS(1.02, 5000.0, E_WD=E)
        CL = m_dash * G0 / (q * 0.30)
        D = q * CDS + q * 0.30 * c.k_induced(1.02) * CL ** 2
        out[tag] = dict(CDS_cm2=CDS * 1e4, drag_N=D, margin=ev["cycle"]["Fn_N"] / D - 1, throttle=D / ev["cycle"]["Fn_N"])
    return dict(D_fus_mm=c.D_fus * 1e3, airframe_systems_kg=af, fuel_kg=fuel, TOGW_kg=togw, margin_to_25=25 - togw, dash=out)

if __name__ == "__main__":
    cases_spec = [c.split(":") for c in os.environ.get("P3_CASES", "centrifugal:85000,centrifugal:75000,axial:0").split(",")]
    rows = []
    cc_ref = float(os.environ["P3_CC_REF"]) if "P3_CC_REF" in os.environ else None   # centrifugal tool eta_c used for the axial fielded debit
    for kind, rpm in cases_spec:
        tag = f"{kind[:2]}{rpm}_opr{OPR:g}_t{T4:g}" + ("_cap" if CAP else "")
        case = design_case(kind, int(rpm) if kind == "centrifugal" else None, tag)
        if kind == "centrifugal" and cc_ref is None: cc_ref = case["eta_c"]
        case["eta_c_centrifugal_ref"] = cc_ref if cc_ref else case["eta_c"]
        for level in ("tool", "fielded"):
            ev = evaluate(case, level)
            if ev is None:
                rows.append(dict(case=tag, arch=kind, rpm=case["rpm"], level=level, note="CYCLE DOES NOT CLOSE at this efficiency level"))
                print(rows[-1], flush=True); continue
            af = airframe(ev)
            e = ev["engine"]
            row = dict(case=tag, arch=kind, rpm=case["rpm"], level=level, eta_c=ev["eta_c"], eta_t=ev["eta_t"], W=ev["cycle"]["W_kgps"],
                       TSFC_dash=ev["cycle"]["TSFC_kgpNh"], Fn=ev["cycle"]["Fn_N"], D_engine_mm=e["D_engine_mm"], D_comp=e["D_breakdown"]["compressor"],
                       D_comb=e["D_breakdown"]["combustor"], D_turb=e["D_breakdown"]["turbine"], D_engine_comb_hi_mm=ev["engine_comb_hi"]["D_engine_mm"],
                       L_engine_mm=e["L_engine_mm"], dry_mass_kg=e["dry_mass_kg"], dry_mass_comb_hi_kg=ev["engine_comb_hi"]["dry_mass_kg"],
                       CDS_nom=af["dash"]["nom"]["CDS_cm2"], CDS_hi=af["dash"]["hi"]["CDS_cm2"], drag_nom=af["dash"]["nom"]["drag_N"], drag_hi=af["dash"]["hi"]["drag_N"],
                       margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"], TOGW=af["TOGW_kg"], fuel=af["fuel_kg"])
            rows.append(row); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
            json.dump(dict(case=case, eval=ev, airframe=af), open(os.path.join(OUT, f"trade_{tag}_{level}.json"), "w"), indent=1, default=float)
    df = pd.DataFrame(rows)
    fn = os.path.join(ROOT, "data", f"phase3_arch_trade_opr{OPR:g}_t{T4:g}{'_cap' if CAP else ''}.csv"); df.to_csv(fn, index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    print(df.round(3).to_string(index=False))
