"""Phase 4 (centrifugal baseline): the chosen rotor configuration - Campbell diagram, damped criticals / API check,
mode shapes and bearing loads. Configuration (cc_rotor_stiffening.py): combustor liner 0.8 x the Phase 3 rule (bearing
span 192 mm), AISI 4340 tube 32 x 25.6 mm, 12 mm journals, soft damped supports k 1.75e6 N/m, c 876 N s/m (Gunter 2023).
Output: data/phase4r_rotor_final.json, plots/phase4r_rotor_final.png
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
tag = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"; sys.argv = [sys.argv[0], tag]
import cc_rotor as cr, rotordynamics as rd, rotordynamics_damped as rdd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
LF, OD, IDR, JOD, K, C = 0.8, 0.032, 0.8, 0.012, cr.K_SOFT, cr.C_GUNTER
geo = cr.geometry(tag, liner_factor=LF); rpm = geo["rpm"]
rot, info = cr.build(geo, K, c=C, shaft_od=OD, id_ratio=IDR, journal_od=JOD)
rot0, info0 = cr.build(geo, K, shaft_od=OD, id_ratio=IDR, journal_od=JOD)
crit = rdd.damped_criticals(rot, 1.8 * rpm, n=60); res, ok = rdd.assess(crit, rpm)
sp, fw, bw = rd.campbell(rot0, 1.8 * rpm, n=40); cu = [c / rd.RPM2RAD for c in rd.forward_criticals(sp, fw)]
mp = cr.mass_props(rot0, geo, info0)
out = dict(tag=tag, config=dict(liner_factor=LF, shaft_od_mm=OD * 1e3, id_ratio=IDR, journal_mm=JOD * 1e3, k=K, c=C), span_mm=info["span"] * 1e3,
           overhang_imp_mm=info["overhang_imp"] * 1e3, overhang_turb_mm=info["overhang_turb"] * 1e3, undamped_crit_rpm=cu, damped=res, api_ok=ok, mass=mp,
           DN_MCS=JOD * 1e3 * rpm * rd.MCS_F)
json.dump(out, open(os.path.join(ROOT, "data", "phase4r_rotor_final.json"), "w"), indent=1, default=float)
print({k: v for k, v in out.items() if k not in ("damped",)}); print(res)
fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
r = sp / rd.RPM2RAD / 1e3
for i in range(fw.shape[1]):
    ax[0].plot(r, fw[:, i] / rd.RPM2RAD / 1e3, "-", c="#1f77b4", lw=1.2, label="forward whirl" if i == 0 else None)
    ax[0].plot(r, bw[:, i] / rd.RPM2RAD / 1e3, "--", c="#ff7f0e", lw=1.0, label="backward whirl" if i == 0 else None)
ax[0].plot(r, r, "k-", lw=0.8, label="1x"); ax[0].axvspan(rd.IDLE * rpm / 1e3, rd.MCS_F * rpm / 1e3, color="0.9", label="35-105 % speed")
for c_ in cu[:3]: ax[0].plot(c_ / 1e3, c_ / 1e3, "ro", ms=5)
ax[0].set_xlim(0, r.max()); ax[0].set_ylim(0, 1.9 * rpm / 1e3); ax[0].grid(alpha=.3); ax[0].legend(fontsize=7)
ax[0].set_xlabel("rotor speed [krpm]"); ax[0].set_ylabel("whirl frequency [krpm]")
ax[0].set_title(f"Campbell (undamped), k {K:.2g} N/m; criticals {', '.join(f'{c/1e3:.1f}' for c in cu[:3])} krpm", fontsize=9)
m = rd.lateral_modes(rot0, 0.01); x = np.array(info0["x_nodes"]) * 1e3; seen = []
for w, d_, v in m:
    if any(abs(w - s) / s < 1e-3 for s in seen): continue
    seen.append(w); u = v[0::4][: len(x)]; u = np.real(u * np.exp(-1j * np.angle(u[np.argmax(np.abs(u))]))); u = u / np.max(np.abs(u))
    ax[1].plot(x, u, label=f"{w / rd.RPM2RAD / 1e3:.1f} krpm (zero speed)")
    if len(seen) == 3: break
for xx, nm in ((geo["imp"]["x"], "impeller"), (geo["turb"]["x"], "turbine")): ax[1].axvline(xx * 1e3, c="0.6", lw=0.8); ax[1].text(xx * 1e3 + 2, -0.3, nm, fontsize=7)
for xb in (info0["x_front"], info0["x_rear"]): ax[1].plot(xb * 1e3, 0, "k^", ms=10)
ax[1].set_xlabel("axial position from the impeller nose [mm]"); ax[1].grid(alpha=.3); ax[1].legend(fontsize=7)
ax[1].set_title(f"mode shapes (triangles: bearings, span {info0['span']*1e3:.0f} mm); shaft tube {OD*1e3:.0f} x {IDR*OD*1e3:.1f} mm", fontsize=9)
fig.suptitle(f"Phase 4 rotor, centrifugal engine: damped AF {[r_['AF'] for r_ in res]} at {[r_['crit_rpm'] for r_ in res]} rpm -> API {'PASS' if ok else 'FAIL'}", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase4r_rotor_final.png"), dpi=130)
