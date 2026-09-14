"""Phase 4 (centrifugal baseline): apply the Phase 4 design changes to the engine and close the Phase 2 <-> 4 loop.

Design changes (from cc_rotor_stiffening.py / the fine sweep, to put the rotor's first bending critical >= 1.26 MCS):
  * bearing span shortened: combustor liner 0.8 x the Phase 3 rule (3 x annulus height);
  * combustor grown radially into the room under the compressor diffuser (the diffuser sets the engine OD): casing OD =
    diffuser envelope - 3 mm. This keeps the combustor loading: theta ~ A_ref D_ref^0.75 rises, and with the liner
    volume A_ref L as the residence measure the volume-corrected theta_eff = theta x L / (3 D_ref) is compared with the
    7-engine reference spread (combustor_sizing.py: geometric mean, log-sigma 0.20);
  * shaft: AISI 4340 tube 32 x 25.6 mm (ID/OD 0.8) in an 18 mm-radius tunnel, 12 mm bearing journals (DN 0.95e6 at MCS);
  * soft, damped bearing supports (k ~1.75e6 N/m, c ~900 N s/m): cartridge mass not separately sourced, inside the
    bearing-housing allowance (flagged).
Closure: calibrated engine (x 1.20 mass, x 1.21 length) + accessories 1.60 kg + Phase 2 bottom-up airframe/systems (at
the engine's diameter and length) x 1.15 growth + sortie fuel from the real-map deck (Phase 3R, cycle unchanged),
iterated; then the take-off, dash, turn and landing checks at the closed mass.
Usage: python cc_closure.py [tag]      output data/phase4r_closure.json
"""
import os, sys, json, copy, numpy as np, pandas as pd
from scipy.interpolate import RegularGridInterpolator
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))
os.environ.setdefault("P3_DATA", "phase3r")
import cc_trade as ct, engine_mass as em, combustor_sizing as cs
import mission_drag_polar as mdp, airframe_model as afm, mass_budget as mb
TAG = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"
LINER_F, SHAFT_OD, SHAFT_ID, TUNNEL_R = 0.8, 0.032, 0.0256, 0.018
at = ct.at

def engine_phase4(d, liner_f=LINER_F, grow=True, shaft=True):
    L = d["levels"]["fielded"]; ev = L["eval"]; cyc = ev["cycle"]; at.OPR = d["OPR"]
    case = ct.with_blades(d["case"], L["stress"]); comp = ct.scale_cc(case["comp"], ev["scales"])
    turb = json.load(open(os.path.join(ROOT, "data", "phase3r", f"{TAG}_ttf70_out.json")))
    comb = copy.deepcopy(ev["combustor"]["mean"]); L_rule = comb["L_liner_mm"]
    D_env = em.centrifugal_compressor_mass(comp, d["rpm"] * np.pi / 30)[1]["D_mm"]
    if grow:
        Ro = (D_env - 3.0) / 2 - 1.5
        comb.update(Ro_mm=Ro, Ri_mm=cs.RI_RO * Ro, D_ref_mm=(1 - cs.RI_RO) * Ro, OD_mm=2 * (Ro + 1.5))
    comb["L_liner_mm"] = liner_f * L_rule
    th = cs.theta(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], cyc["W_kgps"], comb["Ro_mm"] / 1e3)
    ref = cs.reference_thetas(); lt = np.log(ref.theta); th_m, th_s = float(np.exp(lt.mean())), float(lt.std(ddof=1))
    th_eff = th * comb["L_liner_mm"] / (3.0 * comb["D_ref_mm"])
    kw = dict(shaft_od=SHAFT_OD, shaft_id=SHAFT_ID, tunnel_r=TUNNEL_R) if shaft else {}
    e = em.engine(cyc, "centrifugal", comp, turb, comb, d["rpm"], **kw)
    cal = d["calibration"]
    return dict(engine=e, comb=comb, dry_raw=e["dry_mass_kg"], dry_cal=e["dry_mass_kg"] * cal["K_M"], dry_lo=e["dry_mass_kg"] * cal["K_M_lo"],
                dry_hi=e["dry_mass_kg"] * cal["K_M_hi"], L_cal=e["L_engine_mm"] * cal["K_L"], D=e["D_engine_mm"],
                theta=dict(theta=th, theta_eff=th_eff, theta_ref_mean=th_m, log_sigma=th_s, sigma_units=float(np.log(th_eff / th_m) / th_s)))

