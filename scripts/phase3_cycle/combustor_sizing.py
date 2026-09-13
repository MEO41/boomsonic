"""Phase 3 combustor sizing by Lefebvre theta-parameter SCALING from reference micro-turbojet combustors.

theta = P3^1.75 * A_ref * D_ref^0.75 * exp(T3/300) / m_dot     (Lefebvre & Ballal, Gas Turbine
Combustion, 3rd ed., burning-velocity model; form and b = 300 K, x = 0.75 confirmed from the
Cranfield GT Combustion short-course notes, Sethi, 'Combustion Efficiency', slide 7).
eta_comb = f(theta) is specific to a combustor TYPE, so theta is not used as an absolute
criterion: it is calibrated on existing micro-turbojets of the same type (annular, casing =
engine casing) and held equal ('same type, same efficiency') when scaled to our conditions -
this is the scaling use Lefebvre describes.

Reference engines: those with manufacturer PR and airflow (P220, P300, P400, Olympus HP, Titan,
Nike, TJ40-G1). Casing annulus: outer radius Ro = OD/2 - 1.5 mm, shaft-tunnel radius Ri = 0.25 Ro
(geometric similarity assumed for references and our engine), A_ref = pi (Ro^2 - Ri^2),
D_ref = annulus height Ro - Ri (Lefebvre's annular convention). T3 from PR at eta_c = 0.70 (fielded
level, tsfc_anchor.py), P3 = PR * 101.325 kPa (SLS max rating).
Because published airflows are nominal (vendor_calibration.py), the spread of theta across the
seven references is carried as the combustor-size uncertainty.
"""
import os, numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RI_RO = 0.25
CASING_T = 1.5e-3

def theta(P3_Pa, T3_K, mdot, Ro):
    Ri = RI_RO * Ro
    A = np.pi * (Ro ** 2 - Ri ** 2); D = Ro - Ri
    return P3_Pa ** 1.75 * A * D ** 0.75 * np.exp(T3_K / 300.0) / mdot

def reference_thetas(eta_c=0.70):
    db = pd.read_csv(os.path.join(ROOT, "data", "microturbojet_database.csv")).dropna(subset=["pressure_ratio", "mass_flow_kgps", "diameter_mm"])
    rows = []
    for _, e in db.iterrows():
        T3 = 288.15 * (1 + (e.pressure_ratio ** (0.4 / 1.4) - 1) / eta_c)
        P3 = e.pressure_ratio * 101325.0
        Ro = e.diameter_mm / 2e3 - CASING_T
        rows.append(dict(model=e.model, OD_mm=e.diameter_mm, W=e.mass_flow_kgps, PR=e.pressure_ratio, T3=T3, P3_kPa=P3 / 1e3,
                         theta=theta(P3, T3, e.mass_flow_kgps, Ro), U_ref=e.mass_flow_kgps / (P3 / (287.05 * T3) * np.pi * Ro ** 2 * (1 - RI_RO ** 2))))
    return pd.DataFrame(rows)

def size(P3_Pa, T3_K, mdot, theta_target):
    """outer casing radius Ro [m] giving theta = theta_target (theta ~ Ro^2.75)."""
    Ro = 0.08
    for _ in range(60):
        Ro *= (theta_target / theta(P3_Pa, T3_K, mdot, Ro)) ** (1 / 2.75)
    return Ro

def combustor(P3_Pa, T3_K, mdot, loading=1.0):
    """returns casing OD [mm] (mean and +-1 sigma of the reference spread) for theta = theta_ref / loading
    (loading > 1 = a more compact, more highly loaded combustor than the references)."""
    ref = reference_thetas()
    lt = np.log(ref.theta); th_m, th_s = np.exp(lt.mean()), lt.std(ddof=1)
    out = {}
    for tag, th in (("mean", th_m), ("lo", th_m * np.exp(-th_s)), ("hi", th_m * np.exp(th_s))):
        Ro = size(P3_Pa, T3_K, mdot, th / loading)
        out[tag] = dict(OD_mm=2e3 * (Ro + CASING_T), Ro_mm=Ro * 1e3, Ri_mm=RI_RO * Ro * 1e3, D_ref_mm=(1 - RI_RO) * Ro * 1e3,
                        U_ref=mdot / (P3_Pa / (287.05 * T3_K) * np.pi * Ro ** 2 * (1 - RI_RO ** 2)),
                        L_liner_mm=3.0 * (1 - RI_RO) * Ro * 1e3)   # annular liner length ~3 x annulus height (Lefebvre typical L/D_ref)
    return out, ref

if __name__ == "__main__":
    import sys
    P3, T3, m = (float(v) for v in sys.argv[1:4]) if len(sys.argv) > 3 else (407.35e3, 499.0, 1.134)
    out, ref = combustor(P3, T3, m)
    pd.set_option("display.width", 200)
    print(ref.round(3).to_string(index=False))
    print(f"theta_ref geometric mean {np.exp(np.log(ref.theta).mean()):.3e}, log-sigma {np.log(ref.theta).std(ddof=1):.3f}")
    for k, v in out.items(): print(k, {kk: round(vv, 1) for kk, vv in v.items()})
    for L in (1.5, 2.0):
        o, _ = combustor(P3, T3, m, loading=L); print(f"loading x{L}: OD {o['mean']['OD_mm']:.1f} mm, U_ref {o['mean']['U_ref']:.1f} m/s")
