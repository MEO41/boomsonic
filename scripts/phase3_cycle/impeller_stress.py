"""Phase 3R: impeller stress as a DESIGN constraint (run in .venv; scikit-fem).

Wraps the verified solvers of the Phase 4 impeller gate (scripts/phase4_turbomachinery/impeller_stress_gate.py,
verification in verify_axisym_fe.py and the gate's plate check) as a function of the impeller geometry, so that every
candidate in the Phase 3R trade is stress-sized, not checked afterwards:
  * exducer blade root: Morley-plate FE of one exducer blade (backsweep rising linearly from 0 at 0.7 r2 to beta2b at
    r2), Kt 1.4. The ROOT THICKNESS is sized: the smallest t_root >= t_floor whose peak root stress at the maximum
    continuous speed is <= Fty. Blade thickness tapers linearly to 0.8 mm at the shroud (as in the gate).
  * exit blockage: B2 = Z_exit t_mean / (2 pi r2 cos beta2b); physical exit width b2_geo = b2_eff / (1 - B2), where
    b2_eff is the TurboFlow (effective-width) design width. The plate model uses b2_geo (the real blade height).
  * disc: boreless hub (the gate showed a through-bore is marginal), back-face boss A/r2 0.1-0.3 (p 2), axisymmetric
    FE with the smeared blade pull, then the best shape with the eye-to-exit thermal gradient (n = 1, 2).
  * burst: Robinson average-hoop criterion, k 0.85.
Criteria (same material basis as the gate: Ti-6Al-4V at ~250 C, minimum basis Fty 620 / Ftu 681 MPa):
  * stresses evaluated at the maximum continuous speed MCS = 105 % of design speed (the MCS definition used in the
    Phase 4 rotordynamics, API 617 practice) -> peak von Mises (disc, with thermal) <= Fty; blade root x Kt <= Fty;
  * N_burst / N_MCS >= 1.20 (14 CFR 33.27: no burst at 120 % of the maximum permissible speed).
"""
import os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery"))
import impeller_stress_gate as g
import axisym_fe as fe

E_HOT, ALPHA = 98e9, 9.2e-6
MCS = 1.05
T_TIP = 0.8e-3

def set_geometry(rpm, r2, b2_geo, r1s, r1h, L, t_mean):
    g.RPM = rpm; g.W = rpm * np.pi / 30 * MCS          # all stresses at the maximum continuous speed
    g.R2, g.B2, g.R1S, g.R1H, g.L = r2, b2_geo, r1s, r1h, L
    g.LS = L - b2_geo; g.U2 = g.W * r2; g.T_BLADE = t_mean

def blockage(t_root, r2, beta2b, Z_exit):
    return Z_exit * 0.5 * (t_root + T_TIP) / (2 * np.pi * r2 * np.cos(np.radians(beta2b)))

def size_blade(rpm, r2, b2_eff, r1s, r1h, L, beta2b, Z_exit=24, t_floor=1.6e-3, t_max=8e-3):
    """smallest root thickness meeting Kt-peak <= Fty at MCS; iterates thickness, blockage and blade height."""
    t = t_floor; hist = []
    for _ in range(8):
        B = blockage(t, r2, beta2b, Z_exit); b2g = b2_eff / (1 - B)
        set_geometry(rpm, r2, b2g, r1s, r1h, L, 0.5 * (t + T_TIP))
        s = g.plate_root(t, beta2=abs(beta2b))["sig_root_Kt"] if abs(beta2b) > 0.1 else 0.0
        hist.append(dict(t_root_mm=t * 1e3, sigma_MPa=s / 1e6, B2=B, b2_geo_mm=b2g * 1e3))
        if s <= g.FTY * 1.0005 and (t == t_floor or abs(s / g.FTY - 1) < 0.01):
            break
        t_new = float(np.clip(t * s / g.FTY, t_floor, t_max))      # root bending ~ 1/t at fixed load per unit thickness
        if abs(t_new - t) < 1e-5: break
        t = t_new
    ok = s <= g.FTY * 1.01
    return dict(t_root_mm=t * 1e3, t_mean_mm=0.5 * (t + T_TIP) * 1e3, sigma_root_MCS_MPa=s / 1e6, B2=B, b2_geo=b2g, ok=bool(ok and t < t_max), hist=hist)

