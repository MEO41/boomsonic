"""Verify ROSS 2.3.0 (rotordynamic FE, Timoshenko beam elements) against closed-form solutions before use.

(a) uniform simply-supported steel shaft, first bending natural frequency at zero speed:
    w1 = (pi / L)^2 sqrt(E I / (rho A))   (Euler-Bernoulli; ROSS run with shear and rotary inertia OFF,
    and again ON to show the Timoshenko correction)
(b) Jeffcott rotor: point disc m at mid-span of a (near-)massless shaft on rigid supports:
    w = sqrt(48 E I / (m L^3))
(c) overhung disc on a cantilevered massless shaft (clamp approximated by two rigid supports 1 % of L
    apart on a stiff stub), gyroscopic effect: forward / backward whirl from
    det [[k11 - m w^2, k12], [k12, k22 - Id w^2 + Ip Omega w]] = 0,
    k11 = 12 EI/L^3, k12 = -6 EI/L^2, k22 = 4 EI/L  (Friswell, Penny, Garvey & Lees, Dynamics of
    Rotating Machines, CUP 2010, ch. 3 overhung-disc example; sign: + for forward whirl)
(d) the project's fast lateral solver (rotordynamics.Lateral: ROSS M, K, G restricted to lateral DOFs)
    against ROSS run_modal on the same overhung rotor at 40 000 rpm (frequencies, whirl labels), and its
    forward synchronous critical speed (Campbell / 1x intersection) against the closed form
    (k11 - m w^2)(k22 - Id w^2 + Ip w^2) = k12^2.
(e) the damped solver (rotordynamics_damped.Damped): centred disc m on a stiff light shaft, two identical
    supports (k, c), negligible disc inertia -> cylindrical mode wn = sqrt(2k/m), zeta = c / sqrt(2 k m).
Supports: ROSS BearingElement with k = 1e12 N/m (translation only -> pinned).
"""
import os, sys, json, contextlib, io, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from ross_shim import rs
from scipy.optimize import brentq

E, NU, RHO = 211e9, 0.29, 7810.0
steel = rs.Material(name="steel_v", rho=RHO, E=E, Poisson=NU)
KB = 1e12

def pinned(n):
    return rs.BearingElement(n=n, kxx=KB, cxx=0.0)

def shaft(L, d, ne, mat, **kw):
    return [rs.ShaftElement(L=L / ne, idl=0.0, odl=d, material=mat, **kw) for _ in range(ne)]

out = {}
# (a) simply supported uniform shaft
L, d = 1.0, 0.05
I = np.pi * d ** 4 / 64; A = np.pi * d ** 2 / 4
w_eb = (np.pi / L) ** 2 * np.sqrt(E * I / (RHO * A))
for tag, kw in (("EB", dict(shear_effects=False, rotary_inertia=False, gyroscopic=False)), ("Timoshenko", {})):
    rot = rs.Rotor(shaft(L, d, 20, steel, **kw), [], [pinned(0), pinned(20)])
    wn = np.sort(rot.run_modal(0.0, num_modes=12, sparse=False).wn)
    wn = wn[wn > 1.0]
    out[f"a_{tag}"] = dict(ross=float(wn[0]), closed=float(w_eb), err_pct=float((wn[0] / w_eb - 1) * 100))
# (b) Jeffcott
light = rs.Material(name="light_v", rho=1e-3, E=E, Poisson=NU)
L, d, m = 0.5, 0.02, 5.0
I = np.pi * d ** 4 / 64
w_j = np.sqrt(48 * E * I / (m * L ** 3))
rot = rs.Rotor(shaft(L, d, 20, light, shear_effects=False, rotary_inertia=False, gyroscopic=False),
               [rs.DiskElement(n=10, m=m, Id=1e-9, Ip=1e-9)], [pinned(0), pinned(20)])
wn = np.sort(rot.run_modal(0.0, num_modes=12, sparse=False).wn); wn = wn[wn > 1.0]
out["b_Jeffcott"] = dict(ross=float(wn[0]), closed=float(w_j), err_pct=float((wn[0] / w_j - 1) * 100))
# (c) overhung disc, gyroscopics
L, d, m, Id, Ip = 0.3, 0.02, 3.0, 0.004, 0.008
I = np.pi * d ** 4 / 64; k11, k12, k22 = 12 * E * I / L ** 3, -6 * E * I / L ** 2, 4 * E * I / L
def closed(Om, fwd):
    s = 1.0 if fwd else -1.0
    f = lambda w: (k11 - m * w * w) * (k22 - Id * w * w + s * Ip * Om * w) - k12 ** 2
    ws = np.linspace(1.0, 3000.0, 30000); v = f(ws); i = np.where(np.sign(v[:-1]) != np.sign(v[1:]))[0][0]
    return brentq(f, ws[i], ws[i + 1])
