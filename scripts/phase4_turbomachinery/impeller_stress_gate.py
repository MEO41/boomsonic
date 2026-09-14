"""Decision gate: detailed stress check of the pure-centrifugal impeller (OPR 4, 85 000 rpm, fielded
tip speed 537 m/s), beyond the Phase 3 solid-disc screening estimate.

1. HUB / DISC: axisymmetric FE (axisym_fe.py, verified against rotating-disc theory to <0.5 %).
   Meridional section built from the Phase 3 centrifugal geometry scaled to the fielded tip speed:
   r2 = 537 / w = 60.3 mm, b2/r2 0.189, r1s = 48.8 mm (inducer scaled with the fielded flow),
   r1h = 0.35 r1s, axial length 0.65 r2; quarter-ellipse hub and shroud lines. Back face shaped:
   z_back(r) = L + t_rim + A ((r2 - r)/(r2 - r_bore))^p (thick boss at the bore), swept for the
   lowest peak stress. Two shaft attachments: through-bore (r_bore 6 mm, 12 mm tie-bolt/shaft) and
   boreless (stub shaft on the back face). Blades (12 main + 12 splitters from mid-chord, mean
   thickness 1.2 mm, Ti) enter as their centrifugal pull applied as radial traction on the hub
   surface (smeared blade loading; blade hoop stiffness ignored -> conservative for the hub).
2. BURST: average-tangential-stress (Robinson) criterion, N_burst/N = sqrt(k Ftu / sigma_t,avg),
   k = 0.85 (material utilisation factor; sensitivity 0.80-0.95 reported); requirement
   N_burst/N >= 1.20 from 14 CFR 33.27 (no burst for 5 min at 120 % of max permissible speed).
3. BLADE ROOT (exducer, backswept): Kirchhoff plate FE (scikit-fem Morley element) of one exducer
   blade in the r-z plane, clamped at the hub (rigid hub -> conservative), loaded by the component
   of centrifugal force normal to the blade, q = rho t(z) w^2 r sin(beta(r)); beta rises linearly
   from 0 at r = 0.7 r2 to the 30 deg backsweep at r2; linearly tapered thickness t_root -> 0.8 mm.
   Root bending stress x Kt 1.4 (blade-hub fillet, Peterson's stepped-bar-in-bending range).
   Verified against cantilever-plate theory (uniform plate, uniform load).
   Inducer blade root: radial tension of radial-fibred blades, k rho w^2 (r1s^2 - r1h^2)/2, k 0.6.
Material: Ti-6Al-4V annealed at ~250 C (impeller exit air 520 K at the dash): ATI Ti-6Al-4V Grade 5
technical data sheet (2012) typical curve at 480 F: Fty ~100 ksi, Ftu ~111 ksi; reduced to a
minimum basis with the AMS 4928 room-temperature minimum/typical ratio (120/133, 130/146):
Fty 620 MPa, Ftu 681 MPa (typical values also reported). nu 0.34, rho 4430 kg/m3.
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import axisym_fe as fe
from skfem import MeshTri, ElementTriMorley, Basis, BilinearForm, LinearForm, asm, solve, condense
from skfem.helpers import dd, ddot, eye, trace

RPM = 85000.0; W = RPM * np.pi / 30
U2 = 537.0; R2 = U2 / W; B2 = 0.189 * R2
R1S = 0.0441 * np.sqrt(1.326 / 1.084); R1H = 0.35 * R1S
L = 0.65 * R2; LS = L - B2
RHO, NU = 4430.0, 0.34
FTY_T, FTU_T = 100 * 6.895e6, 111 * 6.895e6                  # ATI typical at ~480 F
FTY, FTU = FTY_T * 120 / 133, FTU_T * 130 / 146               # minimum basis (AMS 4928 ratio)
T_BLADE, K_BURST = 1.2e-3, 0.85

def hub_point(phi):  return R1H + (R2 - R1H) * (1 - np.cos(phi)), L * np.sin(phi)
def shroud_point(phi): return R1S + (R2 - R1S) * (1 - np.cos(phi)), LS * np.sin(phi)

def z_front(r):
    r = np.asarray(r, float)
    c = np.clip(1 - (r - R1H) / (R2 - R1H), 0, 1)
    return np.where(r <= R1H, 0.0, L * np.sqrt(np.clip(1 - c ** 2, 0, 1)))

def blade_traction(r, z):
    """radial traction [Pa] on the hub surface from the blades' centrifugal pull."""
    c = np.clip(1 - (r - R1H) / (R2 - R1H), 0, 1); phi = np.arccos(c)
    rs, zs = shroud_point(phi); rh, zh = hub_point(phi)
    h = np.hypot(rs - rh, zs - zh); rc = 0.5 * (rh + rs)
    Z = np.where(phi < np.pi / 4, 12, 24)
    dmdA = RHO * Z * T_BLADE * h / (2 * np.pi * np.maximum(rh, 1e-4))
    return dmdA * W ** 2 * rc * (r >= R1H), 0 * r