def mission_setup(D_m, L_m, deck_csv, idle_frac):
    class Cfg(afm.Config):
        def __post_init__(self):
            super().__post_init__(); self.D_engine = D_m; self.L_engine = L_m
    mdp.Config = Cfg; mdp.INSTALL_LOSS = 0.0; mdp.IDLE_FRAC = idle_frac
    dk = pd.read_csv(deck_csv)
    MS, HS = sorted(dk.MN.unique()), sorted(dk.alt_m.unique())
    grid = lambda col: np.array([[dk[(dk.MN == m) & (dk.alt_m == h)][col].iloc[0] for h in HS] for m in MS])
    mdp.Fn_i = RegularGridInterpolator((MS, HS), grid("Fn_N"), bounds_error=False, fill_value=None)
    mdp.Wf_i = RegularGridInterpolator((MS, HS), grid("Wf_kgps"), bounds_error=False, fill_value=None)
    return Cfg

def landing(Cfg, m_land, S=0.30, flap=True, mu_b=0.3, chute=True, air_m=60.0, t_free=1.0, dt=0.02):
    """Phase 2 landing model (constraint_diagram.landing_distance: alpha-limited touchdown at 12 deg, braked roll, 0.6 m chute),
    with this engine's airframe drag at M 0.05 from the Phase 2 airframe model."""
    c = Cfg(S_wing=S); rho = 1.225; G0 = 9.80665
    CLa = c.CL_alpha(0.1); DCL = 0.9 * 0.9 * 0.40 * np.cos(np.radians(35.0))
    CL_td = CLa * np.radians(12.0) + (DCL if flap else 0.0)
    V = np.sqrt(2 * m_land * G0 / (rho * S * CL_td)); V_td = V; x = air_m; t = 0.0
    CDS = c.CDS(0.05, 0.0) + mdp.GEAR_DCDS; CL_g = 0.10 + (DCL if flap else 0.0); CH = 0.75 * np.pi / 4 * 0.60 ** 2
    while V > 0.5:
        q = 0.5 * rho * V * V; N_ = max(m_land * G0 - q * S * CL_g, 0.0)
        Dg = q * (CDS + (CH if (chute and t > 0.5) else 0.0)) + (mu_b if t > t_free else mdp.MU_R) * N_
        V -= Dg / m_land * dt; x += V * dt; t += dt
    return x, V_td

