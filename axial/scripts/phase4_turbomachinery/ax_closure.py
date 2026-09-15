"""Phase 4A: apply the Phase 4A changes to the refreshed axial and close the Phase 2 <-> 4 loop (run in .venv).
Mirrors cc_closure.py.

Engine changes (raw bottom-up items, engine_mass.engine on the 3A-R design, then the 3R calibration x1.20 / x1.21):
  * rotor (ax_rotor.py, verified ROSS model): layout A, 2 mm Ti drum replacing the 'drum_ties' allowance, AISI 4340
    24 / 12 mm shaft (tunnel radius 14 mm: the Phase 4 limit under the combustor hub), 12 mm journals (DN 1.01e6 at
    MCS), soft damped supports (k 1.75e6 N/m, c 876 N s/m; cartridge mass inside the housing allowance, as 3R);
  * discs re-sized for burst >= 1.20 at MCS (ax_rotor_stress.py): + disc mass delta;
  * stage-1 thickness taper: mass-neutral (not an item);
  * variable geometry (option A, ax_operability.py final configuration), conceptual geometric estimates, each with its
    dimensions below; actuators = the project's HV servo class (Phase 2 mass budget: ~75 g each). NOT sourced from a
    fielded design: flagged provisional.
Closure: calibrated engine + accessories 1.60 kg + Phase 2 bottom-up airframe / systems at the engine's D and L x 1.15
growth + sortie fuel from the axial deck (ax_mission.py) with the real idle, iterated; take-off, dash and landing checks.
Usage: python ax_closure.py <tag>      output data/phase4ax/closure_<tag>.json
"""
import os, sys, json, copy, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))
import engine_mass as em, combustor_sizing as cs, mission_drag_polar as mdp, airframe_model as afm, mass_budget as mb
from cc_closure import mission_setup, landing
TAG = sys.argv[1]; OUT = os.path.join(AXROOT, "data", "phase4ax")
AX = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"axt_{TAG}.json"))); F = AX["levels"]["fielded"]; cal = AX["calibration"]
comp, cyc = F["comp"], F["eval"]["cycle"]; rpm = comp["input"]["rpm"]
turb = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"{TAG}_ttf_out.json")))
RS = json.load(open(os.path.join(OUT, f"rotor_stress_{TAG}.json"))); OPF = json.load(open(os.path.join(OUT, f"operability_{TAG}_final.json")))
MIS = json.load(open(os.path.join(OUT, f"mission_{TAG}.json")))
SHAFT_OD, SHAFT_ID, TUNNEL_R, JOURNAL, T_DRUM = 0.024, 0.012, 0.014, 0.012, 0.002
SERVO = 0.075

def vg_hardware(cfg):
    """conceptual masses [kg] with the stated dimensions (mm): VIGV, start / handling bleed, variable nozzle."""
    s1 = comp["stages"][0]; r_t, r_h, h1, c1 = s1["rotor"]["r_tip"], s1["rotor"]["r_hub"], s1["rotor"]["h"], s1["rotor"]["chord"]
    it = {}
    if cfg["vigv"]:
        Z_igv = s1["stator"]["Z"]                                                   # IGV count = stage-1 stator count (provisional)
        c_v = 0.8 * c1; vanes = Z_igv * em.RHO["Ti"] * 0.7 * c_v * (0.07 * c_v) * h1   # Ti vanes, t/c 0.07, chord 0.8 x rotor 1
        pivots = Z_igv * em.RHO["steel"] * np.pi / 4 * 0.003 ** 2 * 0.020            # 3 mm x 20 mm spindles
        levers = Z_igv * em.RHO["steel"] * 0.012 * 0.004 * 0.0015                    # 12 x 4 x 1.5 mm crank arms
        ring = em.RHO["steel"] * 2 * np.pi * (r_t + 0.012) * 0.006 * 0.002          # unison ring 6 x 2 mm
        it["VIGV vanes + spindles + levers + unison ring"] = vanes + pivots + levers + ring; it["VIGV actuator (servo)"] = SERVO
    if cfg["bleed"] > 0:
        r_c = comp["stages"][2]["stator"]["r_tip"] + 0.004
        it["bleed manifold (Al ring 25 x 1 mm) + band valve (SS 20 x 0.5 mm)"] = em.RHO["Al"] * 2 * np.pi * r_c * 0.025 * 1e-3 + em.RHO["SS"] * 2 * np.pi * r_c * 0.020 * 0.5e-3
        it["bleed valve actuator (servo)"] = SERVO
    if cfg["a8_max"] > 1.0:
        r8 = np.sqrt(cyc["A8_cm2"] / 1e4 / np.pi) * np.sqrt(cfg["a8_max"])          # flaps sized for the largest area
        L_f = 0.6 * 2 * r8; n_f = 12
        flaps = em.RHO["SS"] * (2 * np.pi * r8 * 1.3) * L_f * 0.6e-3                 # 12 overlapping flaps (30 % overlap), 0.6 mm IN/SS sheet
        ring = em.RHO["SS"] * 2 * np.pi * (r8 + 0.010) * 0.008 * 0.002 + n_f * em.RHO["steel"] * np.pi / 4 * 0.003 ** 2 * 0.015
        it["variable nozzle flaps + sync ring + hinges"] = flaps + ring; it["variable nozzle actuator (servo, heat-shielded)"] = SERVO
    return it

