"""Phase 7 step 3: the variable nozzle.  Three concepts, decided on numbers.

The afterburner does not work without a nozzle that opens: at T7 1900 K the throat has to grow
about 54 % in area, and if it does not, the back pressure lands on the turbine and drives the
compressor towards surge -- which is open risk 4.1 of the freeze, the one with no validated
prediction method.  Phase 6A found that no compliant actuator existed for a variable nozzle next
to a 937 K jet on the axial engine; here the jet is near 1900 K, so the actuation is assessed
before anything else is believed.

Concepts
--------
  A  IRIS, continuously variable.  N hinged convergent petals on a sync ring, the classic
     afterburner nozzle.  Full authority at every AB setting.
  B  IRIS, two-position.  The same petals, but a single-acting actuator working between two hard
     stops (dry and full wet).  No intermediate AB modulation.
  C  TRANSLATING PLUG.  A conical centrebody on the axis; A8 is the annulus between a fixed cowl
     and the plug, set by the plug's axial station.  One linear actuator on the centreline.

  and, as the reference that prices what an actuator buys, a FIXED nozzle at a compromise area.

Loads are not assumed.  The internal static-pressure distribution is solved quasi-one-
dimensionally along the actual moving surface from the afterburner's own total conditions, and
integrated.  Actuator candidates are the parts Phase 6A already sourced from datasheets
(axial/data/phase6a/actuators.json), re-checked against these loads and temperatures.

Outputs: data/phase7/ab_nozzle_trade.json, ab_nozzle_loads.csv, plots/phase7_ab_nozzle.png
Usage:   .venv\\Scripts\\python scripts\\phase7_afterburner\\ab_nozzle_trade.py
"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("OPENMDAO_REPORTS", "0")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ab_common as ac

ac.ensure_dirs()
fz = ac.frozen_cycle()

# --- materials (conceptual allowables; no life analysis) -------------------------------------
RHO_IN625 = 8440.0        # kg/m3, Inconel 625 (Special Metals publication SMC-063)
RHO_STEEL = 7850.0
RHO_TI = 4430.0
T_FLAP_WALL = 0.8e-3      # m, petal sheet thickness (A7.5)
T_PLUG_WALL = 0.8e-3
N_PETALS = 12             # A7.6


# ----------------------------------------------------------------------------- quasi-1D flow
def wall_pressures(s, r_wall, W, Tt, Pt, g=ac.GAMMA_AB, R=287.8):
    """Static pressure along a convergent axisymmetric wall, quasi-1D and choked at the exit.

    s, r_wall: arc length along the wall and the local flow radius.  The local flow area is taken
    as the circle of that radius (for the iris) or an annulus (handled by the caller passing an
    effective radius).  Returns Ps(s) and M(s).
    """
    A = np.pi * np.asarray(r_wall) ** 2
    M = np.array([ac.mach_from_area(W, Tt, Pt, a, g, R, clamp=True) for a in A])
    Ps = ac.static_pressure(Pt, M, g)
    return Ps, M


# ----------------------------------------------------------------------------- concept A / B
class Iris:
    """N hinged convergent petals.  The hinge circle is the afterburner duct; each petal is a
    trapezoidal sheet closing to the throat radius.  The throat is the petal trailing edge."""

    def __init__(self, R_hinge, L_flap, n=N_PETALS):
        self.R_h, self.L, self.n = R_hinge, L_flap, n

    def beta(self, A8):
        """Petal angle from the axis for a given throat area."""
        R8 = np.sqrt(A8 / np.pi)
        s = (self.R_h - R8) / self.L
        if not -1.0 < s < 1.0:
            return np.nan
        return np.arcsin(s)

    def A8(self, beta):
        return np.pi * (self.R_h - self.L * np.sin(beta)) ** 2

    def hinge_moment(self, A8, Pt, Tt, W, P_amb, n_int=200):
        """Moment about the hinge line of one petal, from the internal static pressure acting on
        its inner face against ambient on its outer face.  Positive = tends to OPEN the petal.

        The petal is a sector of a cone; at distance t along it the flow radius is
        r(t) = R_h - t sin(beta) and the petal's circumferential width is 2 pi r(t) / n.  The
        pressure acts normal to the petal, so its moment arm about the hinge is t.
        """
        beta = self.beta(A8)
        if not np.isfinite(beta):
            return dict(M_Nm=np.nan, F_N=np.nan, beta_deg=np.nan)
        t = np.linspace(0.0, self.L, n_int)
        r = self.R_h - t * np.sin(beta)
        Ps, M = wall_pressures(t, r, W, Tt, Pt)
        w = 2 * np.pi * r / self.n
        dp = Ps - P_amb
        Mh = np.trapezoid(dp * w * t, t)
        F = np.trapezoid(dp * w, t)
        return dict(M_Nm=float(Mh), F_N=float(F), beta_deg=float(np.degrees(beta)),
                    Ps_hinge_kPa=float(Ps[0] / 1e3), Ps_throat_kPa=float(Ps[-1] / 1e3),
                    M_hinge=float(M[0]), M_throat=float(M[-1]))

    def mass(self):
        """Petals + seal petals + hinge pins + sync ring + links (geometry-based, Inconel 625)."""
        A_petal = 0.5 * (2 * np.pi * self.R_h / self.n + 2 * np.pi * np.sqrt(70.77e-4 / np.pi) / self.n) * self.L
        m_petals = self.n * A_petal * T_FLAP_WALL * RHO_IN625
        m_seals = 0.5 * m_petals                                   # interleaved seal petals, thinner and narrower
        r_ring = self.R_h + 0.012
        m_ring = 2 * np.pi * r_ring * (6e-3 * 3e-3) * RHO_STEEL    # sync ring, 6 x 3 mm section
        m_links = self.n * (0.035 * 4e-3 * 3e-3 * RHO_STEEL) * 2   # two links per petal
        m_pins = self.n * (np.pi * (2e-3) ** 2 * 0.02 * RHO_STEEL)
        return dict(petals=m_petals, seal_petals=m_seals, sync_ring=m_ring, links=m_links, pins=m_pins,
                    total=m_petals + m_seals + m_ring + m_links + m_pins)


# ----------------------------------------------------------------------------- concept C
class Plug:
    """Fixed convergent cowl with a translating conical plug.  A8 is the minimum ANNULUS between
    them, so the plug's axial station sets the area."""

    def __init__(self, R_duct, R_cowl_exit, L_cowl, r_plug_max, L_plug_fwd, L_plug_aft):
        self.R_d, self.R_e, self.L_c = R_duct, R_cowl_exit, L_cowl
        self.rp, self.Lf, self.La = r_plug_max, L_plug_fwd, L_plug_aft

    def r_cowl(self, x):
        return self.R_d + (self.R_e - self.R_d) * np.clip(x / self.L_c, 0.0, 1.0)

    def r_plug(self, x, s):
        """Plug radius at axial station x when the plug's shoulder is at station s.  Forward cone
        of length Lf rising to rp, aft cone of length La falling to a point."""
        xi = x - s
        return np.where(xi < -self.Lf, 0.0,
               np.where(xi < 0.0, self.rp * (1 + xi / self.Lf),
               np.where(xi < self.La, self.rp * (1 - xi / self.La), 0.0)))

    def A_of_x(self, x, s):
        rc, rp = self.r_cowl(x), self.r_plug(x, s)
        return np.pi * np.maximum(rc ** 2 - rp ** 2, 1e-9)

    def A8(self, s, n=400):
        x = np.linspace(0.0, self.L_c, n)
        return float(self.A_of_x(x, s).min())

    def station_for(self, A8_target, lo=None, hi=None, n=400):
        """Plug station giving the wanted throat area (A8 falls as the plug moves aft into the
        narrowing cowl, so the relation is monotonic over the useful travel)."""
        lo = 0.0 if lo is None else lo
        hi = self.L_c if hi is None else hi
        f = lambda s: self.A8(s) - A8_target
        if f(lo) * f(hi) > 0:
            return np.nan
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    def axial_force(self, s, Pt, Tt, W, P_amb, n=600):
        """Net axial pressure force on the plug: the internal static pressure acting on the plug's
        own surface, which is what the actuator has to react.  Positive = pushes the plug AFT.

        The quasi-1D static pressure is evaluated from the local annulus area; the axial component
        of the pressure on a surface of revolution is p dA_projected = p d(pi r_p^2)."""
        x = np.linspace(-self.Lf, self.L_c + self.La, n)
        A = np.pi * np.maximum(self.r_cowl(np.clip(x, 0, self.L_c)) ** 2 - self.r_plug(x, s) ** 2, 1e-9)
        Ms = np.array([ac.mach_from_area(W, Tt, Pt, a, ac.GAMMA_AB, 287.8, clamp=True) for a in A])
        Ps = np.where(np.isfinite(Ms), ac.static_pressure(Pt, Ms, ac.GAMMA_AB), P_amb)
        rp = self.r_plug(x, s)
        dAp = np.gradient(np.pi * rp ** 2, x)
        F = float(np.trapezoid(Ps * dAp, x))          # sign: +ve pressure on a forward-facing area pushes aft
        return dict(F_N=F, Ps_max_kPa=float(np.nanmax(Ps) / 1e3), Ps_throat_kPa=float(np.nanmin(Ps) / 1e3))

    def mass(self):
        slant_f = np.hypot(self.Lf, self.rp); slant_a = np.hypot(self.La, self.rp)
        A_surf = np.pi * self.rp * (slant_f + slant_a)
        m_plug = A_surf * T_PLUG_WALL * RHO_IN625
        m_cowl = 2 * np.pi * 0.5 * (self.R_d + self.R_e) * np.hypot(self.L_c, self.R_d - self.R_e) * 1.0e-3 * RHO_IN625
        m_rod = np.pi * (5e-3) ** 2 * (self.L_c + self.Lf + 0.08) * RHO_STEEL
        m_struts = 3 * (0.05 * 0.02 * 1.5e-3 * RHO_IN625)
        m_bearing = 0.04
        return dict(plug=m_plug, cowl=m_cowl, rod=m_rod, struts=m_struts, slide_bearing=m_bearing,
                    total=m_plug + m_cowl + m_rod + m_struts + m_bearing)