if __name__ == "__main__":
    d = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{TAG}.json")))
    mis = json.load(open(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}.json")))
    base = engine_phase4(d, liner_f=1.0, grow=False, shaft=False)                     # Phase 3R engine, reproduced
    p4 = engine_phase4(d)
    print(f"Phase 3R engine reproduced: {base['dry_cal']:.3f} kg (cct {d['levels']['fielded']['engine_cal']['dry_mass_kg']:.3f}), L {base['L_cal']:.0f} mm, D {base['D']:.1f} mm")
    print(f"Phase 4 engine: {p4['dry_cal']:.3f} kg ({p4['dry_lo']:.2f}-{p4['dry_hi']:.2f}), L {p4['L_cal']:.0f} mm, D {p4['D']:.1f} mm; combustor OD {p4['comb']['OD_mm']:.1f} "
          f"liner {p4['comb']['L_liner_mm']:.1f} mm; theta_eff / reference mean {p4['theta']['theta_eff']/p4['theta']['theta_ref_mean']:.3f} ({p4['theta']['sigma_units']:+.2f} sigma); "
          f"Phase 3R combustor {base['theta']['theta_eff']/base['theta']['theta_ref_mean']:.3f} ({base['theta']['sigma_units']:+.2f} sigma)")
    items_delta = {k: p4["engine"]["items"][k] - base["engine"]["items"].get(k, 0.0) for k in p4["engine"]["items"] if abs(p4["engine"]["items"][k] - base["engine"]["items"].get(k, 0.0)) > 1e-4}
    print("raw mass changes:", {k: round(v, 3) for k, v in items_delta.items()})
    # --- closure
    Cfg = mission_setup(p4["D"] / 1e3, p4["L_cal"] / 1e3, os.path.join(ROOT, "data", f"phase3r_mission_{TAG}_deck.csv"), mis["idle"]["Wf_kgps"] / mis["SLS_100"]["Wf_kgps"])
    c = Cfg(S_wing=0.30); items = mb.bottom_up(c); af = sum(items.values())
    empty = p4["dry_cal"] + 1.60 + af * (1 + mb.GROWTH)
    M = empty + 3.0; res = {}
    for it in range(8):
        s, seg = mdp.run(0.30, E_WD=None, M0=M)
        fuel = s["fuel_total_kg"] * (1 + mb.UNUSABLE)
        M_new = empty + fuel
        if abs(M_new - M) < 0.005: break
        M = M_new
    for E in ("nom", "hi"):
        Ew = None if E == "nom" else max(3.0, max(1.8, c.E_geom()))
        s, seg = mdp.run(0.30, E_WD=Ew, M0=M)
        res[E] = dict(summary=s, segments=seg)
    m_land = res["nom"]["summary"]["m_landing"]
    land = {f"{'flaps' if fl else 'no flaps'}{' + chute' if ch else ''}, mu {mu}": landing(Cfg, m_land, flap=fl, mu_b=mu, chute=ch)[0]
            for fl in (True, False) for ch in (True, False) for mu in (0.3,)}
    budget = {"engine (Phase 4, calibrated)": p4["dry_cal"], "engine accessories (A3.7)": 1.60}
    grp = {"structure": ["fuselage", "inlet", "engine mounts", "wing", "tails"], "landing gear + chute": ["landing gear", "drag chute"],
           "fuel system": ["fuel tank"], "systems + avionics + instrumentation": ["servos", "flight controller", "flight batteries", "wiring", "prize", "flight termination"]}
    for gname, keys in grp.items(): budget[gname] = sum(v for k, v in items.items() if any(k.startswith(x) for x in keys))
    budget["growth allowance 15 %"] = af * mb.GROWTH; budget["fuel (sortie + reserve + 3 % unusable)"] = fuel; budget["TOGW"] = M; budget["margin to 25 kg"] = 25.0 - M
    out = dict(tag=TAG, changes=dict(liner_factor=LINER_F, shaft_od_mm=SHAFT_OD * 1e3, shaft_id_mm=SHAFT_ID * 1e3, tunnel_r_mm=TUNNEL_R * 1e3, journal_mm=12.0),
               phase3r_engine=dict(dry_cal=base["dry_cal"], L_cal=base["L_cal"], D=base["D"], theta=base["theta"]),
               phase4_engine=dict(dry_cal=p4["dry_cal"], dry_lo=p4["dry_lo"], dry_hi=p4["dry_hi"], dry_raw=p4["dry_raw"], L_cal=p4["L_cal"], D=p4["D"],
                                  D_breakdown=p4["engine"]["D_breakdown"], combustor=p4["comb"], theta=p4["theta"], items=p4["engine"]["items"], raw_changes=items_delta),
               budget=budget, airframe_items=items, missions=res, landing_m=land, m_landing=m_land)
    json.dump(out, open(os.path.join(ROOT, "data", "phase4r_closure.json"), "w"), indent=1, default=float)
    print("\nmass budget:"); [print(f"  {k:42s} {v:6.2f} kg") for k, v in budget.items()]
    for E in ("nom", "hi"):
        s = res[E]["summary"]; sg = pd.DataFrame(res[E]["segments"])
        print(f"{E}: dash margin {100*s['dash_margin']:+.1f} %, time to dash {s['time_to_dash_s']:.1f} s, ground roll {s['ground_roll_m']:.0f} m, V_LOF {s['V_LOF_mps']:.1f} m/s, "
              f"fuel {s['fuel_total_kg']:.2f} kg, transonic min excess {sg.excess_min_N.iloc[3]:.0f} N, 3 g turn excess {s['turn3g_excess_N']:.0f} N")
    print("landing distance at", round(m_land, 2), "kg:", {k: round(v) for k, v in land.items()})
