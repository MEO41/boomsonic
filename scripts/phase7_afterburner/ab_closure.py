"""Phase 7 step 5: does the aircraft still close under 25 kg with an afterburner on it?

The afterburner adds mass, length and fuel flow, and the length and the bigger nozzle both change
the fuselage area distribution, which is what the wave drag - and therefore the dash margin - is
built on.  So this is not a bookkeeping exercise: the drag is recomputed on the longer engine.

What is recomputed
------------------
* Airframe drag with the Phase 7 engine length and the WET nozzle exit area, through the same
  Phase 2 airframe model the freeze used (airframe_model.Config), so the comparison is like for
  like.  The frozen closure left the Phase 2 placeholder nozzle / capture areas in place; both are
  set correctly here, and the effect of that correction alone is reported separately so it is not
  confused with the afterburner's own effect.
* TOGW, iterated on fuel, from the frozen Phase 4R budget plus the Phase 7 deltas.
* Afterburner fuel for the segments where it is actually used, from the real wet fuel flows of
  ab_envelope_5km.csv.  The full sortie is NOT re-flown on a wet deck (that needs a wet engine
  deck over the whole Mach-altitude grid, which has not been generated) - see the report.

Outputs: data/phase7/ab_closure.json, plots/phase7_ab_closure.png
Usage:   .venv\\Scripts\\python scripts\\phase7_afterburner\\ab_closure.py
"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("OPENMDAO_REPORTS", "0")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ab_common as ac
import airframe_model as afm

ac.ensure_dirs()
G0 = 9.80665
fz = ac.frozen_cycle()

# Phase 7 configuration choice (D7.x): afterburner duct Mach and diffuser angle, and the nozzle
# concept, both decided in ab_hardware.py / ab_nozzle_trade.py.
CONFIG_KEY = "M0.20_theta7"   # the configuration everything downstream was computed on:
                              # AB duct Mach 0.20 (the envelope and the nozzle trade both used its
                              # duct area) and the 7 deg attached-diffuser limit.  M_ab 0.30 is
                              # shorter and lighter and is recommended as follow-up work, but it was
                              # NOT carried through, so it is not closed here.
NOZZLE = "plug"


def airframe(D_engine_m, L_engine_m, A_nozzle_m2, A_capture_m2, S=0.30):
    cfg = afm.Config(S_wing=S)
    cfg.D_engine = D_engine_m
    cfg.L_engine = L_engine_m
    cfg.A_nozzle = A_nozzle_m2
    cfg.A_capture = A_capture_m2
    return cfg


def dash_point(cfg, mass_kg, Fn_N, M=None, h=None, E_WD=None):
    M = ac.M_DASH if M is None else M
    h = ac.H_DASH if h is None else h
    at = ac.isa(h)
    q = 0.5 * at["rho"] * (M * at["a"]) ** 2
    CL = mass_kg * G0 / (q * cfg.S_wing)
    kw = {} if E_WD is None else dict(E_WD=E_WD)
    cds0 = cfg.CDS(M, h, **kw)
    k = cfg.k_induced(M)
    D = q * cds0 + k * CL * CL * q * cfg.S_wing
    return dict(D_N=D, q_Pa=q, CDS0_cm2=cds0 * 1e4, margin=Fn_N / D - 1.0, CL=CL,
                D0_N=q * cds0, Di_N=k * CL * CL * q * cfg.S_wing)


if __name__ == "__main__":
    frozen = json.load(open(os.path.join(ac.ROOT, "data", "phase4r_closure.json")))
    hw = json.load(open(os.path.join(ac.D7, "ab_hardware.json")))
    noz = json.load(open(os.path.join(ac.D7, "ab_nozzle_trade.json")))
    env = pd.read_csv(os.path.join(ac.D7, "ab_envelope_5km.csv"))
    envj = json.load(open(os.path.join(ac.D7, "ab_envelope.json")))

    cfgk = hw["configurations"][CONFIG_KEY]
    m_module = cfgk["mass"]["total"]
    m_nozzle = noz[NOZZLE]["mass"]["total"]
    # the nozzle actuator: the only sourced part that was compliant on load, mounted forward
    m_actuator = 0.095 + 0.060                      # P16-50-256 (95 g) + pushrod/linkage allowance
    m_ab_fuel_system = 0.150                        # AB pump feed, shut-off valve, extra lines (A7.15)
    m_ab_total = m_module + m_nozzle + m_actuator + m_ab_fuel_system

    D_e = frozen["phase4_engine"]["D"] / 1e3
    L_dry = frozen["phase4_engine"]["L_cal"] / 1e3
    L_wet = L_dry + cfgk["L_module_mm"] / 1e3 + 0.110      # + the nozzle's own length (cowl 110 mm)
    A8_dry = noz["duty"]["A8_dry_cm2"] * 1e-4
    A8_wet = noz["duty"]["A8_wet_cm2"] * 1e-4
    A_cap = fz["A_capture_cm2"] * 1e-4

    print("=" * 104)
    print("1. What the afterburner adds")
    print("=" * 104)
    print("  configuration %s: AB duct Mach %.2f, %.0f deg diffuser" % (CONFIG_KEY, cfgk["M_ab"], cfgk["theta_deg"]))
    print("  AB module        %.3f kg   (diffuser + liner + casing + flameholder + spray bars + igniter)" % m_module)
    print("  %-16s %.3f kg" % (NOZZLE + " nozzle", m_nozzle))
    print("  actuator+linkage %.3f kg" % m_actuator)
    print("  AB fuel system   %.3f kg" % m_ab_fuel_system)
    print("  TOTAL            %.3f kg" % m_ab_total)
    print("  engine length    %.1f mm dry -> %.1f mm with the afterburner (+%.1f mm, +%.0f %%)"
          % (L_dry * 1e3, L_wet * 1e3, (L_wet - L_dry) * 1e3, 100 * (L_wet / L_dry - 1)))

    # ---- drag: three configurations, so the afterburner's own effect is separable
    print()
    print("=" * 104)
    print("2. Airframe drag at the M 1.02 / 5 km dash point")
    print("=" * 104)
    cfg_frozen_as_built = airframe(D_e, L_dry, afm.Config().A_nozzle, afm.Config().A_capture)
    cfg_dry_corrected = airframe(D_e, L_dry, A8_dry, A_cap)
    cfg_wet = airframe(D_e, L_wet, A8_wet, A_cap)

    m0 = frozen["budget"]["TOGW"]
    Fn_dry = float(env[env.MN == 1.02].Fn_dry_N.iloc[0])
    Fn_wet = float(env[env.MN == 1.02].Fn_wet_N.iloc[0])
    rows = []
    for name, cfg, Fn, mass in (("frozen closure, as built", cfg_frozen_as_built, Fn_dry, m0),
                                ("same, with the real A8 and capture", cfg_dry_corrected, Fn_dry, m0),
                                ("Phase 7, dry throttle", cfg_wet, Fn_dry, m0 + m_ab_total),
                                ("Phase 7, afterburner lit", cfg_wet, Fn_wet, m0 + m_ab_total)):
        d = dash_point(cfg, mass, Fn)
        w = cfg._wave_info
        rows.append(dict(case=name, mass_kg=mass, Fn_N=Fn, D_N=d["D_N"], margin=d["margin"],
                         CDS0_cm2=d["CDS0_cm2"], A_max_cm2=w["A_max_cm2"], E_geom=w["E_geom"],
                         E_WD=w["E_WD_used"], L_eq_m=w["l_eq"]))
    dr = pd.DataFrame(rows)
    print(dr.to_string(index=False, float_format=lambda v: "%.4f" % v))

    # pessimistic wave drag, as the freeze reported it
    pess = []
    for name, cfg, Fn, mass in (("Phase 7, dry throttle", cfg_wet, Fn_dry, m0 + m_ab_total),
                                ("Phase 7, afterburner lit", cfg_wet, Fn_wet, m0 + m_ab_total)):
        d = dash_point(cfg, mass, Fn, E_WD=2.5)
        pess.append(dict(case=name + " (pessimistic E_WD 2.5)", D_N=d["D_N"], margin=d["margin"]))
    print()
    print(pd.DataFrame(pess).to_string(index=False, float_format=lambda v: "%.4f" % v))

    # ---- fuel: how much depends entirely on WHEN the afterburner is used
    print()
    print("=" * 104)
    print("3. Fuel: the afterburner burns %.4f kg/s against %.4f kg/s dry (%.2f x)"
          % (float(env[env.MN == 1.02].Wf_wet.iloc[0]), float(fz["Wf_kgps"]),
             float(env[env.MN == 1.02].Wf_wet.iloc[0]) / float(fz["Wf_kgps"])))
    print("=" * 104)
    wf_dry = float(fz["Wf_kgps"])
    wf_wet = float(env[env.MN == 1.02].Wf_wet.iloc[0])

    # supersonic level-acceleration time at 5 km, integrated on the thrust and drag actually
    # computed in ab_envelope.py (m dV/dt = F - D), dry and wet, from M 1.00 to M 1.02.
    def accel_time(col, mass):
        e = env[(env.MN >= 1.00) & (env.MN <= 1.02)].sort_values("MN")
        a0 = ac.isa(ac.H_DASH)["a"]
        t = 0.0
        for k in range(len(e) - 1):
            r0, r1 = e.iloc[k], e.iloc[k + 1]
            exc = 0.5 * ((r0[col] - r0.D_A_N) + (r1[col] - r1.D_A_N))
            if exc <= 0:
                return np.inf
            t += mass * (r1.MN - r0.MN) * a0 / exc
        return t

    t_acc_dry = accel_time("Fn_dry_N", m0)
    t_acc_wet = accel_time("Fn_wet_N", m0)
    print("  level acceleration M 1.00 -> 1.02 at 5 km: %.2f s dry, %.2f s with the afterburner"
          % (t_acc_dry, t_acc_wet))
    print("  (the freeze's brake-release-to-M 1.02 time is 27.7 s; the supersonic part of it is this)")
    print()

    POLICIES = {
        "hold only (7 s)":
            [("mach1_hold", 7.0)],
        "supersonic acceleration + hold":
            [("supersonic_accel", t_acc_wet), ("mach1_hold", 7.0)],
        "whole acceleration + hold (upper bound)":
            [("full_accel", 27.7), ("mach1_hold", 7.0)],
    }
    fuel_by_policy = {}
    for name, segs in POLICIES.items():
        extra = sum(t * (wf_wet - wf_dry) for _, t in segs)
        fuel_by_policy[name] = extra * 1.03
        print("  %-42s wet for %5.1f s  ->  +%.3f kg fuel (incl. 3 %% unusable)"
              % (name, sum(t for _, t in segs), fuel_by_policy[name]))

    # ---- TOGW matrix over hardware configuration x afterburner usage
    print()
    print("=" * 104)
    print("4. Mass closure against 25 kg")
    print("=" * 104)
    b = dict(frozen["budget"])
    growth_key = [k for k in b if k.startswith("growth")][0]
    fuel_key = [k for k in b if k.startswith("fuel (")][0]
    base = sum(v for k, v in b.items() if k not in ("TOGW", "margin to 25 kg", growth_key, fuel_key))
    growth_frac = b[growth_key] / base
    print("  frozen TOGW %.3f kg, margin to 25 kg %.3f kg; growth allowance %.1f %% of dry items"
          % (b["TOGW"], b["margin to 25 kg"], 100 * growth_frac))
    print()

    def togw_for(m_hw, fuel_extra):
        items = base + m_hw
        return items + items * growth_frac + b[fuel_key] + fuel_extra

    matrix = []
    for key, c in sorted(hw["configurations"].items()):
        m_hw = c["mass"]["total"] + m_nozzle + m_actuator + m_ab_fuel_system
        L = c["L_module_mm"] + 110.0
        for pol, fx in fuel_by_policy.items():
            t = togw_for(m_hw, fx)
            matrix.append(dict(config=key, M_ab=c["M_ab"], theta_deg=c["theta_deg"],
                               L_added_mm=L, hardware_kg=m_hw, fuel_extra_kg=fx,
                               TOGW_kg=t, margin_kg=25.0 - t, closes=bool(t <= 25.0),
                               Fn_wet_N=c["Fn_N"]))
    mx = pd.DataFrame(matrix)
    print(mx[["config", "L_added_mm", "hardware_kg", "fuel_extra_kg", "TOGW_kg", "margin_kg", "closes", "Fn_wet_N"]]
          .to_string(index=False, float_format=lambda v: "%.3f" % v))

    sel = mx[(mx.config == CONFIG_KEY)]
    print()
    print("  SELECTED configuration %s:" % CONFIG_KEY)
    for _, r in sel.iterrows():
        pass
    chosen_fuel = fuel_by_policy["supersonic acceleration + hold"]
    togw = togw_for(m_ab_total, chosen_fuel)
    print("    hardware %.3f kg, afterburner used for the supersonic acceleration and the hold" % m_ab_total)
    print("    TOGW %.3f kg, margin to 25 kg %+.3f kg" % (togw, 25.0 - togw))

    # re-run the dash margin at the closed mass
    d_wet = dash_point(cfg_wet, togw, Fn_wet)
    d_dry = dash_point(cfg_wet, togw, Fn_dry)
    d_wet_p = dash_point(cfg_wet, togw, Fn_wet, E_WD=2.5)
    d_dry_p = dash_point(cfg_wet, togw, Fn_dry, E_WD=2.5)
    print()
    print("  at %.3f kg, M 1.02 / 5 km:" % togw)
    print("    dry throttle     thrust %7.1f N  drag %7.1f N  margin %+6.1f %%  (pessimistic %+6.1f %%)"
          % (Fn_dry, d_dry["D_N"], 100 * d_dry["margin"], 100 * d_dry_p["margin"]))
    print("    afterburner lit  thrust %7.1f N  drag %7.1f N  margin %+6.1f %%  (pessimistic %+6.1f %%)"
          % (Fn_wet, d_wet["D_N"], 100 * d_wet["margin"], 100 * d_wet_p["margin"]))

    out = dict(config=CONFIG_KEY, nozzle=NOZZLE,
               mass=dict(module=m_module, nozzle=m_nozzle, actuator=m_actuator,
                         fuel_system=m_ab_fuel_system, total=m_ab_total),
               length=dict(L_dry_mm=L_dry * 1e3, L_wet_mm=L_wet * 1e3, delta_mm=(L_wet - L_dry) * 1e3),
               drag=dr.to_dict("records"), drag_pessimistic=pess,
               fuel=dict(wf_dry_kgps=wf_dry, wf_wet_kgps=wf_wet, by_policy=fuel_by_policy,
                         t_accel_dry_s=t_acc_dry, t_accel_wet_s=t_acc_wet),
               closure=dict(TOGW_frozen=b["TOGW"], TOGW_phase7=togw, margin_to_25=25.0 - togw,
                            growth_frac=growth_frac, matrix=mx.to_dict("records")),
               dash=dict(dry=d_dry, wet=d_wet, dry_pessimistic=d_dry_p, wet_pessimistic=d_wet_p,
                         Fn_dry_N=Fn_dry, Fn_wet_N=Fn_wet),
               envelope=envj)
    json.dump(out, open(os.path.join(ac.D7, "ab_closure.json"), "w"), indent=1, default=float)
    print("\nwrote data/phase7/ab_closure.json")
