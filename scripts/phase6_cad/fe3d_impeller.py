"""Phase 6: 3D FE of the impeller on the CAD geometry (run in .venv-cad: gmsh 4.15 + scikit-fem 12.0.2 + pypardiso 0.4.7).

Checks the 2D Morley-plate model of the exducer blade (impeller_stress_gate.plate_root) that sized the blade root in
Phase 3R, and the disc against the verified axisymmetric FE.
Model:
  * one 30 deg sector of the wheel (1 main + 1 splitter blade + hub sector), cad/engine/impeller_sector.step, bounded
    THROUGH THE PASSAGES by surfaces ruled by radial lines (impeller_cad.py; data/phase6/impeller_sector_boundary.json),
    so that no blade is cut (flat cut planes cut every blade and left slivers: near-singular stiffness);
  * gmsh tetrahedra; scikit-fem P2 vector elements (linear geometry). The cut faces are meshed independently: gmsh's
    setPeriodic needs the same face topology on both planes, which the faceted blades do not give ("cannot find periodic
    counterpart");
  * cyclic symmetry as a tie: every slave-face dof location, rotated -30 deg onto the master plane, is interpolated from
    the P2 trace of the master-face triangle that contains it, u(slave) = R(30 deg) sum N_n u(master node n)
    (transformation matrix T, K_r = T' K T; exact pairing when the meshes happen to match); on the axis u_y = u_z = 0;
  * load: centrifugal body force rho w^2 (0, y, z) at MCS (105 % of 75 000 rpm); Ti-6Al-4V E 110 GPa, nu 0.34, rho 4430
    (the gate's mechanical-case values); no thermal load (the gate's thermal gradient added 15-25 MPa at the hub);
  * support (verification B and production): the back-face boss within the stub-shaft radius (6 mm) held axially
    (u_x = 0); rigid rotation about x removed by one weak tangential spring (the centrifugal load has no moment about x,
    so it carries no load; its reaction is reported). Radial growth at the boss is free (the stub-shaft fit is not
    modelled).
  * solvers: MKL PARDISO (pypardiso) for production (residual ~1e-11); pyamg smoothed-aggregation CG on the matching
    verification B (agrees with SuperLU to 1e-7; it stalls with the interpolated tie, see tools_survey section 9).
Verification, same code path:
  (A) thin rotating disc sector (r 60 mm, 2 mm thick): centre stress (3 + nu)/8 rho w^2 b^2 and the hoop stress in the
      outer 1.5 mm against plane-stress theory at the same points;
  (B) the impeller hub alone (no blades, no blade pull), flat cut planes, against the verified axisymmetric FE;
  (B') the same hub cut by the production sector's twisted passage surfaces (tests the curved cyclic tie; PARDISO vs SuperLU).
Production outputs (data/phase6/fe3d_impeller.json; cad/fe/impeller_sector_<tag>.vtu for plotting):
  * mesh quality (6 sqrt2 V / L_rms^3; the faceted-blade CAD gave 15 % slivers and 1e6 MPa spurious peaks);
  * blade-root stress by surface extrapolation from 0.4 t and 1.0 t off the hub surface (IIW hot-spot rule
    1.67 s(0.4t) - 0.67 s(1.0t)), exducer (r >= 0.7 r2, compared with the plate model's nominal root stress, then x Kt
    1.4 vs Fty) and inducer, both more than one root thickness from the blade ends; the blade ends sit on hub edges in
    this conceptual CAD (LE root on the hub's front edge, TE root on the rim edge): those corner peaks are singular,
    mesh-dependent and reported separately;
  * hub stress more than 1 mm inside the hub surface (maximum and 99.9th percentile) vs the axisymmetric FE with the
    smeared blade pull (313 MPa mechanical at MCS in Phase 3R);
  * blade tip displacement normal to the shroud line (toward the casing) vs the 0.25 mm cold clearance; displacements
    without the rigid rotation about x.
Usage: python fe3d_impeller.py [A,B,BT,P,PF]   (default A,B,P; PF = production on the finer mesh, the mesh check)
"""
import os, sys, json, math, time, numpy as np, scipy.sparse as sp
from scipy.spatial import cKDTree
import scipy.sparse.linalg as spla
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
import gmsh
from skfem import MeshTet, Basis, ElementVector, ElementTetP2, asm, LinearForm
from skfem.models.elasticity import linear_elasticity, lame_parameters
E_TI, NU, RHO = 110e9, 0.34, 4430.0
P = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json"))); ip = P["impeller"]
RPM = ip["rpm"]["value"]; OM = RPM * math.pi / 30 * 1.05                      # MCS
SECT = math.radians(30.0); PHI0 = math.radians(-7.5)
R2, R1H, R1S, LAX, B2 = (ip[k]["value"] for k in ("r2", "r1_hub", "r1_shroud", "axial_length", "b2_physical"))
BF = ip["back_face"]["value"]; T_RIM, A_BOSS, P_BOSS = BF["t_rim"], BF["boss_A_over_r2"] * R2, BF["boss_p"]
T_ROOT, T_TIP, CLEAR = ip["t_root_hub"]["value"], ip["t_tip"]["value"], ip["tip_clearance"]["value"]
R_STUB = 6e-3
OUT = os.path.join(ROOT, "data", "phase6", "fe3d_impeller.json")

