"""Phase 2 parametric airframe geometry + zero-lift drag build-up (subsonic to M 1.05).

Method (all conceptual-level, cited):
  * Friction + form: Raymer, Aircraft Design 6th ed., sec. 12.5.3-12.5.5
      Cf eq. 12.27 (turbulent, compressible) with roughness cutoff eq. 12.28/12.29,
      k = 0.052e-5 m smooth molded composite (Raymer Table 12.5),
      form factors eq. 12.30 (wing/tails) and 12.31 (body), interference Q (Raymer 12.5.5),
      wetted area of thin surfaces eq. 7.10 (t/c < 0.05) / 7.11.
  * Base drag of the annulus between nozzle and body: MIL-HDBK-762 fit (via AeroSandbox
    fuselage_base_drag_coefficient, verified to import; plume-off value).
  * Wave drag: Raymer eq. 12.45/12.46 form  (D/q)_wave,M1.2 = E_WD * 9pi/2 (A_max/l)^2,
      where A_max, l come from the M = 1 normal-cut area distribution of the WHOLE aircraft
      minus the inlet capture stream-tube (transonic area rule).
      Mach dependence below M 1.2 from AeroSandbox approximate_CD_wave (Raymer 12.5.10 +
      Mason ch. 7 / Lock drag-rise shape), anchored at M 1.05 and 1.2; its value at M 1.00-1.02
      depends on the body critical Mach (Raymer Fig. 12.28 fit): ~0.49 at M 1.00, ~0.71 at M 1.02 here.
      Design E_WD = max(E_WD_FLOOR = 1.8 [Raymer 'typical supersonic design' lower bound],
      E_geom), where E_geom is the slender-body integral of the actual area distribution
      (harmonics n <= l/d) divided by the Sears-Haack value of the same A_max and length.
  * Leakage & protuberance: +5 % of subsonic parasite drag (Raymer 12.5.6 range for jets).
  * Lift-dependent drag: Raymer eq. 12.49 Oswald e (swept wing) subsonic; k = 1/CL_alpha
    (zero leading-edge suction) at M >= 1 with CL_alpha from Raymer eq. 12.6.
"""
import json, os, numpy as np
from dataclasses import dataclass, field, asdict
from aero_utils import isa, cf_turbulent, ff_wing, ff_body, wave_drag_area
from aerosandbox.library.aerodynamics.transonic import approximate_CD_wave
from aerosandbox.aerodynamics.aero_3D.aero_buildup_submodels.fuselage_aerodynamics_utilities import (
    fuselage_base_drag_coefficient, critical_mach)

K_ROUGH = 0.052e-5          # m, smooth molded composite (Raymer Table 12.5)
LP_FRAC = 0.05              # leakage & protuberance fraction
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@dataclass
class Surface:
    """Trapezoidal lifting surface, exposed part only is wetted. Symmetric pair unless vertical."""
    S_ref: float             # reference (theoretical, through-body) planform area [m2]
    AR: float
    taper: float
    sweep_le_deg: float
    tc: float
    xc_maxt: float = 0.40    # NACA 64A-series max thickness at 40 % chord
    x_root_le: float = 1.0   # x of theoretical root LE [m]
    vertical: bool = False
    Q: float = 1.0           # interference factor

    # horizontal surfaces: AR = b^2/S (full span b). vertical fin: AR = h^2/S (h = fin height).
    def half_span(self):
        return np.sqrt(self.AR * self.S_ref) if self.vertical else np.sqrt(self.AR * self.S_ref) / 2
    @property
    def span(self):
        return self.half_span() if self.vertical else 2 * self.half_span()
    @property
    def c_root(self):
        return (self.S_ref if self.vertical else self.S_ref / 2) * 2 / (self.half_span() * (1 + self.taper))
    @property
    def mac(self):
        l = self.taper
        return 2 / 3 * self.c_root * (1 + l + l * l) / (1 + l)
    def x_ac(self):
        """x of the MAC quarter-chord point (Raymer Fig. 7.6 construction)."""
        y_mac = self.half_span() / 3 * (1 + 2 * self.taper) / (1 + self.taper)
        return self.x_root_le + y_mac * np.tan(np.radians(self.sweep_le_deg)) + 0.25 * self.mac
    def sweep_at(self, frac):
        """sweep of the frac-chord line [deg]."""
        dx = self.c_root * (1 - self.taper) * frac
        return np.degrees(np.arctan(np.tan(np.radians(self.sweep_le_deg)) - dx / self.half_span()))

    def exposed(self, r_body):
        """exposed planform area [m2] (both halves for horizontal surfaces) and exposed root chord."""
        bh = self.half_span(); cr = self.c_root; ct = cr * self.taper
        y0 = 0.0 if self.vertical else min(r_body, 0.95 * bh)
        c_y0 = cr + (ct - cr) * y0 / bh
        area_half = 0.5 * (c_y0 + ct) * (bh - y0)
        return (area_half if self.vertical else 2 * area_half), c_y0, y0

    def S_wet(self, r_body):
        Sexp, _, _ = self.exposed(r_body)
        return Sexp * (1.977 + 0.52 * self.tc)   # Raymer eq. 7.10 (t/c <= 0.05; tails and wing here are <= 0.05)

    def area_distribution(self, x, r_body):
        """normal-cut cross-sectional area of the exposed surface at stations x (parabolic-arc
        thickness per chord, integrated over span)."""
        bh = self.half_span(); cr = self.c_root; ct = cr * self.taper
        y0 = 0.0 if self.vertical else min(r_body, 0.95 * bh)
        ys = np.linspace(y0, bh, 60)
        A = np.zeros_like(x)
        tanL = np.tan(np.radians(self.sweep_le_deg))
        for j in range(len(ys) - 1):
            y = 0.5 * (ys[j] + ys[j + 1]); dy = ys[j + 1] - ys[j]
            c = cr + (ct - cr) * y / bh; xle = self.x_root_le + y * tanL
            xi = (x - xle) / c
            t = np.where((xi > 0) & (xi < 1), 4 * self.tc * c * xi * (1 - xi), 0.0)
            A += t * dy
        return A if self.vertical else 2 * A


