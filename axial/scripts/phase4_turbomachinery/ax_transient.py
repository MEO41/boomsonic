"""Phase 4A: quasi-steady acceleration margin and idle-to-max acceleration time of the refreshed axial at SLS (run in .venv).
Same method as cc_transient.py / accel.py, with the Phase 4A variable geometry scheduled on speed:
  * compressor: fielded stage-stacking map with the VIGV schedule and the bleed schedule (ax_operability final config);
  * at each fixed speed the bleed fraction and the nozzle area take their scheduled values; T4 is raised above its steady
    value (pyCycle od_mode 'NT4': speed and T4 imposed, shaft power unbalanced) while
      - constant-speed margin to the stacking peak line SM >= 5 % (as cc_transient; 10 % also reported),
      - no row beyond its Howell stalling deflection,
      - T4 <= 1150 K;
  * dN/dt = P_excess / (I_p omega), integrated from idle to the SLS maximum-throttle speed.
I_p: the chosen stiffened rotor (ax_rotor.py: 2 mm drum, 24 / 12 shaft, 12 mm journals).
Usage: python ax_transient.py <tag>      output data/phase4ax/accel_<tag>.csv / .json
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
TAG = sys.argv[1]; OUT = os.path.join(AXROOT, "data", "phase4ax")
OPF = json.load(open(os.path.join(OUT, f"operability_{TAG}_final.json"))); cfg = OPF["config"]
os.environ["AXOP_VG_OPEN"] = str(cfg["bleed_close"])
sys.argv = [sys.argv[0], TAG, "none"]; sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE)
import ax_operability as op
op.A8_N = float(os.environ.get("AXOP_A8_N", 0.80))           # final configuration: nozzle fully open by 80 % speed
import pandas as _pd
rot = _pd.read_csv(os.path.join(OUT, f"rotor_{TAG}.csv"))
sel = rot[(rot.t_drum_mm.round(2) == 2.0) & (rot.shaft_od_mm == 24.0) & (rot.journal_mm == 12.0) & (rot.k == 1.75e6) & (rot.c == 876.0)].iloc[0]
I_P = float(sel.Ip_kgm2); T4_MAX = 1150.0
vigv = op.vigv_linear(cfg["vigv_closure_deg"]); bf = cfg["bleed"]; a8 = op.a8_sched(cfg["a8_max"])
L, cmap_ = op.lines_for(vigv, bf)

def build():
    prob, mp = op.cm.build(od_points=[(op.dc.M_DASH, op.dc.H_DASH)], od_mode="NT4", comp_map=cmap_, turb_map=op.tdata, comp_bleed=True)
    d, _ = op.dc.design(op.OPR, op.T4, op.ETA_C, op.ETA_T, prob=prob)
    op.cm.set_design(prob, op.dc.M_DASH, op.dc.H_DASH, op.OPR, op.T4, op.ETA_C, op.ETA_T, Fn_N=500.0, duct_dPqP=d["duct"]["dPqP"], ram_recovery=d["ram_recovery"],
                     od_names=mp.od_names, od_mode="NT4")
    prob['DESIGN.balance.W'] = d["W_kgps"] / 0.45359237; pt = mp.od_names[0]; Nd = op.g(prob, "DESIGN.Nmech", "rpm")
    prob.set_val(pt + ".Nmech", Nd, units="rpm"); prob.set_val(pt + ".balance.T4_target", op.T4 * 1.8, units="degR")
    prob.set_val(pt + ".comp.sb:frac_P", op.FRAC_P); prob.set_val(pt + ".comp.sb:frac_work", op.FRAC_WORK)
    for nm in ("frac_W", "frac_P", "frac_work"): prob.set_val("DESIGN.comp.sb:" + nm, 0.0)
    prob.run_model(); op.cm.seed_od_from_design(prob, pt); op.goto(prob, pt, 0.0, 0.0)
    return prob, pt, Nd

_last = {}
def solve(prob, pt):
    """a failed solve leaves a NaN / diverged state that poisons the next point: restore the last converged state."""
    try: prob.run_model(); okr = True
    except Exception: okr = False
    try: r = op.cm.read(prob, pt, eta_b=op.dc.ETA_B); r["conv"] = bool(okr and r["res"] < 1e-4)
    except Exception: r = dict(conv=False)
    if r["conv"]: _last["o"] = prob.model._outputs.asarray(copy=True)
    else:
        if "o" in _last: prob.model._outputs.set_val(_last["o"])
        return dict(conv=False)
    r["P_net_kW"] = op.g(prob, pt + ".shaft.pwr_net", "kW")
    for k in ("NcMap", "WcMap"): r["comp_" + k] = op.g(prob, f"{pt}.comp.map.{k}")
    return r

# steady SLS line of the final operability run: the speed continuation follows it (T4 imposed = the steady T4), which
# converges where marching speed at T4 = 1150 K does not (77.5 % failed that way: first complete run, accel.log)
_sls = pd.read_csv(os.path.join(OUT, f"operability_{TAG}_final.csv")); _sls = _sls[(_sls.case == "final_SLS") & (_sls.conv.astype(str) == "True")].sort_values("N_pct")
T4_line = lambda N: float(min(T4_MAX, np.interp(100 * N, _sls.N_pct, _sls.Tt4_K)))
NS_ALL = [0.985, 0.975, 0.95, 0.925, 0.9, 0.875, 0.85, 0.825, 0.8, 0.775]

if __name__ == "__main__":
    prob, pt, Nd = build(); rows = []; Ncur = 1.0
    Ns = [float(x) for x in os.environ["AXTR_NS"].split(",")] if os.environ.get("AXTR_NS") else NS_ALL   # subset: merged into the csv
    for N in Ns:
        tb = bf if N <= op.BLEED_CLOSE else 0.0; ta = a8(N)
        nsub = max(3, int(np.ceil(abs(Ncur - N) / 0.0125)))
        b0 = float(np.ravel(prob.get_val(pt + ".comp.sb:frac_W"))[0]); a0 = float(np.ravel(prob.get_val(pt + ".a8s.A8_scale"))[0])
        for s in np.linspace(0, 1, nsub + 1)[1:]:            # continuation in speed / valve / nozzle along the steady line
            Ns_ = Ncur + s * (N - Ncur)
            prob.set_val(pt + ".comp.sb:frac_W", b0 + s * (tb - b0)); prob.set_val(pt + ".a8s.A8_scale", a0 + s * (ta - a0))
            prob.set_val(pt + ".balance.T4_target", T4_line(Ns_) * 1.8, units="degR")
            prob.set_val(pt + ".Nmech", Ns_ * Nd, units="rpm"); solve(prob, pt)
        Ncur = N
        # T4 marched in 15 K steps from the steady line: DOWN 3 steps (brackets the steady point), back, then UP to the
        # limit (stops after 2 failures). A direct jump 1150 -> 700 K diverged and poisoned every later point (first
        # Phase 4A run); solve() restores the last converged state after a failure.
        pts = []; T0 = T4_line(N)
        def point(T4):
            prob.set_val(pt + ".balance.T4_target", T4 * 1.8, units="degR"); r = solve(prob, pt)
            if not r.get("conv"): return False
            cs = op.comp_state(r["comp_NcMap"], r["comp_WcMap"], L, vigv(r["comp_NcMap"]), (op.K_BLEED, tb) if tb > 0 else None)
            if cs is not None: r.update(cs, T4_set=T4); pts.append(r)
            return True
        for T4 in (T0, T0 - 15, T0 - 30, T0 - 45): point(T4)
        for T4 in (T0 - 30, T0 - 15, T0): prob.set_val(pt + ".balance.T4_target", T4 * 1.8, units="degR"); solve(prob, pt)
        fails = 0
        for T4 in np.arange(T0 + 15.0, T4_MAX, 15.0).tolist() + [T4_MAX]:
            if point(T4): fails = 0
            else:
                fails += 1
                if fails >= 2: break
        for T4 in np.arange(T4_MAX, T0 - 1e-6, -50.0)[1:].tolist() + [T0]:     # back to the steady line
            prob.set_val(pt + ".balance.T4_target", T4 * 1.8, units="degR"); solve(prob, pt)
        if not pts:
            rows.append(dict(N=N, note="no converged point")); print(rows[-1], flush=True); continue
        ss = min(pts, key=lambda q: abs(q["P_net_kW"]))
        # steady point = P_net zero crossing (interpolated in T4); None when the whole T4 range has P_net < 0
        pp = sorted(pts, key=lambda q: q["Tt4_K"]); Tq = [q["Tt4_K"] for q in pp]; Pq = [q["P_net_kW"] for q in pp]
        T4_ss = float(np.interp(0.0, Pq, Tq)) if (min(Pq) < 0 < max(Pq) and np.all(np.diff(Pq) > 0)) else np.nan
        row = dict(N=N, T4_steady=T4_ss, T4_steady_nearest=ss["Tt4_K"], P_net_nearest_kW=ss["P_net_kW"], SM_steady=ss["SM_peak"], bleed=tb, A8=ta, n_pts=len(pts))
        for sm_res in (0.05, 0.10):
            lim = [q for q in pts if q["P_net_kW"] > 0 and q["SM_peak"] >= sm_res and q["stall_index"] <= 1.0]
            b = max(lim, key=lambda q: q["P_net_kW"]) if lim else None; t_ = f"_{int(sm_res*100)}"
            row.update({f"P_ex_kW{t_}": b["P_net_kW"] if b else 0.0, f"T4_lim{t_}": b["Tt4_K"] if b else np.nan, f"SM_lim{t_}": b["SM_peak"] if b else np.nan,
                        f"limit{t_}": ("T4" if b and b["T4_set"] >= T4_MAX - 1 else "surge margin / stall") if b else "none"})
        rows.append(row); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    df = pd.DataFrame(rows); fcsv = os.path.join(OUT, f"accel_{TAG}.csv")
    if os.environ.get("AXTR_NS") and os.path.exists(fcsv):                   # merge a subset run into the full table
        old = pd.read_csv(fcsv); old = old[~old.N.round(4).isin(df.N.round(4))].drop(columns=[c for c in old if c.startswith("t_to_max") or c == "I_p"])
        df = pd.concat([old, df], ignore_index=True).sort_values("N", ascending=False).reset_index(drop=True)
    if "P_ex_kW_5" not in df or df["P_ex_kW_5"].isna().all():
        df.to_csv(os.path.join(OUT, f"accel_{TAG}.csv"), index=False); sys.exit("no speed with a converged NT4 point: acceleration not computed")
    df = df.dropna(subset=["P_ex_kW_5"])
    om = df.N.values * Nd * np.pi / 30; o = np.argsort(om); res = {}
    for t_ in ("_5", "_10"):
        P = df[f"P_ex_kW{t_}"].values[o] * 1e3; w = om[o]
        f = np.where(P > 0, w / np.maximum(P, 1e-9), np.inf)
        t_cum = np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(w))])
        df.loc[df.index[o], f"t_to_max_s{t_}"] = (t_cum[-1] - t_cum) * I_P; res[t_] = float(t_cum[-1] * I_P)
    df["I_p"] = I_P; df.to_csv(os.path.join(OUT, f"accel_{TAG}.csv"), index=False)
    json.dump(dict(tag=TAG, I_p=I_P, idle_pct=100 * float(df.N.min()),t_idle_to_max_s_SM5=res["_5"], t_idle_to_max_s_SM10=res["_10"]), open(os.path.join(OUT, f"accel_{TAG}.json"), "w"), indent=1)
    pd.set_option("display.width", 220); print(df.round(3).to_string(index=False))