def tet_quality(C):
    """6 sqrt(2) V / L_rms^3 per tetrahedron (1 regular, 0 flat); C (ntet, 4, 3)."""
    a, b, c, d = C[:, 0], C[:, 1], C[:, 2], C[:, 3]
    V = np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a) / 6
    E = np.stack([b - a, c - a, d - a, c - b, d - b, d - c], 1)
    return 6 * np.sqrt(2) * np.abs(V) / np.sqrt((np.linalg.norm(E, axis=2) ** 2).mean(1)) ** 3

def mesh_step(step, hmin, hmax, phi0=PHI0, curv=10, periodic=False):
    gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
    c, s = math.cos(SECT), math.sin(SECT)
    def on_plane(tag, phi):
        lo, hi = gmsh.model.getParametrizationBounds(2, tag); n = gmsh.model.getNormal(tag, [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2])
        pc = gmsh.model.occ.getCenterOfMass(2, tag); nref = np.array([0, -math.sin(phi), math.cos(phi)])
        ang = math.atan2(pc[2], pc[1])
        return abs(abs(np.dot(n, nref)) - 1) < 1e-3 and abs(ang - phi) < math.radians(3) and abs(n[0]) < 1e-3, np.array(pc)
    masters, slaves = [], []
    for _, tag in gmsh.model.getEntities(2):
        okm, pm = on_plane(tag, phi0); oks, ps = on_plane(tag, phi0 + SECT)
        if okm: masters.append((tag, pm))
        if oks: slaves.append((tag, ps))
    R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    pairs = []
    for ts, ps in slaves:
        tm, pm = min(masters, key=lambda m: np.linalg.norm(R @ m[1] - ps)); pairs.append((ts, tm, float(np.linalg.norm(R @ pm - ps))))
    aff = [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1]
    if pairs and periodic: gmsh.model.mesh.setPeriodic(2, [p[0] for p in pairs], [p[1] for p in pairs], aff)
    gmsh.option.setNumber("Mesh.MeshSizeMin", hmin); gmsh.option.setNumber("Mesh.MeshSizeMax", hmax)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", curv); gmsh.option.setNumber("Mesh.Algorithm3D", 1)
    gmsh.option.setNumber("Mesh.Optimize", 1); gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
    gmsh.model.mesh.generate(3)
    tags, X, _ = gmsh.model.mesh.getNodes(); X = X.reshape(-1, 3); idx = {int(t): i for i, t in enumerate(tags)}
    et, nt = gmsh.model.mesh.getElementsByType(4)
    T = np.array([idx[int(n)] for n in nt]).reshape(-1, 4)
    gmsh.finalize()
    used = np.unique(T); remap = -np.ones(len(X), int); remap[used] = np.arange(len(used))
    q = tet_quality(X[T])
    info = dict(periodic_pairs=len(pairs), masters=len(masters), slaves=len(slaves), max_pair_centroid_mismatch_mm=max([p[2] for p in pairs], default=0.0),
                quality=dict(min=float(q.min()), p1=float(np.percentile(q, 1)), median=float(np.median(q)), n_below_0p1=int((q < 0.1).sum()), n_below_0p02=int((q < 0.02).sum())))
    return MeshTet(X[used].T * 1e-3, remap[T].T), info                         # metres

def flat_boundary(x): return np.full(np.shape(x), PHI0)

