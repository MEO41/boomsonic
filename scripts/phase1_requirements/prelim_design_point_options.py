"""Phase 1: where should the cycle design point (100 % corrected speed, T4max) sit?

Option A: design at SLS, Fn = 500 N. Mach-1 thrust is then whatever the N-limit allows.
Option B: design at the Mach-1 dash point (h_dash), Fn = 500 N there. SLS thrust is then a
          derived, T4/N-limited value and the engine is physically larger (more airflow).
Both are run with the same placeholder component parameters and maps so the comparison is
like-for-like. Output: data/phase1_design_point_options.csv
"""
import os, numpy as np, pandas as pd
from prelim_turbojet_model import build_and_run, read_point, ENGINE
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES_TOL = 1e-4

def run_case(label, des_MN, des_alt, od_list):
    rows = []
    for mode in ['T4', 'N']:
        prob, mp = build_and_run([od_list[0]], od_mode=mode, des_MN=des_MN, des_alt_m=des_alt)
        pt = mp.od_names[0]; grp = prob.model._get_subsystem(pt)
        des = read_point(prob, 'DESIGN')
        for (m, h) in od_list:
            prob.set_val(pt + '.fc.MN', max(m, 1e-6)); prob.set_val(pt + '.fc.alt', h, units='m'); prob.run_model()
            norm = float(grp._residuals.get_norm())
            if norm > RES_TOL:
                prob[pt + '.balance.W'] = des['W_kgps'] / 0.45359237; prob[pt + '.balance.FAR'] = 0.018
                if mode == 'T4': prob[pt + '.balance.Nmech'] = ENGINE['Nmech_rpm']
                prob.run_model(); norm = float(grp._residuals.get_norm())
            d = read_point(prob, pt)
            rows.append(dict(case=label, mode=mode, MN=m, alt_m=h, Fn_N=d['Fn_N'], Nmech_pct=100 * d['Nmech'] / ENGINE['Nmech_rpm'],
                             T4_K=d['T4_K'], W_kgps=d['W_kgps'], TSFC_kgpNh=d['TSFC_kgpNh'], OPR=d['OPR'], converged=norm <= RES_TOL))
        rows.append(dict(case=label, mode='DESIGN', MN=des['MN'], alt_m=des['alt_m'], Fn_N=des['Fn_N'], Nmech_pct=100.0, T4_K=des['T4_K'],
                         W_kgps=des['W_kgps'], TSFC_kgpNh=des['TSFC_kgpNh'], OPR=des['OPR'], converged=True))
    return rows

pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 3000.0), (1.0, 6000.0)]
rows = []
rows += run_case('A: design SLS 500N', 1e-6, 0.0, pts)
for hd in [0.0, 3000.0, 6000.0]:
    rows += run_case(f'B: design M1 @ {hd/1000:.0f} km 500N', 1.0, hd, pts)
df = pd.DataFrame(rows).drop_duplicates(subset=['case', 'mode', 'MN', 'alt_m'])
df.to_csv(os.path.join(ROOT, 'data', 'phase1_design_point_options.csv'), index=False)

# thrust available = min over converged modes, per case/point
pd.set_option('display.width', 200)
print(df.round(3).to_string(index=False))
print("\n=== thrust available (min of converged T4-/N-limited) ===")
for case, g in df[df['mode'] != 'DESIGN'].groupby('case', sort=False):
    line = []
    for (m, h), gg in g.groupby(['MN', 'alt_m']):
        c = gg[gg.converged]
        line.append(f"M{m:.0f}@{h/1000:.0f}km: {c.Fn_N.min():6.1f} N ({c.loc[c.Fn_N.idxmin(),'mode']}-lim)" if len(c) else f"M{m:.0f}@{h/1000:.0f}km: n/c")
    dsg = df[(df.case == case) & (df['mode'] == 'DESIGN')].iloc[0]
    print(f"{case:28s} design W={dsg.W_kgps:.3f} kg/s | " + " | ".join(line))
