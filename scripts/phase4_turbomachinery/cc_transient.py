"""Phase 4 (centrifugal baseline): quasi-steady acceleration margin and idle-to-max acceleration time at sea-level static.

Same method as accel.py (axial), on the Phase 3R real maps (cc_mission.py: TurboFlow compressor and turbine maps, pyCycle
design point at the fielded dash point, peak-PR surge surrogate benchmarked on the P400):
at a fixed spool speed T4 is raised above its steady value (pyCycle od_mode 'NT4': speed and T4 imposed, shaft power
left unbalanced); the compressor operating point climbs toward the surge surrogate. The fuel schedule is limited by
  * constant-speed surge margin SMN >= SM_RES (5 %, as in accel.py; Rolls-Royce CN112081683A allows up to half of the ~20 %
    design margin for transients; 10 % also reported),
  * T4 <= 1150 K (no transient over-temperature).
The excess shaft power at the limit gives dN/dt = P / (I_p omega); integrating from idle to 100 % gives the minimum
surge-free, over-temperature-free acceleration time. I_p = rotor polar inertia from cc_rotor.py.
Reference: B300F (database, retailer data): 39 000 -> 105 000 rpm in 4.6 s.
Usage: python cc_transient.py <tag> <I_p kg m2>      output data/phase4r_accel_<tag>.csv
"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TAG = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"; I_P = float(sys.argv[2]) if len(sys.argv) > 2 else 1e-3
sys.argv = [sys.argv[0], TAG]
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import cc_mission as ms
T4_MAX = 1150.0

def at_speed(prob, pt, Nd, N):
    prob.set_val(pt + ".Nmech", N * Nd, units="rpm"); out = []
    for T4 in np.arange(650.0, T4_MAX + 1e-6, 20.0):
        prob.set_val(pt + ".balance.T4_target", T4 * 1.8, units="degR")
        r = ms.solve(prob, pt)
        if not r["conv"]: continue
        r["P_net_kW"] = ms.g(prob, pt + ".shaft.pwr_net", "kW"); r["T4_set"] = T4; out.append(r)
    return out

if __name__ == "__main__":
    prob, pt, Nd, _ = ms.build("NT4", 0.0, 0.0)
    rows = []
    for N in (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35):
        pts = at_speed(prob, pt, Nd, N)
        if not pts:
            rows.append(dict(N=N, note="no converged point")); continue
        ss = min(pts, key=lambda q: abs(q["P_net_kW"]))
        row = dict(N=N, T4_steady=ss["Tt4_K"], SM_steady=ss["SMN"])
        for sm_res in (0.05, 0.10):
            lim = [q for q in pts if q["P_net_kW"] > 0 and np.isfinite(q["SMN"]) and q["SMN"] >= sm_res]
            b = max(lim, key=lambda q: q["P_net_kW"]) if lim else None
            tag = f"_{int(sm_res*100)}"
            row.update({f"P_ex_kW{tag}": b["P_net_kW"] if b else 0.0, f"T4_lim{tag}": b["Tt4_K"] if b else np.nan, f"SM_lim{tag}": b["SMN"] if b else np.nan,
                        f"limit{tag}": ("T4" if b and b["T4_set"] >= T4_MAX - 1 else "surge margin") if b else "none"})
        rows.append(row); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    df = pd.DataFrame(rows).dropna(subset=["T4_steady"])
    om = df.N.values * Nd * np.pi / 30; o = np.argsort(om)
    for tag in ("_5", "_10"):
        P = df[f"P_ex_kW{tag}"].values[o] * 1e3; w = om[o]
        f = np.where(P > 0, w / np.maximum(P, 1e-9), np.inf)
        t_cum = np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(w))])
        df.loc[df.index[o], f"t_to_100pct_s{tag}"] = (t_cum[-1] - t_cum) * I_P
    df["I_p"] = I_P
    df.to_csv(os.path.join(ROOT, "data", f"phase4r_accel_{TAG}.csv"), index=False)
    pd.set_option("display.width", 220); print(df.round(3).to_string(index=False))