def solve(mesh, fix_fn, spring_at=None, solver="amg", check_direct=False, phi_b=flat_boundary):
    """fix_fn(doflocs, comp) -> bool mask of fixed dofs; spring_at = (x, r, phi) of a weak tangential spring;
    phi_b(x) = master cut-surface angle psi = atan2(z, y) [rad] at axial position x [m] (slave = master + 30 deg)."""
    e = ElementVector(ElementTetP2()); ib = Basis(mesh, e, intorder=3)
    lam, mu = lame_parameters(E_TI, NU)
    K = asm(linear_elasticity(lam, mu), ib).tocsr()
    @LinearForm
    def fb(v, w): x = w.x; return RHO * OM ** 2 * (x[1] * v.value[1] + x[2] * v.value[2])
    f = asm(fb, ib)
    loc = ib.doflocs; N = K.shape[0]
    comp = np.zeros(N, int)
    for ci, idx in enumerate(ib.split_indices()): comp[idx] = ci
    r = np.hypot(loc[1], loc[2]); tol = 2e-6
    # cut-surface facets from the mesh vertices (exactly on the CAD faces); their dofs (vertices + edge midpoints) by
    # topology: on a curved cut surface the P2 edge-midpoint locations lie slightly off the surface
    P = mesh.p; ph_v = np.arctan2(P[2], P[1]); r_v = np.hypot(P[1], P[2]); pb_v = phi_b(P[0])
    bf = mesh.boundary_facets(); Fb = mesh.facets[:, bf]
    def side(off):
        on = (np.abs(ph_v - pb_v - off) < 1e-6) | (r_v <= tol)
        return bf[np.all(on[Fb], axis=0) & np.any(r_v[Fb] > tol, axis=0)]
    fm, fs = side(0.0), side(SECT)
    axis = r <= tol
    on_m = np.zeros(N, bool); on_m[ib.get_dofs(facets=fm).all()] = True; on_m &= ~axis
    on_s = np.zeros(N, bool); on_s[ib.get_dofs(facets=fs).all()] = True; on_s &= ~axis
    fixed = fix_fn(loc, comp) | (axis & (comp > 0))
    info = {}
    if spring_at is not None:
        xs, rs_ = spring_at; phs = float(phi_b(xs)) + SECT / 2; p0 = np.array([xs, rs_ * math.cos(phs), rs_ * math.sin(phs)])
        cand = np.where((comp == 1) & ~on_m & ~on_s & ~fixed)[0]; d1 = cand[np.argmin(np.linalg.norm(loc[:, cand].T - p0, axis=1))]
        same = np.where(np.all(np.isclose(loc, loc[:, [d1]], atol=1e-12), axis=0))[0]; dy, dz = same[comp[same] == 1][0], same[comp[same] == 2][0]
        phn = math.atan2(loc[2, d1], loc[1, d1]); t = np.array([-math.sin(phn), math.cos(phn)])
        ks = 1e-4 * K.diagonal().mean()
        K = K + sp.csr_matrix((ks * np.outer(t, t).ravel(), (np.repeat([dy, dz], 2), np.tile([dy, dz], 2))), shape=(N, N))
        info["spring"] = dict(k=ks, loc_mm=(loc[:, d1] * 1e3).tolist(), dofs=(int(dy), int(dz)), t=t.tolist())
    # cyclic tie, valid for non-matching cut-face meshes: each slave-face dof location, rotated by -30 deg onto the master
    # surface, is interpolated from the P2 trace of the master-face triangle containing it: u_s = R(30) sum N_n u_n.
    # Triangles are located in (x, r): the cut surfaces (flat, or ruled by radial lines) are graphs over (x, r).
    c, s = math.cos(SECT), math.sin(SECT)
    Rinv = np.array([[1, 0, 0], [0, c, s], [0, -s, c]]); Rm = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    key = lambda p: tuple(np.round(p * 1e8).astype(np.int64))
    by_loc = {}
    for d in np.where(on_m | axis)[0]: by_loc.setdefault(key(loc[:, d]), {})[comp[d]] = d        # axis dofs: master triangles touch the axis
    F = mesh.facets[:, fm]                                                      # master-face triangles
    to2d = lambda X: np.c_[X[0], np.hypot(X[1], X[2])]
    V2 = to2d(P); tri = V2[F.T]                                                 # (nf, 3, 2)
    ftree = cKDTree(tri.mean(axis=1))
    si = np.where(on_s)[0]; pts = to2d(Rinv @ loc[:, si])
    rows, cols, vals = [], [], []; worst = 0.0
    loc_keys = {}
    for k, d in enumerate(si):
        q = pts[k]; best = None
        for fi in np.atleast_1d(ftree.query(q, k=12)[1]):
            a, b_, c_ = tri[fi]; Tm2 = np.c_[b_ - a, c_ - a]
            l12 = np.linalg.solve(Tm2, q - a); lam_ = np.r_[1 - l12.sum(), l12]
            viol = -lam_.min()
            if best is None or viol < best[0]: best = (viol, fi, lam_)
            if viol <= 1e-9: break
        viol, fi, lam_ = best
        if viol > 0: worst = max(worst, viol * np.max(np.linalg.norm(np.diff(np.vstack([tri[fi], tri[fi][:1]]), axis=0), axis=1)))
        vv = F[:, fi]; Xv = P[:, vv]
        nodes = [(Xv[:, i], lam_[i] * (2 * lam_[i] - 1)) for i in range(3)] + \
                [(0.5 * (Xv[:, i] + Xv[:, j]), 4 * lam_[i] * lam_[j]) for i, j in ((0, 1), (1, 2), (0, 2))]
        ci = comp[d]
        for X_n, N_n in nodes:
            if abs(N_n) < 1e-14: continue
            md = by_loc[key(X_n)]
            for cj in range(3):
                if abs(Rm[ci, cj]) > 1e-14: rows.append(d); cols.append(md[cj]); vals.append(Rm[ci, cj] * N_n)
    info["cyclic_tie"] = dict(slave_dofs=int(len(si)), master_triangles=int(F.shape[1]), slave_triangles=int(fs.size),
                              max_outside_distance_mm=float(worst * 1e3))
    if worst > 1e-5: print(f"  WARNING: cyclic tie point up to {worst*1e3:.3f} mm outside the master face")
    slave = np.array(sorted(set(si.tolist())), int)
    indep = np.setdiff1d(np.arange(N), np.concatenate([slave, np.where(fixed)[0]]))
    col_of = -np.ones(N, int); col_of[indep] = np.arange(len(indep))
    Ti = sp.csr_matrix((np.ones(len(indep)), (indep, col_of[indep])), shape=(N, len(indep)))
    cc = col_of[np.array(cols, int)] if cols else np.array([], int); keep = cc >= 0            # masters that are fixed drop out
    Ts = sp.csr_matrix((np.array(vals)[keep], (np.array(rows, int)[keep], cc[keep])), shape=(N, len(indep)))
    Tm = (Ti + Ts).tocsr()
    Kr = (Tm.T @ K @ Tm).tocsr(); fr = Tm.T @ f
    t0 = time.time()
    if solver == "direct":                             # SuperLU: fine to ~150 k dof; at 220 k it committed 13.7 GB and paged
        lu = spla.splu(Kr.tocsc(), permc_spec="MMD_AT_PLUS_A"); q = lu.solve(fr)
        info["direct"] = dict(rel_residual=float(np.linalg.norm(fr - Kr @ q) / np.linalg.norm(fr)), nnz_LU=int(lu.L.nnz + lu.U.nnz))
    elif solver == "pardiso":                          # MKL PARDISO (pypardiso 0.4.7): nested-dissection ordering, far less fill
        import pypardiso
        q = pypardiso.spsolve(Kr.tocsr(), fr)
        info["pardiso"] = dict(rel_residual=float(np.linalg.norm(fr - Kr @ q) / np.linalg.norm(fr)))
    else:
        import pyamg
        Bm = np.zeros((N, 6))                                                     # rigid-body modes on the full dofs
        for ci in range(3): Bm[comp == ci, ci] = 1.0
        X_, Y_, Z_ = loc
        Bm[comp == 1, 3] = -Z_[comp == 1]; Bm[comp == 2, 3] = Y_[comp == 2]      # rotation about x
        Bm[comp == 0, 4] = Z_[comp == 0]; Bm[comp == 2, 4] = -X_[comp == 2]      # about y
        Bm[comp == 0, 5] = -Y_[comp == 0]; Bm[comp == 1, 5] = X_[comp == 1]      # about z
        ml = pyamg.smoothed_aggregation_solver(Kr, B=Bm[indep], symmetry="symmetric", max_coarse=500)
        res = []; q = ml.solve(fr, tol=1e-10, accel="cg", maxiter=2000, residuals=res)
        info["amg"] = dict(iterations=len(res) - 1, rel_residual=float(np.linalg.norm(fr - Kr @ q) / np.linalg.norm(fr)), levels=len(ml.levels))
    info["solve_s"] = time.time() - t0
    if check_direct:
        qd = spla.spsolve(Kr.tocsc(), fr); info[f"{solver}_vs_superlu_max_rel"] = float(np.abs(q - qd).max() / np.abs(qd).max())
    u = Tm @ q
    if spring_at is not None:
        dy, dz = info["spring"]["dofs"]; info["spring"]["reaction_N_per_sector"] = float(info["spring"]["k"] * (t @ u[[dy, dz]]))
    info.update(ndof=N, nred=len(indep), n_slave=len(slave), n_fixed=int(fixed.sum()))
    return ib, u, info

