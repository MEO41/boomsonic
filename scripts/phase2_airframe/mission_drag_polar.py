"""Phase 2: mission re-run with the airframe drag polar (replaces the Phase 1 drag assumption A1.2/A1.3).

Point-mass time integration, 25 kg MTOW, engine = D1.1 dash-design turbojet at max throttle
(data/phase1_thrust_available_dash5km.csv; linear extrapolation to M 1.02-1.05):
  0 ground roll from standstill (mu_R 0.05, CL_ground 0.1) to V_LOF = 1.1 * V_s(alpha_rot)
  1 level acceleration at 300 m to M 0.70
  2 constant-Mach M 0.70 climb to 5000 m (energy-height form, induced drag at n = 1)
  3 level acceleration at 5000 m to M_DASH = 1.02
  4 hold M_DASH for 7 s at part throttle (fuel = max-throttle flow * D/T_max)
  5 decelerate / 3 g turn-back / idle descent to 300 m (idle fuel)
  6 approach + landing (2 min idle-equivalent reserve kept in tank)
Output: data/phase2_mission_<S>.csv summary rows, per-segment thrust required vs available.
"""
import os, sys, json, numpy as np, pandas as pd
from scipy.interpolate import RegularGridInterpolator
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aero_utils import isa, G0
from airframe_model import Config, ROOT

deck = pd.read_csv(os.path.join(ROOT, "data", "phase1_thrust_available_dash5km.csv"))
MS = sorted(deck.MN.unique()); HS = sorted(deck.alt_m.unique())
def _grid(col): return np.array([[deck[(deck.MN == m) & (deck.alt_m == h)][col].iloc[0] for h in HS] for m in MS])
Fn_i = RegularGridInterpolator((MS, HS), _grid("Fn_N"), bounds_error=False, fill_value=None)
Wf_i = RegularGridInterpolator((MS, HS), _grid("Wf_kgps"), bounds_error=False, fill_value=None)
FN_SLS = float(Fn_i((0.0, 0.0)))

M0 = 25.0; M_DASH = 1.02; H_DASH = 5000.0; HOLD_S = 7.0
MU_R = 0.05; CL_GROUND = 0.10; ALPHA_ROT_DEG = 12.0
IDLE_FRAC = 0.10; RESERVE_S = 120.0; DT = 0.1
INSTALL_LOSS = 0.03       # A2.3: duct / inlet-lip / power-extraction installation loss on thrust (3 %)
GEAR_DCDS = 30e-4         # A2.4: extended gear drag area [m2] during ground roll and landing (3 wheels + legs)