def analyse_hub(r_bore, t_rim, A, p, nr=90, nz=18, omega=W, dT=None):
    zb = lambda r: L + t_rim + A * np.clip((R2 - r) / (R2 - r_bore), 0, 1) ** p
    s = np.linspace(0, 1, nr)
    rn = r_bore + (R2 - r_bore) * (0.5 - 0.5 * np.cos(np.pi * s))          # clustered at bore and rim
    m = fe.mapped_mesh(rn, z_front, zb, nz)
    fac = m.facets_satisfying(lambda x: (np.abs(x[1] - z_front(x[0])) < 1e-7) & (x[0] >= R1H))
    basis, u, D = fe.solve_rotating(m, RHO, omega, nu=NU, traction=dict(facets=fac, func=blade_traction), axis_nodes_fix_ur=(r_bore == 0.0), dT=dT)
    st = fe.stresses(basis, u, D)
    vm = st["vm"]; i = np.unravel_index(np.argmax(vm), vm.shape)
    A_sec = st["dA"].sum(); st_avg = (st["st"] * st["dA"]).sum() / A_sec
    V = 2 * np.pi * (st["r"] * st["dA"]).sum(); m_hub = RHO * V
    # blade mass
    phis = np.linspace(0, np.pi / 2, 200); rh, zh = hub_point(phis); rs, zs = shroud_point(phis)
    ds = np.hypot(np.gradient(rh), np.gradient(zh)); h = np.hypot(rs - rh, zs - zh)
    m_bl = RHO * T_BLADE * np.sum(np.where(phis < np.pi / 4, 12, 24) * h * ds)
    bore_mask = st["r"] < (r_bore + 0.002) if r_bore > 0 else st["r"] < 0.002
    # mass properties (Phase 4 rotordynamics): hub from the FE quadrature, blades as rings at the mid-span point
    w = 2 * np.pi * st["r"] * st["dA"] * RHO
    dm_b = RHO * T_BLADE * np.where(phis < np.pi / 4, 12, 24) * h * ds; rb, zb = 0.5 * (rh + rs), 0.5 * (zh + zs)
    m_tot = w.sum() + dm_b.sum(); z_cg = float(((w * st["z"]).sum() + (dm_b * zb).sum()) / m_tot)
    Ip = float((w * st["r"] ** 2).sum() + (dm_b * rb ** 2).sum())
    Id = float((w * (0.5 * st["r"] ** 2 + (st["z"] - z_cg) ** 2)).sum() + (dm_b * (0.5 * rb ** 2 + (zb - z_cg) ** 2)).sum())
    return dict(r_bore_mm=r_bore * 1e3, t_rim_mm=t_rim * 1e3, A_mm=A * 1e3, p=p, vm_peak_MPa=vm.max() / 1e6,
                vm_peak_r_mm=st["r"][i] * 1e3, vm_peak_z_mm=st["z"][i] * 1e3, st_bore_MPa=st["st"][bore_mask].max() / 1e6,
                st_avg_MPa=st_avg / 1e6, mass_hub_kg=m_hub, mass_blades_kg=m_bl, mass_total_kg=m_hub + m_bl,
                burst_ratio=float(np.sqrt(K_BURST * FTU / st_avg)), yield_MS=FTY / vm.max() - 1,
                Ip_kgm2=Ip, Id_cg_kgm2=Id, z_cg_mm=z_cg * 1e3, z_back_axis_mm=(L + t_rim + A) * 1e3)

