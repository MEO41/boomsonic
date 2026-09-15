"""Phase 4A: the refreshed pure axial across the Phase 1 mission on its own maps (run in .venv). Mirrors cc_mission.py.

Maps: stage-stacking compressor map of the 3A-R blading WITH the chosen variable-IGV schedule (the start / handling bleed
and the variable nozzle act only below 90 % speed, so the max-thrust deck does not see them), TurboFlow turbine map of
the fielded turbine (data/phase4ax/turbine_map_<tag>.json). Surge surrogate = the peak of each stacking speed line
(R4.1: not validated). pyCycle design point = the fielded dash point.
  1. max-thrust deck over Mach x altitude = min(100 % speed, T4 1150 K) (secant on N, as cc_mission / engine_deck);
  2. idle = the minimum-fuel ACCEPTABLE steady point of the final operability run (VIGV + bleed + nozzle scheduled;
     ax_operability.py final), as a fraction of the 100 % SLS fuel flow;
  3. the Phase 2 sortie (mission_drag_polar) re-flown on that deck by ax_closure.py.
Usage: python ax_mission.py <tag>      outputs data/phase4ax/mission_<tag>_deck.csv, mission_<tag>.json
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import cycle_model as cm, dash_cycle as dc, axial_map as am, axial_offdesign as ao
TAG = sys.argv[1]; OUT = os.path.join(AXROOT, "data", "phase4ax")
AX = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"axt_{TAG}.json"))); F = AX["levels"]["fielded"]; CYC = F["eval"]["cycle"]
OPR, T4, ETA_C, ETA_T = CYC["comp_PR"], 1150.0, F["eval"]["eta_c"], F["eval"]["eta_t"]
OPF = json.load(open(os.path.join(OUT, f"operability_{TAG}_final.json")))
sch = OPF["vigv_schedule"]; vigv = (lambda N: float(np.interp(N, sch["N"], sch["igv_deg"]))) if OPF["config"]["vigv"] else None
g = lambda prob, n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])
c = ao.fielded(F["comp"], ETA_C)
lines = am.build_compressor_lines(c, igv_sched=vigv); cmap, R_d = am.compressor_mapdata(lines, c.W_d, c.T01, c.P01)
tdata, cover = am.turbine_mapdata(json.load(open(os.path.join(OUT, f"turbine_map_{TAG}.json"))))

def smn(Nc, Wc_lbm):
    W = Wc_lbm / am.KG2LBM * (c.P01 / 101325.0) / np.sqrt(c.T01 / 288.15)
    try: q = c.point(Nc, W, igv=vigv(Nc) if vigv else None)
    except ao.Choked: return np.nan
    Ns = np.array([l["N"] for l in lines]); f = lambda k: float(np.interp(Nc, Ns, [l[k] for l in lines]))
    return (f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1

def build(mn, alt):
    prob, mp = cm.build(od_points=[(dc.M_DASH, dc.H_DASH)], od_mode="N", comp_map=cmap, turb_map=tdata)   # OD starts at the design condition
    dd, _ = dc.design(OPR, T4, ETA_C, ETA_T, prob=prob)
    cm.set_design(prob, dc.M_DASH, dc.H_DASH, OPR, T4, ETA_C, ETA_T, Fn_N=500.0, duct_dPqP=dd["duct"]["dPqP"], ram_recovery=dd["ram_recovery"], od_names=mp.od_names, od_mode="N")
    prob["DESIGN.balance.W"] = dd["W_kgps"] / 0.45359237; pt = mp.od_names[0]
    prob.set_val(pt + ".Nmech", g(prob, "DESIGN.Nmech", "rpm"), units="rpm"); prob.run_model()
    cm.seed_od_from_design(prob, pt)                    # default OD guesses diverge at eta_c 0.709 (Phase 4A)
    return prob, pt, g(prob, "DESIGN.Nmech", "rpm")

def solve(prob, pt):
    prob.run_model(); r = cm.read(prob, pt, eta_b=dc.ETA_B)
    if r["res"] >= 1e-4: prob.run_model(); r = cm.read(prob, pt, eta_b=dc.ETA_B)
    r["conv"] = r["res"] < 1e-4
    for k in ("NcMap", "WcMap"): r["comp_" + k] = g(prob, f"{pt}.comp.map.{k}")
    r["SMN"] = smn(r["comp_NcMap"], r["comp_WcMap"]) if r["conv"] else np.nan
    return r

MACHS = [0.0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0, 1.02, 1.05]
ALTS = [0.0, 300.0, 1000.0, 2500.0, 4000.0, 5000.0, 6000.0]
if __name__ == "__main__" and os.environ.get("AXM_REUSE_DECK") == "1" and os.path.exists(os.path.join(OUT, f"mission_{TAG}_deck.csv")):
    # the max-thrust deck is independent of the bleed / nozzle schedules (closed / 1.0 above 95 % speed): re-used
    dk = pd.read_csv(os.path.join(OUT, f"mission_{TAG}_deck.csv")); rows = None
elif __name__ == "__main__":
    prob, pt, Nd = build(1.02, 5000.0); path, rows = [], []
    for i, h in enumerate(ALTS[::-1]): path += [(m, h) for m in (MACHS[::-1] if i % 2 == 0 else MACHS)]
    for (m, h) in path:
        prob.set_val(pt + ".fc.MN", max(m, 1e-6)); prob.set_val(pt + ".fc.alt", h, units="m"); prob.set_val(pt + ".inlet.ram_recovery", dc.normal_shock_recovery(m))
        prob.set_val(pt + ".Nmech", Nd, units="rpm"); r = solve(prob, pt); binding = "N"; r100 = r
        if r["conv"] and r["Tt4_K"] > T4 + 0.5:
            binding = "T4"; n0, t0 = 1.0, r["Tt4_K"]; n1 = 0.98
            for _ in range(12):
                prob.set_val(pt + ".Nmech", n1 * Nd, units="rpm"); r = solve(prob, pt)
                if not r["conv"]: break
                t1 = r["Tt4_K"]
                if abs(t1 - T4) < 0.5: break
                n0, t0, n1 = n1, t1, float(np.clip(n1 - (t1 - T4) * (n1 - n0) / (t1 - t0) if t1 != t0 else n1 - 0.01, 0.8, 1.0))
        rows.append(dict(MN=m, alt_m=h, Fn_N=r["Fn_N"] if r["conv"] else np.nan, Wf_kgps=r["Wf_kgps"] if r["conv"] else np.nan, W_kgps=r["W_kgps"], T4_K=r["Tt4_K"],
                         N_pct=100 * r["Nmech"] / Nd, SMN=r["SMN"], binding=binding, conv=r["conv"], Fn_at_100pct=r100["Fn_N"], T4_at_100pct=r100["Tt4_K"]))
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
    dk = pd.DataFrame(rows).sort_values(["alt_m", "MN"]).reset_index(drop=True); dk.to_csv(os.path.join(OUT, f"mission_{TAG}_deck.csv"), index=False)
if __name__ == "__main__":
    pts = pd.read_csv(os.path.join(OUT, f"operability_{TAG}_final.csv")); sls = pts[pts.case == "final_SLS"]
    ok = sls[sls.ok.astype(str) == "True"]; idle = ok.loc[ok.Wf_kgps.idxmin()] if len(ok) else None
    s100 = sls.loc[(sls.N_pct - 100).abs().idxmin()]
    out = dict(tag=TAG, config=OPF["config"], idle=dict(N_pct=float(idle.N_pct), Fn_N=float(idle.Fn_N), Wf_kgps=float(idle.Wf_kgps), T4_K=float(idle.Tt4_K),
                                                         SM=float(idle.SM_peak), bleed=float(idle.bleed), A8_scale=float(idle.A8_scale), igv_deg=float(idle.igv_deg)) if idle is not None else None,
               idle_frac=float(idle.Wf_kgps / s100.Wf_kgps) if idle is not None else None, SLS_100=dict(Fn_N=float(s100.Fn_N), Wf_kgps=float(s100.Wf_kgps), T4_K=float(s100.Tt4_K)),
               SLS_max=dk[(dk.MN == 0) & (dk.alt_m == 0)].iloc[0].to_dict(), dash=dk[(dk.MN == 1.02) & (dk.alt_m == 5000)].iloc[0].to_dict(), turbine_cover=cover, R_design=R_d)
    json.dump(out, open(os.path.join(OUT, f"mission_{TAG}.json"), "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k in ("idle", "idle_frac", "SLS_100", "SLS_max", "dash")}, indent=1, default=lambda x: round(float(x), 3)))