def stress(ib, u):
    lam, mu = lame_parameters(E_TI, NU)
    uh = ib.interpolate(u); G = uh.grad                                            # (3, 3, nel, nqp)
    eps = 0.5 * (G + np.swapaxes(G, 0, 1)); tr = eps[0, 0] + eps[1, 1] + eps[2, 2]
    S = 2 * mu * eps + lam * np.einsum("ij,kl->ijkl", np.eye(3), np.ones(tr.shape)) * tr
    vm = np.sqrt(0.5 * ((S[0, 0] - S[1, 1]) ** 2 + (S[1, 1] - S[2, 2]) ** 2 + (S[2, 2] - S[0, 0]) ** 2) + 3 * (S[0, 1] ** 2 + S[1, 2] ** 2 + S[0, 2] ** 2))
    X = ib.mapping.F(ib.X)                                                         # quadrature point coordinates (3, nel, nqp)
    r = np.hypot(X[1], X[2]); ph = np.arctan2(X[2], X[1]); cp, sn = np.cos(ph), np.sin(ph)
    st = S[1, 1] * sn ** 2 + S[2, 2] * cp ** 2 - 2 * S[1, 2] * sn * cp
    sr = S[1, 1] * cp ** 2 + S[2, 2] * sn ** 2 + 2 * S[1, 2] * sn * cp
    return dict(vm=vm, st=st, sr=sr, x=X[0], r=r, dV=np.abs(ib.dx))

