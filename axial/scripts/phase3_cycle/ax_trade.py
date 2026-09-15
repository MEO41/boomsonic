"""Phase 3A-R: the pure-axial baseline (6 stages, OPR 5, 80 000 rpm) re-evaluated with the Phase 3R corrections
(run in .venv; calls TurboFlow in .venv-np1).

What changes against the Phase 3 / Phase 4 axial evaluation (arch_trade.evaluate, tag ax0_opr5_t1150_cap_blk):
  1. fielded compressor efficiency: A3.4 debits the axial tool efficiency by the ratio fielded / tool of the
     centrifugal. Its reference 0.794 was the Phase 3 centrifugal computed with TurboFlow's defective Wiesner slip
     (F3R.1). The reference is now the Phase 3R centrifugal tool efficiency (data/phase3r/cct_<3R tag>.json)
     -> eta_c,fielded = eta_c,tool x 0.70 / eta_ref (A3A.1);
  2. fielded compressor geometry: the Phase 3 sqrt(W) scaling cannot match both the fielded flow (area ~ r^2) and
     the fielded stage work (U^2) at fixed speed (the same flaw F3R.3 found for the impeller). The blading is instead
     re-designed AT the fielded cycle: TurboDesigner at the fielded W / Tt2 / Pt2 / PR with the fielded efficiency as
     its (work-setting) input, the Howell loss model evaluated once (it reports the tool-level efficiency of that
     blading), the Phase 3 limits applied (DF <= 0.5, de Haller >= 0.72, rotor-1 tip M_rel <= 1.35, last blade >= 10 mm);
  3. fielded turbine: re-designed by TurboFlow at the fielded cycle (350 MPa blade-root limit, envelope cap) instead of
     the sqrt(W) scaling that put the Phase 3 turbine tip ~11 % past its limit (F3R.3);
  4. mass and length calibrations: the Phase 3R re-anchored values (data/phase3_mass_model_validation_3r.csv).
The tool-level design (TurboDesigner + Howell compressor, TurboFlow turbine) is re-used from the Phase 3 file: neither
tool is touched by the slip defect.
Selection (Phase 3 rule): among fielded designs whose turbine closes within its stress limit, the highest loss-model
compressor efficiency.
  python ax_trade.py grid        fielded compressor grid -> data/phase3ax/fielded_axial_grid.csv
  python ax_trade.py run [rpm]   full chain at the best design of each rpm (or one rpm) -> data/phase3ax/axt_<tag>.json
  python ax_trade.py compile     summary table
"""
import os, sys, json, copy, glob, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
# absolute, so arch_trade writes into the axial tree instead of the shared data/
os.environ["P3_DATA"] = os.path.join(AXROOT, "data", "phase3ax"); os.environ["P3_TURB_CAP"] = "1"; os.environ["P3_OPR"] = "5"
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, HERE)
import arch_trade as at, axial_design as ad, combustor_sizing as cs, engine_mass as em
from cc_trade import calibration, calibrated
at.OPR = 5.0; at.CAP = True
OUT = at.OUT; os.makedirs(OUT, exist_ok=True)
OLD = json.load(open(os.path.join(ROOT, "data", "phase3", "trade_ax0_opr5_t1150_cap_blk_fielded.json")))
CASE = OLD["case"]
REF_TAG = "ce75000_opr4_t1150_b15_cap"
ETA_REF = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{REF_TAG}.json")))["levels"]["tool"]["eval"]["cycle"]["comp_eff"]
K_F = at.FIELDED["eta_c_centrifugal"] / ETA_REF
GRID = dict(rpm=(70000, 75000, 80000, 85000, 90000), N=(5, 6, 7, 8), hub_tip=(0.40, 0.45, 0.50, 0.55), Cx=(170, 185, 200))
LIM = dict(DF=0.5, deHaller=0.72, M_rel_tip=1.35, h_last=0.010)

def fielded_cycle(eta_c):
    cyc, _ = at.dc.design(at.OPR, at.T4, eta_c, at.FIELDED["eta_t"])
    if cyc["res"] > 1e-3 or abs(cyc["Fn_N"] - 500.0) > 1.0: raise RuntimeError(f"fielded cycle not closed at eta_c {eta_c:.3f}")
    return cyc

def size_axial(cyc, eta, rpm, N, ht, Cx):
    p = dict(mdot=cyc["W_kgps"], T01=cyc["Tt2_K"], P01=cyc["Pt2_kPa"] * 1e3, PR=at.OPR, rpm=rpm, N=N, hub_tip=ht, Cx=Cx, clearance=0.25e-3)
    r = ad.evaluate(p, eta)
    st = r["stages"]
    chk = dict(DF=max(s["DF_rotor"] for s in st), deHaller=min(s["deHaller_r"] for s in st), M_rel_tip=st[0]["M_rel_tip"], h_last=st[-1]["stator"]["h"])
    ok = chk["DF"] <= LIM["DF"] and chk["deHaller"] >= LIM["deHaller"] and chk["M_rel_tip"] <= LIM["M_rel_tip"] and chk["h_last"] >= LIM["h_last"] and np.isfinite(r["eta_is"])
    r.update(input=p, eta_sizing=eta, D_casing_mm=2e3 * (r["r_tip_max"] + 0.25e-3 + 0.0025), checks=chk, feasible=bool(ok))
    return r

