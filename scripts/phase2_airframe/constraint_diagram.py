"""Phase 2 constraint diagram (ADRpy 0.2.6, run in .venv-np1).

  .venv-np1/Scripts/python scripts/phase2_airframe/constraint_diagram.py

ADRpy supplies the constraint equations (take-off, climb, cruise = Mach-1 dash, sustained turn,
service ceiling). Two deliberate departures from ADRpy defaults, both logged:
  1. CDminclean is NOT a constant: the fuselage is sized by the engine, so its drag area is fixed
     while wing/tail drag scales with S. For each wing loading W/S -> S = W_TO/(W/S) and a
     separate ADRpy AircraftConcept is built with CDminclean = CD*S(S, M, h)/S from the Phase 2
     drag table (data/phase2_drag_table.csv), at the Mach/altitude of that constraint.
  2. Thrust lapse from the pyCycle deck of the D1.1 engine, not ADRpy's generic bpr/throttle-
     ratio model: ADRpy is called with map2sl=False (T/W at the flight condition) and mapped to
     sea-level-static T/W with Fn_SLS / Fn_avail(M, h). ADRpy's own map2sl result is plotted
     for comparison.
Landing is added (ADRpy has no landing-distance constraint): alpha-limited touchdown,
braked ground roll (Raymer ch. 17 form).
Outputs: plots/phase2_constraint_diagram.png, data/phase2_constraints.csv
"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from ADRpy import constraintanalysis as ca, atmospheres as at, unitconversions as co

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
G0 = 9.80665
MTOW = 25.0; W_TO = MTOW * G0
atm = at.Atmosphere()

# ---------- inputs from other phases ----------
dt = pd.read_csv(os.path.join(ROOT, "data", "phase2_drag_table.csv"))
deck = pd.read_csv(os.path.join(ROOT, "data", "phase1_thrust_available_dash5km.csv"))
mis = pd.read_csv(os.path.join(ROOT, "data", "phase2_mission_vs_wing_area.csv"))
INSTALL = 0.97                                    # A2.3 installation loss 3 %
MS = sorted(deck.MN.unique()); HS = sorted(deck.alt_m.unique())
Fn_i = RegularGridInterpolator((MS, HS), np.array([[deck[(deck.MN == m) & (deck.alt_m == h)].Fn_N.iloc[0] for h in HS] for m in MS]),
                               bounds_error=False, fill_value=None)
FN_SLS = float(Fn_i((0.0, 0.0)))
TW_AVAIL = INSTALL * FN_SLS / W_TO

def table(S, M, h, col="CDS_m2", case="nom"):
    d = dt[(dt.E_case == case) & (dt.alt_m == h)]
    Ss = sorted(d.S_wing.unique()); Mm = sorted(d.MN.unique())
    grid = np.array([[d[(d.S_wing == s) & (d.MN == m)][col].iloc[0] for m in Mm] for s in Ss])
    return float(RegularGridInterpolator((Ss, Mm), grid)((S, M)))

nom = mis[mis.E_case == "nom"].sort_values("S_wing")
def wfrac(col, S): return float(np.interp(S, nom.S_wing, nom[col])) / MTOW
# ---------- design brief (Phase 1 mission + Phase 2 choices; see docs/phase2_airframe.md) ----------
M_DASH, H_DASH = 1.02, 5000.0
T5, a5 = atm.airtemp_k(H_DASH), None
def ktas(M, h): return co.mps2kts(M * atm.vsound_mps(h))
def kias(M, h):
    V = M * atm.vsound_mps(h); return co.mps2kts(V * np.sqrt(atm.airdens_kgpm3(h) / atm.airdens_kgpm3(0)))
BRIEF = dict(rwyelevation_m=0.0, groundrun_m=150.0,
             climbalt_m=2500.0, climbspeed_kias=kias(0.70, 2500.0), climbrate_fpm=50.0 / 0.00508,
             cruisealt_m=H_DASH, cruisespeed_ktas=ktas(M_DASH, H_DASH), cruisethrustfact=0.75,
             stloadfactor=3.0, turnalt_m=H_DASH, turnspeed_ktas=ktas(0.90, H_DASH),
             servceil_m=6000.0, secclimbspd_kias=kias(0.70, 6000.0))
ALPHA_ROT = 12.0; CL_GROUND = 0.10; MU_R = 0.05; GEAR_DCDS = 30e-4
SWEEP25 = float(np.degrees(np.arctan(np.tan(np.radians(55.0)) - 4 / 3.0 * 0.25 * (1 - 0.2) / (1 + 0.2))))

WS = np.arange(300, 1601, 20.0)
rows = []
for ws in WS:
    S = W_TO / ws
    Sq = float(np.clip(S, 0.15, 0.80))
    CLa_low = table(Sq, 0.05, 0.0, "CLa")
    CLrot = CLa_low * np.radians(ALPHA_ROT)
    def concept(M, h, cd0, wf_climb, extra_perf=None):
        # sweep_25_deg passed explicitly: ADRpy 0.2.6 default (constraintanalysis.py:392) has an operator-
        # precedence bug, 2*LE + 5*MT/7 instead of (2*LE + 5*MT)/7 -> 143.6 deg here -> CL_alpha 1.23 instead of 2.87/rad
        design = dict(aspectratio=3.0, sweep_le_deg=55.0, sweep_mt_deg=47.0, sweep_25_deg=SWEEP25, bpr=0, tr=1.0, weight_n=W_TO,
                      weightfractions=dict(climb=wf_climb, cruise=wfrac("m_at_dash", Sq), turn=wf_climb, servceil=wf_climb))
        perf = dict(CDTO=table(Sq, 0.05, 0.0) / Sq + GEAR_DCDS / Sq + table(Sq, 0.05, 0.0, "k") * CL_GROUND ** 2,
                    CLTO=CL_GROUND, CLmaxTO=CLrot, CLmaxclean=CLrot, mu_R=MU_R, CDminclean=cd0,
                    etaprop=dict(take_off=0, climb=0, cruise=0, turn=0, servceil=0))
        return ca.AircraftConcept(BRIEF, design, perf, atm)
    r = dict(WS_Pa=ws, S_m2=S)
    # take-off (sea level, low speed)
    c = concept(0.05, 0.0, table(Sq, 0.05, 0.0) / Sq, 1.0)
    tw_to, vlof_to, _ = c.twrequired_to([ws], map2sl=False)
    r["TO_cond"] = float(tw_to); r["V_LOF"] = float(vlof_to)
    r["TO_sls"] = r["TO_cond"] * FN_SLS / float(Fn_i((vlof_to / np.sqrt(2) / 340.3, 0.0)))
    r["TO_adrpy_sls"] = float(c.twrequired_to([ws], map2sl=True)[0])
    # climb M0.70 / 2.5 km, 50 m/s
    wf = wfrac("m_at_dash", Sq) * 0.5 + 0.5          # mid-climb mass
    c = concept(0.70, 2500.0, table(Sq, 0.70, 2500.0) / Sq, wf)
    r["CLIMB_cond"] = float(c.twrequired_clm([ws], map2sl=False)); r["CLIMB_sls"] = r["CLIMB_cond"] * FN_SLS / float(Fn_i((0.70, 2500.0)))
    r["CLIMB_adrpy_sls"] = float(c.twrequired_clm([ws], map2sl=True))
    # dash = ADRpy cruise at M1.02 / 5 km with 25 % thrust margin (cruisethrustfact 0.75)
    for case in ("nom", "hi"):
        c = concept(M_DASH, H_DASH, table(Sq, M_DASH, H_DASH, case=case) / Sq, wf)
        r[f"DASH_{case}_cond"] = float(c.twrequired_crs([ws], map2sl=False))
        r[f"DASH_{case}_sls"] = r[f"DASH_{case}_cond"] * FN_SLS / float(Fn_i((M_DASH, H_DASH)))
    r["DASH_adrpy_sls"] = float(c.twrequired_crs([ws], map2sl=True)) * 1.0
    # 3 g sustained turn M0.90 / 5 km
    wft = wfrac("m_at_dash", Sq)
    c = concept(0.90, H_DASH, table(Sq, 0.90, H_DASH) / Sq, wft)
    trn = c.twrequired_trn([ws], map2sl=False)
    r["TURN_cond"] = float(trn[0]); r["TURN_CL"] = float(trn[1]); r["TURN_sls"] = r["TURN_cond"] * FN_SLS / float(Fn_i((0.90, H_DASH)))
    # service ceiling 6 km at M0.70
    c = concept(0.70, 6000.0, table(Sq, 0.70, 5000.0) / Sq, wft)
    r["CEIL_cond"] = float(c.twrequired_sec([ws], map2sl=False)); r["CEIL_sls"] = r["CEIL_cond"] * FN_SLS / float(Fn_i((0.70, 6000.0)))
    r["CLa_low"] = CLa_low; r["CL_rot"] = CLrot
    r["ADRpy_CLa"] = float(c.liftslope_prad(mach_inf=0.1))
    rows.append(r)
df = pd.DataFrame(rows)

# ---------- landing: alpha-limited touchdown + integrated braked roll ----------
# Touchdown at alpha_TD = 12 deg (gear/tail-strike limited, Raymer ch. 11 typical 10-15 deg).
# Air segment (flare from ~5 m, 1.15 V_TD) fixed 60 m. Free roll 1 s, then brakes (mu_b on
# weight minus lift at CL_ground) + aircraft drag (+ extended gear) + optional drag chute.
# Chute: 0.60 m flat circular canopy, CD0 = 0.75 (Knacke, Parachute Recovery Systems Design
# Manual, NWC TP 6575, Table 5-1: flat circular 0.75-0.80) -> CD*S = 0.212 m2.
CHUTE_CDS = 0.75 * np.pi / 4 * 0.60 ** 2
wf_land = float(nom.m_landing.mean()) / MTOW
def CLa_of(S): return table(float(np.clip(S, 0.15, 0.8)), 0.05, 0.0, "CLa")
DCL_FLAP = 0.9 * 0.9 * 0.40 * np.cos(np.radians(35.0))     # Raymer eq. 12.21: plain flap dCl 0.9 (Table 12.2), Sflap/S 0.4, hinge sweep 35 deg
def landing_distance(S, flap, mu_b, chute, air_m=60.0, t_free=1.0, dt=0.02):
    m = MTOW * wf_land; rho = atm.airdens_kgpm3(0.0)
    CL_td = CLa_of(S) * np.radians(12.0) + (DCL_FLAP if flap else 0.0)
    V = np.sqrt(2 * m * G0 / (rho * S * CL_td)); V_td = V
    x = air_m; t = 0.0
    CDS_ac = table(float(np.clip(S, 0.15, 0.8)), 0.05, 0.0) + GEAR_DCDS
    CL_g = 0.10 + (DCL_FLAP if flap else 0.0)
    while V > 0.5:
        q = 0.5 * rho * V * V
        brake = mu_b * max(m * G0 - q * S * CL_g, 0.0) if t > t_free else MU_R * max(m * G0 - q * S * CL_g, 0.0)
        Dg = q * (CDS_ac + (CHUTE_CDS if (chute and t > 0.5) else 0.0)) + brake
        V -= Dg / m * dt; x += V * dt; t += dt
    return x, V_td, CL_td
land = []
for S in [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]:
    for flap in (False, True):
        for mu in (0.2, 0.3):
            for chute in (False, True):
                d, V, CL = landing_distance(S, flap, mu, chute)
                land.append(dict(S_m2=S, WS_TO_Pa=W_TO / S, flap=flap, mu_brake=mu, chute=chute, CL_TD=CL, V_TD_mps=V, landing_dist_m=d))
land = pd.DataFrame(land)
def ws_max(runway, flap, mu, chute):
    """bisection on S in [0.15, 0.80] (landing distance decreases monotonically with S)."""
    lo, hi = 0.15, 0.80
    if landing_distance(lo, flap, mu, chute)[0] <= runway: return W_TO / lo      # capped at the table edge
    if landing_distance(hi, flap, mu, chute)[0] > runway: return np.nan
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        if landing_distance(mid, flap, mu, chute)[0] <= runway: hi = mid
        else: lo = mid
    return W_TO / hi
landlim = []
for rw in (300, 500, 800):
    for flap in (False, True):
        for chute in (False, True):
            for mu in (0.2, 0.3):
                landlim.append(dict(runway_m=rw, flap=flap, chute=chute, mu_brake=mu, WS_max_Pa=ws_max(rw, flap, mu, chute)))
landlim = pd.DataFrame(landlim); landlim["S_min_m2"] = W_TO / landlim.WS_max_Pa
landlim.to_csv(os.path.join(ROOT, "data", "phase2_landing_limits.csv"), index=False)
df.to_csv(os.path.join(ROOT, "data", "phase2_constraints.csv"), index=False)
land.to_csv(os.path.join(ROOT, "data", "phase2_landing_distances.csv"), index=False)

pd.set_option("display.width", 220)
print(f"Fn_SLS = {FN_SLS:.1f} N, installed T/W available (SLS) = {TW_AVAIL:.3f}, landing weight fraction = {wf_land:.3f}")
print(f"CL_alpha low speed (Raymer 12.6, ours) median = {df.CLa_low.median():.3f}/rad; ADRpy liftslope_prad(M0.1) = {df.ADRpy_CLa.median():.3f}/rad")
print(df[["WS_Pa", "S_m2", "TO_sls", "TO_adrpy_sls", "V_LOF", "CLIMB_sls", "CLIMB_adrpy_sls", "DASH_nom_sls", "DASH_hi_sls", "DASH_adrpy_sls",
          "TURN_sls", "TURN_CL", "CEIL_sls"]].round(3).to_string(index=False))
print(land[(land.mu_brake == 0.3)].round(2).to_string(index=False))
print(landlim.round(3).to_string(index=False))
# feasible W/S window: dash lower bound (T/W avail) vs landing upper bounds
def ws_dash(col):
    y = df[col].values - TW_AVAIL; i = np.where(np.diff(np.sign(y)) != 0)[0]
    return float(np.interp(0, [y[i[0]], y[i[0] + 1]], [df.WS_Pa.values[i[0]], df.WS_Pa.values[i[0] + 1]])) if len(i) else np.nan
WS_DASH_NOM, WS_DASH_HI = ws_dash("DASH_nom_sls"), ws_dash("DASH_hi_sls")
print(f"dash lower bound W/S (25 kg): nominal {WS_DASH_NOM:.0f} Pa (S <= {W_TO/WS_DASH_NOM:.3f} m2), pessimistic {WS_DASH_HI:.0f} Pa (S <= {W_TO/WS_DASH_HI:.3f} m2)")
pd.DataFrame([dict(WS_dash_nom=WS_DASH_NOM, WS_dash_hi=WS_DASH_HI, S_max_nom=W_TO/WS_DASH_NOM, S_max_hi=W_TO/WS_DASH_HI, TW_avail=TW_AVAIL)]).to_csv(
    os.path.join(ROOT, "data", "phase2_dash_bounds.csv"), index=False)

# ---------- plot ----------
fig, ax = plt.subplots(figsize=(9.5, 6))
ax.plot(df.WS_Pa, df.TO_sls, label="take-off, 150 m ground roll")
ax.plot(df.WS_Pa, df.CLIMB_sls, label="climb 50 m/s @ M0.70, 2.5 km")
ax.plot(df.WS_Pa, df.DASH_nom_sls, lw=2.5, label="dash M1.02 @ 5 km, 25 % margin (E_WD nominal)")
ax.plot(df.WS_Pa, df.DASH_hi_sls, "--", lw=2, c=ax.lines[-1].get_color(), label="dash, pessimistic E_WD = 3.0")
ax.plot(df.WS_Pa, df.DASH_adrpy_sls, ":", c="gray", label="dash nominal, ADRpy generic thrust lapse (comparison)")
ax.plot(df.WS_Pa, df.TURN_sls, label="3 g sustained turn @ M0.90, 5 km")
ax.plot(df.WS_Pa, df.CEIL_sls, label="service ceiling 6 km")
ax.axhline(TW_AVAIL, c="k", lw=2, label=f"available: {FN_SLS:.0f} N SLS x 0.97 / 25 kg = {TW_AVAIL:.2f}")
cols = {300: "tab:red", 500: "tab:purple", 800: "tab:brown"}
for _, l in landlim[(landlim.mu_brake == 0.3) & (landlim.flap) & (~landlim.chute)].iterrows():
    if np.isnan(l.WS_max_Pa): continue
    ax.axvline(l.WS_max_Pa, c=cols[l.runway_m], ls="--", lw=1.4)
    ax.text(l.WS_max_Pa - 8, 0.08, f"landing limit {l.runway_m:.0f} m runway\n(plain flap, no chute)", rotation=90, fontsize=7, va="bottom", ha="right", color=cols[l.runway_m])
    ax.annotate("", xy=(l.WS_max_Pa - 60, 0.6), xytext=(l.WS_max_Pa, 0.6), arrowprops=dict(arrowstyle="->", color=cols[l.runway_m]))
ax.text(1530, 1.45, "with 0.6 m drag chute: landing on 300 m\nfeasible at every W/S shown (S >= 0.15 m2)", fontsize=7.5, ha="right",
        bbox=dict(fc="white", ec="gray", alpha=.9))
ws_des = W_TO / 0.30
ax.plot([ws_des], [TW_AVAIL], "k*", ms=16, zorder=5)
ax.annotate("design point S = 0.30 m2\n(shown at the 25 kg ceiling;\nestimated TOGW 18.8 kg)", (ws_des, TW_AVAIL), xytext=(ws_des + 80, 1.95), fontsize=7.5, bbox=dict(fc="white", ec="gray", alpha=.9),
            arrowprops=dict(arrowstyle="->"))
ax.axvspan(W_TO / 0.323, 1600, ymin=0, ymax=TW_AVAIL / 3.6, color="green", alpha=0.06)
ax.set_xlabel("take-off wing loading W/S [Pa]"); ax.set_ylabel("sea-level-static T/W required (pyCycle lapse)")
ax.set_ylim(0, 3.6); ax.set_xlim(WS[0], WS[-1]); ax.grid(alpha=.3); ax.legend(fontsize=7, loc="upper left", ncol=2)
sec = ax.secondary_xaxis("top", functions=(lambda w: W_TO / np.maximum(w, 1), lambda s: W_TO / np.maximum(s, 1e-3)))
sec.set_xlabel("wing area S [m2] at 25 kg")
ax.set_title("Phase 2 constraint diagram at the 25 kg ceiling, D1.1 engine (pyCycle lapse). Shaded: feasible for nominal drag with a drag chute", fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase2_constraint_diagram.png"), dpi=140)
print("saved")