# ---- geometry helpers (m): hub surface line and back face, as the CAD (impeller_cad.py) builds them ----
_phi = np.linspace(0, math.pi / 2, 2001)
HUB_XR = np.c_[LAX * np.sin(_phi), R1H + (R2 - R1H) * (1 - np.cos(_phi))]
SHR_XR = np.c_[(LAX - B2) * np.sin(_phi), R1S + (R2 - R1S) * (1 - np.cos(_phi))]
_tree_h = cKDTree(HUB_XR)
def hub_signed_distance(x, r):
    """distance to the hub line in the meridional plane; > 0 on the flow side (blades), < 0 inside the hub body."""
    d, _ = _tree_h.query(np.c_[x.ravel(), r.ravel()])
    xh = np.interp(r.ravel(), HUB_XR[:, 1], HUB_XR[:, 0])
    inside = (x.ravel() > xh) | (r.ravel() < R1H)
    return np.where(inside, -d, d).reshape(x.shape)
_rb = np.linspace(R2, 0, 40); _xb = LAX + T_RIM + A_BOSS * ((R2 - _rb) / R2) ** P_BOSS     # the CAD polyline
def x_back(r): return np.interp(r, _rb[::-1], _xb[::-1])
def boss_axial(loc, comp):
    r = np.hypot(loc[1], loc[2]); return (comp == 0) & (r < R_STUB) & (loc[0] > x_back(r) - 2e-6)
SPRING = (LAX + T_RIM + 0.5 * A_BOSS, 0.5 * R_STUB)                              # (x, r); angle: mid-sector
def passage_boundary():
    """master cut surface of the production sector (impeller_cad.py): psi(x), ruled by radial lines."""
    b = json.load(open(os.path.join(ROOT, "data", "phase6", "impeller_sector_boundary.json")))
    xb, pb = np.array(b["x_mm"]) * 1e-3, np.radians(b["psi_master_deg"])
    return lambda x: np.interp(x, xb, pb)

def hub_sector_step(path, twisted=False):
    """hub alone: flat 30 deg sector at PHI0, or cut by the production sector's passage boundary (tests the curved tie)."""
    import cadquery as cq
    prof = [(0.0, 0.0), (0.0, R1H * 1e3)] + [(float(x) * 1e3, float(r) * 1e3) for x, r in HUB_XR[::40][1:]] + [((LAX + T_RIM) * 1e3, R2 * 1e3)] \
           + [(float(x) * 1e3, float(r) * 1e3) for x, r in zip(_xb[1:], _rb[1:])]
    if not twisted:
        sol = cq.Workplane("XY").polyline(prof).close().revolve(30, (0, 0, 0), (1, 0, 0)).val().rotate((0, 0, 0), (1, 0, 0), math.degrees(PHI0))
    else:
        sys.path.insert(0, HERE); import cadlib as cl
        b = json.load(open(os.path.join(ROOT, "data", "phase6", "impeller_sector_boundary.json")))
        ws = [cl.polygon_wire([(x_, 0, 0), (x_, 250 * math.cos(math.radians(p_)), 250 * math.sin(math.radians(p_))),
                               (x_, 250 * math.cos(math.radians(p_ + 30)), 250 * math.sin(math.radians(p_ + 30)))]) for x_, p_ in zip(b["x_mm"], b["psi_master_deg"])]
        sol = cl.revolve(prof).intersect(cl.loft(ws, ruled=True))
    cq.exporters.export(cq.Workplane().add(sol), path)

def axisym_hub_reference():
    """verified axisymmetric FE (impeller_stress_gate.analyse_hub via impeller_stress), same hub, no blade pull, E 110 GPa, MCS."""
    sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery"))
    import impeller_stress as ist, impeller_stress_gate as g, axisym_fe as fe
    ist.set_geometry(RPM, R2, B2, R1S, R1H, LAX, 0.5 * (T_ROOT + T_TIP))
    g.blade_traction = lambda r, z: (0 * r, 0 * r)
    orig = ist._solve(E=E_TI)
    try: d = g.analyse_hub(0.0, T_RIM, A_BOSS, P_BOSS, nr=120, nz=24, omega=g.W)
    finally: fe.solve_rotating = orig
    assert abs(g.W - OM) < 1e-6 * OM
    return d

def summarise_hub(S):
    """3D counterparts of analyse_hub's outputs (peak von Mises, hoop within 2 mm of the axis, section-average hoop)."""
    i = np.argmax(S["vm"]); w = S["dV"] / np.maximum(S["r"], 1e-9)             # meridional-area weights dA = dV / (r dphi)
    return dict(vm_peak_MPa=float(S["vm"].ravel()[i] / 1e6), vm_peak_x_mm=float(S["x"].ravel()[i] * 1e3), vm_peak_r_mm=float(S["r"].ravel()[i] * 1e3),
                st_axis_MPa=float(S["st"][S["r"] < 2e-3].max() / 1e6), st_avg_MPa=float((S["st"] * w).sum() / w.sum() / 1e6))

