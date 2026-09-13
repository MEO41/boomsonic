"""Phase 3 dash design-point cycle: Fn = 500 N at M 1.02 / 5000 m ISA (D1.1 moved to the Phase 2
drag design point, D2.1), with the intake modelled inside the cycle (replaces A2.3's 3 % flat
installation loss).

Intake (nose pitot, Phase 2 configuration):
  * normal shock at the lip at M 1.02: Pt ratio from Rankine-Hugoniot (gamma 1.4)
  * subsonic duct lip -> compressor face, length L_d (nose to engine face, Phase 2 layout):
      friction  dPt/Pt = f (L/D) q/Pt  at the mean duct Mach, f from Haaland (smooth, Re_D)
      diffusion dPt/Pt = K (1 - A1/A2)^2 q1/Pt  (Borda-Carnot form, K = 0.3 for a gentle conical
      diffuser; Idelchik, Handbook of Hydraulic Resistance, diffusers section)
Other losses: burner dP/P 0.05 (Lefebvre & Ballal: 0.04-0.06 for small annular combustors),
nozzle Cv 0.98, combustion efficiency 0.95 (post-processed on fuel flow).
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cycle_model as cm

M_DASH, H_DASH, FN_DASH = 1.02, 5000.0, 500.0
ETA_B = 0.95
L_DUCT = 1.32          # m, nose lip -> engine face (Phase 2 layout: 0.45 L_fus + 0.1)

def isa(h):
    T = 288.15 - 0.0065 * h; P = 101325.0 * (T / 288.15) ** 5.25588
    return T, P, P / (287.053 * T), np.sqrt(1.4 * 287.053 * T), 1.458e-6 * T ** 1.5 / (T + 110.4)

def normal_shock_recovery(M, g=1.4):
    if M <= 1.0: return 1.0
    a = ((g + 1) * M * M / ((g - 1) * M * M + 2)) ** (g / (g - 1))
    b = ((g + 1) / (2 * g * M * M - (g - 1))) ** (1 / (g - 1))
    return a * b

def qP(M, g=1.4):
    return 0.5 * g * M * M / (1 + 0.2 * M * M) ** (g / (g - 1))

def duct_loss(W, face_area_m2, M_lip=0.65, Tt=308.9, Pt=104.6e3):
    """total-pressure loss fraction of the subsonic intake duct."""
    g, R = 1.4, 287.053
    def area_at(M):
        return W * np.sqrt(Tt) / (Pt * np.sqrt(g / R) * M * (1 + 0.2 * M * M) ** (-(g + 1) / (2 * (g - 1))))
    A1 = area_at(M_lip); A2 = face_area_m2
    M2 = 0.45
    for _ in range(50):  # Mach at the face from its area
        f = area_at(M2) - A2; df = (area_at(M2 + 1e-4) - area_at(M2)) / 1e-4; M2 -= f / df
    Mm = 0.5 * (M_lip + M2); Dm = np.sqrt(4 * 0.5 * (A1 + A2) / np.pi)
    T = Tt / (1 + 0.2 * Mm * Mm); P = Pt / (1 + 0.2 * Mm * Mm) ** 3.5
    rho = P / (R * T); V = Mm * np.sqrt(g * R * T); mu = 1.458e-6 * T ** 1.5 / (T + 110.4)
    Re = rho * V * Dm / mu
    f = (-1.8 * np.log10(6.9 / Re)) ** -2                        # Haaland, smooth pipe
    fric = f * L_DUCT / Dm * qP(Mm)
    diff = 0.3 * (1 - A1 / A2) ** 2 * qP(M_lip) if A2 > A1 else 0.0
    return dict(dPqP=fric + diff, friction=fric, diffusion=diff, M_face=M2, A_lip_cm2=A1 * 1e4, D_mean_mm=Dm * 1e3, Re=Re, f=f)

def design(OPR, T4, eta_c, eta_t, face_area_m2=None, nozz='CV', prob=None, Fn=FN_DASH, duct_override=None):
    """Size the engine (W) for Fn at the dash; iterate the duct loss on the resulting airflow."""
    T0, P0, rho0, a0, mu0 = isa(H_DASH)
    rec = normal_shock_recovery(M_DASH)
    Tt = T0 * (1 + 0.2 * M_DASH ** 2); Pt = P0 * (1 + 0.2 * M_DASH ** 2) ** 3.5 * rec
    if prob is None:
        prob, _ = cm.build(design_W='Fn', nozz_type=nozz)
    dl = dict(dPqP=0.03)
    W = 1.1
    for _ in range(4):
        if duct_override is not None:
            dl = dict(dPqP=duct_override)
        else:
            A_face = face_area_m2 if face_area_m2 is not None else W / 160.0 * (101325 / Pt) * np.sqrt(Tt / 288.15)  # ~160 kg/s/m2 corrected flow per face area
            dl = duct_loss(W, A_face, Tt=Tt, Pt=Pt)
        d = None
        for Wg, tprg in ((None, None), (W, 2.0), (W, 2.6), (W * 1.2, 3.0), (W * 1.2, 3.5), (W * 0.9, 2.4)):
            cm.set_design(prob, M_DASH, H_DASH, OPR, T4, eta_c, eta_t, Fn_N=Fn, duct_dPqP=dl["dPqP"], ram_recovery=rec, burner_dPqP=0.05, Cv=0.98)
            if Wg is not None:                               # retry from other initial guesses (robustness at high OPR / low efficiency)
                prob['DESIGN.balance.W'] = Wg / 0.45359237; prob['DESIGN.balance.turb_PR'] = tprg
            prob.run_model()
            d = cm.read(prob, 'DESIGN', eta_b=ETA_B)
            if d["res"] < 1e-4 and abs(d["Fn_N"] - Fn) < 0.5: break
        if abs(d["W_kgps"] - W) < 1e-4: break
        W = d["W_kgps"]
    d.update(ram_recovery=rec, duct=dl, A_capture_cm2=d["W_kgps"] / (rho0 * M_DASH * a0) * 1e4, spec_thrust=d["Fn_N"] / d["W_kgps"])
    return d, prob

if __name__ == "__main__":
    d, prob = design(4.0, 1150.0, 0.78, 0.85)
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()})
