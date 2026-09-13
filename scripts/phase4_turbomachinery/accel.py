"""Phase 4: quasi-steady acceleration margin and idle-to-max acceleration time (sea-level static).

At a fixed spool speed, T4 is raised above its steady value (pyCycle od_mode 'NT4': speed and T4
imposed, shaft power left unbalanced). The compressor operating point climbs toward the surge
surrogate line; the transient limit is reached at the first of:
  * constant-speed surge margin to the peak-PR line = SM_RES (5 %; Rolls-Royce CN112081683A: up to half
    of the ~20 % design surge margin is allowed for transient working-line excursions),
  * T4 = T4_MAX_TRANSIENT (1150 K, the steady design limit; no over-temperature allowed).
The excess shaft power at that limit gives dN/dt = P / (I omega); integrating from idle to 100 % gives
the minimum acceleration time for a surge-free, over-temperature-free fuel schedule.
Usage: python accel.py <trade tag> <I_polar kg m2> [vigv]   (vigv: use the VIGV map from operability.py)
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "ax0_opr5_t1150_cap_blk"] + sys.argv[2:]
TAG = sys.argv[1]; I_POLAR = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
USE_VIGV = len(sys.argv) > 3 and sys.argv[3] == "vigv"
sys.argv = sys.argv[:2]
sys.path.insert(0, HERE)
import operability as op
import axial_map as am
SM_RES, T4_MAX = 0.05, 1150.0

sched = None; cmap_ = None; lines_ = None
if USE_VIGV:
    v = json.load(open(os.path.join(op.OUT, f"vigv_{TAG}_nw1.json")))
    lines_ = v["lines"]; cmap_, _ = am.compressor_mapdata(lines_, op.c.W_d, op.c.T01, op.c.P01)
    sched = lambda N: float(np.interp(N, v["N"], v["igv_deg"]))

def at_speed(N, prob, mp, Nd):
    pt = mp.od_names[0]
    prob.set_val(pt + ".Nmech", N * Nd, units="rpm")
    out = []
    for T4 in np.arange(700.0, T4_MAX + 1e-6, 25.0):
        prob.set_val(pt + ".balance.T4_target", T4 * 1.8, units="degR")
        prob.run_model()
        r = op.read_od(prob, pt, Nd)
        if not r["conv"]: prob.run_model(); r = op.read_od(prob, pt, Nd)
        if not r["conv"]: continue
        cs = op.comp_state(r["comp_NcMap"], r["comp_WcMap"], igv=sched(r["comp_NcMap"]) if sched else None, lines_=lines_)
        if cs is None: continue
        r.update(cs); r["T4_set"] = T4; out.append(r)
    return out

if __name__ == "__main__":
    prob, mp, d = op.build("NT4", [(0.0, 0.0)], cmap_)
    pt = mp.od_names[0]; Nd = op.g(prob, "DESIGN.Nmech", "rpm")
    prob.set_val(pt + ".fc.MN", 1e-6); prob.set_val(pt + ".fc.alt", 0.0, units="m"); prob.set_val(pt + ".inlet.ram_recovery", 1.0)
    rows = []
    for N in (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4):
        pts = at_speed(N, prob, mp, Nd)
        ok = [q for q in pts if q["pwr_net_kW"] > 0]
        if not ok:
            rows.append(dict(N=N, P_ex_kW=0.0, note="no positive excess power up to T4 max")); print(rows[-1], flush=True); continue
        lim = [q for q in ok if q["SM_peak"] >= SM_RES]
        best = max(lim, key=lambda q: q["pwr_net_kW"]) if lim else None
        ss = min(pts, key=lambda q: abs(q["pwr_net_kW"]))            # ~ steady point
        rows.append(dict(N=N, T4_steady=ss["Tt4_K"], SM_steady=ss["SM_peak"], stall_idx_steady=ss["stall_index"],
                         T4_lim=best["Tt4_K"] if best else np.nan, P_ex_kW=best["pwr_net_kW"] if best else 0.0,
                         SM_at_lim=best["SM_peak"] if best else np.nan, stall_idx_lim=best["stall_index"] if best else np.nan,
                         limit=("T4" if best and best["T4_set"] >= T4_MAX - 1 else "surge margin") if best else "surge margin at steady"))
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
    df = pd.DataFrame(rows)
    # time from each speed to 100 %: t = I * int omega / P domega
    rpm_d = op.case["rpm"]; om = df["N"].values * rpm_d * np.pi / 30; P = df["P_ex_kW"].values * 1e3
    order = np.argsort(om); om, P = om[order], P[order]
    f = np.where(P > 0, om / np.maximum(P, 1e-9), np.inf)
    t_cum = np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(om))])       # from lowest speed
    t_to_max = (t_cum[-1] - t_cum) * I_POLAR
    df_t = pd.DataFrame(dict(N=df["N"].values[order], t_to_100pct_s=t_to_max))
    df = df.merge(df_t, on="N")
    df.to_csv(os.path.join(ROOT, "data", f"phase4_accel_{TAG}{'_vigv' if USE_VIGV else ''}.csv"), index=False)
    print(df.round(3).to_string(index=False))
