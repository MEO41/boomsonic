"""Verify axisym_fe against plane-stress rotating-disc theory (Timoshenko & Goodier sec. 32):
solid disc:  sigma_r(0) = sigma_t(0) = (3+nu)/8 rho w^2 b^2 ; sigma_t(b) = (1-nu)/4 rho w^2 b^2
bored disc:  sigma_t(a) = (3+nu)/4 rho w^2 (b^2 + (1-nu)/(3+nu) a^2) ; sigma_r,max = (3+nu)/8 rho w^2 (b-a)^2 at r = sqrt(ab)
Thin disc (h = 0.02 b) so the axisymmetric solution approaches plane stress."""
import numpy as np, axisym_fe as fe
rho, w, nu, b, h = 4430.0, 1000.0, 0.34, 0.10, 0.002
q = rho * w ** 2 * b ** 2
for label, a in (("solid", 0.0), ("bore a = 0.2 b", 0.02)):
    rn = np.linspace(a, b, 81)
    m = fe.mapped_mesh(rn, lambda r: 0 * r, lambda r: 0 * r + h, 3)
    basis, u, D = fe.solve_rotating(m, rho, w, nu=nu, axis_nodes_fix_ur=(a == 0.0))
    s = fe.stresses(basis, u, D)
    r = s["r"]; st = s["st"]; sr = s["sr"]
    if a == 0.0:
        th_c = (3 + nu) / 8 * q; th_b = (1 - nu) / 4 * q
        i0 = np.argmin(r); ib = np.argmax(r)
        print(f"{label}: sigma_t(center) FE {st.flat[i0]/1e6:.4f} vs {th_c/1e6:.4f} MPa ({(st.flat[i0]/th_c-1)*100:+.2f} %); "
              f"sigma_t(rim) FE {st.flat[ib]/1e6:.4f} vs {th_b/1e6:.4f} ({(st.flat[ib]/th_b-1)*100:+.2f} %); sigma_r,max FE {sr.max()/1e6:.4f} vs {th_c/1e6:.4f}")
    else:
        th_a = (3 + nu) / 4 * rho * w ** 2 * (b ** 2 + (1 - nu) / (3 + nu) * a ** 2)
        srm = (3 + nu) / 8 * rho * w ** 2 * (b - a) ** 2
        i0 = np.argmin(r)
        print(f"{label}: sigma_t(bore) FE {st.flat[i0]/1e6:.4f} vs {th_a/1e6:.4f} MPa ({(st.flat[i0]/th_a-1)*100:+.2f} %); "
              f"sigma_r,max FE {sr.max()/1e6:.4f} vs {srm/1e6:.4f} ({(sr.max()/srm-1)*100:+.2f} %)")
