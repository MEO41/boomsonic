"""Phase 4 (centrifugal baseline): screening Campbell check of the impeller exducer blades.

Model: the same Kirchhoff (Morley) plate as the stress gate's exducer-blade model (impeller_stress_gate.plate_root:
blade in the meridional plane from 0.7 r2 to r2, clamped along the hub, thickness tapering from the root to 0.8 mm),
with the consistent mass matrix rho t w v added -> generalised eigenproblem K x = w^2 M x. Static (non-rotating)
frequencies; centrifugal stiffening, which raises the out-of-plane bending frequencies with speed, is NOT included, so
crossings found here are conservative-low in speed (the real crossing occurs at a somewhat higher speed).
Verification: uniform strip clamped along one edge (cylindrical bending), f1 = (1.8751^2 / 2 pi) sqrt(D / (rho t L^4)),
D = E t^3 / 12 (1 - nu^2), L = blade height.
Excitation orders: engine orders 1-6 (inlet distortion; the inlet has no struts) and the vaned diffuser's 19 vanes
(potential-field interaction, 19 x N). Operating range 35-105 % of 75 000 rpm.
Usage: python cc_blade_modes.py [tag]      output data/phase4r_blade_modes.json
"""
import os, sys, json, numpy as np, scipy.linalg as la
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import impeller_stress as ist
g = ist.g
from skfem import MeshTri, ElementTriMorley, Basis, BilinearForm, asm, condense
from skfem.helpers import dd, ddot, eye, trace
TAG = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"
E, NU, RHO = 110e9, 0.34, 4430.0

def modes(t_root, t_tip=0.8e-3, r_i_frac=0.7, nx=36, ny=14, nmodes=6, verify=False):
    R2, B2, R1H = g.R2, g.B2, g.R1H
    r_i = r_i_frac * R2
    phi_i = np.arccos(np.clip(1 - (r_i - R1H) / (R2 - R1H), 0, 1))
    b_i = np.hypot(*(np.array(g.shroud_point(phi_i)) - np.array(g.hub_point(phi_i))))
    m = MeshTri.init_tensor(np.linspace(r_i, R2, nx), np.linspace(0, 1, ny))
    r = m.p[0]; t = m.p[1]; bh = b_i + (B2 - b_i) * (r - r_i) / (R2 - r_i)
    if verify: bh = 0 * r + B2
    m = MeshTri(np.vstack([r, t * bh]), m.t)
    ib = Basis(m, ElementTriMorley(), intorder=4)
    def thick(x):
        if verify: return 0 * x[0] + t_root
        b = b_i + (B2 - b_i) * (x[0] - r_i) / (R2 - r_i)
        return t_root + (t_tip - t_root) * np.clip(x[1] / b, 0, 1)
    def C(T): return E / (1 + NU) * (T + NU / (1 - NU) * eye(trace(T), 2))
    @BilinearForm
    def a(u, v, w): return thick(w.x) ** 3 / 12.0 * ddot(C(dd(u)), dd(v))
    @BilinearForm
    def mm(u, v, w): return RHO * thick(w.x) * u * v
    K = asm(a, ib); M = asm(mm, ib)
    D = ib.get_dofs(m.facets_satisfying(lambda x: x[1] < 1e-9)).all()
    Kc, Mc, _, _ = condense(K, M, D=D)
    lam = la.eigh(Kc.toarray(), Mc.toarray(), eigvals_only=True, subset_by_index=[0, nmodes - 1])
    return np.sqrt(np.maximum(lam, 0)) / (2 * np.pi)

if __name__ == "__main__":
    d = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{TAG}.json"))); L = d["levels"]["fielded"]; sg, s = L["stress_geo"], L["stress"]
    rpm = d["rpm"]
    ist.set_geometry(rpm, sg["r2"], s["blade"]["b2_geo"], sg["r1s"], sg["r1h"], sg["L"], s["blade"]["t_mean_mm"] / 1e3)
    t_root = s["blade"]["t_root_mm"] / 1e3
    # verification: uniform clamped strip
    tv = 1.5e-3; f_fe = modes(tv, verify=True, nmodes=1)[0]
    Dp = E * tv ** 3 / (12 * (1 - NU ** 2)); f_an = 1.8751 ** 2 / (2 * np.pi) * np.sqrt(Dp / (RHO * tv * g.B2 ** 4))
    print(f"verification (uniform strip, L = {g.B2*1e3:.1f} mm, t = 1.5 mm): FE f1 {f_fe:.0f} Hz vs cantilever {f_an:.0f} Hz ({100*(f_fe/f_an-1):+.1f} %)")
    f = modes(t_root)
    fN = rpm / 60.0; lo, hi = 0.35 * fN, 1.05 * fN
    cross = []
    for i, fi in enumerate(f):
        for eo in (1, 2, 3, 4, 5, 6, 19):
            Nc = fi / eo                                                   # rev/s at which EO x N = f_i
            if lo <= Nc <= hi: cross.append(dict(mode=i + 1, f_Hz=float(fi), EO=eo, crossing_pct_speed=100 * Nc / fN))
    out = dict(tag=TAG, t_root_mm=t_root * 1e3, b2_geo_mm=g.B2 * 1e3, r2_mm=g.R2 * 1e3, f_static_Hz=f.tolist(), rev_per_s_100pct=fN,
               verification=dict(f_FE=f_fe, f_analytic=f_an), crossings_35_105pct=cross, note="static frequencies; centrifugal stiffening raises them")
    json.dump(out, open(os.path.join(ROOT, "data", "phase4r_blade_modes.json"), "w"), indent=1, default=float)
    print(f"exducer blade (root {t_root*1e3:.2f} mm, height {g.B2*1e3:.1f} mm): static modes {[round(x) for x in f]} Hz; 100 % speed = {fN:.0f} rev/s, "
          f"19/rev = {19*fN:.0f} Hz")
    for c in cross: print(f"  mode {c['mode']} ({c['f_Hz']:.0f} Hz) crosses EO {c['EO']} at {c['crossing_pct_speed']:.0f} % speed")