def grid(cyc, eta):
    rows, best = [], {}
    for rpm, N, ht, Cx in itertools.product(*GRID.values()):
        try: r = size_axial(cyc, eta, rpm, N, ht, Cx)
        except Exception as ex:
            rows.append(dict(rpm=rpm, N=N, hub_tip=ht, Cx=Cx, feasible=False, note=str(ex)[:60])); continue
        rows.append(dict(rpm=rpm, N=N, hub_tip=ht, Cx=Cx, feasible=r["feasible"], eta_is_tool=r["eta_is"], **r["checks"], r_tip_mm=r["r_tip_max"] * 1e3,
                         length_mm=r["length"] * 1e3, D_casing_mm=r["D_casing_mm"], n_blades=r["n_blades"]))
        if r["feasible"] and (rpm not in best or r["eta_is"] > best[rpm]["eta_is"]): best[rpm] = r
    return pd.DataFrame(rows), best

def fielded_turbine(cyc, comp, rpm, tag):
    tin = dict(T04=cyc["Tt4_K"], P04=cyc["Pt4_kPa"] * 1e3, p_out=at.turb_pout(cyc), rpm=rpm, mdot=cyc["W_kgps"] + cyc["Wf_kgps"] * at.dc.ETA_B,
               tip_clearance=0.30e-3, r_tip_cap=at.envelope_cap("axial", comp, cyc))
    fo = os.path.join(OUT, f"{tag}_out.json")
    if os.path.exists(fo):
        old = json.load(open(fo))
        if all(abs(old["input"].get(k, np.nan) - v) <= 1e-6 * max(1.0, abs(v)) for k, v in tin.items()): return old
    return at.run_np1("turbine_design.py", tin, tag)

def engine_eval(cyc, comp, turb, rpm, eta_c, level):
    comb_all, _ = cs.combustor(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], cyc["W_kgps"])
    e = em.engine(cyc, "axial", comp, turb, comb_all["mean"], rpm); e_hi = em.engine(cyc, "axial", comp, turb, comb_all["hi"], rpm)
    return dict(level=level, eta_c=eta_c, eta_t=cyc["turb_eff"], cycle=cyc, engine=e, engine_comb_hi=e_hi, combustor=comb_all)

def turb_summary(turb):
    return dict(eta_tt_tool=turb["overall"]["efficiency_tt"] / 100, r_tip_mm=turb["r_tip_max"] * 1e3, r_tip_stress_limit_mm=turb["r_tip_stress_limit"] * 1e3,
                r_tip_cap_mm=turb["r_tip_limit"] * 1e3, success=bool(turb["success"]),
                within_stress=bool(turb["r_tip_max"] <= turb["r_tip_stress_limit"] * (1 + 1e-6)))