a = 0.01 * L
elems = [rs.ShaftElement(L=a, idl=0.0, odl=0.2, material=light, shear_effects=False, rotary_inertia=False, gyroscopic=False)] + \
        shaft(L, d, 30, light, shear_effects=False, rotary_inertia=False, gyroscopic=False)
rot = rs.Rotor(elems, [rs.DiskElement(n=31, m=m, Id=Id, Ip=Ip)], [pinned(0), pinned(1)])
rows = []
for rpm in (0.0, 20000.0, 40000.0, 60000.0):
    Om = rpm * np.pi / 30
    mr = rot.run_modal(Om, num_modes=12, sparse=False)
    wd = np.asarray(mr.wd); wh = np.asarray(mr.whirl_direction()) if callable(getattr(mr, "whirl_direction", None)) else None
    idx = np.argsort(wd); wd = wd[idx]; wh = wh[idx] if wh is not None else None
    keep = wd > 1.0; wd = wd[keep]; wh = wh[keep] if wh is not None else None
    cf, cb = closed(Om, True), closed(Om, False)
    if Om == 0:
        rf = rb = float(wd[0])
    else:
        rf = float(wd[[i for i in range(len(wd)) if str(wh[i]).lower().startswith("forward")][0]])
        rb = float(wd[[i for i in range(len(wd)) if str(wh[i]).lower().startswith("backward")][0]])
    rows.append(dict(rpm=rpm, fwd_ross=rf, fwd_closed=cf, bwd_ross=rb, bwd_closed=cb,
                     err_fwd_pct=(rf / cf - 1) * 100, err_bwd_pct=(rb / cb - 1) * 100))
out["c_overhung_gyro"] = rows
# (d) fast solver vs ROSS and vs closed-form forward critical
import rotordynamics as rd
Om = 40000.0 * np.pi / 30
mr = rot.run_modal(Om, num_modes=12, sparse=False)
wd = np.asarray(mr.wd); wh = np.asarray(mr.whirl_direction()); o = np.argsort(wd); wd, wh = wd[o], wh[o]
lat = [(w, str(h)) for w, h in zip(wd, wh) if str(h) in ("Forward", "Backward") and w > 1.0][:4]
fast = [(w, h) for w, h, _ in rd.lateral_modes(rot, Om)][:4]
out["d_fast_vs_ross"] = [dict(ross=a[0], ross_whirl=a[1], fast=b[0], fast_whirl=b[1], err_pct=(b[0] / a[0] - 1) * 100) for a, b in zip(lat, fast)]
fc = lambda w: (k11 - m * w * w) * (k22 - Id * w * w + Ip * w * w) - k12 ** 2
ws = np.linspace(1.0, 3000.0, 30000); v = fc(ws); i = np.where(np.sign(v[:-1]) != np.sign(v[1:]))[0][0]
w_c = brentq(fc, ws[i], ws[i + 1])
sp, fw, bw = rd.campbell(rot, 2.0 * w_c * 30 / np.pi, n=60)
w_f = rd.forward_criticals(sp, fw)[0]
out["d_forward_critical"] = dict(fast=w_f, closed=w_c, err_pct=(w_f / w_c - 1) * 100)
# (e) damped solver vs single-DOF closed form
import rotordynamics_damped as rdd
kS, cS, mS = 2.0e6, 800.0, 2.0
stiff = rs.Material(name="stiff_v", rho=1e-3, E=1e15, Poisson=NU)
rotE = rs.Rotor([rs.ShaftElement(L=0.02, idl=0.0, odl=0.03, material=stiff, shear_effects=False, rotary_inertia=False, gyroscopic=False) for _ in range(10)],
                [rs.DiskElement(n=5, m=mS, Id=1e-7, Ip=1e-7)], [rs.BearingElement(n=0, kxx=kS, cxx=cS), rs.BearingElement(n=10, kxx=kS, cxx=cS)])
wz = rdd.Damped(rotE).forward(1.0)[0]
wn_c = np.sqrt(2 * kS / mS); z_c = cS / np.sqrt(2 * kS * mS); wd_c = wn_c * np.sqrt(1 - z_c ** 2)
out["e_damped_sdof"] = dict(wd=wz[0], wd_closed=float(wd_c), zeta=wz[1], zeta_closed=float(z_c),
                            err_wd_pct=(wz[0] / wd_c - 1) * 100, err_zeta_pct=(wz[1] / z_c - 1) * 100)
out["versions"] = dict(ross=rs.__version__)
json.dump(out, open(os.path.join(ROOT, "data", "phase4_rotordynamics_verification.json"), "w"), indent=1, default=float)
for k, v in out.items():
    if isinstance(v, list):
        for r in v: print(k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in r.items()})
    else: print(k, v)
