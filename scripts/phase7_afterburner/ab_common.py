"""Phase 7 shared constants and gas-dynamic relations for the afterburner study.

Everything the Phase 7 scripts hold in common lives here so that no number is retyped:
the frozen engine is read from its Phase 3R case file, not transcribed.

Stated assumptions (each carries a design_log id; none of them is a tool output):
  A7.1  AB exit total temperature limit T7_DESIGN = 1900 K.
  A7.2  AB combustion efficiency ETA_AB = 0.90, applied to the fuel flow in post-processing
        (the same convention cycle_model uses for the main burner's eta_b).
  A7.3  AB dry total-pressure loss AB_DRY_DPQP = 0.02 (flameholder + wall friction), on top of
        which the Rayleigh loss of the heat addition is computed, not assumed.
  A7.4  AB duct Mach AB_MN = 0.20 at the design point.
"""
import os, sys, json, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))

TAG = "ce75000_opr4_t1150_b15_cap"
D3R = os.path.join(ROOT, "data", "phase3r")
D7 = os.path.join(ROOT, "data", "phase7")
PLOTS = os.path.join(ROOT, "plots")

# --- the frozen engine, read from its case file -------------------------------------------
_case = None


def case():
    global _case
    if _case is None:
        _case = json.load(open(os.path.join(D3R, "cct_%s.json" % TAG)))
    return _case


def frozen_cycle():
    """The frozen FIELDED dash cycle (eta_c 0.70, eta_t 0.75), design_freeze.md section 1.1."""
    return case()["levels"]["fielded"]["eval"]["cycle"]


def frozen_engine():
    """The frozen engine mass / envelope block."""
    return case()["levels"]["fielded"]["eval"]["engine"]


_f = frozen_cycle()
M_DASH, H_DASH = _f["MN"], _f["alt_m"]
OPR, T4 = case()["OPR"], _f["Tt4_K"]
ETA_C, ETA_T = case()["levels"]["fielded"]["eval"]["eta_c"], case()["levels"]["fielded"]["eval"]["eta_t"]
ETA_B = 0.95                       # Phase 3 A3.x, unchanged
W_FROZEN = _f["W_kgps"]
DUCT_DPQP = _f["duct"]["dPqP"]
RAM_REC = _f["ram_recovery"]
RPM = case()["rpm"]

# --- afterburner assumptions ---------------------------------------------------------------
T7_DESIGN = 1900.0                 # A7.1  K
ETA_AB = 0.90                      # A7.2
AB_DRY_DPQP = 0.02                 # A7.3
AB_MN = 0.20                       # A7.4
FAR_TABLE_MAX = 0.05               # F7.1: upper edge of pyCycle's AIR_JETA_TAB_SPEC FAR axis
FAR_STOICH_JETA = 0.068            # Jet-A / air, mass basis
GAMMA_AB = 1.33                    # representative for the AB duct; the cycle itself uses the tabular gas
LHV_TAB = None                     # measured in verify_ab_cycle.py, not assumed


# --- gas dynamics ---------------------------------------------------------------------------
def rayleigh_T0_ratio(M, g=1.4):
    """Rayleigh line: Tt / Tt* (Shapiro, The Dynamics and Thermodynamics of Compressible Fluid
    Flow, Vol. 1, ch. 7).  Verified against published Rayleigh tables in verify_ab_cycle.py."""
    M2 = M * M
    return ((1 + g) * M2 / (1 + g * M2) ** 2) * (2 + (g - 1) * M2)


def rayleigh_P0_ratio(M, g=1.4):
    """Rayleigh line: Pt / Pt*."""
    M2 = M * M
    return ((1 + g) / (1 + g * M2)) * ((1 + 0.5 * (g - 1) * M2) / (0.5 * (g + 1))) ** (g / (g - 1))


def rayleigh_loss(M_in, tau, g=GAMMA_AB):
    """Total-pressure loss of constant-area heat addition raising the total temperature by tau.

    Returns dict(dPqP, M_out, thermally_choked).  If tau would drive the Rayleigh line past
    M = 1 the duct is thermally choked and no solution exists at this inlet Mach."""
    t_in = rayleigh_T0_ratio(M_in, g)
    t_out = t_in * tau
    if t_out >= 1.0:
        return dict(dPqP=np.nan, M_out=np.nan, thermally_choked=True, margin=t_out)
    lo, hi = M_in, 1.0
    for _ in range(200):                       # Tt/Tt* is monotonic in M below 1
        mid = 0.5 * (lo + hi)
        if rayleigh_T0_ratio(mid, g) < t_out:
            lo = mid
        else:
            hi = mid
    M_out = 0.5 * (lo + hi)
    pr = rayleigh_P0_ratio(M_out, g) / rayleigh_P0_ratio(M_in, g)
    return dict(dPqP=1.0 - pr, M_out=M_out, thermally_choked=False, margin=t_out)


