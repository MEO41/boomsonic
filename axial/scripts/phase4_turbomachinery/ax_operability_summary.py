"""Phase 4A: re-evaluate the operability search points with the corrected idle rule (run in .venv).

The search run (ax_operability.py <tag> search) required every point from 100 % down to pass, but at SLS the engine is
T4-limited below 100 % speed (T4 1169 K at 100 %), so the points above the T4 limit are beyond maximum throttle. Idle =
the lowest speed from which every point up to the maximum-throttle speed passes (converged, T4 <= 1150 K, stall index
<= 1, SM >= 10 %). Also reports the maximum-throttle speed and thrust of each configuration.
Usage: python ax_operability_summary.py <tag>      output data/phase4ax/operability_<tag>_search_summary.csv
"""
import os, sys, numpy as np, pandas as pd
AXROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
TAG = sys.argv[1]; D = os.path.join(AXROOT, "data", "phase4ax")
import glob
parts = [pd.read_csv(f) for f in sorted(glob.glob(os.path.join(D, f"operability_{TAG}_cfg_*.csv")))]
sp = os.path.join(D, f"operability_{TAG}_search_points.csv")
if os.path.exists(sp): parts.append(pd.read_csv(sp))
p = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["case", "N_pct"], keep="first")
p["ok"] = p["ok"].astype(str) == "True"; p["conv"] = p["conv"].astype(str) == "True"
SM_MIN = float(os.environ.get("AXOP_SM_MIN", 0.10))
if SM_MIN != 0.10:                                       # sensitivity to the steady margin requirement
    p["ok"] = p["conv"] & (p["Tt4_K"] <= 1150.5) & (p["stall_index"] <= 1.0) & (p["SM_peak"] >= SM_MIN)
rows = []
for cfg, g in p.groupby("case", sort=False):
    g = g.sort_values("N_pct", ascending=False).reset_index(drop=True); i = 0
    while i < len(g) and g.conv[i] and g.Tt4_K[i] > 1150.5: i += 1
    top = g.iloc[i] if i < len(g) else None; low = None; fail = "none"
    for j in range(i, len(g)):
        r = g.iloc[j]
        if not r.ok:
            fail = f"{r.N_pct:.1f} %: conv {r.conv}, T4 {r.Tt4_K:.0f}, si {r.get('stall_index', np.nan):.2f} ({r.get('stall_row', '-')}), SM {r.get('SM_peak', np.nan):+.3f}"; break
        low = r.N_pct
    idle_pts = g[(g.N_pct <= (top.N_pct if top is not None else 100)) & (g.N_pct >= (low if low else 999)) & g.ok]
    rows.append(dict(config=cfg, max_throttle_pct=top.N_pct if top is not None else np.nan, Fn_max_N=top.Fn_N if top is not None else np.nan,
                     SM_at_max=top.get("SM_peak", np.nan) if top is not None else np.nan, idle_pct=low, Fn_idle_N=idle_pts.Fn_N.iloc[-1] if len(idle_pts) else np.nan,
                     Wf_idle_gps=1e3 * idle_pts.Wf_kgps.min() if len(idle_pts) else np.nan, first_fail_below=fail))
df = pd.DataFrame(rows); df.to_csv(os.path.join(D, f"operability_{TAG}_search_summary{'' if SM_MIN == 0.10 else f'_sm{int(SM_MIN*100)}'}.csv"), index=False)
pd.set_option("display.width", 250); print(df.round(3).to_string(index=False))
