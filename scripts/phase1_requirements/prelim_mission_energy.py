"""Phase 1: candidate mission profiles for the Mach-1 dash, compared on numbers.

Point-mass energy integration of: level acceleration near sea level -> constant-Mach climb to
the dash altitude -> level acceleration to Mach 1 -> 7 s hold -> idle descent -> landing.
Thrust available and max-throttle fuel flow come from the pyCycle sweep
(data/phase1_thrust_available.csv, 500 N SLS placeholder engine, 100 %-N limited).

The airframe drag is NOT known yet (user statement). It is therefore parameterised on the
thrust available at the dash point:
    CD*S(M=1, h_dash) = DRAG_MARGIN * Fn_avail(M=1, h_dash) / q(M=1, h_dash)
    CD*S(M)           = CD*S(M=1) * r(M),  r = 0.5 for M <= 0.8, linear to 1.0 at M = 1.0
i.e. an assumed transonic drag-rise factor of 2 (labelled assumption A1.3; replaced by the
Phase 2 drag estimate). Lift-induced drag is neglected at these dynamic pressures
(CL < 0.05 for a 25 kg aircraft at q > 20 kPa with S ~ 0.3 m^2) and checked in Phase 2.

Outputs: data/phase1_mission_candidates.csv, plots/phase1_mission_candidates.png
"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator

import argparse
ap = argparse.ArgumentParser(); ap.add_argument("--tag", default=""); ARGS = ap.parse_args()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
df = pd.read_csv(os.path.join(ROOT, "data", "phase1_thrust_available%s.csv" % ARGS.tag))
MACHS = sorted(df.MN.unique()); ALTS = sorted(df.alt_m.unique())
def grid(col):
    return np.array([[df[(df.MN == m) & (df.alt_m == h)][col].iloc[0] for h in ALTS] for m in MACHS])
Fn_i = RegularGridInterpolator((MACHS, ALTS), grid("Fn_N"), bounds_error=False, fill_value=None)
Wf_i = RegularGridInterpolator((MACHS, ALTS), grid("Wf_kgps"), bounds_error=False, fill_value=None)

G = 9.80665
def isa(h):
    T = 288.15 - 0.0065 * min(h, 11000.0); P = 101325.0 * (T / 288.15) ** 5.2559
    return T, P, np.sqrt(1.4 * 287.05 * T)
def q_of(M, h):
    return 0.7 * isa(h)[1] * M ** 2

# ---- assumptions (all labelled in docs/phase1_requirements.md) ----
M0_KG = 25.0            # MTOW
DRAG_MARGIN = 0.75      # A1.2: airframe CD*S at M1 = 75 % of what thrust can overcome (25 % excess for acceleration)
RISE = 2.0              # A1.3: transonic drag-rise factor CD*S(M1)/CD*S(M<=0.8)
M_CLIMB = 0.70          # climb Mach
H_ACCEL0 = 300.0        # m, altitude of the initial level acceleration
V_LIFTOFF = 40.0        # m/s, start of airborne integration (ground roll handled in Phase 2)
HOLD_S = 7.0
IDLE_FRAC = 0.10        # A1.4: idle fuel flow as fraction of max-throttle SLS fuel flow
DESCENT_VS = 20.0       # m/s vertical speed in idle descent
RESERVE_S = 120.0       # A1.5: 2 min idle reserve + go-around allowance
DT = 0.2

def run_profile(h_dash, drag_margin=DRAG_MARGIN, rise=RISE):
    Fn_dash = float(Fn_i((1.0, h_dash))); q_dash = q_of(1.0, h_dash)
    CDS_M1 = drag_margin * Fn_dash / q_dash
    def drag(M, h):
        return q_of(M, h) * CDS_M1 * (1.0 / rise + (1.0 - 1.0 / rise) * min(1.0, max(0.0, (M - 0.8) / 0.2)))
    m = M0_KG; t = 0.0; x = 0.0
    log = []   # (phase, t, h, M, m)
    def rec(ph, h, M): log.append((ph, t, h, M, m))
    fuel = {}
    # phase 1: level accel at H_ACCEL0 from V_LIFTOFF to M_CLIMB
    h = H_ACCEL0; V = V_LIFTOFF; f0 = 0.0
    while V / isa(h)[2] < M_CLIMB:
        M = V / isa(h)[2]; T = float(Fn_i((M, h))); D = drag(M, h)
        a = (T - D) / m
        if a <= 0.05: return None
        wf = float(Wf_i((M, h))); V += a * DT; x += V * DT; m -= wf * DT; f0 += wf * DT; t += DT; rec("accel0", h, M)
    fuel["1 accel to M%.2f @ %.0f m" % (M_CLIMB, H_ACCEL0)] = f0
    # phase 2: constant-Mach climb to h_dash (excess power -> rate of climb; kinetic-energy change along the climb included)
    f1 = 0.0
    while h < h_dash:
        M = M_CLIMB; a_s = isa(h)[2]; V = M * a_s; T = float(Fn_i((M, h))); D = drag(M, h)
        dVdh = M * (-0.0065) * 0.5 * np.sqrt(1.4 * 287.05 / isa(h)[0])   # dV/dh at constant M in the troposphere
        roc = (T - D) * V / (m * G) / (1.0 + V * dVdh / G)               # energy-height correction
        if roc <= 0.1: return None
        wf = float(Wf_i((M, h))); h += roc * DT; x += V * DT; m -= wf * DT; f1 += wf * DT; t += DT; rec("climb", h, M)
    fuel["2 climb M%.2f to %.0f m" % (M_CLIMB, h_dash)] = f1
    # phase 3: level accel to M1
    f2 = 0.0; h = h_dash; V = M_CLIMB * isa(h)[2]
    while V / isa(h)[2] < 1.0:
        M = V / isa(h)[2]; T = float(Fn_i((M, h))); D = drag(M, h); a = (T - D) / m
        if a <= 0.05: return None
        wf = float(Wf_i((M, h))); V += a * DT; x += V * DT; m -= wf * DT; f2 += wf * DT; t += DT; rec("accel1", h, M)
    fuel["3 accel M%.2f->1.0 @ %.0f m" % (M_CLIMB, h_dash)] = f2
    # phase 4: hold M1 for HOLD_S (part throttle: fuel scaled by D/T)
    T = float(Fn_i((1.0, h))); D = drag(1.0, h); wf = float(Wf_i((1.0, h))) * D / T
    f3 = wf * HOLD_S; m -= f3; t += HOLD_S; x += isa(h)[2] * HOLD_S; rec("hold", h, 1.0)
    fuel["4 hold M1 %.0f s" % HOLD_S] = f3
    # phase 5: idle descent to 300 m, then landing (not modelled)
    t_desc = (h - 300.0) / DESCENT_VS; wf_idle = IDLE_FRAC * float(Wf_i((0.0, 0.0)))
    f4 = wf_idle * t_desc; m -= f4; t += t_desc; rec("descent", 300.0, 0.5)
    fuel["5 idle descent"] = f4
    fuel["6 reserve (%.0f s idle)" % RESERVE_S] = wf_idle * RESERVE_S
    T_dash, P_dash, a_dash = isa(h_dash)
    T2 = T_dash * 1.2; P2 = P_dash * 1.8929 * 0.98
    # Reynolds index relative to SLS static compressor inlet: Re ~ rho V / mu ~ (P2/T2) * sqrt(T2) / T2^0.7  (Sutherland ~T^0.7)
    Re_idx = (P2 / 101325.0) / (T2 / 288.15) ** 1.2
    return dict(h_dash_m=h_dash, Fn_avail_M1_N=Fn_dash, q_M1_Pa=q_dash, CDS_budget_cm2=1e4 * Fn_dash / q_dash,
                CDS_assumed_cm2=1e4 * CDS_M1, V_M1_mps=a_dash, energy_height_m=h_dash + a_dash ** 2 / (2 * G),
                time_to_M1_s=t - HOLD_S - t_desc, sortie_time_s=t, ground_track_km=x / 1000.0,
                fuel_total_kg=sum(fuel.values()), fuel_no_reserve_kg=sum(v for k, v in fuel.items() if not k.startswith("6")),
                fuel_frac=sum(fuel.values()) / M0_KG, T2_dash_K=T2, P2_dash_kPa=P2 / 1000, Re_index_dash=Re_idx,
                P3_dash_kPa=P2 * float(df[(df.MN == 1.0) & (df.alt_m == h_dash)].comp_PR.iloc[0]) / 1000 if h_dash in ALTS else np.nan,
                **{"fuel_" + k: v for k, v in fuel.items()}), log

CANDS = {"A: low dash 1 km": 1000.0, "B: mid dash 3 km": 3000.0, "C: mid dash 5 km": 5000.0, "D: high dash 10 km": 10000.0}
rows, logs = [], {}
for name, hd in CANDS.items():
    r = run_profile(hd)
    if r is None:
        print(name, ": INFEASIBLE with these assumptions"); continue
    res, log = r; res["candidate"] = name; rows.append(res); logs[name] = log
out = pd.DataFrame(rows).set_index("candidate")
out.to_csv(os.path.join(ROOT, "data", "phase1_mission_candidates%s.csv" % ARGS.tag))
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 40)
print(out.T.round(3).to_string())

# sensitivity: fuel vs drag margin and drag-rise factor for each candidate
print("\nSensitivity: total fuel [kg] (with reserve)")
sens = []
for name, hd in CANDS.items():
    for dm in (0.6, 0.75, 0.9):
        for rs in (1.5, 2.0, 3.0):
            r = run_profile(hd, dm, rs)
            sens.append(dict(candidate=name, drag_margin=dm, rise=rs, fuel_kg=(r[0]["fuel_total_kg"] if r else np.nan),
                             time_to_M1_s=(r[0]["time_to_M1_s"] if r else np.nan)))
sens = pd.DataFrame(sens)
print(sens.pivot_table(index=["candidate", "rise"], columns="drag_margin", values="fuel_kg").round(2).to_string())
sens.to_csv(os.path.join(ROOT, "data", "phase1_mission_sensitivity%s.csv" % ARGS.tag), index=False)

fig, ax = plt.subplots(1, 3, figsize=(14, 4))
for name, log in logs.items():
    L = np.array([(t, h, M, m) for _, t, h, M, m in log])
    ax[0].plot(L[:, 0], L[:, 1] / 1000, label=name); ax[1].plot(L[:, 0], L[:, 2], label=name)
ax[0].set_xlabel("time [s]"); ax[0].set_ylabel("altitude [km]"); ax[0].grid(alpha=.3); ax[0].legend(fontsize=8)
ax[1].set_xlabel("time [s]"); ax[1].set_ylabel("Mach"); ax[1].grid(alpha=.3)
fk = [c for c in out.columns if c.startswith("fuel_") and c[5].isdigit()]
bottom = np.zeros(len(out))
for c in fk:
    ax[2].bar(range(len(out)), out[c], bottom=bottom, label=c[5:]); bottom += out[c].values
ax[2].set_xticks(range(len(out))); ax[2].set_xticklabels([i.split(":")[0] for i in out.index]); ax[2].set_ylabel("fuel [kg]"); ax[2].legend(fontsize=7)
ax[2].set_title("fuel by phase (drag margin %.2f, rise %.1f)" % (DRAG_MARGIN, RISE), fontsize=9)
fig.suptitle("Phase 1 candidate mission profiles, 25 kg MTOW, placeholder engine table %s (N/T4-limited thrust)" % (ARGS.tag or "SLS-design"), fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase1_mission_candidates%s.png" % ARGS.tag), dpi=130)
print("saved")