def engine_4a():
    comb_all, _ = cs.combustor(cyc["Pt3_kPa"] * 1e3, cyc["Tt3_K"], cyc["W_kgps"])
    base = em.engine(cyc, "axial", comp, turb, comb_all["mean"], rpm)                # 3A-R engine (reproduces the axt file)
    e = em.engine(cyc, "axial", comp, turb, comb_all["mean"], rpm, shaft_od=SHAFT_OD, shaft_id=SHAFT_ID, tunnel_r=TUNNEL_R)
    items = dict(e["items"]); items.pop("fasteners_seals_balancing_10pct")
    # drum: 2 mm Ti shell at the mean disc-rim radius over the drum length (rotor_model geometry) replaces the 10 % tie allowance
    r_bar = np.mean([s["rotor"]["r_hub"] for s in comp["stages"]]); L_d = sum(1.25 * (s["rotor"]["chord"] + s["stator"]["chord"]) for s in comp["stages"][:-1])
    items["drum_ties"] = em.RHO["Ti"] * 2 * np.pi * r_bar * L_d * T_DRUM
    items["rotor_discs"] += RS["disc_check"]["mass_delta_kg"]
    items.update(vg_hardware(OPF["config"]))
    items["fasteners_seals_balancing_10pct"] = 0.10 * sum(items.values())
    raw = sum(items.values())
    return dict(base_raw=base["dry_mass_kg"], raw=raw, cal=raw * cal["K_M"], lo=raw * cal["K_M_lo"], hi=raw * cal["K_M_hi"], L_cal=e["L_engine_mm"] * cal["K_L"], D=e["D_engine_mm"],
                items=items, D_breakdown=e["D_breakdown"], combustor=comb_all["mean"], drum=dict(r_mean_mm=r_bar * 1e3, L_mm=L_d * 1e3, t_mm=T_DRUM * 1e3))

