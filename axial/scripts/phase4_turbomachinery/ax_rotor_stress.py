"""Phase 4A: axial compressor rotor stress and blade vibration screening (run in .venv).

The pure-axial counterpart of the impeller gate (impeller_stress_gate.py / impeller_stress.py): every rotor row of the
fielded 3A-R blading (data/phase3ax/axt_<tag>.json) at the maximum continuous speed MCS = 105 %.
Material: Ti-6Al-4V, the gate's minimum-basis values at ~250 C (Fty 620, Ftu 681 MPa; the rear stages run at up to Tt3
~ 560 K, the front near ambient: conservative for the front), rho 4430, E 110 GPa.
1. BLADE ROOT. Section: the mass model's constant-section blade, taken as a symmetric parabolic-arc (biconvex) section
   of chord c and thickness t = (t/c) c: A = 2/3 c t, I_min = 4/105 c t^3 (both integrated from t(xi) = 4 t xi (1 - xi)),
   minimum section modulus Z = I_min / (t/2).
   * centrifugal: sigma_cf = rho w^2 (r_t^2 - r_h^2) / 2 (constant section: the mass model's blade; no taper credit);
   * gas bending: per blade tangential force W dC_theta / Z (dC_theta = stage work / U_mean) and axial force
     0.5 x (stage static-pressure rise, 50 % reaction) x annulus area / Z, uniform along the span -> root moment F h / 2,
     taken about the minimum-modulus axis (conservative: the stagger would share it between the axes);
   * peak = Kt 1.4 x (sigma_cf + sigma_gb) <= Fty (the gate's fillet factor and rule). Untwist and lean stresses ignored.
   * a row that fails with the constant section gets the smallest linear THICKNESS TAPER about the design mean t/c
     (root t (1 + d), tip t (1 - d), d in 0.05 steps): blade mass and mean blockage unchanged, less tip mass pulling
     on the root, larger root modulus; the taper is carried into the vibration model (PROVISIONAL geometry).
2. DISC. The mass model's constant-stress (Stodola) discs at 450 MPa (design speed). Checked like the impeller:
   yield sigma(MCS) <= Fty; burst (Robinson average-hoop, k 0.85) N_burst / N_MCS = sqrt(0.85 Ftu / sigma_avg(MCS))
   >= 1.20 (14 CFR 33.27). For a constant-stress disc sigma_avg = sigma. The allowable meeting both is found and the
   disc masses re-computed with it (engine_mass.stodola_disc) -> mass delta for the closure.
3. BLADE VIBRATION. First flap (1F) and second flap (2F) of each rotor blade: cantilever Euler-Bernoulli beam FE (cubic
   Hermite, 20 elements, clamped at the hub radius) with the centrifugal geometric stiffness of the rotating blade
   (tension T(r) = rho A w^2 (r_t^2 - r^2)/2, flapwise, no spin softening). Verified: static 3.5160 / 22.0345 (closed
   form), rotating at the speed parameter 1 and 2 (hub radius 0) against Wright, Smith, Thompson & Worley (1982),
   J. Appl. Mech. 49, 197-202: 3.6816 and 4.1373. Campbell: crossings of 1F / 2F with the engine orders of the vane
   rows next to each rotor (upstream and downstream vane counts) and 2E-4E, between 40 % and 105 % speed.
Outputs: data/phase4ax/rotor_stress_<tag>.json
"""
import os, sys, json, numpy as np
from scipy.linalg import eigh
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import engine_mass as em
TAG = sys.argv[1] if len(sys.argv) > 1 else "ax80000_opr5_t1150_n6_cap_3r"
RHO, E, FTY, FTU, KT, K_BURST, MCS = 4430.0, 110e9, 620e6, 681e6, 1.4, 0.85, 1.05
CP, G = 1004.5, 1.4

