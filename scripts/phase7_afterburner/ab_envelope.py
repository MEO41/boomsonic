"""Phase 7 step 2: how far past Mach 1 does the afterburner actually take the aircraft?

This is the question the user's answer to the Phase 7 scoping decision put first, and it is the
one that cannot be answered by a rubber-nozzle design point.  It is run on the REAL Phase 3R
component maps, at fixed geometry, with the nozzle throat scheduled, and against the airframe's
own drag.

Method
------
* The engine is the frozen one.  DESIGN is the dry dash point, so the maps scale exactly as in
  phase3_cycle/cc_mission.py and the dry deck reproduces the frozen deck (checked, --regress).
* At each flight condition the DRY point is solved first at max throttle (the lower of 100 %
  mechanical speed and T4 = 1150 K, the same ECU logic as cc_mission.deck), and its compressor
  R-line is recorded.
* The afterburner is then lit to T7 and the nozzle throat scale A8/A8_design is solved so the
  compressor returns to that same R-line.  That IS the nozzle schedule: a variable nozzle exists
  precisely so that lighting the afterburner does not move the compressor.  How far A8 has to
  travel is an output, and it is what the nozzle trade in ab_nozzle_trade.py has to deliver.
* The afterburner's Rayleigh pressure loss is recomputed at each point from the ACTUAL AB-duct
  Mach (the duct area is fixed at its design value) and the actual temperature ratio, because
  pyCycle's Combustor does not model it (F7.2).
* Intake: nose-pitot normal-shock recovery at each Mach, the same relation Phase 2/3 used.  The
  capture stream tube is reported so spillage can be judged; spillage drag is NOT in the Phase 2
  drag model (R7.x).

Drag
----
The Phase 2 airframe model states its own validity as "subsonic to M 1.05".  Above that it is an
extrapolation, so the top speed is bracketed by two methods rather than quoted as a number:
  A  the Phase 2 model as built (AeroSandbox approximate_CD_wave, which asymptotes to 0.8x its
     M 1.2 value and is documented by its authors as "likely not valid for high-supersonic");
  B  a supersonic-linear-theory floor: volume wave drag held at the slender-body value (Mach
     independent for a slender body, Ashley & Landahl), supersonic skin friction from the same
     Raymer relation, and lift-induced drag with the supersonic CL_alpha = 4/sqrt(M^2-1).
Both include the lift-induced drag of level flight at the Phase 7 closed weight.

Outputs: data/phase7/ab_envelope_5km.csv, ab_envelope_alt.csv, ab_envelope.json,
         plots/phase7_ab_envelope.png
Usage:   .venv\\Scripts\\python scripts\\phase7_afterburner\\ab_envelope.py [--regress]
"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("OPENMDAO_REPORTS", "0")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ab_common as ac
import cycle_model as cm, dash_cycle as dc

ac.ensure_dirs()
fz = ac.frozen_cycle()
G0 = 9.80665
R_GAS = 287.8                      # J/kg/K, vitiated stream at station 5 (tabular value)
# First-guess constants for the wet seed only; the secants below correct whatever they get wrong.
# Measured once from the verified T7 = 1900 K design-point solve (verify_ab_cycle.py).
GAM7, R7 = 1.2664, 287.08          # nozzle-throat gamma and gas constant at T7 1900 K
LHV_JETA = 42.8e6                  # J/kg, Jet-A lower heating value (seed only)
# Real turbine exit annulus of the frozen engine: TurboFlow's own geometry at the fielded
# redesign, data/phase3r/<tag>_ttf70_out.json -> geometry.A_out[-1] (hub 36.67, tip 61.12 mm).
A_TURB_EXIT = float(json.load(open(os.path.join(ac.D3R, "%s_ttf70_out.json" % ac.TAG)))["geometry"]["A_out"][-1])

MACHS_5KM = [1.00, 1.02, 1.05, 1.10, 1.20, 1.30, 1.40, 1.50, 1.60, 1.70, 1.80, 1.90, 2.00]
ALT_SWEEP = [(M, h) for h in (3000.0, 7000.0, 9000.0, 11000.0) for M in (1.02, 1.20, 1.40, 1.60)]

# Airframe limits that are NOT in the Phase 2 drag model but are computable, and which decide the
# answer once thrust stops being the constraint (see the report, section on what actually limits it).
Q_DESIGN_PA = 37.8e3        # dynamic pressure at the frozen M 1.02 / 5 km dash point (design_freeze 1.1 / Phase 1)
TG_EPOXY_K = 393.15         # 120 C, the conservative end of the glass-transition range for a room-temperature
                            # -cured / low-temperature-cured epoxy prepreg as used in a hobby-built composite
                            # airframe.  NOT a structural allowable: a stated screening threshold (A7.7).


# ----------------------------------------------------------------------------- engine
class Engine:
    def __init__(self, T7=ac.T7_DESIGN, eta_ab=ac.ETA_AB):
        m = ac.real_maps()
        self.smn = m["smn"]; self.T7 = T7; self.eta_ab = eta_ab
        self.prob, self.mp = cm.build(od_points=[(ac.M_DASH, ac.H_DASH)], od_mode='N',
                                      comp_map=m["cmap"], turb_map=m["tmap"],
                                      afterburner=True, ab_mode='FAR', ab_mode_design='FAR')
        self.pt = self.mp.od_names[0]
        dd, _ = dc.design(ac.OPR, ac.T4, ac.ETA_C, ac.ETA_T, prob=self.prob)
        cm.set_design(self.prob, ac.M_DASH, ac.H_DASH, ac.OPR, ac.T4, ac.ETA_C, ac.ETA_T, Fn_N=500.0,
                      duct_dPqP=dd["duct"]["dPqP"], ram_recovery=dd["ram_recovery"],
                      od_names=self.mp.od_names, od_mode='N', ab_dPqP=0.0, ab_FAR=0.0)
        self.prob["DESIGN.balance.W"] = dd["W_kgps"] / 0.45359237
        self.prob.run_model()
        self.Nd = self._g("DESIGN.Nmech", "rpm")
        self.A8_design = self._g("DESIGN.nozz.Throat:stat:area", "m**2")
        self.A_ab = self._g("DESIGN.ab.Fl_O:stat:area", "m**2")
        self.duct_dPqP = dd["duct"]["dPqP"]

        self._state_names = [n for n, _ in self.prob.model.list_outputs(implicit=True, explicit=False, out_stream=None)
                             if n.startswith(self.pt + ".")]
        self._good = self._snapshot()

    def _g(self, n, u=None):
        return float(np.ravel(self.prob.get_val(n, units=u))[0])

    # pyCycle off-design defect (CLAUDE.md, F4A.x): a diverged Newton solve leaves every implicit
    # state of the point at garbage and poisons every later point in the same problem.  The whole
    # off-design state is therefore snapshotted after each converged solve and restored after a
    # failure, and the grid is always marched from the design condition outwards.
    def _snapshot(self):
        return {n: np.ravel(self.prob.get_val(n)).copy() for n in self._state_names}

    def _restore(self, s):
        for n, v in s.items():
            try:
                self.prob[n] = v
            except Exception:
                pass

    def _solve(self):
        with np.errstate(all="ignore"):
            self.prob.run_model()
            r = cm.read(self.prob, self.pt, eta_b=ac.ETA_B, eta_ab=self.eta_ab)
            if r["res"] >= 1e-4:                       # one retry from the last converged state
                self._restore(self._good)
                self.prob.run_model()
                r = cm.read(self.prob, self.pt, eta_b=ac.ETA_B, eta_ab=self.eta_ab)
        r["conv"] = r["res"] < 1e-4
        if r["conv"]:
            self._good = self._snapshot()
        else:
            self._restore(self._good)
        for k in ("RlineMap", "NcMap", "WcMap"):
            r["comp_" + k] = self._g("%s.comp.map.%s" % (self.pt, k))
        r["SMN"] = self.smn(r["comp_NcMap"], r["comp_WcMap"]) if r["conv"] else np.nan
        return r

    def _condition(self, mn, alt):
        self.prob.set_val(self.pt + ".fc.MN", max(mn, 1e-6))
        self.prob.set_val(self.pt + ".fc.alt", alt, units="m")
        self.prob.set_val(self.pt + ".inlet.ram_recovery", ac.normal_shock_recovery(mn))

    def _max_throttle(self, n_start=1.0):
        """min(100 % mechanical speed, T4 1150 K) -- cc_mission.deck's ECU logic, unchanged.

        n_start warm-starts the T4 secant.  Lighting the afterburner behind a scheduled nozzle
        leaves the compressor where it was, so the wet point binds at almost the same speed as
        the dry one and starting there cuts the solve count by roughly five."""
        self.prob.set_val(self.pt + ".Nmech", min(n_start, 1.0) * self.Nd, units="rpm")
        r = self._solve(); binding = "N"
        if r["conv"] and n_start < 1.0 and r["Tt4_K"] < ac.T4 - 0.5:
            self.prob.set_val(self.pt + ".Nmech", self.Nd, units="rpm")   # speed limit is not binding after all
            r = self._solve()
        if r["conv"] and r["Tt4_K"] > ac.T4 + 0.5:
            binding = "T4"; n0, t0 = float(np.ravel(self.prob.get_val(self.pt + ".Nmech", units="rpm"))[0]) / self.Nd, r["Tt4_K"]
            n1 = n0 - 0.02
            for _ in range(14):
                self.prob.set_val(self.pt + ".Nmech", n1 * self.Nd, units="rpm")
                r = self._solve()
                if not r["conv"]:
                    break
                t1 = r["Tt4_K"]
                if abs(t1 - ac.T4) < 0.5:
                    break
                # simultaneous assignment: n0 must become the PREVIOUS n1, not the new one
                n0, t0, n1 = n1, t1, float(np.clip(n1 - (t1 - ac.T4) * (n1 - n0) / (t1 - t0) if t1 != t0 else n1 - 0.01, 0.75, 1.0))
        r["binding"] = binding; r["N_pct"] = 100 * r["Nmech"] / self.Nd
        return r

    def ab_loss(self, r):
        """Rayleigh loss at the ACTUAL AB-duct Mach for this point (duct area fixed at design)."""
        W5 = r["W_kgps"] * (1 + r["FAR"])
        M_in = ac.mach_from_area(W5, r["Tt5_K"], r["Pt5_kPa"] * 1e3, self.A_ab, ac.GAMMA_AB, R_GAS)
        if not np.isfinite(M_in):
            return dict(dPqP=np.nan, M_in=np.nan, thermally_choked=True, rayleigh=np.nan)
        L = ac.ab_dPqP(self.T7, M_in, Tt_in=r["Tt5_K"])
        L["M_in"] = M_in
        return L

    def _wet_seed(self, dry):
        """Closed-form first guess for (A8 scale, AB fuel-air ratio) from the DRY state.

        With A8 scheduled to hold the compressor where it was, the core state at the wet point is
        the dry one, so the afterburner and the nozzle can be sized analytically before the solver
        is asked anything:
          * AB-duct Mach from the fixed duct area and the dry station-5 flow;
          * Rayleigh loss at that Mach and the required temperature ratio -> Pt7;
          * AB fuel from an enthalpy balance on the cycle's own cp between Tt5 and T7;
          * A8 from the choked-throat relation at (W7, T7, Pt7).
        """
        W2 = dry["W_kgps"]; W5 = W2 * (1 + dry["FAR"])
        M_in = ac.mach_from_area(W5, dry["Tt5_K"], dry["Pt5_kPa"] * 1e3, self.A_ab, ac.GAMMA_AB, R_GAS)
        if not np.isfinite(M_in):
            return None
        L = ac.ab_dPqP(self.T7, M_in, Tt_in=dry["Tt5_K"])
        if L["thermally_choked"]:
            return None
        L["M_in"] = M_in
        cp = 0.5 * (dry.get("t_out_Cp", 1166.0) + 1300.0)          # mean cp between Tt5 and ~1900 K
        far = float(np.clip(cp * (self.T7 - dry["Tt5_K"]) * W5 / (LHV_JETA * W2), 0.0, 0.048))
        Pt7 = dry["Pt5_kPa"] * 1e3 * (1 - L["dPqP"])
        A8 = ac.choked_area(W5 + W2 * far, self.T7, Pt7, GAM7, R7)
        return float(np.clip(A8 / self.A8_design, 0.8, 3.0)), far, L

    def point(self, mn, alt, wet):
        """One flight condition, dry or wet.  Wet: A8 scheduled to hold the dry compressor R-line."""
        self._condition(mn, alt)
        self.prob.set_val(self.pt + ".ab.Fl_I:FAR", 0.0)
        self.prob.set_val(self.pt + ".ab.dPqP", 0.0)
        self.prob.set_val(self.pt + ".a8s.A8_scale", 1.0)
        dry = self._max_throttle()
        dry["A8_scale"] = 1.0; dry["wet"] = False
        if not wet or not dry["conv"]:
            return dry, None
        seed = self._wet_seed(dry)
        if seed is None:
            return dry, dict(thermally_choked=True, wet=False)
        for attempt in range(2):
            # second attempt re-seeds from the previous converged flight condition, which the
            # marching order keeps nearby; the closed-form seed occasionally lands in a region the
            # Newton solver cannot climb out of.
            s = seed if attempt == 0 else (getattr(self, "_wet_guess", (seed[0], seed[1])) + (seed[2],))
            got = self._wet_solve(dry, s)
            if got is not None:
                return dry, got
        return dry, None

    def _wet_solve(self, dry, seed):
        scale, far, L = seed
        self.prob.set_val(self.pt + ".ab.dPqP", L["dPqP"])

        # The whole point of the schedule is that the CORE does not move.  So the wet point is
        # solved at the dry point's own mechanical speed, and the nozzle is opened until the
        # turbine inlet temperature comes back to the dry value.  Same speed and same T4 behind a
        # choked NGV means the same compressor operating point, which the R-line check confirms
        # afterwards rather than chases.  This also removes the N-limit / T4-limit switching that
        # makes a max-throttle search discontinuous and the secants fight each other.
        self.prob.set_val(self.pt + ".Nmech", dry["Nmech"], units="rpm")
        T4_target = dry["Tt4_K"]
        hf = hs = None
        r = None
        for _ in range(20):
            self.prob.set_val(self.pt + ".a8s.A8_scale", scale)
            self.prob.set_val(self.pt + ".ab.Fl_I:FAR", far)
            r = self._solve()
            if not r["conv"]:
                return None
            e_T = r["Tt7_K"] - self.T7
            e_4 = r["Tt4_K"] - T4_target
            Lk = self.ab_loss(r)
            if Lk["thermally_choked"]:
                return dict(thermally_choked=True, wet=False)
            if abs(e_T) < 0.5 and abs(e_4) < 0.5:
                r.update(A8_scale=scale, wet=True, ab_M_in=Lk["M_in"], ab_rayleigh=Lk["rayleigh"],
                         ab_dPqP_total=Lk["dPqP"], thermally_choked=False,
                         Rline_err=r["comp_RlineMap"] - dry["comp_RlineMap"],
                         N_pct=100 * r["Nmech"] / self.Nd, binding=dry["binding"])
                self._wet_guess = (scale, far)
                return r
            if abs(e_T) >= 0.5:                        # AB fuel controls T7
                step = (-e_T * far / max(r["Tt7_K"] - r["Tt5_K"], 1.0) if (hf is None or abs(e_T - hf[1]) < 1e-9)
                        else -e_T * (far - hf[0]) / (e_T - hf[1]))
                hf = (far, e_T)
                far = float(np.clip(far + step, 0.0, 0.048))
            if abs(e_4) >= 0.5:                        # throat area controls the back pressure, hence T4
                step = (0.002 * e_4 * scale if (hs is None or abs(e_4 - hs[1]) < 1e-9)
                        else -e_4 * (scale - hs[0]) / (e_4 - hs[1]))
                hs = (scale, e_4)
                scale = float(np.clip(scale + step, 0.8, 3.0))
            self.prob.set_val(self.pt + ".ab.dPqP", Lk["dPqP"])
        return None


# ----------------------------------------------------------------------------- airframe
class Airframe:
    """The frozen Phase 2 airframe at the Phase 7 engine's envelope and nozzle area."""

    def __init__(self, D_engine_m, L_engine_m, A8_max_m2, A_capture_m2):
        import airframe_model as afm
        self.afm = afm
        cfg = afm.Config(S_wing=0.30)
        cfg.D_engine = D_engine_m; cfg.L_engine = L_engine_m
        # Phase 2 defaults carry placeholder nozzle / capture areas (49.1 and 47.5 cm2); the real
        # ones change the area distribution and therefore the wave drag, so they are set here.
        cfg.A_nozzle = A8_max_m2
        cfg.A_capture = A_capture_m2
        cfg.__post_init__.__self__ if False else None
        self.cfg = cfg

    def cds_zero_lift(self, M, h):
        return self.cfg.CDS(M, h)

    def drag(self, M, h, mass_kg, method="A"):
        at = ac.isa(h)
        q = 0.5 * at["rho"] * (M * at["a"]) ** 2
        S = self.cfg.S_wing
        CL = mass_kg * G0 / (q * S)
        if method == "A":
            cds0 = self.cds_zero_lift(M, h)
            k = self.cfg.k_induced(M)
        else:
            cds0 = self.cds_zero_lift_supersonic(M, h)
            k = np.sqrt(max(M * M - 1.0, 1e-6)) / 4.0     # CL_alpha = 4/beta -> k = 1/CL_alpha
        D = q * cds0 + k * CL * CL * q * S
        return dict(D_N=D, q_Pa=q, CL=CL, CDS0_m2=cds0, k=k, D0_N=q * cds0, Di_N=k * CL * CL * q * S)

    def cds_zero_lift_supersonic(self, M, h):
        """Method B: the same build-up, but with the volume wave drag held at the slender-body
        value instead of decaying to 0.8x it.  Ashley & Landahl (Aerodynamics of Wings and Bodies,
        sec. 9-5): for a slender body the linear-theory volume wave drag is, to first order,
        independent of Mach number.  This is the pessimistic bracket on the top speed."""
        bd = self.cfg.drag_breakdown(M, h)
        wave_faired = bd["wave"]
        info = self.cfg._wave_info
        wave_full = info["E_WD_used"] * info["SH_cm2"] * 1e-4      # the un-faired M 1.2 value
        return sum(bd.values()) - wave_faired + wave_full