def run(S, E_WD=None, M_dash=M_DASH, verbose=False, M0=None):
    M0 = globals()['M0'] if M0 is None else M0
    c = Config(S_wing=S, E_WD=E_WD)
    CLa0 = c.CL_alpha(0.1)
    CL_rot = CLa0 * np.radians(ALPHA_ROT_DEG)
    def T_av(M, h): return (1 - INSTALL_LOSS) * float(Fn_i((M, h)))
    def D(M, h, W, n=1.0, gear=False):
        q = 0.7 * isa(h)[1] * M ** 2
        CL = n * W / (q * S)
        return q * (c.CDS(M, h) + (GEAR_DCDS if gear else 0.0)) + q * S * c.k_induced(M) * CL ** 2
    m = M0; t = 0.0; x = 0.0; seg = []
    EX = [np.inf]                       # running minimum of (T_avail - D) inside the current segment
    def track(T, Dd): EX[0] = min(EX[0], T - Dd)
    def close(name, t0, x0, m0, Treq_max, Tav_min, extra=None):
        d = dict(segment=name, time_s=t - t0, dist_km=(x - x0) / 1000, fuel_kg=m0 - m, Treq_max_N=Treq_max, Tavail_min_N=Tav_min,
                 excess_min_N=EX[0] if np.isfinite(EX[0]) else np.nan)
        EX[0] = np.inf
        if extra: d.update(extra)
        seg.append(d)
    # 0 ground roll
    t0, x0, m0 = t, x, m; V = 0.0; rho = isa(0)[2]
    V_lof = 1.1 * np.sqrt(2 * M0 * G0 / (rho * S * CL_rot))
    Treq = 0; Tmin = 1e9
    while V < V_lof:
        M = V / isa(0)[3]; W = m * G0; q = 0.5 * rho * V ** 2
        L = q * S * CL_GROUND
        Dg = q * (c.CDS(max(M, 0.05), 0.0) + GEAR_DCDS) + q * S * c.k_induced(0.1) * CL_GROUND ** 2 + MU_R * (W - L)
        T = T_av(M, 0.0); a = (T - Dg) / m
        V += a * DT; x += V * DT; m -= float(Wf_i((M, 0.0))) * DT; t += DT
        Treq = max(Treq, Dg); Tmin = min(Tmin, T); track(T, Dg)
    close("0 ground roll to V_LOF", t0, x0, m0, Treq, Tmin, dict(V_LOF_mps=V_lof, CL_rot=CL_rot))
    # 1 level accel at 300 m to M0.7
    t0, x0, m0 = t, x, m; h = 300.0; a_s = isa(h)[3]; Treq = 0; Tmin = 1e9
    while V / a_s < 0.70:
        M = V / a_s; Dd = D(M, h, m * G0); T = T_av(M, h)
        V += (T - Dd) / m * DT; x += V * DT; m -= float(Wf_i((M, h))) * DT; t += DT; Treq = max(Treq, Dd); Tmin = min(Tmin, T); track(T, Dd)
    close("1 level accel 300 m to M0.70", t0, x0, m0, Treq, Tmin)
    # 2 climb at M0.7
    t0, x0, m0 = t, x, m; Treq = 0; Tmin = 1e9; roc_min = 1e9
    while h < H_DASH:
        M = 0.70; T_, P_, rho_, a_s, mu_ = isa(h); V = M * a_s
        Dd = D(M, h, m * G0); T = T_av(M, h)
        dVdh = M * 0.5 * np.sqrt(1.4 * 287.053 / T_) * (-0.0065)
        roc = (T - Dd) * V / (m * G0) / (1 + V * dVdh / G0)
        if roc <= 0.2: return None
        h += roc * DT; x += V * DT; m -= float(Wf_i((M, h))) * DT; t += DT
        Treq = max(Treq, Dd); Tmin = min(Tmin, T); roc_min = min(roc_min, roc); track(T, Dd)
    close("2 climb M0.70 to 5 km", t0, x0, m0, Treq, Tmin, dict(roc_min_mps=roc_min))
    # 3 level accel to M_dash
    t0, x0, m0 = t, x, m; h = H_DASH; a_s = isa(h)[3]; V = 0.70 * a_s; Treq = 0; Tmin = 1e9; acc_min = 1e9
    while V / a_s < M_dash:
        M = V / a_s; Dd = D(M, h, m * G0); T = T_av(M, h); acc = (T - Dd) / m
        if acc <= 0.02: return None
        V += acc * DT; x += V * DT; m -= float(Wf_i((M, h))) * DT; t += DT
        Treq = max(Treq, Dd); Tmin = min(Tmin, T); acc_min = min(acc_min, acc); track(T, Dd)
    close(f"3 level accel to M{M_dash:.2f} @ 5 km", t0, x0, m0, Treq, Tmin, dict(acc_min_mps2=acc_min))
    # 4 hold
    t0, x0, m0 = t, x, m
    Dd = D(M_dash, h, m * G0); T = T_av(M_dash, h); track(T, Dd)
    m -= float(Wf_i((M_dash, h))) * Dd / T * HOLD_S; t += HOLD_S; x += M_dash * a_s * HOLD_S
    close(f"4 hold M{M_dash:.2f} {HOLD_S:.0f} s", t0, x0, m0, Dd, T, dict(throttle_frac=Dd / T, D_over_Tmax=Dd / T))
    # 5 3 g sustained turn-back at M0.9 check (not integrated for fuel, reported as constraint) + idle descent
    Dturn = D(0.90, h, m * G0, n=3.0); Tturn = T_av(0.90, h)
    track(Tturn, Dturn)
    t0, x0, m0 = t, x, m
    wf_idle = IDLE_FRAC * float(Wf_i((0.0, 0.0))); t_desc = (h - 300.0) / 20.0
    m -= wf_idle * t_desc; t += t_desc; x += 0.6 * a_s * t_desc
    close("5 turn-back + idle descent", t0, x0, m0, Dturn, Tturn, dict(note="Treq = 3 g sustained turn at M0.90/5 km"))
    # 6 approach/landing: 60 s pattern at ~20 % throttle-equivalent fuel
    t0, x0, m0 = t, x, m
    m -= 2.0 * wf_idle * 60.0; t += 60.0
    close("6 pattern + landing", t0, x0, m0, np.nan, np.nan)
    fuel_used = M0 - m; reserve = wf_idle * RESERVE_S
    summ = dict(S_wing=S, E_WD=c._wave_info["E_WD_used"], CDS_dash_cm2=c.CDS(M_dash, H_DASH) * 1e4, fuel_used_kg=fuel_used,
                reserve_kg=reserve, fuel_total_kg=fuel_used + reserve, sortie_s=t, time_to_dash_s=sum(s["time_s"] for s in seg[:4]),
                V_LOF_mps=V_lof, ground_roll_m=seg[0]["dist_km"] * 1000, dash_throttle=seg[4]["throttle_frac"],
                dash_margin=1 / seg[4]["throttle_frac"] - 1, m_at_dash=M0 - sum(s["fuel_kg"] for s in seg[:4]),
                m_landing=m, turn3g_excess_N=Tturn - Dturn)
    return summ, seg

if __name__ == "__main__":
    rows, segs = [], {}
    for S in [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
        for E in [None, "hi"]:
            E = max(3.0, max(1.8, Config(S_wing=S).E_geom())) if E == "hi" else None
            r = run(S, E_WD=E)
            if r is None:
                rows.append(dict(S_wing=S, E_WD=E, note="INFEASIBLE")); continue
            s, seg = r; rows.append(s)
            s["E_case"] = "nom" if E is None else "hi"
            if E is None: segs[S] = seg
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ROOT, "data", "phase2_mission_vs_wing_area.csv"), index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
    print(df.round(3).to_string(index=False))
    for S in [0.30]:
        sd = pd.DataFrame(segs[S]); sd.to_csv(os.path.join(ROOT, "data", "phase2_mission_segments_S030.csv"), index=False)
        print(f"\nSegments, S = {S} m2 (nominal E_WD):"); print(sd.round(3).to_string(index=False))