def production(hmin, hmax, tag):
    step = os.path.join(ROOT, "cad", "engine", "impeller_sector.step")
    t0 = time.time(); m, minfo = mesh_step(step, hmin, hmax); tm = time.time() - t0
    print(f"  mesh {tag}: {m.t.shape[1]} tets, {m.p.shape[1]} vertices, periodic pairs {minfo['periodic_pairs']} ({tm:.0f} s)", flush=True)
    ib, u, info = solve(m, boss_axial, spring_at=SPRING, phi_b=passage_boundary(), solver="pardiso")
    print(f"  solved: {info['ndof']} dof, pardiso {info.get('pardiso')}, tie {info['cyclic_tie']}, {info['solve_s']:.0f} s", flush=True)
    S = stress(ib, u)
    d = hub_signed_distance(S["x"], S["r"])
    vm = S["vm"]; i = np.argmax(vm)
    res = dict(mesh=dict(hmin_mm=hmin, hmax_mm=hmax, tets=int(m.t.shape[1]), **minfo), solve=info,
               peak=dict(vm_MPa=float(vm.ravel()[i] / 1e6), x_mm=float(S["x"].ravel()[i] * 1e3), r_mm=float(S["r"].ravel()[i] * 1e3),
                         d_hub_mm=float(d.ravel()[i] * 1e3), note="sharp blade-root corner in the CAD: singular, mesh-dependent"))
    # blade roots: hot-spot extrapolation 1.67 s(0.4 t) - 0.67 s(1.0 t) along the root line. The blade ENDS sit on hub
    # edges in this conceptual geometry (LE root on the hub's front edge at x = 0 -- no nose ahead of the blades; TE root on
    # the rim edge at r2): those corners are singular and are reported separately; the root line is taken more than one
    # root thickness away from them.
    ends = (S["x"] < T_ROOT) | (S["r"] > R2 - T_ROOT)
    def root(region, excl):
        msk = region & ~excl if excl is not None else region
        def band(a, b):
            mm_ = msk & (d >= a * T_ROOT) & (d <= b * T_ROOT); k = np.argmax(np.where(mm_, vm, -1))
            return float(vm.ravel()[k]), float(S["x"].ravel()[k] * 1e3), float(S["r"].ravel()[k] * 1e3)
        (s04, x04, r04), (s10, x10, r10) = band(0.3, 0.5), band(0.9, 1.1)
        hs = 1.67 * s04 - 0.67 * s10
        return dict(vm_at_0p4t_MPa=s04 / 1e6, at_0p4t_x_r_mm=(x04, r04), vm_at_1p0t_MPa=s10 / 1e6, at_1p0t_x_r_mm=(x10, r10),
                    hot_spot_MPa=hs / 1e6, hot_spot_x_Kt_MPa=1.4 * hs / 1e6)
    ex = S["r"] >= 0.7 * R2; ind = S["r"] < 0.7 * R2
    res["exducer_root"] = root(ex, ends); res["exducer_root_incl_TE_corner"] = root(ex, None)
    res["inducer_root"] = root(ind, ends); res["inducer_root_incl_LE_corner"] = root(ind, None)
    res["root_note"] = ("max von Mises in blade material with hub distance 0.3-0.5 t_root and 0.9-1.1 t_root (t_root 2.235 mm); "
                        "exducer r >= 0.7 r2, inducer r < 0.7 r2; 'excluding' = more than t_root from the LE (x) and the rim (r2)")
    blade = d > 0
    res["blade_corner_peak_MPa"] = dict(LE_corner=float(vm[blade & (S["x"] < T_ROOT)].max() / 1e6), TE_corner=float(vm[blade & (S["r"] > R2 - T_ROOT)].max() / 1e6))
    # hub body away from the root corners: the maximum and the 99.9th percentile over quadrature points (single-point
    # maxima moved 336 -> 438 MPa between meshes while the 99.9th percentile held)
    hb = d < -1e-3; j = np.argmax(np.where(hb, vm, 0))
    res["hub"] = dict(vm_max_MPa=float(vm.ravel()[j] / 1e6), x_mm=float(S["x"].ravel()[j] * 1e3), r_mm=float(S["r"].ravel()[j] * 1e3),
                      vm_p999_MPa=float(np.percentile(vm[hb], 99.9) / 1e6), st_axis_MPa=float(S["st"][S["r"] < 2e-3].max() / 1e6))
    # blade tip displacement normal to the shroud line (toward the casing)
    loc = ib.doflocs; comp = np.zeros(loc.shape[1], int)
    for ci, idx in enumerate(ib.split_indices()): comp[idx] = ci
    r_l = np.hypot(loc[1], loc[2]); ts = cKDTree(SHR_XR); dsh, k = ts.query(np.c_[loc[0], r_l])
    near = (dsh < 0.3e-3) & (comp == 0)
    tg = np.gradient(SHR_XR, axis=0); tg /= np.linalg.norm(tg, axis=1, keepdims=True); nrm = np.c_[-tg[:, 1], tg[:, 0]]   # casing side
    ux = u[near]; base = np.where(near)[0]
    same = lambda d0, cc_: np.where(np.all(np.isclose(loc, loc[:, [d0]], atol=1e-12), axis=0) & (comp == cc_))[0][0]
    un = []
    for d0 in base:
        dy, dz = same(d0, 1), same(d0, 2); ph = math.atan2(loc[2, d0], loc[1, d0])
        ur = u[dy] * math.cos(ph) + u[dz] * math.sin(ph); nn = nrm[k[d0]]
        un.append((u[d0] * nn[0] + ur * nn[1], loc[0, d0], r_l[d0]))
    un = np.array(un); jm = np.argmax(un[:, 0])
    res["tip"] = dict(n_points=int(len(un)), max_closing_mm=float(un[jm, 0] * 1e3), at_x_mm=float(un[jm, 1] * 1e3), at_r_mm=float(un[jm, 2] * 1e3),
                      cold_clearance_mm=CLEAR * 1e3, note="blade tip vs a rigid casing; casing / hub thermal growth not included")
    # displacements without the rigid rotation about x (a free mode held by the weak spring; it carries no stress)
    Ux, Uy, Uz = (u[ib.nodal_dofs[i]] for i in range(3)); Pv = m.p
    rv = np.hypot(Pv[1], Pv[2]); phv = np.arctan2(Pv[2], Pv[1])
    ut = -Uy * np.sin(phv) + Uz * np.cos(phv); ur = Uy * np.cos(phv) + Uz * np.sin(phv); om = float(np.sum(ut * rv) / np.sum(rv ** 2))
    res["displacement"] = dict(rigid_rotation_rad=om, max_meridional_mm=float(np.hypot(Ux, ur).max() * 1e3),
                               max_tangential_deformation_mm=float(np.abs(ut - om * rv).max() * 1e3))
    # field output for plotting (render_cad.py): element-mean von Mises, vertex displacement
    import meshio
    nv = m.p.shape[1]; U = np.c_[u[ib.nodal_dofs[0]], u[ib.nodal_dofs[1]], u[ib.nodal_dofs[2]]][:nv]
    meshio.write(os.path.join(ROOT, "cad", "fe", f"impeller_sector_{tag}.vtu"),
                 meshio.Mesh(m.p.T * 1e3, [("tetra", m.t.T)], point_data=dict(u_mm=U * 1e3), cell_data=dict(vm_MPa=[vm.mean(axis=1) / 1e6])))
    return res