# ----------------------------------------------------------------------------- plot
def plot(df, res, mass_kg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(11.8, 8.4))

    a = ax[0, 0]
    a.plot(df.MN, df.Fn_dry_N, "o-", color="tab:blue", label="thrust, dry")
    a.plot(df.MN, df.Fn_wet_N, "o-", color="tab:red", label="thrust, afterburner $T_{t7}$ %.0f K" % ac.T7_DESIGN)
    a.plot(df.MN, df.D_A_N, "s--", color="tab:gray", label="drag, Phase 2 model (extrapolated)")
    a.plot(df.MN, df.D_B_N, "s:", color="k", label="drag, slender-body floor")
    a.axvline(1.02, ls="-.", lw=1, color="tab:green", label="frozen dash point")
    a.set_xlabel("Mach"); a.set_ylabel("force [N]")
    a.set_title("Level flight at %.2f kg, 5 km ISA" % mass_kg, fontsize=9)
    a.legend(fontsize=7); a.grid(alpha=.3)

    a = ax[0, 1]
    a.plot(df.MN, df.q_ratio, "o-", color="tab:purple", label="dynamic pressure / frozen dash $q$")
    a.axhline(1.0, ls=":", color="k")
    a.axhline(2.0, ls="--", color="tab:red", lw=1, label="2 x design $q$")
    a2 = a.twinx()
    a2.plot(df.MN, df.Tt_stag_K - 273.15, "s--", color="tab:orange", ms=3)
    a2.axhline(TG_EPOXY_K - 273.15, ls="--", color="tab:orange", lw=1)
    a2.set_ylabel("stagnation temperature [C]", color="tab:orange")
    a.set_xlabel("Mach"); a.set_ylabel("$q / q_{design}$", color="tab:purple")
    a.set_title("Airframe limits the drag model does not contain", fontsize=9)
    a.legend(fontsize=7, loc="upper left"); a.grid(alpha=.3)

    a = ax[1, 0]
    a.plot(df.MN, df.A8_scale, "o-", color="tab:green", label="$A_8/A_{8,dry}$ the schedule needs")
    a.plot(df.MN, df.ab_M_in, "s--", color="tab:brown", label="afterburner-duct Mach")
    a.axhline(0.39, ls="--", color="tab:red", lw=1, label="AB thermal-choking Mach")
    a.set_xlabel("Mach"); a.set_ylabel("ratio / Mach")
    a.set_title("What the nozzle and the AB duct have to do", fontsize=9)
    a.legend(fontsize=7); a.grid(alpha=.3)

    a = ax[1, 1]
    a.plot(df.MN, 100 * df.turb_exit_margin, "o-", color="tab:red", label="turbine exit annulus flow margin")
    a.axhline(0.0, ls="--", color="k", lw=1, label="choked")
    a2 = a.twinx()
    a2.plot(df.MN, df.ram_recovery, "s--", color="tab:blue", ms=3, label="pitot recovery")
    a2.plot(df.MN, df.mil_e_5008b, "^:", color="tab:cyan", ms=3, label="MIL-E-5008B (designed inlet)")
    a2.set_ylabel("intake total-pressure recovery", color="tab:blue")
    a2.legend(fontsize=7, loc="lower left")
    a.set_xlabel("Mach"); a.set_ylabel("turbine exit capacity margin [%]", color="tab:red")
    a.set_title("Two things that bite before the airframe does", fontsize=9)
    a.legend(fontsize=7, loc="upper right"); a.grid(alpha=.3)

    fig.suptitle("Phase 7: envelope with the afterburner, frozen centrifugal engine on its real maps, "
                 "nozzle scheduled to hold the compressor", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(ac.PLOTS, "phase7_ab_envelope.png")
    fig.savefig(out, dpi=150); print("wrote", out)


# ----------------------------------------------------------------------------- driver
def march_order(machs, start=1.02):
    """Always step outwards from the design condition: a jump across the grid is what leaves the
    off-design solver diverged in the first place."""
    return sorted(machs, key=lambda m: abs(m - start))


def regress(eng):
    ref = pd.read_csv(os.path.join(ac.ROOT, "data", "phase3r_mission_%s_deck.csv" % ac.TAG))
    ref = ref[ref.alt_m == 5000.0].set_index("MN")
    print("regression of the DRY deck against data/phase3r_mission_%s_deck.csv (5 km)" % ac.TAG)
    out, worst = {}, 0.0
    for M in march_order(list(ref.index)):
        dry, _ = eng.point(M, 5000.0, wet=False)
        out[M] = dry
    print("   MN      Fn now       Fn frozen     d%        T4 now    N% now   binding  conv")
    for M in sorted(out):
        dry = out[M]; want = float(ref.loc[M, "Fn_N"])
        d = 100 * (dry["Fn_N"] - want) / want
        worst = max(worst, abs(d))
        print("  %4.2f  %10.3f  %12.3f  %+7.3f %%  %8.2f  %7.3f  %-7s  %s"
              % (M, dry["Fn_N"], want, d, dry["Tt4_K"], dry["N_pct"], dry["binding"], dry["conv"]))
    print("  worst deviation %.3f %%" % worst)
    return worst


def turbine_exit_margin(dry):
    """Can the real turbine exit annulus still pass the flow?

    Phase 6A found on the axial engine (F6A.5) that the drawn hot end's minimum area was the
    turbine exit annulus and not the nozzle, because arch_trade.turb_pout hands TurboFlow a static
    pressure computed from an ASSUMED exit Mach of 0.45.  The same assumption is in this engine's
    turbine design, so the same check is run here, at every flight condition: with an afterburner
    the nozzle throat opens by half again, which makes the turbine annulus the tightest area in
    the hot end by a wide margin, and rising Mach raises the physical flow through it.
    """
    W5 = dry["W_kgps"] * (1 + dry["FAR"])
    cap = ac.choked_flow(A_TURB_EXIT, dry["Tt5_K"], dry["Pt5_kPa"] * 1e3, 1.3265, R_GAS)
    return dict(W5_kgps=W5, turb_exit_capacity_kgps=cap, turb_exit_margin=cap / W5 - 1.0,
                turb_exit_MN=ac.mach_from_area(W5, dry["Tt5_K"], dry["Pt5_kPa"] * 1e3, A_TURB_EXIT, 1.3265, R_GAS))


def run_5km(eng, af, mass_kg):
    rows = []
    for M in march_order(MACHS_5KM):
        dry, wet = eng.point(M, 5000.0, wet=True)
        at = ac.isa(5000.0)
        dA = af.drag(M, 5000.0, mass_kg, "A"); dB = af.drag(M, 5000.0, mass_kg, "B")
        A0 = dry["W_kgps"] / (at["rho"] * M * at["a"])
        te = turbine_exit_margin(dry)
        Tt_skin = at["T"] * (1 + 0.2 * M * M)
        row = dict(MN=M, alt_m=5000.0, Tt5_dry=dry["Tt5_K"], Pt5_dry=dry["Pt5_kPa"],
                   Tt_stag_K=Tt_skin, q_ratio=dA["q_Pa"] / Q_DESIGN_PA, **te,
                   Fn_dry_N=dry["Fn_N"], W_dry=dry["W_kgps"], T4_dry=dry["Tt4_K"], N_dry=dry["N_pct"],
                   binding_dry=dry["binding"], SMN_dry=dry["SMN"], Rline_dry=dry["comp_RlineMap"],
                   Nc_dry=dry["comp_NcMap"], A0_capture_cm2=A0 * 1e4,
                   ram_recovery=ac.normal_shock_recovery(M), mil_e_5008b=ac.mil_e_5008b(M),
                   D_A_N=dA["D_N"], D0_A_N=dA["D0_N"], Di_A_N=dA["Di_N"], CDS0_A_cm2=dA["CDS0_m2"] * 1e4,
                   D_B_N=dB["D_N"], D0_B_N=dB["D0_N"], Di_B_N=dB["Di_N"], CDS0_B_cm2=dB["CDS0_m2"] * 1e4,
                   q_Pa=dA["q_Pa"], CL=dA["CL"])
        if wet is not None and wet.get("wet"):
            row.update(Fn_wet_N=wet["Fn_N"], Wf_wet=wet["Wf_kgps"], Wf_ab=wet["Wf_ab_kgps"],
                       TSFC_wet=wet["TSFC_kgpNh"], A8_scale=wet["A8_scale"], A8_wet_cm2=wet["A8_cm2"],
                       Tt7_K=wet["Tt7_K"], FAR_total=wet["FAR_total"], ab_M_in=wet["ab_M_in"],
                       ab_rayleigh=wet["ab_rayleigh"], ab_dPqP=wet["ab_dPqP_total"],
                       SMN_wet=wet["SMN"], Rline_wet=wet["comp_RlineMap"], T4_wet=wet["Tt4_K"],
                       N_wet=wet["N_pct"], W_wet=wet["W_kgps"], NPR_wet=wet["NPR"],
                       ab_choked=bool(wet.get("thermally_choked", False)))
        else:
            for k in ("Fn_wet_N", "Wf_wet", "Wf_ab", "TSFC_wet", "A8_scale", "A8_wet_cm2", "Tt7_K",
                      "FAR_total", "ab_M_in", "ab_rayleigh", "ab_dPqP", "SMN_wet", "Rline_wet",
                      "T4_wet", "N_wet", "W_wet", "NPR_wet"):
                row[k] = np.nan
            row["ab_choked"] = bool(wet.get("thermally_choked", False)) if wet is not None else False
        rows.append(row)
        print("  M %4.2f: dry %7.1f N  wet %7.1f N  A8x %5.3f  D_A %7.1f N  D_B %7.1f N  SMN %5.3f->%5.3f"
              % (M, row["Fn_dry_N"], row.get("Fn_wet_N", np.nan), row.get("A8_scale", np.nan),
                 row["D_A_N"], row["D_B_N"], row["SMN_dry"], row.get("SMN_wet", np.nan)), flush=True)
    return pd.DataFrame(rows).sort_values("MN").reset_index(drop=True)


def crossing(M, F, D):
    """Highest Mach where thrust still exceeds drag (linear interpolation on F - D).

    Returns +inf if thrust never falls below drag inside the grid: saying 'M 2.0' when the grid
    simply stopped at 2.0 would be a fabricated limit."""
    ok = np.isfinite(F) & np.isfinite(D)
    M, e = np.asarray(M)[ok], (np.asarray(F) - np.asarray(D))[ok]
    if len(M) < 2 or e[0] <= 0:
        return np.nan
    for i in range(1, len(M)):
        if e[i] <= 0:
            return float(M[i - 1] + (M[i] - M[i - 1]) * e[i - 1] / (e[i - 1] - e[i]))
    return np.inf


def first_exceeding(M, y, limit):
    """Mach at which a monotone quantity first crosses a limit (linear interpolation)."""
    M, y = np.asarray(M, float), np.asarray(y, float)
    ok = np.isfinite(y)
    M, y = M[ok], y[ok]
    for i in range(1, len(M)):
        if y[i] >= limit > y[i - 1]:
            return float(M[i - 1] + (M[i] - M[i - 1]) * (limit - y[i - 1]) / (y[i] - y[i - 1]))
    return np.inf if (len(y) and y[-1] < limit) else np.nan


if __name__ == "__main__":
    eng = Engine()
    print("engine built: design A8 %.3f cm2, AB duct area %.1f cm2, N_design %.0f rpm"
          % (eng.A8_design * 1e4, eng.A_ab * 1e4, eng.Nd))

    if "--regress" in sys.argv:
        regress(eng); sys.exit(0)

    # mass: the frozen TOGW plus the Phase 7 afterburner mass, refined later by ab_closure.py
    togw = json.load(open(os.path.join(ac.ROOT, "data", "phase4r_closure.json")))
    mass0 = float(togw["budget"]["TOGW"])
    print("using take-off mass %.2f kg (frozen closure; ab_closure.py re-closes it)" % mass0)

    # A8 must be sized for the hottest wet case: read it from the design-point study
    dp = json.load(open(os.path.join(ac.D7, "ab_design_point.json")))
    A8_max = dp["wet"]["A8_cm2"] * 1e-4
    af = Airframe(ac.frozen_engine()["D_engine_mm"] / 1e3,
                  ac.frozen_engine()["L_engine_mm"] * ac.case()["calibration"]["K_L"] / 1e3,
                  A8_max, fz["A_capture_cm2"] * 1e-4)

    print()
    alt_only = "--alt-only" in sys.argv          # reuse the saved 5 km line, redo only the altitudes
    if alt_only:
        df = pd.read_csv(os.path.join(ac.D7, "ab_envelope_5km.csv"))
        print("reusing data/phase7/ab_envelope_5km.csv")
    else:
        print("5 km ISA, level flight at %.2f kg" % mass0)
        df = run_5km(eng, af, mass0)
        df.to_csv(os.path.join(ac.D7, "ab_envelope_5km.csv"), index=False)

    res = dict(mass_kg=mass0, T7_K=ac.T7_DESIGN, A_turb_exit_cm2=A_TURB_EXIT * 1e4,
               M_max_dry_A=crossing(df.MN, df.Fn_dry_N, df.D_A_N),
               M_max_wet_A=crossing(df.MN, df.Fn_wet_N, df.D_A_N),
               M_max_dry_B=crossing(df.MN, df.Fn_dry_N, df.D_B_N),
               M_max_wet_B=crossing(df.MN, df.Fn_wet_N, df.D_B_N),
               M_q_2x=first_exceeding(df.MN, df.q_ratio, 2.0),
               M_skin_Tg=first_exceeding(df.MN, df.Tt_stag_K, TG_EPOXY_K),
               M_turb_exit_choke=first_exceeding(df.MN, -df.turb_exit_margin, 0.0),
               M_ab_thermal_choke=first_exceeding(df.MN, df.ab_M_in.fillna(0.0), 0.39),
               A8_scale_max=float(np.nanmax(df.A8_scale)),
               A8_scale_at_dash=float(df[df.MN == 1.02].A8_scale.iloc[0]),
               Rline_err_max=float(np.nanmax(np.abs(df.Rline_wet - df.Rline_dry))))

    fmt = lambda v: ("never inside the grid (M <= %.2f)" % max(MACHS_5KM)) if not np.isfinite(v) else "M %.3f" % v
    print()
    print("=" * 100)
    print("WHAT LIMITS THE SPEED at 5 km, level flight, %.2f kg" % mass0)
    print("=" * 100)
    print("  thrust = drag, drag method A (Phase 2 model extrapolated):   dry %s   wet %s"
          % (fmt(res["M_max_dry_A"]), fmt(res["M_max_wet_A"])))
    print("  thrust = drag, drag method B (slender-body wave-drag floor): dry %s   wet %s"
          % (fmt(res["M_max_dry_B"]), fmt(res["M_max_wet_B"])))
    print("  --- limits the Phase 2 drag model does not contain ---")
    print("  dynamic pressure reaches 2 x the frozen dash value:          %s" % fmt(res["M_q_2x"]))
    print("  stagnation temperature reaches %.0f K (epoxy screening):      %s"
          % (TG_EPOXY_K, fmt(res["M_skin_Tg"])))
    print("  turbine exit annulus (%.2f cm2) runs out of capacity:        %s"
          % (A_TURB_EXIT * 1e4, fmt(res["M_turb_exit_choke"])))
    print("  afterburner duct approaches thermal choking (M_ab 0.39):      %s" % fmt(res["M_ab_thermal_choke"]))
    print()
    print("  nozzle throat travel required: A8/A8_dry up to %.3f (%.3f at the M 1.02 dash)"
          % (res["A8_scale_max"], res["A8_scale_at_dash"]))
    print("  schedule check: worst compressor R-line shift, dry -> wet = %.2e (target 0)" % res["Rline_err_max"])

    print()
    print("altitude sweep (wet), marched in 1000 m steps from the design altitude")
    arows = []
    for h in sorted({h for _, h in ALT_SWEEP}, key=lambda z: abs(z - 5000.0)):
        # Walk to the target altitude at the design Mach in 1000 m steps.  A 2 km jump diverges
        # the off-design solver, and a diverged point then poisons the whole altitude block.
        steps = np.arange(5000.0, h + (1000.0 if h > 5000 else -1000.0), 1000.0 if h > 5000 else -1000.0)
        for hh in steps:
            eng.point(1.02, float(hh), wet=False)
        for M in march_order(sorted({m for m, hh in ALT_SWEEP if hh == h})):
            dry, wet = eng.point(M, h, wet=True)
            ok = bool(wet) and wet.get("wet", False)
            row = dict(MN=M, alt_m=h, conv_dry=bool(dry["conv"]),
                       Fn_dry_N=dry["Fn_N"] if dry["conv"] else np.nan,
                       Fn_wet_N=wet["Fn_N"] if ok else np.nan,
                       A8_scale=wet["A8_scale"] if ok else np.nan,
                       Tt7_K=wet["Tt7_K"] if ok else np.nan,
                       TSFC_wet=wet["TSFC_kgpNh"] if ok else np.nan)
            # the turbine-exit capacity check is only meaningful on a converged dry point
            row.update({k: (v if dry["conv"] else np.nan) for k, v in turbine_exit_margin(dry).items()})
            arows.append(row)
            print("  M %.2f / %5.0f m: dry %7.1f N  wet %7.1f N  turbine-exit margin %+6.1f %%"
                  % (M, h, row["Fn_dry_N"], row["Fn_wet_N"], 100 * row["turb_exit_margin"]), flush=True)
    pd.DataFrame(arows).sort_values(["alt_m", "MN"]).to_csv(os.path.join(ac.D7, "ab_envelope_alt.csv"), index=False)

    json.dump(res, open(os.path.join(ac.D7, "ab_envelope.json"), "w"), indent=1)
    plot(df, res, mass0)