def run(rpm_only=None):
    cal = calibration(); eta_f = CASE["eta_c"] * K_F
    cyc_f = fielded_cycle(eta_f)
    df, best = grid(cyc_f, eta_f)
    df.to_csv(os.path.join(OUT, "fielded_axial_grid.csv"), index=False)
    # tool level: the Phase 3 design re-used, re-evaluated with the 3R calibration
    ev_t = at.evaluate(CASE, "tool"); evt_c = calibrated(ev_t, cal)
    tool = dict(eval=ev_t, engine_cal=evt_c["engine"], airframe=at.airframe(evt_c), airframe_comb_hi=at.airframe(calibrated(ev_t, cal, "hi")))
    for rpm in sorted(best):
        if rpm_only and rpm != rpm_only: continue
        comp = best[rpm]; tag = f"ax{rpm}_opr5_t1150_n{comp['input']['N']}_cap_3r"
        turb = fielded_turbine(cyc_f, comp, rpm, f"{tag}_ttf")
        ts = turb_summary(turb)
        ev = engine_eval(cyc_f, comp, turb, rpm, eta_f, "fielded"); evc = calibrated(ev, cal)
        fld = dict(eval=ev, comp=comp, turbine=ts, engine_cal=evc["engine"], airframe=at.airframe(evc), airframe_comb_hi=at.airframe(calibrated(ev, cal, "hi")))
        # worst corner: compressor efficiency debited 0.66 / 0.70 further, same blading choice re-sized, combustor +1 sigma, pessimistic drag
        eta_w = eta_f * 0.66 / 0.70
        try:
            cyc_w = fielded_cycle(eta_w); i = comp["input"]
            comp_w = size_axial(cyc_w, eta_w, rpm, i["N"], i["hub_tip"], i["Cx"])
            turb_w = fielded_turbine(cyc_w, comp_w, rpm, f"{tag}_ttw"); ev_w = engine_eval(cyc_w, comp_w, turb_w, rpm, eta_w, "worst")
            worst = dict(eta_c=eta_w, comp_feasible=comp_w["feasible"], checks=comp_w["checks"], turbine=turb_summary(turb_w),
                         margin_hi=at.airframe(calibrated(ev_w, cal, "hi"))["dash"]["hi"]["margin"], D_mm=ev_w["engine_comb_hi"]["D_engine_mm"])
        except Exception as ex:
            worst = dict(note=str(ex))
        out = dict(tag=tag, rpm=rpm, OPR=at.OPR, calibration=cal, eta_ref_centrifugal=ETA_REF, ref_tag=REF_TAG, K_F=K_F, case_phase3=CASE,
                   levels=dict(tool=tool, fielded=fld), worst_corner=worst)
        json.dump(out, open(os.path.join(OUT, f"axt_{tag}.json"), "w"), indent=1, default=float)
        a = fld["airframe"]["dash"]; e = fld["engine_cal"]
        print(f"{tag}: eta_c f {eta_f:.3f} (tool blading {comp['eta_is']:.3f}), N {comp['input']['N']}, h/t {comp['input']['hub_tip']}, Cx {comp['input']['Cx']}, "
              f"turbine ok {ts['success'] and ts['within_stress']}, D {e['D_engine_mm']:.0f} mm, L {e['L_engine_mm']:.0f} mm, m {e['dry_mass_kg']:.2f} kg, "
              f"margin {100*a['nom']['margin']:+.0f} / {100*a['hi']['margin']:+.0f} %, worst {100*worst.get('margin_hi', np.nan):+.0f} %", flush=True)

def compile_():
    rows = []
    for fn in sorted(glob.glob(os.path.join(AXROOT, "data", "phase3ax", "axt_*.json"))):
        d = json.load(open(fn))
        for lv, L in d["levels"].items():
            ev, e, a = L["eval"], L["engine_cal"], L["airframe"]
            c = L.get("comp") or d["case_phase3"]["comp"]; t = L.get("turbine", {})
            rows.append(dict(tag=d["tag"], level=lv, rpm=d["rpm"], N=c["input"]["N"], hub_tip=c["input"]["hub_tip"], Cx=c["input"]["Cx"], eta_c=ev["eta_c"],
                             eta_blading_tool=c["eta_is"], W=ev["cycle"]["W_kgps"], TSFC=ev["cycle"]["TSFC_kgpNh"], DF=max(s["DF_rotor"] for s in c["stages"]),
                             M_rel_1=c["stages"][0]["M_rel_tip"], r_tip_comp_mm=c["r_tip_max"] * 1e3, turb_ok=(t.get("success", True) and t.get("within_stress", True)),
                             D_mm=e["D_engine_mm"], D_comp=e["D_breakdown"]["compressor"], D_comb=e["D_breakdown"]["combustor"], D_turb=e["D_breakdown"]["turbine"],
                             L_mm=e["L_engine_mm"], m_cal=e["dry_mass_kg"], margin_nom=a["dash"]["nom"]["margin"], margin_hi=a["dash"]["hi"]["margin"],
                             worst=d["worst_corner"].get("margin_hi", np.nan) if lv == "fielded" else np.nan, TOGW=a["TOGW_kg"]))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(AXROOT, "data", "phase3ax_trade.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); print(df.round(3).to_string(index=False))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    print(f"eta reference (3R centrifugal tool) {ETA_REF:.4f} -> K_F {K_F:.4f}; axial tool {CASE['eta_c']:.4f} -> fielded {CASE['eta_c']*K_F:.4f} "
          f"(Phase 3: x {0.70/0.794:.4f} -> {CASE['eta_c']*0.70/0.794:.4f})", flush=True)
    if cmd == "grid":
        eta_f = CASE["eta_c"] * K_F; cyc = fielded_cycle(eta_f); df, best = grid(cyc, eta_f)
        df.to_csv(os.path.join(OUT, "fielded_axial_grid.csv"), index=False)
        print(f"fielded cycle W {cyc['W_kgps']:.4f} kg/s; feasible {int(df.feasible.sum())} of {len(df)}")
        for rpm, r in sorted(best.items()):
            i = r["input"]; print(f"  {rpm}: best N {i['N']} h/t {i['hub_tip']} Cx {i['Cx']} eta {r['eta_is']:.4f} DF {r['checks']['DF']:.3f} M1 {r['checks']['M_rel_tip']:.3f} "
                                  f"r_tip {r['r_tip_max']*1e3:.1f} mm L {r['length']*1e3:.0f} mm")
        f = df[df.feasible]; print(f.sort_values("eta_is_tool", ascending=False).head(12).round(3).to_string(index=False))
    elif cmd == "run":
        run(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        compile_()