def ab_dPqP(T7, M_in=AB_MN, Tt_in=None, dry=AB_DRY_DPQP, g=GAMMA_AB):
    """Total AB total-pressure loss: the assumed dry loss plus the computed Rayleigh loss.

    pyCycle's Combustor applies dPqP as a fixed fraction and does NOT model the momentum
    (Rayleigh) loss of heat addition.  In the main burner at MN 0.10 that is negligible; in an
    afterburner at MN 0.20 with a total-temperature ratio near 2 it is not (F7.2), so it is
    computed here and handed to the element."""
    if Tt_in is None:
        Tt_in = frozen_cycle()["Tt5_K"]
    r = rayleigh_loss(M_in, T7 / Tt_in, g)
    out = dict(dry=dry, rayleigh=r["dPqP"], dPqP=dry + r["dPqP"], M_out=r["M_out"],
               thermally_choked=r["thermally_choked"], tau=T7 / Tt_in)
    return out


def choked_area(W, Tt, Pt, g, R):
    """Area of a choked (M = 1) throat passing W:  W = A Pt/sqrt(Tt) sqrt(g/R) ((g+1)/2)^-((g+1)/(2(g-1)))."""
    return W * np.sqrt(Tt) / (Pt * np.sqrt(g / R) * (0.5 * (g + 1)) ** (-(g + 1) / (2 * (g - 1))))


def choked_flow(A, Tt, Pt, g, R):
    """Inverse of choked_area: the mass flow a choked area A can pass."""
    return A * Pt / np.sqrt(Tt) * np.sqrt(g / R) * (0.5 * (g + 1)) ** (-(g + 1) / (2 * (g - 1)))


def duct_area(W, Tt, Pt, M, g, R):
    """Area of a duct carrying W at Mach M."""
    return W * np.sqrt(Tt) / (Pt * np.sqrt(g / R) * M * (1 + 0.5 * (g - 1) * M * M) ** (-0.5 * (g + 1) / (g - 1)))


def mach_from_area(W, Tt, Pt, A, g, R, clamp=False):
    """Subsonic Mach that passes W through area A.

    NaN if A cannot pass W, i.e. the area is smaller than the choked area -- that is a real
    physical statement and the caller usually wants to see it.  clamp=True returns M = 1 instead,
    which is what integrating along a convergent nozzle wall DOWN TO its throat needs: the throat
    sits at the choked area by construction and floating-point rounding otherwise puts it a hair
    on the impossible side and returns NaN for the one station that matters.
    """
    f = lambda M: duct_area(W, Tt, Pt, M, g, R)
    if f(1.0) > A:
        return 1.0 if clamp else np.nan
    lo, hi = 1e-4, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > A:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def static_pressure(Pt, M, g):
    return Pt * (1 + 0.5 * (g - 1) * M * M) ** (-g / (g - 1))


def isa(h):
    T = 288.15 - 0.0065 * h
    P = 101325.0 * (T / 288.15) ** 5.25588
    return dict(T=T, P=P, rho=P / (287.053 * T), a=np.sqrt(1.4 * 287.053 * T))


def normal_shock_recovery(M, g=1.4):
    """Pitot-intake total-pressure recovery: Rankine-Hugoniot normal shock (same relation
    dash_cycle.py uses, repeated here so Phase 7 scripts do not depend on import order)."""
    if M <= 1.0:
        return 1.0
    a = ((g + 1) * M * M / ((g - 1) * M * M + 2)) ** (g / (g - 1))
    b = ((g + 1) / (2 * g * M * M - (g - 1))) ** (1 / (g - 1))
    return a * b


def mil_e_5008b(M):
    """MIL-E-5008B intake pressure-recovery standard for supersonic inlets: 1 - 0.075 (M-1)^1.35
    above M = 1 (Mattingly, Elements of Gas Turbine Propulsion, sec. 6.4).  Quoted alongside the
    normal-shock value to show what a designed supersonic intake would recover; the frozen
    airframe has a NOSE PITOT intake, so the normal-shock value is the one used."""
    return 1.0 if M <= 1.0 else 1.0 - 0.075 * (M - 1.0) ** 1.35


_maps = None