def _solve(dT=None, E=110e9):
    orig = fe.solve_rotating
    def patched(*a, **k):
        k["E"] = E
        if dT is not None: k.update(dT=dT, alpha=ALPHA)
        return orig(*a, **k)
    fe.solve_rotating = patched
    return orig

def disc(T_eye, T_exit, A_fracs=(0.1, 0.2, 0.3)):
    """boreless hub, boss sweep, then thermal on the best shape; geometry must already be set (set_geometry)."""
    hubs = []
    for Af in A_fracs:
        orig = _solve()
        try: d = g.analyse_hub(0.0, 0.003, Af * g.R2, 2.0, omega=g.W)
        finally: fe.solve_rotating = orig
        d["A_over_r2"] = Af; hubs.append(d)
    best = min(hubs, key=lambda h: h["vm_peak_MPa"]); th = []
    for n in (1, 2):
        dT = (lambda n: (lambda r, z: (T_exit - T_eye) * np.clip(r / g.R2, 0, 1) ** n))(n)
        orig = _solve(dT=dT, E=E_HOT)
        try: d = g.analyse_hub(0.0, 0.003, best["A_mm"] / 1e3, 2.0, omega=g.W)
        finally: fe.solve_rotating = orig
        th.append(d["vm_peak_MPa"])
    vm_th = max(th)
    return dict(A_over_r2=best["A_over_r2"], vm_mech_MCS_MPa=best["vm_peak_MPa"], vm_thermal_MCS_MPa=vm_th, yield_MS=g.FTY / 1e6 / vm_th - 1,
                burst_ratio_MCS=best["burst_ratio"], mass_kg=best["mass_total_kg"],
                ok=bool(vm_th <= g.FTY / 1e6 and best["burst_ratio"] >= 1.20))

def evaluate(rpm, r2, b2_eff, r1s, r1h, L, beta2b, T_eye, T_exit, Z_exit=24, t_floor=1.6e-3, do_disc=True):
    b = size_blade(rpm, r2, b2_eff, r1s, r1h, L, beta2b, Z_exit=Z_exit, t_floor=t_floor)
    set_geometry(rpm, r2, b["b2_geo"], r1s, r1h, L, b["t_mean_mm"] / 1e3)
    inducer = 0.6 * g.RHO * g.W ** 2 * (r1s ** 2 - r1h ** 2) / 2 / 1e6
    out = dict(blade=b, inducer_root_MCS_MPa=inducer, U2_design=rpm * np.pi / 30 * r2, U2_MCS=g.U2, Fty_MPa=g.FTY / 1e6)
    if do_disc:
        out["disc"] = disc(T_eye, T_exit)
    out["ok"] = bool(b["ok"] and inducer <= g.FTY / 1e6 and (out["disc"]["ok"] if do_disc else True))
    return out

if __name__ == "__main__":
    # regression against the gate: Phase 3 centrifugal at 537 m/s, 30 deg, 3.5 mm root at 100 % speed -> gate 656 MPa
    R2 = 537.0 / (85000 * np.pi / 30); B2 = 0.189 * R2; R1S = 0.0441 * np.sqrt(1.326 / 1.084)
    set_geometry(85000, R2, B2, R1S, 0.35 * R1S, 0.65 * R2, 1.2e-3); g.W = 85000 * np.pi / 30; g.U2 = 537.0
    print(f"gate regression: 3.5 mm root at 100 % speed {g.plate_root(3.5e-3)['sig_root_Kt']/1e6:.0f} MPa (gate 656 MPa)")
    r = evaluate(85000, R2, B2 * 0.92, R1S, 0.35 * R1S, 0.65 * R2, -30.0, 309.0, 520.0)
    print({k: v for k, v in r.items() if k != "blade"}, {k: v for k, v in r["blade"].items() if k != "hist"})