# ----------------------------------------------------------------------------- fixed-nozzle cost
def fixed_nozzle_cost(scales):
    """What a FIXED nozzle costs, by running the real engine on the real maps at each fixed A8.

    Dry: a nozzle sized for the afterburner is far too large dry, so the compressor runs down its
    speed line to a lower pressure ratio and the engine loses thrust.
    Wet: a nozzle sized for dry is far too small wet, so the back pressure pushes the compressor
    up towards surge.  The surge-margin surrogate is the freeze's UNVALIDATED one (risk 4.1), so
    the wet column says only which direction and roughly how far, never an absolute margin.
    """
    import ab_envelope as ae
    eng = ae.Engine()
    rows = []
    for sc in scales:
        eng._condition(ac.M_DASH, ac.H_DASH)
        eng.prob.set_val(eng.pt + ".a8s.A8_scale", sc)
        eng.prob.set_val(eng.pt + ".ab.Fl_I:FAR", 0.0)
        eng.prob.set_val(eng.pt + ".ab.dPqP", 0.0)
        d = eng._max_throttle()
        row = dict(A8_scale=sc, A8_cm2=sc * eng.A8_design * 1e4,
                   Fn_dry_N=d["Fn_N"] if d["conv"] else np.nan,
                   SMN_dry=d["SMN"] if d["conv"] else np.nan,
                   T4_dry=d["Tt4_K"] if d["conv"] else np.nan,
                   N_dry=d["N_pct"] if d["conv"] else np.nan,
                   conv_dry=d["conv"])
        # wet at the same fixed area
        far = 0.030
        w = None
        for _ in range(25):
            eng.prob.set_val(eng.pt + ".ab.Fl_I:FAR", far)
            w = eng._max_throttle()
            if not w["conv"]:
                break
            L = eng.ab_loss(w)
            if L["thermally_choked"]:
                w = None
                break
            eng.prob.set_val(eng.pt + ".ab.dPqP", L["dPqP"])
            w = eng._max_throttle()
            if not w["conv"]:
                break
            e = w["Tt7_K"] - ac.T7_DESIGN
            if abs(e) < 0.5:
                break
            far = float(np.clip(far - e * far / max(w["Tt7_K"] - w["Tt5_K"], 1.0) * 0.9, 0.0, 0.048))
        if w is not None and w["conv"] and abs(w["Tt7_K"] - ac.T7_DESIGN) < 2.0:
            row.update(Fn_wet_N=w["Fn_N"], SMN_wet=w["SMN"], T4_wet=w["Tt4_K"], N_wet=w["N_pct"],
                       W_wet=w["W_kgps"], conv_wet=True)
        else:
            row.update(Fn_wet_N=np.nan, SMN_wet=np.nan, T4_wet=np.nan, N_wet=np.nan, W_wet=np.nan, conv_wet=False)
        rows.append(row)
        print("  A8 x %.3f: dry Fn %7.1f N  SMN %6.3f   |  wet Fn %7.1f N  SMN %6.3f"
              % (sc, row["Fn_dry_N"], row["SMN_dry"], row["Fn_wet_N"], row["SMN_wet"]), flush=True)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- actuators