def real_maps():
    """The Phase 3R TurboFlow compressor and turbine maps of THIS engine, loaded exactly as
    phase3_cycle/cc_mission.py loads them (same helpers, same surge surrogate), so the dry deck
    this study starts from is the frozen one."""
    global _maps
    if _maps is not None:
        return _maps
    import json as _json
    import ac_offdesign as acm, axial_map as am, axial_offdesign as ao
    MAPS = os.path.join(D3R, "maps")
    c = acm.PureCC(os.path.join(MAPS, "centrifugal_map_%s.json" % TAG))
    NS = tuple(sorted(set(round(l["N"], 3) for l in c.cc.lines)))
    lines = []
    for N in NS:
        try:
            lines.append(am.build_compressor_lines(c, Ns=(N,))[0])
        except Exception as e:
            print("  compressor map: N %.3f dropped (%s)" % (N, e), flush=True)
    cmap, R_d = am.compressor_mapdata(lines, c.W_d, c.T01, c.P01)
    tdata, cover = am.turbine_mapdata(_json.load(open(os.path.join(MAPS, "turbine_map_%s.json" % TAG))))

    def smn(Nc, Wc_lbm):
        """Design-point surge-margin surrogate = peak of the speed line.  UNVALIDATED for a vaned
        diffuser (design_freeze.md open risk 4.1, hecc_surge_check.py): carried only so Phase 7
        can say whether the afterburner made it better or worse, never as an absolute margin."""
        W = Wc_lbm / am.KG2LBM * (c.P01 / 101325.0) / np.sqrt(c.T01 / 288.15)
        try:
            q = c.point(Nc, W)
        except ao.Choked:
            return np.nan
        Ns = np.array([l["N"] for l in lines])
        f = lambda k: float(np.interp(Nc, Ns, [l[k] for l in lines]))
        return (f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1

    _maps = dict(cmap=cmap, tmap=tdata, R_design=R_d, smn=smn, cc=c, lines=lines)
    return _maps


_probs = {}


def design_point(T7=None, ab_MN=AB_MN, eta_ab=ETA_AB, dry_dPqP=AB_DRY_DPQP, W=None, MN=None, alt=None, Fn=None):
    """Solve the frozen core at the dash point with the afterburner at T7 (None = AB off).

    The core is held at its frozen operating point and the nozzle throat is an output, i.e. the
    'rubber nozzle' idealisation: whatever A8 the flow needs, it gets.  That is the upper bound
    on afterburner performance; ab_envelope.py replaces it with a real scheduled nozzle.

    Returns the cycle_model.read dict, plus the AB loss breakdown under key 'loss'.
    """
    import cycle_model as cm
    key = ('T7' if T7 is not None else 'FAR')
    if key not in _probs:
        _probs[key] = cm.build(design_W='fixed', afterburner=True, ab_mode=key)
    prob, _ = _probs[key]
    fz = frozen_cycle()
    loss = ab_dPqP(T7 if T7 is not None else fz["Tt5_K"], ab_MN, Tt_in=fz["Tt5_K"], dry=dry_dPqP)
    if T7 is None:
        loss = dict(dry=0.0, rayleigh=0.0, dPqP=0.0, M_out=ab_MN, thermally_choked=False, tau=1.0)
    kw = dict(ab_dPqP=loss["dPqP"])
    kw['T7_K' if T7 is not None else 'ab_FAR'] = T7 if T7 is not None else 0.0
    cm.set_design(prob, MN if MN is not None else M_DASH, alt if alt is not None else H_DASH,
                  OPR, T4, ETA_C, ETA_T, W_kgps=(W if W is not None else W_FROZEN) if Fn is None else None,
                  Fn_N=Fn, duct_dPqP=DUCT_DPQP, ram_recovery=RAM_REC, burner_dPqP=0.05, Cv=0.98, **kw)
    prob.set_val('DESIGN.ab.MN', ab_MN)
    prob['DESIGN.balance.turb_PR'] = 2.6
    if T7 is not None:
        prob['DESIGN.balance.ab_FAR'] = 0.025
    prob.run_model()
    r = cm.read(prob, 'DESIGN', eta_b=ETA_B, eta_ab=eta_ab)
    r["loss"] = loss
    return r


def cantera_ab_exit(T3, P3, FAR_main, T5, P_ab, FAR_ab, fuel="c12h26:1"):
    """Independent equilibrium check of the AFTERBURNER exit temperature (Cantera, .venv).

    Mirrors phase3_cycle/cantera_check.py but for a second burn in an already-vitiated stream:
      1. air + FAR_main kg fuel per kg air, equilibrated at constant H and P from (T3, P3)
         -> the main-burner products;
      2. those products brought to the turbine-exit temperature T5 at the AB pressure;
      3. FAR_ab more kg fuel per kg air mixed in at T5 and equilibrated at constant H and P.

    Step 3 uses the same fuel-at-inflow-temperature convention as the Phase 3 main-burner check
    (and as pyCycle's tabular thermo, whose fuel injection enthalpy is zero in the table datum),
    so the two are compared like for like.  Returns the AB exit temperature in K.
    """
    import cantera as ct
    gas = ct.Solution("nDodecane_Reitz.yaml")
    air = "O2:0.2095, N2:0.7809, AR:0.0093" if "AR" in gas.species_names else "O2:0.21, N2:0.79"
    gas.TP = T3, P3
    gas.set_mixture_fraction(FAR_main / (1 + FAR_main), fuel, air)
    gas.equilibrate("HP")
    prod = ct.Quantity(gas, mass=1.0 + FAR_main, constant="HP")
    prod.TP = T5, P_ab                                   # products carried to the AB face
    f = ct.Solution("nDodecane_Reitz.yaml")
    f.TPX = T5, P_ab, fuel
    add = ct.Quantity(f, mass=FAR_ab, constant="HP")
    mix = prod + add                                     # Cantera mixes at constant H and P
    m = mix.phase
    m.equilibrate("HP")
    return float(m.T)


def ensure_dirs():
    os.makedirs(D7, exist_ok=True)
    os.makedirs(PLOTS, exist_ok=True)