def beam_modes(L, EI, rhoA, omega, r_h, n_el=20, n_modes=2, taper=0.0):
    """flapwise modes of a clamped rotating beam, x from the hub (radius r_h) to the tip. taper: thickness taper
    t(xi) = t_m (1 + taper (1 - 2 xi)) about the mean (EI ~ t^3, rhoA ~ t); taper 0 = the uniform beam."""
    ne = n_el; le = L / ne; ndof = 2 * (ne + 1)
    K = np.zeros((ndof, ndof)); M = np.zeros((ndof, ndof)); Kg = np.zeros((ndof, ndof))
    tf = lambda xi: 1 + taper * (1 - 2 * xi)
    gp, gw = np.polynomial.legendre.leggauss(4)
    r_t = r_h + L
    xg = np.linspace(0, L, 401); Tt = np.array([rhoA * omega ** 2 * np.trapezoid(tf(xx / L) * (r_h + xx), xx) for xx in [xg[i:] for i in range(len(xg))]])
    for e in range(ne):
        xm = (e + 0.5) / ne; EIe, rAe = EI * tf(xm) ** 3, rhoA * tf(xm)
        ke = EIe / le ** 3 * np.array([[12, 6 * le, -12, 6 * le], [6 * le, 4 * le ** 2, -6 * le, 2 * le ** 2], [-12, -6 * le, 12, -6 * le], [6 * le, 2 * le ** 2, -6 * le, 4 * le ** 2]])
        me = rAe * le / 420 * np.array([[156, 22 * le, 54, -13 * le], [22 * le, 4 * le ** 2, 13 * le, -3 * le ** 2], [54, 13 * le, 156, -22 * le], [-13 * le, -3 * le ** 2, -22 * le, 4 * le ** 2]])
        idx = slice(2 * e, 2 * e + 4); K[idx, idx] += ke; M[idx, idx] += me
        kg = np.zeros((4, 4))
        for xi, w in zip(gp, gw):
            s = 0.5 * (xi + 1); x = (e + s) * le
            T = rhoA * omega ** 2 * (r_t ** 2 - (r_h + x) ** 2) / 2 if taper == 0 else float(np.interp(x, xg, Tt))
            dN = np.array([(-6 * s + 6 * s * s) / le, 1 - 4 * s + 3 * s * s, (6 * s - 6 * s * s) / le, -2 * s + 3 * s * s])   # dN/dx
            kg += T * np.outer(dN, dN) * w * 0.5 * le
        Kg[idx, idx] += kg
    free = np.arange(2, ndof)
    lam = eigh((K + Kg)[np.ix_(free, free)], M[np.ix_(free, free)], eigvals_only=True)[:n_modes]
    return np.sqrt(np.maximum(lam, 0)) / (2 * np.pi)

def verify():
    L, EI, rhoA = 1.0, 1.0, 1.0
    f0 = beam_modes(L, EI, rhoA, 0.0, 0.0) * 2 * np.pi
    out = dict(static=[float(v) for v in f0], static_exact=[3.5160, 22.0345])
    for eta, ref in ((1.0, 3.6816), (2.0, 4.1373)):
        f = beam_modes(L, EI, rhoA, eta * np.sqrt(EI / (rhoA * L ** 4)), 0.0)[0] * 2 * np.pi
        out[f"rotating_eta{eta:g}"] = dict(FE=float(f), Wright_1982=ref, err_pct=float(100 * (f / ref - 1)))
    return out