def actuators():
    p = os.path.join(ac.ROOT, "axial", "data", "phase6a", "actuators.json")
    return json.load(open(p))["actuators"]


def pick_actuator(acts, demand_Nm=None, demand_N=None, T_site_C=None):
    """Check each sourced actuator against a demand.  Nothing here is "selected" that fails; the
    failures are the point -- Phase 6A (D6A.2) found the axial variable nozzle had no compliant
    actuator at 937 K, and this jet is hotter."""
    out = []
    for key, a in acts.items():
        row = dict(part=key, model=a["model"], mass_kg=a["mass_kg"], T_rating_C=a["T_operating_C"])
        if "torque_rated_Nm" in a and demand_Nm is not None:
            row.update(kind="rotary", rated=a["torque_rated_Nm"], peak=a.get("torque_peak_Nm"),
                       demand=demand_Nm, utilisation_rated=demand_Nm / a["torque_rated_Nm"],
                       reduction_needed=max(1.0, demand_Nm / a["torque_rated_Nm"]))
        elif "force_max_static_N" in a and demand_N is not None:
            row.update(kind="linear", rated=a["force_max_lifted_N"], peak=a["force_max_static_N"],
                       demand=demand_N, utilisation_rated=demand_N / a["force_max_lifted_N"],
                       reduction_needed=max(1.0, demand_N / a["force_max_lifted_N"]))
        else:
            continue
        row["load_ok"] = bool(row["utilisation_rated"] <= 1.0)
        row["temp_ok"] = None if T_site_C is None else bool(T_site_C <= a["T_operating_C"][1])
        row["compliant"] = bool(row["load_ok"] and (row["temp_ok"] is not False))
        out.append(row)
    return out


