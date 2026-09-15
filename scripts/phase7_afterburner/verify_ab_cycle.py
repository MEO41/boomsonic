"""Phase 7 verification: the afterburner option must not disturb the frozen engine, and the
afterburner itself must reproduce closed-form gas dynamics.

Three checks, all of which must pass before any Phase 7 number is used:

  1. REGRESSION.  cycle_model with afterburner=False must reproduce the Phase 3 / Phase 3R
     reference points exactly: the centrifugal dash at the tool level (W 1.32575 kg/s is the
     FIELDED value; the CLAUDE.md reproduction targets are W 1.32575 kg/s and TSFC 0.16416 at
     the fielded level) and the frozen fielded dash station set.
  2. NULL AFTERBURNER.  cycle_model with afterburner=True, zero AB fuel and zero AB pressure
     loss must give the same answer as afterburner=False.  This proves the extra station is
     transparent and that any difference later is the afterburner, not the plumbing.
  3. CLOSED FORM.  The afterburner's own physics against hand relations:
       a) energy:    Wf_ab predicted by pyCycle vs an enthalpy balance on the tabular thermo
                     (the cycle's own cp), so the fuel flow is not taken on trust;
       b) area:      the nozzle throat area pyCycle sizes vs the choked-flow relation
                     A = W sqrt(Tt) / (Pt sqrt(g/R) ((g+1)/2)^(-(g+1)/(2(g-1)))), the same
                     check Phase 6A used on the axial hot end (F6A.5);
       c) thrust:    gross thrust vs momentum + pressure on the throat.

Usage:  .venv\\Scripts\\python scripts\\phase7_afterburner\\verify_ab_cycle.py
"""
import os, sys, json, numpy as np
os.environ.setdefault("OPENMDAO_REPORTS", "0")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import cycle_model as cm
import ab_common as ac

TOL = 1e-6
fails = []


def check(name, got, want, tol=TOL, rel=True, unit=""):
    err = abs(got - want) / abs(want) if (rel and want != 0) else abs(got - want)
    ok = err <= tol
    if not ok:
        fails.append(name)
    print("  %-46s %14.7f vs %14.7f %-7s %s (%s %.2e)"
          % (name, got, want, unit, "OK  " if ok else "FAIL", "rel" if rel else "abs", err))
    return ok


def run_point(afterburner, ab_mode='FAR', T7=None, ab_FAR=None, ab_dPqP=0.0):
    """The frozen fielded dash point, W fixed at its frozen value."""
    prob, mp = cm.build(design_W='fixed', afterburner=afterburner, ab_mode=ab_mode)
    kw = {}
    if afterburner:
        kw = dict(ab_dPqP=ab_dPqP)
        if ab_mode == 'T7':
            kw['T7_K'] = T7
        else:
            kw['ab_FAR'] = ab_FAR if ab_FAR is not None else 0.0
    cm.set_design(prob, ac.M_DASH, ac.H_DASH, ac.OPR, ac.T4, ac.ETA_C, ac.ETA_T,
                  W_kgps=ac.W_FROZEN, duct_dPqP=ac.DUCT_DPQP, ram_recovery=ac.RAM_REC,
                  burner_dPqP=0.05, Cv=0.98, **kw)
    prob['DESIGN.balance.turb_PR'] = 2.6
    prob.run_model()
    return prob, cm.read(prob, 'DESIGN', eta_b=ac.ETA_B, eta_ab=(ac.ETA_AB if afterburner else None))


