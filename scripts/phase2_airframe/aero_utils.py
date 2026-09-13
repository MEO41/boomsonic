"""Shared aerodynamic utilities for Phase 2 (ISA, skin friction, form factors, wave drag)."""
import numpy as np

G0 = 9.80665

def isa(h):
    """ISA troposphere/lower stratosphere. Returns T [K], P [Pa], rho [kg/m3], a [m/s], mu [Pa s]."""
    h = float(h)
    if h <= 11000.0:
        T = 288.15 - 0.0065 * h; P = 101325.0 * (T / 288.15) ** 5.25588
    else:
        T = 216.65; P = 22632.06 * np.exp(-G0 * (h - 11000.0) / (287.053 * T))
    rho = P / (287.053 * T); a = np.sqrt(1.4 * 287.053 * T)
    mu = 1.458e-6 * T ** 1.5 / (T + 110.4)      # Sutherland
    return T, P, rho, a, mu

def cf_turbulent(Re, M, length, k_rough):
    """Raymer (Aircraft Design, 6th ed.) eq. 12.27 turbulent flat-plate Cf with compressibility,
    with the surface-roughness cutoff Reynolds number (eq. 12.28 subsonic / 12.29 transonic+)."""
    Re_cut_sub = 38.21 * (length / k_rough) ** 1.053
    Re_cut_trans = 44.62 * (length / k_rough) ** 1.053 * max(M, 1e-3) ** 1.16
    Re_cut = Re_cut_sub if M < 0.9 else Re_cut_trans
    Re_eff = min(Re, Re_cut)
    return 0.455 / (np.log10(Re_eff) ** 2.58 * (1 + 0.144 * M ** 2) ** 0.65), Re_eff < Re

def ff_wing(tc, xc_max, M, sweep_maxt_deg):
    """Raymer eq. 12.30: wing/tail form factor."""
    return (1 + 0.6 / xc_max * tc + 100 * tc ** 4) * (1.34 * M ** 0.18 * np.cos(np.radians(sweep_maxt_deg)) ** 0.28)

def ff_body(f):
    """Raymer eq. 12.31: fuselage/smooth canopy form factor, f = l/d."""
    return 0.9 + 5.0 / f ** 1.5 + f / 400.0

def wave_drag_area(x, S, n_max=200):
    """Zero-lift wave-drag area D/q of a slender equivalent body (von Karman slender-body theory,
    valid as M -> 1+ for the transonic area rule). Fourier-sine form:
        x = (l/2)(1 - cos th),  S'(x) = l * sum a_n sin(n th),  D/q = (pi l^2 / 4) sum n a_n^2
    Requires S'(0) = S'(l) = 0 (pointed or zero-slope ends); any kink in S(x) makes the full series
    diverge logarithmically, so shape comparisons use n_max ~ l / d_body. Verified against Sears-Haack in
    verify_aero_tools.py.  x: stations [m] from 0 to l; S: cross-section area [m2]."""
    x = np.asarray(x, float); S = np.asarray(S, float)
    l = x[-1] - x[0]
    Sp = np.gradient(S, x)
    th = np.linspace(0, np.pi, 4001)
    xs = x[0] + 0.5 * l * (1 - np.cos(th))
    Sp_th = np.interp(xs, x, Sp) / l
    N = n_max   # truncate: slender-body theory does not resolve features shorter than ~1 body diameter
    n = np.arange(1, N + 1)
    a = np.array([2 / np.pi * np.trapezoid(Sp_th * np.sin(k * th), th) for k in n])
    return np.pi * l ** 2 / 4 * np.sum(n * a ** 2)