@dataclass
class Config:
    name: str = "C1 conventional swept wing + all-moving HT + VT, nose pitot inlet"
    # engine envelope (overwritten from data/engine_envelope.json when present)
    D_engine: float = 0.150
    L_engine: float = 0.400
    # fuselage
    L_fus: float = 2.70                 # D2.4: fuselage-length trade with database engine envelope
    D_fus_extra: float = 0.030          # body diameter = engine casing + 2 x 15 mm (structure, clearance, cooling air)
    L_nose_frac: float = 0.45           # forebody length / L_fus (inlet lip -> max diameter); shaping sweep D2.2/D2.4
    L_bt_frac: float = 0.28             # boattail length / L_fus (D2.6 aft-closure trade)
    A_capture: float = 47.5e-4          # m2, inlet stream-tube at M1/5 km (pyCycle W = 1.120 kg/s)
    lip_wall: float = 0.002             # sharp supersonic pitot lip: outer dia = capture dia + 2 x 2 mm
    A_nozzle: float = 49.1e-4           # nozzle throat = exit area (convergent) [m2]
    t_nozzle_wall: float = 0.002
    plume_area_ratio: float = 1.16     # fully-expanded jet / throat, isentropic, NPR 3.40, gamma 1.33 (M9 = 1.465)
    area_rule_waist: float = 0.5        # fraction of wing cross-section area removed from the body at the wing (D2.6; ~10 mm engine clearance kept)
    # wing
    S_wing: float = 0.30
    AR: float = 3.0
    taper: float = 0.20
    sweep_le: float = 55.0             # shaping sweep D2.2 (spreads wing volume along x)
    tc: float = 0.05
    x_wing_frac: float = 0.45           # root LE station / L_fus (D2.4)
    # tails (Raymer Table 6.4, jet fighter tail volume coefficients)
    c_HT: float = 0.40
    c_VT: float = 0.07
    tail_tc: float = 0.045
    tailless: bool = False
    E_WD: float = None                  # None -> max(1.8, E_geom). Raymer: ~1.2 very clean, 1.8-2.2 typical, 2.5-3 poor

    def __post_init__(self):
        p = os.path.join(ROOT, "data", "engine_envelope.json")
        if os.path.exists(p):
            e = json.load(open(p)); self.D_engine = e["D_engine_m"]; self.L_engine = e["L_engine_m"]

    @property
    def D_fus(self): return self.D_engine + self.D_fus_extra
    @property
    def r_fus(self): return self.D_fus / 2

    # ---------------- geometry ----------------
    def body_radius(self, x):
        L = self.L_fus; Ln = self.L_nose_frac * L; Lb = self.L_bt_frac * L
        r0 = np.sqrt(self.A_capture / np.pi) + self.lip_wall; rm = self.r_fus
        r_noz = np.sqrt(self.A_nozzle / np.pi) + self.t_nozzle_wall
        r = np.full_like(x, rm)
        m = x < Ln
        s = x[m] / Ln
        r[m] = np.sqrt((np.pi * r0 ** 2 + (np.pi * rm ** 2 - np.pi * r0 ** 2) * 0.5 * (1 - np.cos(np.pi * s))) / np.pi)   # cosine AREA law: zero dA/dx at lip and at max dia
        m = x > L - Lb
        s = (x[m] - (L - Lb)) / Lb
        r[m] = rm - (rm - r_noz) * (3 * s ** 2 - 2 * s ** 3)        # cubic boattail (zero slope both ends)
        return r

    def surfaces(self):
        L = self.L_fus
        w = Surface(self.S_wing, self.AR, self.taper, self.sweep_le, self.tc, x_root_le=self.x_wing_frac * L)
        out = {"wing": w}
        x_ac_w = w.x_ac()
        x_ac_t = 0.90 * L                     # tail MAC quarter-chords near the start of the nozzle
        l_t = x_ac_t - x_ac_w
        if not self.tailless:
            S_h = self.c_HT * w.mac * self.S_wing / l_t            # Raymer eq. 6.29
            h = Surface(S_h, 3.0, 0.30, 40.0, self.tail_tc, Q=1.04)
            h.x_root_le = x_ac_t - (h.x_ac() - h.x_root_le)
            out["htail"] = h
        S_v = self.c_VT * w.span * self.S_wing / l_t               # Raymer eq. 6.28
        v = Surface(S_v, 1.2, 0.35, 45.0, self.tail_tc, vertical=True, Q=1.04)
        v.x_root_le = x_ac_t - (v.x_ac() - v.x_root_le)
        out["vtail"] = v
        self._x_ac_w = x_ac_w; self._l_t = l_t
        return out

    def area_distribution(self, n=1500, plume=0.15):
        """equivalent-body area (external minus capture stream-tube) incl. a short constant plume."""
        L = self.L_fus
        x = np.linspace(0, L + plume, n)
        r = self.body_radius(np.minimum(x, L))
        A_body = np.pi * r ** 2
        A_exit = np.pi * self.body_radius(np.array([L]))[0] ** 2
        A_plume = self.plume_area_ratio * self.A_nozzle
        # past the nozzle exit the jet plume replaces the body; expands to fully-expanded area over 5 cm
        A_body = np.where(x > L, A_exit + (A_plume - A_exit) * (3 * np.clip((x - L) / 0.05, 0, 1) ** 2 - 2 * np.clip((x - L) / 0.05, 0, 1) ** 3), A_body)
        # sharp lip: fair the equivalent body from zero over the first 2 cm
        ramp = np.clip(x / 0.02, 0, 1)
        A = (A_body - self.A_capture) * ramp
        surfs = self.surfaces()
        for k, s in surfs.items():
            A = A + s.area_distribution(x, self.r_fus if not s.vertical else 0.0)
        # optional area-rule waist at the wing
        if self.area_rule_waist > 0:
            Aw = surfs["wing"].area_distribution(x, self.r_fus)
            A = A - self.area_rule_waist * Aw
        return x, np.maximum(A, 0.0)

    def body_wetted(self):
        x = np.linspace(0, self.L_fus, 800); r = self.body_radius(x)
        return np.trapezoid(2 * np.pi * r * np.sqrt(1 + np.gradient(r, x) ** 2), x)

    def body_volume(self):
        x = np.linspace(0, self.L_fus, 800); r = self.body_radius(x)
        return np.trapezoid(np.pi * r ** 2, x)

    # ---------------- drag ----------------
    def drag_breakdown(self, M, h, E_WD=None, wave_fairing=True):
        """zero-lift drag area D/q [m2] by component at Mach M, altitude h."""
        T, P, rho, a, mu = isa(h)
        V = max(M, 0.05) * a
        Rel = rho * V / mu
        out = {}
        # fuselage
        f = self.L_fus / self.D_fus
        cf, cut = cf_turbulent(Rel * self.L_fus, M, self.L_fus, K_ROUGH)
        out["fuselage friction+form"] = cf * ff_body(f) * 1.0 * self.body_wetted()
        # surfaces
        for k, s in self.surfaces().items():
            Sexp, c_r, _ = s.exposed(self.r_fus if not s.vertical else 0.0)
            cf_s, _ = cf_turbulent(Rel * s.mac, M, s.mac, K_ROUGH)
            out[f"{k} friction+form"] = cf_s * ff_wing(s.tc, s.xc_maxt, max(M, 0.05), s.sweep_at(s.xc_maxt)) * s.Q * s.S_wet(self.r_fus if not s.vertical else 0.0)
        # base annulus
        r_noz = np.sqrt(self.A_nozzle / np.pi)
        A_base = np.pi * ((r_noz + self.t_nozzle_wall) ** 2 - r_noz ** 2)
        out["nozzle base annulus"] = float(fuselage_base_drag_coefficient(mach=M)) * A_base
        parasite = sum(out.values())
        out["leakage+protuberance"] = LP_FRAC * parasite
        # wave drag
        x, A = self.area_distribution()
        Amax = A.max(); lw = x[A > 1e-6][-1] - x[A > 1e-6][0]
        sh = 9 * np.pi / 2 * (Amax / lw) ** 2
        Mcrit = float(critical_mach(fineness_ratio_nose=self.L_nose_frac * self.L_fus / self.D_fus))
        frac = float(approximate_CD_wave(M, Mcrit, 1.0)) if wave_fairing else 1.0
        E_geom = self.E_geom(x, A, lw, sh)
        if E_WD is None:
            E_WD = self.E_WD if self.E_WD is not None else max(1.8, E_geom)
        out["wave"] = E_WD * sh * frac
        self._wave_info = dict(A_max_cm2=Amax * 1e4, l_eq=lw, SH_cm2=sh * 1e4, Mcrit=Mcrit, frac=frac, E_geom=E_geom, E_WD_used=E_WD)
        return out

    def E_geom(self, x=None, A=None, lw=None, sh=None):
        key = (self.L_fus, self.D_fus, self.S_wing, self.AR, self.sweep_le, self.tc, self.x_wing_frac, self.L_nose_frac, self.tailless)
        if getattr(self, "_Eg_key", None) == key:
            return self._Eg
        if x is None:
            x, A = self.area_distribution(); lw = x[A > 1e-6][-1] - x[A > 1e-6][0]; sh = 9 * np.pi / 2 * (A.max() / lw) ** 2
        self._Eg = wave_drag_area(x, A, n_max=int(np.ceil(lw / self.D_fus))) / sh; self._Eg_key = key
        return self._Eg

    def CDS(self, M, h, **kw):
        return sum(self.drag_breakdown(M, h, **kw).values())

    def k_induced(self, M):
        """lift-dependent drag factor k in CD_i = k CL^2 (reference S_wing)."""
        Lam = self.sweep_le
        if M < 0.95:
            e = 4.61 * (1 - 0.045 * self.AR ** 0.68) * np.cos(np.radians(Lam)) ** 0.15 - 3.1     # Raymer eq. 12.49
            return 1.0 / (np.pi * self.AR * e)
        return 1.0 / self.CL_alpha(M)

    def CL_alpha(self, M):
        """Raymer eq. 12.6 (subsonic/transonic, beta -> small near M 1), per rad, ref S_wing, with
        exposed-area and fuselage-lift factors F = 1.07(1+d/b)^2 (eq. 12.7)."""
        w = self.surfaces()["wing"]
        beta2 = max(1 - M ** 2, 0.02)
        eta = 0.95
        tanLm = np.tan(np.radians(w.sweep_at(w.xc_maxt)))
        A = self.AR
        Sexp, _, _ = w.exposed(self.r_fus)
        F = min(1.07 * (1 + self.D_fus / w.span) ** 2, 0.98 * self.S_wing / Sexp)
        return 2 * np.pi * A / (2 + np.sqrt(4 + A ** 2 * beta2 / eta ** 2 * (1 + tanLm ** 2 / beta2))) * Sexp / self.S_wing * F

    def summary(self):
        s = self.surfaces()
        w = s["wing"]
        d = dict(name=self.name, L_fus=self.L_fus, D_fus=self.D_fus, fineness=self.L_fus / self.D_fus,
                 S_wing=self.S_wing, span=w.span, c_root=w.c_root, mac=w.mac, AR=self.AR, sweep_le=self.sweep_le, tc=self.tc,
                 S_htail=s["htail"].S_ref if "htail" in s else 0.0, S_vtail=s["vtail"].S_ref, tail_arm=self._l_t,
                 S_wet_body=self.body_wetted(), body_volume_L=self.body_volume() * 1000,
                 S_wet_wing=w.S_wet(self.r_fus), S_wet_tails=sum(v.S_wet(self.r_fus if not v.vertical else 0.0) for k, v in s.items() if k != "wing"))
        return d