def plate_root(t_root, t_tip=0.8e-3, r_i_frac=0.7, beta2=30.0, nx=40, ny=16, Kt=1.4, E=110e9, verify=False):
    """Morley-plate FE of one exducer blade; returns peak root bending stress (x Kt) [Pa]."""
    r_i = r_i_frac * R2
    phi_i = np.arccos(np.clip(1 - (r_i - R1H) / (R2 - R1H), 0, 1))
    b_i = np.hypot(*(np.array(shroud_point(phi_i)) - np.array(hub_point(phi_i))))
    m = MeshTri.init_tensor(np.linspace(r_i, R2, nx), np.linspace(0, 1, ny))
    r = m.p[0]; t = m.p[1]; bh = b_i + (B2 - b_i) * (r - r_i) / (R2 - r_i)
    if verify: bh = 0 * r + B2
    m = MeshTri(np.vstack([r, t * bh]), m.t)
    e = ElementTriMorley(); ib = Basis(m, e, intorder=4)
    def thick(x):
        if verify: return 0 * x[0] + t_root
        bh = b_i + (B2 - b_i) * (x[0] - r_i) / (R2 - r_i)
        return t_root + (t_tip - t_root) * np.clip(x[1] / bh, 0, 1)
    def Cmat(T):
        return E / (1 + NU) * (T + NU / (1 - NU) * eye(trace(T), 2))
    @BilinearForm
    def a(u, v, w):
        d = thick(w.x)
        return d ** 3 / 12.0 * ddot(Cmat(dd(u)), dd(v))
    @LinearForm
    def f(v, w):
        x = w.x; d = thick(x)
        if verify: return 1.0e6 * v                           # uniform unit load 1 MPa
        beta = np.radians(beta2) * np.clip((x[0] - r_i) / (R2 - r_i), 0, 1)
        return RHO * d * W ** 2 * x[0] * np.sin(beta) * v
    K = asm(a, ib); F = asm(f, ib)
    clamped = ib.get_dofs(m.facets_satisfying(lambda x: x[1] < 1e-9)).all()
    u = solve(*condense(K, F, D=clamped))
    # bending stress at quadrature points: sigma = E z / (1 - nu^2) (k_xx + nu k_yy) with z = t/2
    uh = ib.interpolate(u); H = uh.hess
    x = ib.mapping.F(ib.X); d = thick(x)
    kyy, kxx, kxy = H[1][1], H[0][0], H[0][1]
    s_zz = E * d / 2 / (1 - NU ** 2) * (kyy + NU * kxx)       # spanwise bending (root)
    s_rr = E * d / 2 / (1 - NU ** 2) * (kxx + NU * kyy)
    s_rz = E * d / 2 / (1 + NU) * kxy
    vm = np.sqrt(s_zz ** 2 + s_rr ** 2 - s_zz * s_rr + 3 * s_rz ** 2)
    root = x[1] < (x[1].max() * 0.08)
    return dict(sig_root_nom=float(np.abs(s_zz[root]).max()), vm_root_nom=float(vm[root].max()), vm_peak_nom=float(vm.max()),
                sig_root_Kt=Kt * float(vm[root].max()), b_i_mm=b_i * 1e3, b2_mm=B2 * 1e3, max_defl_mm=float(np.abs(u[ib.nodal_dofs[0]]).max() * 1e3))

if __name__ == "__main__":
    out = {"geometry": dict(rpm=RPM, U2=U2, r2_mm=R2 * 1e3, b2_mm=B2 * 1e3, r1s_mm=R1S * 1e3, r1h_mm=R1H * 1e3, L_mm=L * 1e3),
           "material": dict(Fty_min_MPa=FTY / 1e6, Ftu_min_MPa=FTU / 1e6, Fty_typ_MPa=FTY_T / 1e6, Ftu_typ_MPa=FTU_T / 1e6)}
    print(json.dumps(out, indent=0))
    # --- plate verification: uniform plate, uniform load q, clamped at root: sigma = 3 q b^2 / t^2
    tv = 3e-3; v = plate_root(tv, verify=True, Kt=1.0)
    ana = 3 * 1e6 * B2 ** 2 / tv ** 2
    print(f"plate verification: FE root bending {v['sig_root_nom']/1e6:.1f} MPa vs cantilever theory {ana/1e6:.1f} MPa ({(v['sig_root_nom']/ana-1)*100:+.1f} %)")
    # --- hub sweep
    res = []
    for r_bore in (0.006, 0.0):
        for t_rim in (0.0030, 0.0045):
            for A in (0.0, 0.006, 0.012, 0.018):
                for p in (1.0, 2.0):
                    if A == 0.0 and p == 2.0: continue
                    d = analyse_hub(r_bore, t_rim, A, p); res.append(d)
                    print({k: round(v, 3) for k, v in d.items()}, flush=True)
    out["hub_sweep"] = res
    # --- blade roots
    blades = []
    for tr in (1.5e-3, 2.5e-3, 3.5e-3, 5.0e-3, 7.0e-3):
        b = plate_root(tr); b["t_root_mm"] = tr * 1e3
        b["blockage_root"] = 24 * tr / (2 * np.pi * R2); blades.append(b)
        print({k: round(v / 1e6, 1) if k.startswith(("sig", "vm")) else round(v, 3) for k, v in b.items()}, flush=True)
    out["exducer_blade"] = blades
    out["inducer_blade_root_MPa"] = 0.6 * RHO * W ** 2 * (R1S ** 2 - R1H ** 2) / 2 / 1e6
    print("inducer blade root tension (radial-fibred, k 0.6):", round(out["inducer_blade_root_MPa"], 1), "MPa")
    json.dump(out, open(os.path.join(ROOT, "data", "phase4_impeller_stress_gate.json"), "w"), indent=1, default=float)