if __name__ == "__main__":
    fzc = ac.frozen_cycle()
    dp = json.load(open(os.path.join(ac.D7, "ab_design_point.json")))
    env = json.load(open(os.path.join(ac.D7, "ab_envelope.json")))

    A8_dry = dp["dry"]["A8_cm2"] * 1e-4
    A8_wet = A8_dry * env["A8_scale_max"]          # worst case over the whole envelope
    R_duct = np.sqrt(dp["duct"]["A_in_cm2"] * 1e-4 / np.pi)
    Pt7 = dp["wet"]["Pt7_kPa"] * 1e3
    Tt7 = ac.T7_DESIGN
    W7 = fzc["W_kgps"] * (1 + dp["wet"]["FAR_total"])
    W5 = fzc["W_kgps"] * (1 + fzc["FAR"])
    P_amb = ac.isa(ac.H_DASH)["P"]

    print("=" * 104)
    print("Nozzle duty")
    print("=" * 104)
    print("  throat  dry %.2f cm2 (D %.1f mm)  ->  wet %.2f cm2 (D %.1f mm),  ratio %.3f"
          % (A8_dry * 1e4, 2e3 * np.sqrt(A8_dry / np.pi), A8_wet * 1e4, 2e3 * np.sqrt(A8_wet / np.pi), A8_wet / A8_dry))
    print("  wet: Pt7 %.1f kPa, Tt7 %.0f K, W7 %.4f kg/s;  ambient %.1f kPa;  AB duct radius %.1f mm"
          % (Pt7 / 1e3, Tt7, W7, P_amb / 1e3, R_duct * 1e3))

    # ---------------- concepts A / B: iris
    L_FLAP = 0.090
    iris = Iris(R_duct, L_FLAP, N_PETALS)
    rows = []
    for name, A8, Pt, Tt, W in (("dry", A8_dry, fzc["Pt5_kPa"] * 1e3, fzc["Tt5_K"], W5),
                                ("wet", A8_wet, Pt7, Tt7, W7)):
        h = iris.hinge_moment(A8, Pt, Tt, W, P_amb)
        h.update(state=name, A8_cm2=A8 * 1e4)
        rows.append(h)
    iris_df = pd.DataFrame(rows)
    beta_dry, beta_wet = iris.beta(A8_dry), iris.beta(A8_wet)
    travel_deg = float(np.degrees(beta_dry - beta_wet))
    M_total = float(np.nanmax(np.abs(iris_df.M_Nm))) * N_PETALS
    ring_r = R_duct + 0.012
    ring_force = M_total / ring_r
    iris_mass = iris.mass()

    print()
    print("=" * 104)
    print("Concept A / B  IRIS: %d hinged petals %.0f mm long on a hinge circle R %.1f mm"
          % (N_PETALS, L_FLAP * 1e3, R_duct * 1e3))
    print("=" * 104)
    print(iris_df[["state", "A8_cm2", "beta_deg", "Ps_hinge_kPa", "Ps_throat_kPa", "M_hinge", "M_throat", "F_N", "M_Nm"]]
          .to_string(index=False, float_format=lambda v: "%.4f" % v))
    print("  petal angle %.2f deg dry -> %.2f deg wet, travel %.2f deg"
          % (np.degrees(beta_dry), np.degrees(beta_wet), travel_deg))
    print("  worst hinge moment %.4f N m per petal, %.3f N m over %d petals" % (M_total / N_PETALS, M_total, N_PETALS))
    print("  sync ring at R %.1f mm -> %.0f N ring force" % (ring_r * 1e3, ring_force))
    print("  mass %.3f kg: " % iris_mass["total"] + ", ".join("%s %.3f" % (k, v) for k, v in iris_mass.items() if k != "total"))

    # ---------------- concept C: translating plug
    plug = Plug(R_duct=R_duct, R_cowl_exit=0.062, L_cowl=0.110, r_plug_max=0.045,
                L_plug_fwd=0.070, L_plug_aft=0.100)
    s_dry = plug.station_for(A8_dry)
    s_wet = plug.station_for(A8_wet)
    plug_rows = []
    for name, s, Pt, Tt, W in (("dry", s_dry, fzc["Pt5_kPa"] * 1e3, fzc["Tt5_K"], W5),
                               ("wet", s_wet, Pt7, Tt7, W7)):
        if not np.isfinite(s):
            plug_rows.append(dict(state=name, station_mm=np.nan, A8_cm2=np.nan, F_N=np.nan,
                                  Ps_max_kPa=np.nan, Ps_throat_kPa=np.nan))
            continue
        f = plug.axial_force(s, Pt, Tt, W, P_amb)
        f.update(state=name, station_mm=s * 1e3, A8_cm2=plug.A8(s) * 1e4)
        plug_rows.append(f)
    plug_df = pd.DataFrame(plug_rows)
    stroke = float(abs(plug_df.station_mm.iloc[1] - plug_df.station_mm.iloc[0])) if plug_df.station_mm.notna().all() else np.nan
    plug_mass = plug.mass()
    plug_force = float(np.nanmax(np.abs(plug_df.F_N))) if plug_df.F_N.notna().any() else np.nan

    print()
    print("=" * 104)
    print("Concept C  TRANSLATING PLUG: fixed cowl %.1f -> 62.0 mm over 110 mm, plug r_max 45.0 mm" % (R_duct * 1e3))
    print("=" * 104)
    print(plug_df[["state", "station_mm", "A8_cm2", "Ps_max_kPa", "Ps_throat_kPa", "F_N"]]
          .to_string(index=False, float_format=lambda v: "%.4f" % v))
    print("  stroke %.1f mm, worst axial pressure force on the plug %.0f N" % (stroke, plug_force))
    print("  mass %.3f kg: " % plug_mass["total"] + ", ".join("%s %.3f" % (k, v) for k, v in plug_mass.items() if k != "total"))

    # ---------------- actuator check
    acts = actuators()
    T_nozzle_C = fzc["Tt5_K"] - 273.15     # metal beside the tailpipe; the jet inside is at Tt7
    T_fwd_C = fzc["Tt2_K"] - 273.15        # compressor-face air, the only cool mounting site
    print()
    print("=" * 104)
    print("Actuators (the parts Phase 6A sourced from datasheets) against these loads")
    print("=" * 104)
    print("  mounting sites: at the nozzle %.0f C (tailpipe skin, jet inside at %.0f K)  |  forward on the"
          % (T_nozzle_C, Tt7))
    print("  compressor casing %.0f C, reached by pushrods running aft outside the engine" % T_fwd_C)
    print()
    cases = (("iris: 5 mm crank on the sync ring", dict(demand_Nm=ring_force * 0.005), None),
             ("iris: linear actuator on the ring", dict(demand_N=ring_force), None),
             ("plug: direct axial", dict(demand_N=plug_force), None))
    for label, kw, _ in cases:
        for site, T in (("at nozzle", T_nozzle_C), ("forward", T_fwd_C)):
            for r in pick_actuator(acts, T_site_C=T, **kw):
                print("  %-34s %-10s %-22s demand %8.2f rated %7.2f util %6.2f  need %5.2fx  load_ok %-5s temp_ok %-5s"
                      % (label, site, r["model"], r["demand"], r["rated"], r["utilisation_rated"],
                         r["reduction_needed"], r["load_ok"], r["temp_ok"]))
        print()

    # ---------------- the fixed-nozzle reference
    print("=" * 104)
    print("Reference: what a FIXED nozzle costs (real engine on its real maps, at the dash point)")
    print("=" * 104)
    fx = fixed_nozzle_cost([1.00, 1.15, 1.30, 1.45, 1.54])
    fx.to_csv(os.path.join(ac.D7, "ab_nozzle_fixed.csv"), index=False)
    print(fx[["A8_scale", "A8_cm2", "Fn_dry_N", "SMN_dry", "T4_dry", "N_dry",
              "Fn_wet_N", "SMN_wet", "T4_wet", "N_wet"]].to_string(index=False, float_format=lambda v: "%.4f" % v))

    out = dict(duty=dict(A8_dry_cm2=A8_dry * 1e4, A8_wet_cm2=A8_wet * 1e4, ratio=A8_wet / A8_dry,
                         D8_dry_mm=2e3 * np.sqrt(A8_dry / np.pi), D8_wet_mm=2e3 * np.sqrt(A8_wet / np.pi),
                         Pt7_kPa=Pt7 / 1e3, Tt7_K=Tt7, W7_kgps=W7, P_amb_kPa=P_amb / 1e3,
                         R_duct_mm=R_duct * 1e3),
               iris=dict(n_petals=N_PETALS, L_flap_mm=L_FLAP * 1e3,
                         beta_dry_deg=float(np.degrees(beta_dry)), beta_wet_deg=float(np.degrees(beta_wet)),
                         travel_deg=travel_deg, hinge_moment_total_Nm=M_total,
                         sync_ring_force_N=float(ring_force), sync_ring_radius_mm=ring_r * 1e3,
                         mass=iris_mass, loads=iris_df.to_dict("records")),
               plug=dict(stroke_mm=stroke, axial_force_N=plug_force, mass=plug_mass,
                         loads=plug_df.to_dict("records")),
               sites=dict(T_nozzle_C=T_nozzle_C, T_forward_C=T_fwd_C, jet_T_K=Tt7))
    json.dump(out, open(os.path.join(ac.D7, "ab_nozzle_trade.json"), "w"), indent=1, default=float)
    print("\nwrote data/phase7/ab_nozzle_trade.json and ab_nozzle_fixed.csv")