if __name__ == "__main__":
    frozen = ac.frozen_cycle()

    print("=" * 112)
    print("0. RAYLEIGH RELATIONS in ab_common vs published Rayleigh-flow tables (gamma 1.4)")
    print("=" * 112)
    # Standard Rayleigh-flow tables, e.g. Zucrow & Hoffman, Gas Dynamics Vol. 1, App. D;
    # Shapiro Vol. 1 Table B.4.  Tt/Tt* and Pt/Pt* at three Mach numbers.
    for M, tt_ref, pt_ref in ((0.2, 0.17355, 1.23460), (0.3, 0.34686, 1.19855), (0.5, 0.69136, 1.11405)):
        check("Rayleigh Tt/Tt* at M %.1f" % M, ac.rayleigh_T0_ratio(M, 1.4), tt_ref, tol=3e-5)
        check("Rayleigh Pt/Pt* at M %.1f" % M, ac.rayleigh_P0_ratio(M, 1.4), pt_ref, tol=3e-5)

    print()
    print("=" * 112)
    print("1. REGRESSION: afterburner=False must reproduce the frozen fielded dash point (data/phase3r/cct_%s.json)" % ac.TAG)
    print("=" * 112)
    _, dry = run_point(False)
    for k, fk, unit in (("Fn_N", "Fn_N", "N"), ("W_kgps", "W_kgps", "kg/s"), ("Wf_kgps", "Wf_kgps", "kg/s"),
                        ("TSFC_kgpNh", "TSFC_kgpNh", "kg/N/h"), ("Tt3_K", "Tt3_K", "K"), ("Pt3_kPa", "Pt3_kPa", "kPa"),
                        ("Tt5_K", "Tt5_K", "K"), ("Pt5_kPa", "Pt5_kPa", "kPa"), ("turb_PR", "turb_PR", "-"),
                        ("A8_cm2", "A8_cm2", "cm2"), ("Vj_mps", "Vj_mps", "m/s"), ("NPR", "NPR", "-")):
        check("dry " + k, dry[k], frozen[fk], unit=unit)
    print("  CLAUDE.md reproduction targets: W 1.32575 kg/s, TSFC 0.16416")
    check("CLAUDE.md W", dry["W_kgps"], 1.32575, tol=1e-5, unit="kg/s")
    check("CLAUDE.md TSFC", dry["TSFC_kgpNh"], 0.16416, tol=1e-4, unit="kg/N/h")

    print()
    print("=" * 112)
    print("2. NULL AFTERBURNER: afterburner=True with zero AB fuel and zero AB loss == afterburner=False")
    print("=" * 112)
    _, nul = run_point(True, ab_mode='FAR', ab_FAR=0.0, ab_dPqP=0.0)
    for k, unit in (("Fn_N", "N"), ("W_kgps", "kg/s"), ("Wf_kgps", "kg/s"), ("TSFC_kgpNh", "kg/N/h"),
                    ("Tt5_K", "K"), ("Pt5_kPa", "kPa"), ("turb_PR", "-"), ("A8_cm2", "cm2"), ("Vj_mps", "m/s")):
        check("null-AB " + k, nul[k], dry[k], tol=1e-9, unit=unit)
    check("null-AB Tt7 == Tt5", nul["Tt7_K"], dry["Tt5_K"], tol=1e-9, unit="K")
    check("null-AB Pt7 == Pt5", nul["Pt7_kPa"], dry["Pt5_kPa"], tol=1e-9, unit="kPa")
    check("null-AB Wf_ab", nul["Wf_ab_kgps"], 0.0, tol=1e-12, rel=False, unit="kg/s")

    print()
    print("=" * 112)
    print("3. CLOSED FORM: the afterburner's own physics at Tt7 = %.0f K" % ac.T7_DESIGN)
    print("=" * 112)
    dp = ac.ab_dPqP(ac.T7_DESIGN, ac.AB_MN, Tt_in=frozen["Tt5_K"])
    prob, wet = run_point(True, ab_mode='T7', T7=ac.T7_DESIGN, ab_dPqP=dp["dPqP"])
    g = lambda n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])

    # (a) fuel bookkeeping.  pyCycle's tabular ThermoAdd references the mix ratio to the DRY AIR
    # of the incoming stream (thermo_add.py: "for reactant mode, we reference from the incoming
    # air"), so for a SECOND burner in series the added ratio is still per unit dry air and the
    # composition simply accumulates.  If that reading were wrong, TSFC would be wrong, so it is
    # checked rather than trusted.
    W2 = g('DESIGN.inlet.Fl_O:stat:W', 'kg/s')          # dry air; no bleed in this model
    FAR_main = g('DESIGN.balance.FAR'); FAR_ab = g('DESIGN.balance.ab_FAR')
    Wf_main_burnt = g('DESIGN.burner.Wfuel', 'kg/s'); Wf_ab_burnt = g('DESIGN.ab.Wfuel', 'kg/s')
    check("Wf_main == W_air * FAR_main", Wf_main_burnt, W2 * FAR_main, tol=1e-9, unit="kg/s")
    check("Wf_ab   == W_air * FAR_ab", Wf_ab_burnt, W2 * FAR_ab, tol=1e-9, unit="kg/s")
    check("FAR_total == FAR_main + FAR_ab", wet["FAR_total"], FAR_main + FAR_ab, tol=1e-9, unit="-")

    # (b) energy.  pyCycle's TABULAR fuel carries ZERO injection enthalpy in the table's datum
    # (thermo/tabular/thermo_add.py never sets mix:h, so it stays 0 and the heat of reaction is
    # carried entirely by the FAR-dependence of h): W_out h_out = W_in h_in exactly, for BOTH
    # burners.  That makes an internal energy balance vacuous, so the heat release is checked
    # against Cantera instead -- the same cross-check phase3_cycle/cantera_check.py runs on the
    # main burner, extended to a second burn in the vitiated stream.
    W5 = g('DESIGN.turb.Fl_O:stat:W', 'kg/s'); W7 = W5 + Wf_ab_burnt
    h5 = g('DESIGN.turb.Fl_O:tot:h', 'J/kg'); h7 = g('DESIGN.ab.Fl_O:tot:h', 'J/kg')
    check("tabular fuel injection enthalpy is 0", (W7 * h7 - W5 * h5) / Wf_ab_burnt, 0.0, tol=1e-3, rel=False, unit="J/kg")
    T7_ct = ac.cantera_ab_exit(T3=g('DESIGN.comp.Fl_O:tot:T', 'degK'), P3=g('DESIGN.comp.Fl_O:tot:P', 'Pa'),
                               FAR_main=FAR_main, T5=g('DESIGN.turb.Fl_O:tot:T', 'degK'),
                               P_ab=g('DESIGN.ab.Fl_O:tot:P', 'Pa'), FAR_ab=FAR_ab)
    print("  Cantera (n-dodecane surrogate) AB exit %.1f K vs pyCycle %.1f K  (%+.2f %%)"
          % (T7_ct, wet["Tt7_K"], 100 * (T7_ct - wet["Tt7_K"]) / wet["Tt7_K"]))
    check("AB exit T vs Cantera equilibrium", T7_ct, wet["Tt7_K"], tol=2e-2, unit="K")

    # (c) choked-throat area against the closed-form capacity relation
    gam = g('DESIGN.nozz.Throat:stat:gamma'); R = g('DESIGN.ab.Fl_O:tot:R', 'J/(kg*degK)')
    Pt7 = g('DESIGN.ab.Fl_O:tot:P', 'Pa'); Tt7 = g('DESIGN.ab.Fl_O:tot:T', 'degK')
    A_cf = ac.choked_area(W7, Tt7, Pt7, gam, R)
    check("A8 vs choked-flow relation", wet["A8_cm2"] / 1e4, A_cf, tol=3e-3, unit="m2")

    # (d) gross thrust.  pyCycle's Nozzle with lossCoef='Cv' forms
    #     Fg = W_in V_actual Cv Cang CmixCorr + A_actual (Ps_actual - Ps_ambient)   (nozzle.py:117),
    # i.e. Cv debits the momentum term only, not the pressure term.
    Ps8 = g('DESIGN.nozz.Throat:stat:P', 'Pa'); P0 = g('DESIGN.fc.Fl_O:stat:P', 'Pa')
    Cv = g('DESIGN.nozz.Cv'); W_noz = g('DESIGN.nozz.perf_calcs.W_in', 'kg/s')
    A8 = wet["A8_cm2"] / 1e4; Vj = wet["Vj_mps"]
    Fg_cf = W_noz * Vj * Cv + (Ps8 - P0) * A8
    check("Fg vs momentum + pressure", wet["Fg_N"], Fg_cf, tol=3e-3, unit="N")
    check("nozzle inlet W == W5 + Wf_ab", W_noz, W7, tol=1e-9, unit="kg/s")

    print()
    print("  AB at Tt7 %.0f K: Fn %.1f N (%.3f x dry), TSFC %.4f, A8 %.2f cm2 (%.3f x dry), FAR_total %.4f"
          % (wet["Tt7_K"], wet["Fn_N"], wet["Fn_N"] / dry["Fn_N"], wet["TSFC_kgpNh"],
             wet["A8_cm2"], wet["A8_cm2"] / dry["A8_cm2"], wet["FAR_total"]))

    print()
    print("=" * 112)
    if fails:
        print("FAILED: " + ", ".join(fails)); sys.exit(1)
    print("All Phase 7 cycle-model verification checks passed.")