if __name__ == "__main__":
    ver = verify()
    print("beam FE verification:", json.dumps(ver), flush=True)
    AX = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"axt_{TAG}.json")))
    F = AX["levels"]["fielded"]; comp = F["comp"]; cyc = F["eval"]["cycle"]
    rpm = comp["input"]["rpm"]; om = rpm * np.pi / 30; omM = MCS * om; W = cyc["W_kgps"]
    T0, P0 = comp["input"]["T01"], comp["input"]["P01"]
    rows, discs = [], []
    stages = comp["stages"]
    # disc allowable meeting yield and burst at MCS (constant-stress disc: sigma_avg = sigma)
    sig_burst_MCS = K_BURST * FTU / 1.20 ** 2; sig_allow_design = min(FTY, sig_burst_MCS) / MCS ** 2
    for k, s in enumerate(stages):
        ro, st = s["rotor"], s["stator"]; c, h, rh, rt, Z = ro["chord"], ro["h"], ro["r_hub"], ro["r_tip"], ro["Z"]
        t = ro["tc"] * c; A = 2 / 3 * c * t; I = 4 / 105 * c * t ** 3; Zmod = I / (t / 2)
        # stage work and pressure (stacked from the stage PRs of the design, fielded work at eta_sizing)
        PRs = s["PR"]; T0o = T0 * (1 + (PRs ** ((G - 1) / G) - 1) / comp["eta_sizing"]); dh = CP * (T0o - T0)
        U_m = s["U_mean"]; dCt = dh / U_m
        P0o = P0 * PRs; Cx = comp["input"]["Cx"]
        Ts_in = T0 - Cx ** 2 / (2 * CP); Ts_out = T0o - Cx ** 2 / (2 * CP)
        p_in = P0 * (Ts_in / T0) ** (G / (G - 1)); p_out = P0o * (Ts_out / T0o) ** (G / (G - 1))
        A_ann = np.pi * (rt ** 2 - rh ** 2)
        F_t = W * dCt / Z; F_x = 0.5 * (p_out - p_in) * A_ann / Z; Fb = np.hypot(F_t, F_x)
        def stresses(dl):
            """thickness taper dl about the mean t/c (mass unchanged): root t = t (1 + dl), tip t (1 - dl)."""
            xx = np.linspace(0, h, 401); af = 1 + dl * (1 - 2 * xx / h)
            I_cf = np.trapezoid(af * (rh + xx), xx) / af[0]                # int A r dr / A_root
            Zr = Zmod * (1 + dl) ** 2
            out = {}
            for lab, w in (("design", om), ("MCS", omM)):
                s_cf = RHO * w ** 2 * I_cf
                s_gb = Fb * h / 2 / Zr * (w / om) ** 2          # gas load scales ~ with work ~ N^2 along the running line
                out[lab] = dict(sigma_cf_MPa=s_cf / 1e6, sigma_gb_MPa=s_gb / 1e6, sigma_peak_Kt_MPa=KT * (s_cf + s_gb) / 1e6)
            return out
        res0 = stresses(0.0)
        dl = next((d_ for d_ in np.arange(0.0, 0.501, 0.05) if stresses(d_)["MCS"]["sigma_peak_Kt_MPa"] <= FTY / 1e6), None)
        res = stresses(dl if dl is not None else 0.5)
        # vibration (with the taper adopted)
        EI, rhoA = E * I, RHO * A; tp = dl or 0.0
        f_static = beam_modes(h, EI, rhoA, 0.0, rh, taper=tp)
        Nf = np.linspace(0.40, 1.05, 27)
        fm_ = [beam_modes(h, EI, rhoA, n * om, rh, taper=tp) for n in Nf]; f1 = np.array([q[0] for q in fm_]); f2 = np.array([q[1] for q in fm_])
        Z_up = stages[k - 1]["stator"]["Z"] if k > 0 else None; Z_dn = st["Z"]
        orders = {"2E": 2, "3E": 3, "4E": 4, f"stator {k+1} ({Z_dn})": Z_dn}
        if Z_up: orders[f"stator {k} ({Z_up})"] = Z_up
        cross = []
        for name, eo in orders.items():
            for mode, fm in (("1F", f1), ("2F", f2)):
                exc = eo * Nf * rpm / 60; d = fm - exc
                for i in range(len(Nf) - 1):
                    if d[i] * d[i + 1] <= 0:
                        n_c = Nf[i] - d[i] * (Nf[i + 1] - Nf[i]) / (d[i + 1] - d[i]); cross.append(dict(mode=mode, order=name, speed_pct=float(100 * n_c)))
        # margins of 1F to the low engine orders at 100 % speed
        f1_100 = float(np.interp(1.0, Nf, f1))
        rows.append(dict(stage=k + 1, r_hub_mm=rh * 1e3, r_tip_mm=rt * 1e3, h_mm=h * 1e3, chord_mm=c * 1e3, t_mm=t * 1e3, Z=Z, Z_stator=Z_dn,
                         U_tip_MCS=omM * rt, F_t_N=F_t, F_x_N=F_x, uniform_MCS_peak_Kt_MPa=res0["MCS"]["sigma_peak_Kt_MPa"], taper=dl,
                         t_root_mm=t * (1 + (dl or 0)) * 1e3, t_tip_mm=t * (1 - (dl or 0)) * 1e3, tc_tip=ro["tc"] * (1 - (dl or 0)),
                         **{f"{lab}_{kk}": vv for lab, d_ in res.items() for kk, vv in d_.items()},
                         ok_root=bool(res["MCS"]["sigma_peak_Kt_MPa"] <= FTY / 1e6), f1_static_Hz=float(f_static[0]), f2_static_Hz=float(f_static[1]),
                         f1_100_Hz=f1_100, f1_100_over_4E=f1_100 / (4 * rpm / 60), f1_100_over_stator=f1_100 / (Z_dn * rpm / 60), crossings_40_105=cross))
        # disc: re-size at the burst / yield allowable
        m_b = RHO * Z * 0.7 * c * (ro["tc"] * c) * h; F_rim = m_b * om ** 2 * (rh + 0.5 * h)
        m_old, _, _ = em.stodola_disc(rh, om, RHO, em.SIG["Ti"], F_rim); m_new, h0, hr = em.stodola_disc(rh, om, RHO, sig_allow_design, F_rim)
        discs.append(dict(stage=k + 1, r_rim_mm=rh * 1e3, m_disc_450_kg=m_old, m_disc_new_kg=m_new, bore_width_new_mm=h0 * 1e3, rim_width_new_mm=hr * 1e3))
        T0, P0 = T0o, P0o
    sig450_MCS = em.SIG["Ti"] * MCS ** 2
    disc_chk = dict(sigma_design_model_MPa=em.SIG["Ti"] / 1e6, sigma_MCS_model_MPa=sig450_MCS / 1e6, burst_ratio_model=float(np.sqrt(K_BURST * FTU / sig450_MCS)),
                    yield_ok_model=bool(sig450_MCS <= FTY), sigma_allow_design_new_MPa=sig_allow_design / 1e6, sigma_MCS_new_MPa=sig_allow_design * MCS ** 2 / 1e6,
                    burst_ratio_new=float(np.sqrt(K_BURST * FTU / (sig_allow_design * MCS ** 2))),
                    mass_delta_kg=float(sum(d_["m_disc_new_kg"] - d_["m_disc_450_kg"] for d_ in discs)))
    out = dict(tag=TAG, rpm=rpm, material=dict(Fty_MPa=FTY / 1e6, Ftu_MPa=FTU / 1e6, Kt=KT, k_burst=K_BURST), verification=ver, blades=rows, discs=discs, disc_check=disc_chk)
    os.makedirs(os.path.join(AXROOT, "data", "phase4ax"), exist_ok=True)
    json.dump(out, open(os.path.join(AXROOT, "data", "phase4ax", f"rotor_stress_{TAG}.json"), "w"), indent=1, default=float)
    for r in rows:
        print(f"stage {r['stage']}: h {r['h_mm']:.1f} c {r['chord_mm']:.1f} t {r['t_mm']:.2f} mm Z {r['Z']}; uniform peak(Kt) {r['uniform_MCS_peak_Kt_MPa']:.0f} -> taper {r['taper']} "
              f"(t {r['t_root_mm']:.2f}/{r['t_tip_mm']:.2f} mm): MCS cf {r['MCS_sigma_cf_MPa']:.0f} gb {r['MCS_sigma_gb_MPa']:.0f} peak(Kt) {r['MCS_sigma_peak_Kt_MPa']:.0f} MPa ok {r['ok_root']};1F {r['f1_static_Hz']:.0f} Hz static, {r['f1_100_Hz']:.0f} at 100 % "
              f"(/4E {r['f1_100_over_4E']:.2f}, /stator {r['f1_100_over_stator']:.2f}); crossings {[(x['mode'], x['order'], round(x['speed_pct'],1)) for x in r['crossings_40_105']]}")
    print("disc:", json.dumps({k: round(v, 3) if isinstance(v, float) else v for k, v in disc_chk.items()}))
