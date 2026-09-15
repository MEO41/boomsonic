"""Phase 7 step 4: the afterburner itself -- diffuser, flameholder, flame stabilisation,
liner cooling, length and mass.

The cycle says an afterburner is worth about +79 % thrust at the dash.  This script asks what it
physically is, and the answer is dominated by one thing nobody budgeted for: LENGTH.  The flow
leaves the turbine at about Mach 0.6 in a 75 cm2 annulus and has to be diffused to the afterburner
duct Mach before anything can be burnt, and a diffuser that does not separate is long.

What is computed rather than assumed
------------------------------------
* The real turbine-exit state, from the frozen engine's own TurboFlow turbine geometry, not from
  the cycle's assumed turb.MN = 0.45.  (That assumption is the same one Phase 6A traced as the
  cause of F6A.5 on the axial engine, and it is present here too -- see F7.4.)
* Diffuser length from an equivalent-cone-angle limit, swept against the afterburner duct Mach,
  so the duct Mach is chosen on a length/thrust trade instead of being assumed.
* Flameholder dry pressure loss from a bluff-body blockage relation -- which is what justifies
  (or refutes) the 2 % dry loss assumed in ab_common.A7.3.
* Flame stabilisation: Cantera ignition delay and, where it converges, laminar flame speed of the
  ACTUAL vitiated mixture at the afterburner inlet, compared with the recirculation-zone residence
  time.  At 972 K the afterburner inlet is above the autoignition temperature of the fuel, which
  changes what stabilisation means here.
* Liner cooling flow from a wall energy balance, and the resulting core-stream penalty.

Outputs: data/phase7/ab_hardware.json, ab_duct_mach_length.csv, plots/phase7_ab_hardware.png
Usage:   .venv\\Scripts\\python scripts\\phase7_afterburner\\ab_hardware.py
"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("OPENMDAO_REPORTS", "0")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ab_common as ac

ac.ensure_dirs()
fz = ac.frozen_cycle()
R_GAS = 287.8
GAM5 = 1.3265

# --- stated assumptions (design_log A7.x) ----------------------------------------------------
THETA_EQ_DEG = 7.0        # A7.8  equivalent-cone half-angle limit for an attached conical diffuser
                          #       (Idelchik, Handbook of Hydraulic Resistance, diffusers section; the
                          #       same source Phase 2 used for the intake diffuser).  10 and 12 deg are
                          #       swept alongside because afterburner diffusers routinely run steeper
                          #       with struts and accept some separation.
BLOCKAGE = 0.30           # A7.9  V-gutter flameholder blockage ratio
CD_GUTTER = 1.4           # A7.10 bluff-body drag coefficient of a V-gutter
N_GUTTER_RINGS = 2        # A7.11
U_OVER_U = 0.10           # A7.14 turbulence intensity u'/U in the afterburner duct
LINER_T = 0.6e-3          # m
CASING_T = 1.0e-3         # m
RHO_IN625 = 8440.0
RHO_HAST_X = 8220.0
T_LINER_MAX = 1200.0      # K, conceptual metal-temperature limit for a sheet Hastelloy-X liner (A7.12)


def turbine_exit():
    """The frozen engine's real turbine exit, from TurboFlow's own geometry."""
    t = json.load(open(os.path.join(ac.D3R, "%s_ttf70_out.json" % ac.TAG)))
    g = t["geometry"]
    A = float(g["A_out"][-1])
    r_hub, r_tip = float(g["radius_hub_out"][-1]), float(g["radius_tip_out"][-1])
    W5 = fz["W_kgps"] * (1 + fz["FAR"])
    Tt5, Pt5 = fz["Tt5_K"], fz["Pt5_kPa"] * 1e3
    MN = ac.mach_from_area(W5, Tt5, Pt5, A, GAM5, R_GAS)
    V = float(t["overall"]["exit_velocity"]); swirl = float(t["overall"]["exit_flow_angle"])
    Ts = Tt5 / (1 + 0.5 * (GAM5 - 1) * MN ** 2)
    a = np.sqrt(GAM5 * R_GAS * Ts)
    cap = ac.choked_flow(A, Tt5, Pt5, GAM5, R_GAS)
    return dict(A_cm2=A * 1e4, A_m2=A, r_hub_mm=r_hub * 1e3, r_tip_mm=r_tip * 1e3,
                r_equivalent_mm=np.sqrt(A / np.pi) * 1e3, W5_kgps=W5, Tt5_K=Tt5, Pt5_kPa=Pt5 / 1e3,
                MN_from_area=MN, V_axial_mps=MN * a, V_turboflow_mps=V, swirl_deg=swirl,
                cycle_assumed_MN=0.45, choke_capacity_kgps=cap, capacity_margin=cap / W5 - 1.0,
                p_out_handed_to_turboflow_kPa=float(t["input"]["p_out"]) / 1e3)


def diffuser(te, M_ab, theta_deg):
    """Length of a conical-equivalent diffuser from the turbine exit to the AB duct."""
    A2 = ac.duct_area(te["W5_kgps"], te["Tt5_K"], te["Pt5_kPa"] * 1e3, M_ab, GAM5, R_GAS)
    r1 = np.sqrt(te["A_m2"] / np.pi); r2 = np.sqrt(A2 / np.pi)
    L = (r2 - r1) / np.tan(np.radians(theta_deg))
    return dict(A_ab_cm2=A2 * 1e4, D_ab_mm=2 * r2 * 1e3, AR=A2 / te["A_m2"],
                L_diffuser_mm=L * 1e3, r_eq_in_mm=r1 * 1e3, r_eq_out_mm=r2 * 1e3)


def flameholder(te, M_ab, B=BLOCKAGE, Cd=CD_GUTTER):
    """Dry total-pressure loss of a bluff-body flameholder array in a constant-area duct.

    dPt/q1 = Cd B / (1 - B)^2 is the standard blockage form for bluff-body flameholder drag
    (Lefebvre & Ballal, Gas Turbine Combustion, afterburner chapter).  q1 is the approach dynamic
    pressure in the afterburner duct.  This is what the A7.3 dry-loss assumption should equal.
    """
    Pt = te["Pt5_kPa"] * 1e3
    Ps = ac.static_pressure(Pt, M_ab, GAM5)
    q = 0.5 * GAM5 * Ps * M_ab ** 2
    dPt = Cd * B / (1 - B) ** 2 * q
    return dict(M_ab=M_ab, q_kPa=q / 1e3, Ps_kPa=Ps / 1e3, dPt_kPa=dPt / 1e3, dPqP=dPt / Pt,
                blockage=B, Cd=Cd)


def duct_velocity(te, M_ab):
    Ts = te["Tt5_K"] / (1 + 0.5 * (GAM5 - 1) * M_ab ** 2)
    return M_ab * np.sqrt(GAM5 * R_GAS * Ts), Ts


def stabilisation(te, M_ab, d_gutter_mm=25.0):
    """Can the flame hold?  Cantera on the ACTUAL vitiated mixture at the afterburner inlet.

    The flame lives in the recirculation zone behind a V-gutter, whose residence time is about
    L_rz / U with L_rz ~ 3 d (Zukoski & Marble's bluff-body recirculation length).  Two chemical
    times are computed and they say different things:

      * AUTOIGNITION delay of a FRESH stoichiometric pocket at the afterburner inlet state.  This
        is what would matter if the afterburner could light itself.  It comes out far longer than
        the residence time here, which is the answer to a real question: at 1.45 bar this
        afterburner is NOT autoignition-stabilised despite a 972 K inlet, so it needs a
        flameholder and an igniter, not just fuel.
      * WELL-STIRRED-REACTOR blowout residence time (Longwell & Weiss; the standard model of
        bluff-body flame stabilisation, in which the recirculation zone is treated as a stirred
        reactor of hot products continuously reigniting incoming fresh mixture).  THIS is the one
        that sizes the gutter: the recirculation zone must be slower than tau_PSR or the flame
        blows out.
    """
    import cantera as ct
    # nDodecane_Reitz.yaml ships two phases: nDodecane_RK (Redlich-Kwong, the default, which a
    # reactor and a flame both refuse) and nDodecane_IG (ideal gas).  At 1.4 bar the real-gas
    # correction is irrelevant, so the ideal-gas phase is the right one here.  phase3_cycle/
    # cantera_check.py uses the default phase because it only calls equilibrate(), which accepts it.
    MECH = ("nDodecane_Reitz.yaml", "nDodecane_IG")
    U, Ts = duct_velocity(te, M_ab)
    Ps = ac.static_pressure(te["Pt5_kPa"] * 1e3, M_ab, GAM5)
    out = dict(U_mps=U, Ts_K=Ts, Ps_kPa=Ps / 1e3, d_gutter_mm=d_gutter_mm,
               L_rz_mm=3 * d_gutter_mm, tau_res_ms=3 * d_gutter_mm * 1e-3 / U * 1e3)

    # vitiated air leaving the turbine: air burnt at the main-burner FAR, equilibrated
    gas = ct.Solution(*MECH)
    air = "O2:0.2095, N2:0.7809, AR:0.0093" if "AR" in gas.species_names else "O2:0.21, N2:0.79"
    gas.TP = fz["Tt3_K"], fz["Pt3_kPa"] * 1e3
    gas.set_mixture_fraction(fz["FAR"] / (1 + fz["FAR"]), "c12h26:1", air)
    gas.equilibrate("HP")
    vit = gas.mole_fraction_dict()
    out["O2_after_main_burn_pct"] = 100 * gas["O2"].X[0]

    # stoichiometric pocket on the oxygen that is actually LEFT: C12H26 + 18.5 O2 -> 12 CO2 + 13 H2O
    g2 = ct.Solution(*MECH)
    g2.TPX = Ts, Ps, vit
    xO2 = g2["O2"].X[0]
    xfuel = xO2 / 18.5
    X = {k: v * (1 - xfuel) for k, v in vit.items()}
    X["c12h26"] = X.get("c12h26", 0.0) + xfuel
    out["phi_pocket"] = 1.0

    # --- autoignition delay of the fresh pocket
    g2.TPX = Ts, Ps, X
    r = ct.IdealGasConstPressureReactor(g2, clone=False)
    net = ct.ReactorNet([r])
    T0, t, tau = r.T, 0.0, np.nan
    while t < 0.2:
        t = net.step()
        if r.T > T0 + 400.0:
            tau = t
            break
    out["tau_ign_ms"] = tau * 1e3 if np.isfinite(tau) else np.nan
    out["Da_autoignition"] = (out["tau_res_ms"] / out["tau_ign_ms"]) if np.isfinite(tau) else np.nan
    out["autoignition_stabilised"] = bool(np.isfinite(tau) and out["Da_autoignition"] > 1.0)

    # --- well-stirred-reactor blowout residence time
    out["tau_psr_blowout_ms"], out["psr_status"] = psr_blowout(MECH, Ts, Ps, X)
    if np.isfinite(out["tau_psr_blowout_ms"]) and out["psr_status"] == "extinguished":
        out["Da_psr"] = out["tau_res_ms"] / out["tau_psr_blowout_ms"]
        out["holds_flame"] = bool(out["Da_psr"] > 1.0)
        out["d_gutter_min_mm"] = U * out["tau_psr_blowout_ms"] * 1e-3 / 3.0 * 1e3   # L_rz = 3 d > U tau_PSR
    else:
        # No extinction fold found (or the solver stopped first).  What CAN be said is the bound:
        # the reactor still burnt at the shortest residence time reached, and that bound is
        # already far below the recirculation-zone residence time.
        out["Da_psr"] = (out["tau_res_ms"] / out["tau_psr_blowout_ms"]) if np.isfinite(out["tau_psr_blowout_ms"]) else np.nan
        out["holds_flame"] = None
        out["d_gutter_min_mm"] = np.nan

    # --- laminar flame speed (needs an explicit transport model on the Solution)
    try:
        # NOTE: nDodecane_Reitz.yaml carries NO gas-phase transport data for c12h26, so a flame
        # cannot be solved with this mechanism at all (F7.x).  The call is kept so the failure is
        # recorded rather than assumed, and the turbulent flame speed used downstream is
        # turbulence-dominated (S_T ~ 2 u' >> S_L), so the missing S_L changes it by a few per cent.
        g3 = ct.Solution(*MECH, transport_model="mixture-averaged")
        g3.TPX = Ts, Ps, X
        f = ct.FreeFlame(g3, width=0.01)
        f.set_refine_criteria(ratio=3, slope=0.2, curve=0.4)
        f.solve(loglevel=0, auto=True)
        SL = float(f.velocity[0])
        out.update(S_L_mps=SL, flame_solved=True)
    except Exception as e:
        out.update(S_L_mps=np.nan, flame_solved=False, flame_error=str(e).strip().splitlines()[-1][:120])
    return out


def psr_blowout(mech, T, P, X, tau_start=0.05, factor=0.6, tau_min=1e-8):
    """Blowout residence time of a perfectly stirred reactor at (T, P, X), by CONTINUATION.

    Longwell & Weiss / Zukoski's stirred-reactor model of bluff-body flame stabilisation: the
    recirculation zone is a stirred reactor fed with fresh mixture, and below a critical residence
    time it extinguishes.  The residence time is walked DOWN, each solve restarted from the
    previous burning state, because a PSR is bistable: bisecting from a freshly equilibrated
    initial condition lands on the burning branch at every tau and reports no blowout at all.

    Returns (tau_blowout_ms, status).  status is one of
      'extinguished'  -- a genuine extinction fold was found;
      'no extinction' -- still burning at tau_min, which at a 965 K inlet is a real answer:
                         above the mixture's crossover temperature there is no extinction fold;
      'solver failed at <tau> ms' -- Cantera could not converge below that residence time.  This
                         is reported rather than papered over: it means the stirred-reactor model
                         did not answer the question, and the blowout margin rests instead on the
                         residence-time / autoignition-delay comparison alongside it.
    """
    import cantera as ct
    fresh = ct.Solution(*mech); fresh.TPX = T, P, X
    inlet = ct.Reservoir(fresh)
    exhaust = ct.Reservoir(ct.Solution(*mech))
    burning = ct.Solution(*mech); burning.TPX = T, P, X; burning.equilibrate("HP")
    state = (burning.T, burning.density, burning.Y.copy())
    tau, last = tau_start, np.nan
    while tau > tau_min:
        g = ct.Solution(*mech)
        g.TDY = state
        # Each tau gets a fresh reactor seeded from the previous burning state: continuation
        # without carrying the integrator's history, which is what kept failing.
        comb = ct.IdealGasReactor(g, clone=False)
        comb.volume = 1.0
        mfc = ct.MassFlowController(inlet, comb, mdot=comb.mass / tau)
        ct.PressureController(comb, exhaust, primary=mfc, K=0.01)
        net = ct.ReactorNet([comb])
        try:
            net.advance(300.0 * tau)
        except Exception:
            return (last * 1e3 if np.isfinite(last) else np.nan,
                    "solver failed at %.4g ms" % (tau * 1e3))
        if comb.T < T + 400.0:
            return tau * 1e3, "extinguished"
        state = (comb.T, comb.thermo.density, comb.thermo.Y.copy())
        last = tau
        tau *= factor
    return last * 1e3, "no extinction down to %.4g ms" % (tau_min * 1e3)


def combustion_length(te, M_ab, stab, n_rings=N_GUTTER_RINGS, D_ab_mm=None, u_over_U=U_OVER_U):
    """Length needed to burn out.

    The controlling mechanism here is TURBULENT FLAME SPREADING from the gutters, not
    autoignition: the stabilisation calculation shows the fresh-mixture autoignition delay is more
    than twenty times the recirculation residence time at this pressure, so the flame is held by
    the recirculation zone and then spreads.  The spreading half-angle is arctan(S_T / U), and the
    flame must cross half the gutter spacing.

    S_T is estimated as S_L + 2 u' with u' = u_over_U x U (A7.14): in the high-turbulence limit the
    turbulent flame speed is set by the turbulence, not by the chemistry, and 2 is the usual
    order-unity coefficient of Damkohler's large-scale relation.  It is an order-of-magnitude
    estimate and is flagged as such; the autoignition length is reported alongside so it is clear
    which mechanism is which.
    """
    U, _ = duct_velocity(te, M_ab)
    SL = stab.get("S_L_mps", np.nan)
    u_prime = u_over_U * U
    S_T = (SL if np.isfinite(SL) else 0.0) + 2.0 * u_prime
    ang = np.degrees(np.arctan(S_T / U))
    spacing = (D_ab_mm / 2.0) / n_rings if D_ab_mm else np.nan
    L_prop = (spacing / 2.0) / np.tan(np.radians(ang)) if np.isfinite(spacing) else np.nan
    L_ign = U * stab["tau_ign_ms"] * 1e-3 * 1e3 if np.isfinite(stab.get("tau_ign_ms", np.nan)) else np.nan
    return dict(U_mps=U, u_prime_mps=u_prime, S_L_mps=SL, S_T_mps=S_T, spread_angle_deg=ang,
                gutter_spacing_mm=spacing, L_burn_mm=L_prop, L_autoignition_mm=L_ign)


def liner_cooling(te, T7, M_ab, T_wall_max=T_LINER_MAX):
    """Fraction of the afterburner flow that has to run down the liner wall as a cooling film.

    Energy balance on a film-cooled liner: the film must absorb the radiative + convective load
    from the flame and stay below the metal limit.  At conceptual level the standard screening
    form is the film effectiveness needed:
        eta_film = (T_gas - T_wall) / (T_gas - T_coolant)
    and the cooling fraction from a film-effectiveness correlation is not available without a
    slot geometry, so what is reported is the REQUIRED effectiveness -- a number that says how
    hard the cooling job is, not a design.  A value above ~0.5 means conventional single-slot
    film cooling will not do it and a corrugated (screech) liner with continuous injection is
    needed, which is what afterburners actually use.
    """
    T_cool = te["Tt5_K"]          # there is no cold air in a turbojet afterburner: the film is
                                  # turbine-exit gas, already at 972 K.  That is the crux.
    eta_req = (T7 - T_wall_max) / (T7 - T_cool)
    return dict(T_gas_K=T7, T_wall_max_K=T_wall_max, T_coolant_K=T_cool,
                film_effectiveness_required=eta_req,
                feasible_with_simple_film=bool(eta_req < 0.5))


def ab_mass(te, M_ab, L_diff_mm, L_comb_mm, D_ab_mm, n_rings=N_GUTTER_RINGS):
    """Bottom-up afterburner-module mass (module only; the nozzle is in ab_nozzle_trade.py)."""
    r1o, r1i = te["r_tip_mm"] / 1e3, te["r_hub_mm"] / 1e3
    r2 = D_ab_mm / 2e3
    Ld, Lc = L_diff_mm / 1e3, L_comb_mm / 1e3
    # diffuser outer cone and inner tailcone
    A_out_cone = np.pi * (r1o + r2) * np.hypot(Ld, r2 - r1o)
    A_tailcone = np.pi * r1i * np.hypot(Ld, r1i)
    # combustion section: outer casing + liner (corrugated screech liner, x1.25 developed area)
    A_case = 2 * np.pi * r2 * Lc
    r_liner = r2 - 0.006
    A_liner = 2 * np.pi * r_liner * Lc * 1.25
    # V-gutter rings: developed width 2.5 x gutter width, at radii spread over the duct
    d_g = 0.025
    A_gutter = sum(2 * np.pi * (r_liner * (i + 0.5) / n_rings) * 2.5 * d_g for i in range(n_rings))
    # spray bars: 12 radial tubes 4 mm OD x 0.5 mm wall spanning the duct, plus a manifold ring
    n_bars = 12
    V_bars = n_bars * np.pi * ((2e-3) ** 2 - (1.5e-3) ** 2) * r_liner
    V_manifold = 2 * np.pi * (r2 + 0.008) * np.pi * ((4e-3) ** 2 - (3e-3) ** 2)
    m = dict(
        diffuser_outer_cone=A_out_cone * CASING_T * RHO_IN625,
        diffuser_tailcone=A_tailcone * 0.8e-3 * RHO_IN625,
        ab_outer_casing=A_case * CASING_T * RHO_IN625,
        ab_liner=A_liner * LINER_T * RHO_HAST_X,
        flameholder_gutters=A_gutter * 1.2e-3 * RHO_HAST_X,
        gutter_struts=n_rings * 3 * (0.04 * 0.015 * 1.5e-3 * RHO_HAST_X),
        spray_bars=V_bars * RHO_IN625,
        fuel_manifold=V_manifold * RHO_IN625,
        fuel_valve_and_lines=0.120,      # AB fuel shut-off / metering valve + lines, allowance (A7.13)
        igniter=0.060,                   # surface / torch igniter + lead, allowance (A7.13)
    )
    m["flanges_fasteners_10pct"] = 0.10 * sum(m.values())
    m["total"] = sum(m.values())
    return m


def sweep_duct_mach(te, machs=(0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.32, 0.35, 0.38)):
    stab_cache = {}
    rows = []
    for M in machs:
        fh = flameholder(te, M)
        ray = ac.ab_dPqP(ac.T7_DESIGN, M, Tt_in=te["Tt5_K"], dry=fh["dPqP"])
        d7 = diffuser(te, M, THETA_EQ_DEG)
        d10 = diffuser(te, M, 10.0)
        d12 = diffuser(te, M, 12.0)
        row = dict(M_ab=M, D_ab_mm=d7["D_ab_mm"], A_ab_cm2=d7["A_ab_cm2"], AR=d7["AR"],
                   L_diff_7deg_mm=d7["L_diffuser_mm"], L_diff_10deg_mm=d10["L_diffuser_mm"],
                   L_diff_12deg_mm=d12["L_diffuser_mm"],
                   dPqP_flameholder=fh["dPqP"], dPqP_rayleigh=ray["rayleigh"], dPqP_total=ray["dPqP"],
                   thermally_choked=ray["thermally_choked"],
                   fits_engine_OD=bool(d7["D_ab_mm"] + 2 * 1000 * (0.006 + CASING_T) <= ac.frozen_engine()["D_engine_mm"]))
        if not ray["thermally_choked"]:
            r = ac.design_point(T7=ac.T7_DESIGN, ab_MN=M, dry_dPqP=fh["dPqP"])
            row.update(Fn_N=r["Fn_N"], TSFC=r["TSFC_kgpNh"], A8_cm2=r["A8_cm2"])
            st = stabilisation(te, M)
            stab_cache[M] = st
            cl = combustion_length(te, M, st, D_ab_mm=d7["D_ab_mm"])
            row.update(U_mps=st["U_mps"], tau_res_ms=st["tau_res_ms"], tau_ign_ms=st["tau_ign_ms"],
                       tau_psr_ms=st["tau_psr_blowout_ms"], Da_psr=st["Da_psr"],
                       holds_flame=st["holds_flame"], d_gutter_min_mm=st["d_gutter_min_mm"],
                       S_T_mps=cl["S_T_mps"], spread_angle_deg=cl["spread_angle_deg"],
                       L_burn_mm=cl["L_burn_mm"], L_autoignition_mm=cl["L_autoignition_mm"],
                       L_total_7deg_mm=d7["L_diffuser_mm"] + cl["L_burn_mm"])
        else:
            for k in ("Fn_N", "TSFC", "A8_cm2", "U_mps", "tau_res_ms", "tau_ign_ms", "tau_psr_ms",
                      "Da_psr", "d_gutter_min_mm", "S_T_mps", "spread_angle_deg", "L_burn_mm",
                      "L_autoignition_mm", "L_total_7deg_mm"):
                row[k] = np.nan
        rows.append(row)
        print("  M_ab %.2f: D %6.1f  L_diff(7d) %6.1f  dPt %5.2f %%  Fn %7.1f N  tau_PSR %6.3f ms (res %5.3f)  d_min %5.1f mm  L_burn %6.1f mm"
              % (M, row["D_ab_mm"], row["L_diff_7deg_mm"], 100 * row["dPqP_total"], row.get("Fn_N", np.nan),
                 row.get("tau_psr_ms", np.nan), row.get("tau_res_ms", np.nan),
                 row.get("d_gutter_min_mm", np.nan), row.get("L_burn_mm", np.nan)), flush=True)
    return pd.DataFrame(rows), stab_cache


if __name__ == "__main__":
    te = turbine_exit()
    print("=" * 108)
    print("1. The real turbine exit (frozen engine's own TurboFlow geometry, not the cycle's assumed MN)")
    print("=" * 108)
    for k, v in te.items():
        print("   %-34s %s" % (k, ("%.4f" % v) if isinstance(v, float) else v))
    print()
    print("   NOTE: the cycle model sets turb.MN = %.2f at design; the real annulus runs at M %.3f."
          % (te["cycle_assumed_MN"], te["MN_from_area"]))
    print("   arch_trade.turb_pout used the 0.45 assumption to convert the cycle's Pt5 into the static")
    print("   pressure handed to TurboFlow (%.1f kPa).  This is the same inconsistency Phase 6A traced"
          % te["p_out_handed_to_turboflow_kPa"])
    print("   as F6A.5 on the axial engine.  It is PRE-EXISTING in the frozen design, not created here.")

    print()
    print("=" * 108)
    print("2. Afterburner duct Mach: what it costs in length and what it buys in thrust")
    print("=" * 108)
    df, stab = sweep_duct_mach(te)

    print()
    print("=" * 108)
    print("3. Flame stabilisation at the chosen duct Mach %.2f" % ac.AB_MN)
    print("=" * 108)
    st = stab.get(ac.AB_MN) or stabilisation(te, ac.AB_MN)
    for k, v in st.items():
        print("   %-34s %s" % (k, ("%.5f" % v) if isinstance(v, float) else v))

    print()
    print("=" * 108)
    print("4. Liner cooling")
    print("=" * 108)
    lc = liner_cooling(te, ac.T7_DESIGN, ac.AB_MN)
    for k, v in lc.items():
        print("   %-34s %s" % (k, ("%.4f" % v) if isinstance(v, float) else v))

    print()
    print("=" * 108)
    print("5. Length and mass of the afterburner module")
    print("=" * 108)
    out = {}
    for M_sel in (0.20, 0.30):
        row = df[np.isclose(df.M_ab, M_sel)].iloc[0]
        for theta, col in ((7.0, "L_diff_7deg_mm"), (10.0, "L_diff_10deg_mm"), (12.0, "L_diff_12deg_mm")):
            Ld, Lb = float(row[col]), float(row["L_burn_mm"])
            m = ab_mass(te, M_sel, Ld, Lb, float(row["D_ab_mm"]))
            key = "M%.2f_theta%.0f" % (M_sel, theta)
            out[key] = dict(M_ab=M_sel, theta_deg=theta, L_diffuser_mm=Ld, L_burn_mm=Lb,
                            L_module_mm=Ld + Lb, D_ab_mm=float(row["D_ab_mm"]),
                            Fn_N=float(row["Fn_N"]), dPqP=float(row["dPqP_total"]), mass=m)
            print("   M_ab %.2f, %2.0f deg diffuser: L_diff %6.1f + L_burn %6.1f = %6.1f mm,  mass %.3f kg,  Fn %7.1f N"
                  % (M_sel, theta, Ld, Lb, Ld + Lb, m["total"], row["Fn_N"]))
    print()
    print("   frozen engine length %.1f mm -> the afterburner module alone is %.0f-%.0f %% of it again"
          % (ac.frozen_engine()["L_engine_mm"] * ac.case()["calibration"]["K_L"],
             100 * min(v["L_module_mm"] for v in out.values()) / (ac.frozen_engine()["L_engine_mm"] * ac.case()["calibration"]["K_L"]),
             100 * max(v["L_module_mm"] for v in out.values()) / (ac.frozen_engine()["L_engine_mm"] * ac.case()["calibration"]["K_L"])))

    df.to_csv(os.path.join(ac.D7, "ab_duct_mach_length.csv"), index=False)
    json.dump(dict(turbine_exit=te, stabilisation=st, liner=lc, configurations=out,
                   assumptions=dict(theta_eq_deg=THETA_EQ_DEG, blockage=BLOCKAGE, Cd_gutter=CD_GUTTER,
                                    n_gutter_rings=N_GUTTER_RINGS, liner_t_mm=LINER_T * 1e3,
                                    casing_t_mm=CASING_T * 1e3, T_liner_max_K=T_LINER_MAX)),
              open(os.path.join(ac.D7, "ab_hardware.json"), "w"), indent=1, default=float)
    print("\nwrote data/phase7/ab_hardware.json and ab_duct_mach_length.csv")