if __name__ == "__main__":
    p4 = engine_4a()
    assert abs(p4["base_raw"] - F["eval"]["engine"]["dry_mass_kg"]) < 1e-6, "3A-R engine not reproduced"
    print(f"3A-R engine {F['engine_cal']['dry_mass_kg']:.3f} kg cal -> Phase 4A {p4['cal']:.3f} kg ({p4['lo']:.2f}-{p4['hi']:.2f}), L {p4['L_cal']:.0f} mm, D {p4['D']:.1f} mm")
    Cfg = mission_setup(p4["D"] / 1e3, p4["L_cal"] / 1e3, os.path.join(OUT, f"mission_{TAG}_deck.csv"), MIS["idle_frac"])
    c = Cfg(S_wing=0.30); items = mb.bottom_up(c); af = sum(items.values())
    empty = p4["cal"] + 1.60 + af * (1 + mb.GROWTH); M = empty + 3.0; res = {}
    for it in range(8):
        s, seg = mdp.run(0.30, E_WD=None, M0=M); fuel = s["fuel_total_kg"] * (1 + mb.UNUSABLE); M_new = empty + fuel
        if abs(M_new - M) < 0.005: break
        M = M_new
    for E in ("nom", "hi"):
        Ew = None if E == "nom" else max(3.0, max(1.8, c.E_geom()))
        s, seg = mdp.run(0.30, E_WD=Ew, M0=M); res[E] = dict(summary=s, segments=seg)
    m_land = res["nom"]["summary"]["m_landing"]
    land = {f"{'flaps' if fl else 'no flaps'}{' + chute' if ch else ''}, mu 0.3": landing(Cfg, m_land, flap=fl, mu_b=0.3, chute=ch)[0] for fl in (True, False) for ch in (True, False)}
    budget = {"engine (Phase 4A, calibrated)": p4["cal"], "engine accessories (A3.7)": 1.60}
    grp = {"structure": ["fuselage", "inlet", "engine mounts", "wing", "tails"], "landing gear + chute": ["landing gear", "drag chute"],
           "fuel system": ["fuel tank"], "systems + avionics + instrumentation": ["servos", "flight controller", "flight batteries", "wiring", "prize", "flight termination"]}
    for gname, keys in grp.items(): budget[gname] = sum(v for k, v in items.items() if any(k.startswith(x) for x in keys))
    budget["growth allowance 15 %"] = af * mb.GROWTH; budget["fuel (sortie + reserve + 3 % unusable)"] = fuel; budget["TOGW"] = M; budget["margin to 25 kg"] = 25.0 - M
    # variant: engine shut down at the top of descent (idle thrust ~ 5x the approach drag makes a powered idle descent
    # and approach impossible): descent and pattern engine-off (glide), dead-stick landing; the 120 s reserve is kept at
    # the real idle fuel flow. Fuel of the descent / pattern segments removed from the Phase 2 mission model.
    wf_idle = MIS["idle"]["Wf_kgps"]; mdp.IDLE_FRAC = 1e-9; M2 = empty + 3.0
    for it in range(8):
        s2, seg2 = mdp.run(0.30, E_WD=None, M0=M2); fuel2 = (s2["fuel_used_kg"] + wf_idle * mdp.RESERVE_S) * (1 + mb.UNUSABLE); M2n = empty + fuel2
        if abs(M2n - M2) < 0.005: break
        M2 = M2n
    s2h, _ = mdp.run(0.30, E_WD=max(3.0, max(1.8, c.E_geom())), M0=M2)
    variant = dict(note="engine off from the top of descent; glide + dead-stick landing with the chute; reserve 120 s at idle fuel flow",
                   fuel_kg=fuel2, TOGW=M2, margin_to_25=25.0 - M2, dash_margin_nom=s2["dash_margin"], dash_margin_hi=s2h["dash_margin"])
    mdp.IDLE_FRAC = MIS["idle_frac"]
    out = dict(tag=TAG, variant_engine_off_descent=variant, changes=dict(shaft_od_mm=SHAFT_OD * 1e3, shaft_id_mm=SHAFT_ID * 1e3, journal_mm=JOURNAL * 1e3, tunnel_r_mm=TUNNEL_R * 1e3, drum_mm=T_DRUM * 1e3,
                                     vg=OPF["config"]), engine=p4, budget=budget, airframe_items=items, missions=res, landing_m=land, m_landing=m_land)
    json.dump(out, open(os.path.join(OUT, f"closure_{TAG}.json"), "w"), indent=1, default=float)
    print("VG / rotor items:", {k: round(v, 3) for k, v in p4["items"].items() if any(w in k for w in ("VIGV", "bleed", "nozzle", "drum", "shaft"))})
    print("mass budget:"); [print(f"  {k:42s} {v:6.2f} kg") for k, v in budget.items()]
    for E in ("nom", "hi"):
        s = res[E]["summary"]; sg = pd.DataFrame(res[E]["segments"])
        print(f"{E}: dash margin {100*s['dash_margin']:+.1f} %, time to dash {s['time_to_dash_s']:.1f} s, ground roll {s['ground_roll_m']:.0f} m, fuel {s['fuel_total_kg']:.2f} kg, "
              f"transonic min excess {sg.excess_min_N.iloc[3]:.0f} N")
    print("landing distance at", round(m_land, 2), "kg:", {k: round(v) for k, v in land.items()})
    print("variant engine-off descent:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in variant.items()})
