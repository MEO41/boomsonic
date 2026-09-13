"""Phase 1: thrust available vs Mach and altitude for a 500 N SLS-rated turbojet (placeholder cycle).

Method: one pyCycle problem (DESIGN + one off-design point) per limit mode. The off-design
point is walked along a snake path through the (altitude, Mach) grid so each solve is
warm-started from a neighbouring converged state (continuation). Convergence is judged on
the off-design group's residual norm, not on the iteration count. Two max-throttle limit
modes are run (T4-limited, 100 %-mechanical-speed-limited); the lower thrust is the
thrust available, as a real ECU limits whichever of EGT or RPM is reached first.

Outputs: data/phase1_thrust_available.csv, plots/phase1_thrust_lapse.png
"""
import os, time, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from prelim_turbojet_model import build_and_run, read_point, ENGINE

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--des_MN", type=float, default=0.0); ap.add_argument("--des_alt", type=float, default=0.0)
ap.add_argument("--Fn", type=float, default=500.0); ap.add_argument("--tag", default="")
ARGS = ap.parse_args()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MACHS = [0.0, 0.3, 0.6, 0.8, 0.9, 1.0]
ALTS_M = [0, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 11000]
RES_TOL = 1e-4

def snake_path():
    path = []
    for i, h in enumerate(ALTS_M):
        ms = MACHS if i % 2 == 0 else MACHS[::-1]
        path += [(m, h) for m in ms]
    return path

def isa(h):
    T = 288.15 - 0.0065 * min(h, 11000); P = 101325 * (T / 288.15) ** 5.2559
    return T, P

def sweep(mode):
    t0 = time.time()
    prob, mp = build_and_run([(0.0, 0.0)], od_mode=mode, des_MN=ARGS.des_MN, des_alt_m=ARGS.des_alt, Fn_des_N=ARGS.Fn)
    pt = mp.od_names[0]
    grp = prob.model._get_subsystem(pt)
    res = {}
    for (m, h) in snake_path():
        prob.set_val(pt + '.fc.MN', max(m, 1e-6)); prob.set_val(pt + '.fc.alt', h, units='m')
        prob.run_model()
        norm = float(grp._residuals.get_norm())
        if norm > RES_TOL:                      # one retry from design-point-like guesses
            prob[pt + '.balance.W'] = 0.9 * ENGINE['Fn_SLS_N'] / 500 * 2.0 * isa(h)[1] / 101325
            prob[pt + '.balance.FAR'] = 0.018
            if mode == 'T4': prob[pt + '.balance.Nmech'] = ENGINE['Nmech_rpm']
            prob.run_model(); norm = float(grp._residuals.get_norm())
        d = read_point(prob, pt); d['res_norm'] = norm; d['converged'] = norm <= RES_TOL
        res[(m, h)] = d
        print(f"  [{mode}] M{m:.1f} h{h:5.0f} m  Fn={d['Fn_N']:7.1f} N  N={100*d['Nmech']/ENGINE['Nmech_rpm']:6.1f}%  "
              f"T4={d['T4_K']:6.1f} K  W={d['W_kgps']:.3f}  res={norm:.1e} {'' if d['converged'] else '<-- NOT CONVERGED'}")
    des = read_point(prob, 'DESIGN')
    print(f"  [{mode}] sweep done in {time.time()-t0:.0f} s")
    return res, des

resT4, des = sweep('T4')
resN, _ = sweep('N')

out = []
for h in ALTS_M:
    for m in MACHS:
        a, b = resT4[(m, h)], resN[(m, h)]
        cands = [d for d in (a, b) if d['converged']]
        T, P = isa(h); V = m * np.sqrt(1.4 * 287.05 * T); q = 0.7 * P * m ** 2
        row = dict(MN=m, alt_m=h, T_K=T, P_Pa=P, V_mps=V, q_Pa=q,
                   Fn_T4mode_N=a['Fn_N'], Nmech_pct_T4mode=100 * a['Nmech'] / ENGINE['Nmech_rpm'], conv_T4=a['converged'],
                   Fn_Nmode_N=b['Fn_N'], T4_Nmode_K=b['T4_K'], conv_N=b['converged'])
        if cands:
            best = min(cands, key=lambda d: d['Fn_N'])
            row.update(Fn_N=best['Fn_N'], binding='T4' if best is a else 'N', T4_K=best['T4_K'],
                       Nmech_pct=100 * best['Nmech'] / ENGINE['Nmech_rpm'], NcPct=best['NcPct'], W_kgps=best['W_kgps'],
                       Wf_kgps=best['Wf_kgps'], TSFC_kgpNh=best['TSFC_kgpNh'], OPR=best['OPR'], comp_PR=best['comp_PR'],
                       comp_eff=best['comp_eff'], NPR=best['NPR'], Vj_mps=best['Vj_mps'], Fram_N=best['Fram_N'],
                       CDS_allow_m2=best['Fn_N'] / q if q > 0 else np.nan)
        else:
            row.update(Fn_N=np.nan, binding='NONE')
        out.append(row)
df = pd.DataFrame(out)
df.to_csv(os.path.join(ROOT, "data", "phase1_thrust_available%s.csv" % ARGS.tag), index=False)
print("\nDESIGN (SLS):", {k: round(v, 4) for k, v in des.items() if isinstance(v, float)})
pd.set_option("display.width", 220)
print(df[["MN", "alt_m", "Fn_N", "binding", "Fn_T4mode_N", "Nmech_pct_T4mode", "Fn_Nmode_N", "T4_Nmode_K",
          "TSFC_kgpNh", "W_kgps", "q_Pa", "CDS_allow_m2", "conv_T4", "conv_N"]].round(4).to_string(index=False))

fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
for h in ALTS_M:
    s = df[df.alt_m == h]; ax[0].plot(s.MN, s.Fn_N, "o-", ms=3, label=f"{h/1000:.0f} km")
ax[0].set_xlabel("Mach"); ax[0].set_ylabel("net thrust available [N]"); ax[0].grid(alpha=.3); ax[0].legend(fontsize=7, title="altitude", ncol=2)
ax[0].set_title("Max-throttle thrust = min(T4-limited, N-limited)", fontsize=9)
s = df[df.MN == 1.0]
ax[1].plot(s.alt_m / 1000, s.Fn_N, "o-", label="Fn available at M1 [N]")
ax[1].plot(s.alt_m / 1000, s.Fn_T4mode_N, ":", c="gray", label="T4-limited (ignoring N limit)")
ax[1].plot(s.alt_m / 1000, s.CDS_allow_m2 * 1e4, "s--", label="allowable CD*S at M1 [cm^2]")
ax[1].set_xlabel("altitude [km]"); ax[1].grid(alpha=.3); ax[1].legend(fontsize=8); ax[1].set_title("Mach 1: thrust and drag-area budget vs altitude", fontsize=9)
fig.suptitle(f"Phase 1 preliminary: {ARGS.Fn:.0f} N @ M{ARGS.des_MN:.1f}/{ARGS.des_alt/1000:.0f} km design turbojet, OPR {ENGINE['OPR']}, T4 {ENGINE['T4_K']:.0f} K (placeholder cycle + scaled NPSS maps)", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase1_thrust_lapse%s.png" % ARGS.tag), dpi=130)
print("saved csv + plot")
