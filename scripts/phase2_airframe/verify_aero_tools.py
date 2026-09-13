"""Phase 2 tool verification: AeroSandbox transonic helpers + our slender-body wave-drag integral.

Checks
1. Sears-Haack wave drag, analytic: D/q = (9*pi/2) (A_max/l)^2  (von Karman; Raymer eq. 12.45 form)
   vs aerosandbox.library.aerodynamics.transonic.sears_haack_drag (radius form)
   vs ...sears_haack_drag_from_volume (volume form)
2. Our Fourier-sine slender-body integral (wave_drag_area) reproduces 1. for a Sears-Haack
   area distribution, and gives the textbook larger value for a parabolic (non-optimal) body.
3. Shape of AeroSandbox approximate_CD_wave (Raymer 12.5.10 + Mason/Lock fairing) at M = 1.0.
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aerosandbox.library.aerodynamics import transonic as tr
from aero_utils import wave_drag_area

l, r = 2.0, 0.09
A = np.pi * r**2
analytic = 9 * np.pi / 2 * (A / l) ** 2
V_sh = 3 * np.pi**2 * r**2 * l / 16      # Sears-Haack volume
print(f"1) Sears-Haack l={l} m, r_max={r} m:  analytic D/q = {analytic*1e4:.3f} cm^2")
print(f"   asb sears_haack_drag(r, l)          = {tr.sears_haack_drag(r, l)*1e4:.3f} cm^2   <-- ratio {tr.sears_haack_drag(r, l)/analytic:.2f}")
print(f"   asb sears_haack_drag_from_volume     = {tr.sears_haack_drag_from_volume(V_sh, l)*1e4:.3f} cm^2   <-- ratio {tr.sears_haack_drag_from_volume(V_sh, l)/analytic:.4f}")

x = np.linspace(0, l, 4001)
xi = x / l
S_sh = A * np.clip(4 * xi * (1 - xi), 0, None) ** 1.5
print(f"2) our integral, Sears-Haack area   = {wave_drag_area(x, S_sh)*1e4:.3f} cm^2  (ratio {wave_drag_area(x, S_sh)/analytic:.4f})")
# parabolic-arc body of same A_max: S = A (4 xi (1-xi))^2  -> textbook E_WD = 4/3 * ... compute analytic via series
S_par = A * (4 * xi * (1 - xi)) ** 2
print(f"   our integral, parabolic-area body = {wave_drag_area(x, S_par)*1e4:.3f} cm^2  (ratio {wave_drag_area(x, S_par)/analytic:.4f}; exact analytic 2048/(216 pi^2) = {2048/(216*np.pi**2):.4f})")

print("3) asb approximate_CD_wave / CD_wave(M1.2) at M = 0.90, 0.95, 1.00, 1.02, 1.05, 1.10, 1.20 (mach_crit = 0.85):")
for m in [0.90, 0.95, 1.00, 1.02, 1.05, 1.10, 1.20]:
    print(f"   M={m:.2f}: {float(tr.approximate_CD_wave(m, 0.85, 1.0)):.3f}")
