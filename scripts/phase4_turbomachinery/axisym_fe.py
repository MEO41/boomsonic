"""Axisymmetric linear-elastic FE for rotating bodies (scikit-fem 12, P2 triangles on the r-z plane).

Unknowns u = (u_r, u_z). Strains e_r = du_r/dr, e_z = du_z/dz, e_t = u_r/r, g_rz = du_r/dz + du_z/dr.
Weak form: int eps(v)^T D eps(u) r dA = int rho w^2 r v_r r dA + int t . v r ds  (2 pi dropped).
Material: isotropic D(E, nu) (stresses in a rotating homogeneous body do not depend on E).
Verified in verify_axisym_fe.py against the plane-stress rotating-disc solutions (Timoshenko &
Goodier, Theory of Elasticity, sec. 32): solid disc and disc with a central bore.
"""
import numpy as np
from skfem import MeshTri, ElementTriP2, ElementVector, Basis, FacetBasis, BilinearForm, LinearForm, asm, solve, condense

def mapped_mesh(r_nodes, z_lo, z_hi, nz, grade_z=None):
    """structured triangle mesh of {r in r_nodes, z_lo(r) <= z <= z_hi(r)}; t = 0 on z_lo, 1 on z_hi."""
    t = np.linspace(0, 1, nz) if grade_z is None else grade_z
    m = MeshTri.init_tensor(np.asarray(r_nodes, float), t)
    r, tt = m.p
    z = z_lo(r) + tt * (z_hi(r) - z_lo(r))
    return MeshTri(np.vstack([r, z]), m.t)

def D_iso(E, nu):
    c = E / ((1 + nu) * (1 - 2 * nu))
    D = np.array([[1 - nu, nu, nu, 0], [nu, 1 - nu, nu, 0], [nu, nu, 1 - nu, 0], [0, 0, 0, (1 - 2 * nu) / 2]]) * c
    return D   # order: e_r, e_z, e_t, g_rz

def solve_rotating(mesh, rho, omega, E=110e9, nu=0.34, traction=None, axis_nodes_fix_ur=False, intorder=4, dT=None, alpha=9.0e-6):
    """traction: callable (r, z) -> (t_r, t_z) applied on the boundary facets selected by traction['facets']."""
    e = ElementVector(ElementTriP2())
    basis = Basis(mesh, e, intorder=intorder)
    D = D_iso(E, nu)

    def eps(u, r):
        return [u.grad[0][0], u.grad[1][1], u.value[0] / r, u.grad[0][1] + u.grad[1][0]]

    @BilinearForm
    def a(u, v, w):
        r = w.x[0]
        eu, ev = eps(u, r), eps(v, r)
        s = 0.0
        for i in range(4):
            for j in range(4):
                if D[i, j] != 0.0:
                    s = s + D[i, j] * eu[j] * ev[i]
        return s * r

    @LinearForm
    def body(v, w):
        r = w.x[0]
        return rho * omega ** 2 * r * v.value[0] * r

    K = asm(a, basis); f = asm(body, basis)
    if dT is not None:                                  # thermal load: eps_th = alpha dT in e_r, e_z, e_t
        @LinearForm
        def therm(v, w):
            r, z = w.x; eth = alpha * dT(r, z); ev = eps(v, r)
            return sum((D[i, 0] + D[i, 1] + D[i, 2]) * eth * ev[i] for i in range(4)) * r
        f = f + asm(therm, basis)
    if traction is not None:
        fb = FacetBasis(mesh, e, facets=traction["facets"], intorder=intorder)
        tf = traction["func"]

        @LinearForm
        def trac(v, w):
            r, z = w.x
            tr, tz = tf(r, z)
            return (tr * v.value[0] + tz * v.value[1]) * r
        f = f + asm(trac, fb)
    # constraints: axial rigid body (u_z = 0 at one node); u_r = 0 on the axis if the mesh touches r = 0
    dofs = basis.nodal_dofs
    iz = int(np.argmin(np.hypot(mesh.p[0] - mesh.p[0].max(), mesh.p[1] - mesh.p[1].min())))
    D_fix = [dofs[1, iz]]
    if axis_nodes_fix_ur:
        on_axis = np.where(mesh.p[0] < 1e-12)[0]
        D_fix += list(dofs[0, on_axis])
        # P2 facet (edge) dofs on the axis
        fac_axis = mesh.facets_satisfying(lambda x: x[0] < 1e-12)
        D_fix += list(basis.get_dofs(fac_axis).all("u^1")) if len(fac_axis) else []
    u = solve(*condense(K, f, D=np.unique(D_fix)))
    basis.dT_func, basis.alpha = dT, alpha
    return basis, u, D

def stresses(basis, u, D):
    """stress components at quadrature points: returns dict of arrays (n_elem, n_qp) and qp coordinates."""
    uf = basis.interpolate(u)
    x = basis.mapping.F(basis.X)
    r = x[0]
    eps = [uf.grad[0][0], uf.grad[1][1], uf.value[0] / r, uf.grad[0][1] + uf.grad[1][0]]
    if getattr(basis, "dT_func", None) is not None:
        eth = basis.alpha * basis.dT_func(x[0], x[1])
        eps = [eps[0] - eth, eps[1] - eth, eps[2] - eth, eps[3]]
    sig = [sum(D[i, j] * eps[j] for j in range(4)) for i in range(4)]
    sr, sz, st, trz = sig
    vm = np.sqrt(0.5 * ((sr - sz) ** 2 + (sz - st) ** 2 + (st - sr) ** 2) + 3 * trz ** 2)
    w = basis.dx                      # quadrature weights x jacobian (area, no r factor)
    return dict(r=x[0], z=x[1], sr=sr, sz=sz, st=st, trz=trz, vm=vm, dA=w)
