"""Phase 2 flutter screening of the thin (5 % / 4.5 %) lifting surfaces. SCREENING ONLY.

Method: NACA TN 4197 (Martin, 1958) flutter boundary in the simplified closed form widely used
for thin fins (e.g. Apogee Components "Peak of Flight" #291):
    V_f = a * sqrt( G / X ),   X = 1.337 AR^3 P (lambda + 1) / (2 (AR + 2) (t/c)^3)
AR = b_e^2 / S_e of ONE exposed panel, lambda = c_tip/c_root(exposed), P = ambient static
pressure, a = speed of sound, G = shear modulus of an equivalent SOLID plate of thickness t.
We invert it for the G required to put V_f at 1.25 x the highest flight speed at that
condition, then compare with the G_eff of a thin-walled closed composite section:
    G_eff = G_skin * J_box / J_plate,  J_box = 4 A^2 t_s / perimeter (biconvex, A = 2/3 c t),
    J_plate = c t^3 / 3,   G_skin = 20 GPa (+-45 woven carbon/epoxy; CLT gives ~27 GPa for
    E1 = E2 = 57 GPa, G12 = 4.5 GPa, nu 0.05 -> knocked down to 20 GPa).
Limitations: the formula was derived for flat solid fins, ignores bending-torsion frequency
separation, mass balance and transonic dip; it is a go/no-go screen for Phase 2 only. A
proper flutter analysis (modal + unsteady aero) is a Phase 4/5 item.
"""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from airframe_model import Config, ROOT
from aero_utils import isa

G_SKIN = 20e9
T_SKIN = 0.5e-3          # each skin: 2 plies x 0.25 mm (mass budget layup)
MARGIN = 1.25
CONDS = [("dash M1.05 / 5 km", 1.05, 5000.0), ("accel M0.80 / 300 m", 0.80, 300.0), ("descent M0.95 / 3 km", 0.95, 3000.0)]

def screen(S=0.30):
    c = Config(S_wing=S); rows = []
    for name, srf in c.surfaces().items():
        bh = srf.half_span(); cr = srf.c_root; ct = cr * srf.taper
        y0 = 0.0 if srf.vertical else min(c.r_fus, 0.95 * bh)
        c_e = cr + (ct - cr) * y0 / bh; b_e = bh - y0
        S_e = 0.5 * (c_e + ct) * b_e; AR = b_e ** 2 / S_e; lam = ct / c_e
        c_ref = 0.5 * (c_e + ct)                                  # mean exposed chord for the section stiffness
        t = srf.tc * c_ref
        J_box = 4 * (2 / 3 * c_ref * t) ** 2 * T_SKIN / (2.0 * c_ref)
        J_plate = c_ref * t ** 3 / 3
        G_eff = G_SKIN * J_box / J_plate
        for cname, M, h in CONDS:
            T, P, rho, a, mu = isa(h)
            X = 1.337 * AR ** 3 * P * (lam + 1) / (2 * (AR + 2) * srf.tc ** 3)
            G_req = X * (MARGIN * M * a / a) ** 2                 # V_f = 1.25 V  ->  G = X (V_f/a)^2
            Vf_eff = a * np.sqrt(G_eff / X)
            rows.append(dict(surface=name, condition=cname, AR_panel=AR, taper=lam, tc=srf.tc, c_ref_m=c_ref,
                             G_req_GPa=G_req / 1e9, G_eff_GPa=G_eff / 1e9, stiffness_factor=G_eff / G_req,
                             V_flutter_mps=Vf_eff, V_flight_mps=M * a, Vf_over_V=Vf_eff / (M * a)))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    df = screen(0.30)
    df.to_csv(os.path.join(ROOT, "data", "phase2_flutter_screening.csv"), index=False)
    pd.set_option("display.width", 200)
    print(df.round(3).to_string(index=False))
    print(f"\nminimum V_f / V over all surfaces and conditions = {df.Vf_over_V.min():.2f} (screen requires >= {MARGIN})")