out = json.load(open(OUT)) if os.path.exists(OUT) else {}
if __name__ == "__main__":
    cases = (sys.argv[1] if len(sys.argv) > 1 else "A,B,P").split(",")
    tmp = os.path.join(ROOT, "cad", "fe"); os.makedirs(tmp, exist_ok=True)
    out["conditions"] = dict(rpm_MCS=OM * 30 / math.pi, E_GPa=E_TI / 1e9, nu=NU, rho=RHO, support="boss axial within r 6 mm + weak tangential spring")
    if "A" in cases:                                   # ---------- (A) thin rotating disc sector ----------
        import cadquery as cq
        b, h = 60.0, 2.0
        disc = cq.Workplane("XY").polyline([(0, 0), (h, 0), (h, b), (0, b)]).close().revolve(30, (0, 0, 0), (1, 0, 0)).val().rotate((0, 0, 0), (1, 0, 0), math.degrees(PHI0))
        cq.exporters.export(cq.Workplane().add(disc), os.path.join(tmp, "disc_sector.step"))
        m, minfo = mesh_step(os.path.join(tmp, "disc_sector.step"), 1.0, 3.0)
        ib, u, info = solve(m, lambda L, c: (np.hypot(L[1], L[2]) < 1e-3) & (L[0] < 1e-6), solver="direct")
        S = stress(ib, u)
        c0 = (3 + NU) / 8 * RHO * OM ** 2 * (b * 1e-3) ** 2; rim = (1 - NU) / 4 * RHO * OM ** 2 * (b * 1e-3) ** 2
        near0 = S["r"] < 4e-3; nearb = S["r"] > (b - 1.5) * 1e-3
        st_th = RHO * OM ** 2 / 8 * ((3 + NU) * (b * 1e-3) ** 2 - (1 + 3 * NU) * S["r"] ** 2)          # plane-stress hoop, theory
        out["verify_disc"] = dict(**minfo, elements=int(m.t.shape[1]), **info, centre_radial_FE=float(np.mean(S["sr"][near0])), centre_hoop_FE=float(np.mean(S["st"][near0])),
                                  centre_theory=c0, rim_hoop_FE=float(np.mean(S["st"][nearb])), rim_hoop_theory_same_points=float(np.mean(st_th[nearb])), rim_hoop_theory_at_b=rim)
        v = out["verify_disc"]
        print(f"(A) disc sector: {v['elements']} tets; centre radial {v['centre_radial_FE']/1e6:.2f} / hoop {v['centre_hoop_FE']/1e6:.2f} vs theory {c0/1e6:.2f} MPa; "
              f"outer 1.5 mm hoop {v['rim_hoop_FE']/1e6:.2f} vs theory at the same points {v['rim_hoop_theory_same_points']/1e6:.2f} MPa", flush=True)
    if "B" in cases:                                   # ---------- (B) hub alone vs axisymmetric FE ----------
        hub_sector_step(os.path.join(tmp, "hub_sector.step"))
        m, minfo = mesh_step(os.path.join(tmp, "hub_sector.step"), 0.8, 2.5)
        ib, u, info = solve(m, boss_axial, spring_at=SPRING, solver="amg", check_direct=True)
        h3 = summarise_hub(stress(ib, u)); ref = axisym_hub_reference()
        out["verify_hub"] = dict(**minfo, elements=int(m.t.shape[1]), **info, fe3d=h3,
                                 axisym=dict(vm_peak_MPa=ref["vm_peak_MPa"], vm_peak_z_mm=ref["vm_peak_z_mm"], vm_peak_r_mm=ref["vm_peak_r_mm"],
                                             st_axis_MPa=ref["st_bore_MPa"], st_avg_MPa=ref["st_avg_MPa"], mass_hub_kg=ref["mass_hub_kg"]))
        print(f"(B) hub alone: {m.t.shape[1]} tets, AMG vs SuperLU {info['amg_vs_superlu_max_rel']:.1e}; 3D vm peak {h3['vm_peak_MPa']:.1f} MPa at (x {h3['vm_peak_x_mm']:.1f}, r {h3['vm_peak_r_mm']:.1f}) "
              f"vs axisym {ref['vm_peak_MPa']:.1f} at (z {ref['vm_peak_z_mm']:.1f}, r {ref['vm_peak_r_mm']:.1f}); hoop at axis {h3['st_axis_MPa']:.1f} vs {ref['st_bore_MPa']:.1f}; "
              f"avg hoop {h3['st_avg_MPa']:.1f} vs {ref['st_avg_MPa']:.1f}", flush=True)
    if "BT" in cases:                                  # ---------- (B') hub alone, passage-following (twisted) cut surfaces ----------
        hub_sector_step(os.path.join(tmp, "hub_sector_twisted.step"), twisted=True)
        m, minfo = mesh_step(os.path.join(tmp, "hub_sector_twisted.step"), 0.8, 2.5)
        ib, u, info = solve(m, boss_axial, spring_at=SPRING, phi_b=passage_boundary(), solver="pardiso", check_direct=True)
        h3 = summarise_hub(stress(ib, u)); ref = out.get("verify_hub", {}).get("axisym") or axisym_hub_reference()
        out["verify_hub_twisted"] = dict(elements=int(m.t.shape[1]), **info, fe3d=h3)
        print(f"(B') hub alone, twisted cut: {m.t.shape[1]} tets, tie {info['cyclic_tie']}, AMG {info.get('amg')}; vm peak {h3['vm_peak_MPa']:.1f} "
              f"vs axisym {ref['vm_peak_MPa']:.1f}; hoop at axis {h3['st_axis_MPa']:.1f} vs {ref.get('st_axis_MPa', ref.get('st_bore_MPa')):.1f}; avg hoop {h3['st_avg_MPa']:.1f} vs {ref['st_avg_MPa']:.1f}", flush=True)
    if "P" in cases:
        out["production"] = production(0.6, 3.0, "baseline")
        print(json.dumps(out["production"], indent=1, default=lambda x: round(float(x), 3)), flush=True)
    if "PF" in cases:
        out["production_fine"] = production(0.4, 2.0, "fine")
        print(json.dumps(out["production_fine"], indent=1, default=lambda x: round(float(x), 3)), flush=True)
    cct = json.load(open(os.path.join(ROOT, "data", "phase3r", "cct_ce75000_opr4_t1150_b15_cap.json")))["levels"]["fielded"]["stress"]
    out["reference_phase3r"] = dict(blade_root_Kt_MPa=cct["blade"]["sigma_root_MCS_MPa"], disc_vm_mech_MCS_MPa=cct.get("disc", {}).get("vm_mech_MCS_MPa"),
                                    Fty_MPa=cct.get("Fty_MPa"))
    json.dump(out, open(OUT, "w"), indent=1, default=float)
