"""Phase 4 conceptual rotordynamics of the pure-axial engine (ROSS 2.3.0, verified in rotordynamics_verify.py).

Model: rotor_model.py (geometry from the Phase 3 trade file, env P4_TRADE or argv[1]).
Analyses (undamped, linear, isotropic bearings with translational stiffness k only):
1. critical-speed map: first forward-whirl synchronous critical speeds vs bearing stiffness
   k = 1e6 .. 1e9 N/m, layouts A and B, drum and through-shaft variants;
2. Campbell diagram (forward/backward whirl vs speed, gyroscopics) at the sourced stiffness levels:
   k_hard = 1.9e7 N/m (max radial stiffness of a 10 x 26 mm 15 deg angular-contact ball bearing at
   63 000 rpm, Wang, Lv & Luo, Sensors 2023, PMC10181543; Gunter 2023 assumes 250 000 lb/in = 4.4e7 N/m
   for turbocharger ball bearings on rigid supports), k_soft = 1.75e6 N/m (optimum damper-cartridge
   spring rate 10 000 +- 3 000 lb/in of a ball-bearing turbocharger, E. J. Gunter, "Design of oil and
   air squeeze film dampers for a ball bearing turbocharger", Dyrobes 2023) and k_soft_min = 6e5 N/m
   (elastic bearing suspension of a micro gas turbine, manufacturer data confirmed by test, ASME
   J. Eng. Gas Turbines Power 146(10) 101002, 2024);
3. mode type at zero speed: share of modal strain energy in the bearings (> 50 % = rigid-body /
   bearing-dominated, otherwise shaft-bending);
4. separation margins per API 684 (2003) / API 617 criteria, amplification factor unknown (no damping
   model) -> the most demanding values are applied: a critical above the operating range must be
   >= 26 % above maximum continuous speed (MCS), one below it >= 16 % below minimum operating speed;
   MCS = 105 % of the design speed (API definition), idle = 35 % (operating range 35-105 %);
5. shaft-diameter sweep: the steel shaft OD (wall ratio ID/OD 0.5 kept) needed for the first bending
   critical to clear 1.26 MCS, with the bearing DN value it implies;
6. rotor mass, polar moment of inertia, static bearing reactions.
Outputs: data/phase4_rotordynamics.json, data/phase4_rotordynamics_critmap.csv,
plots/phase4_critical_speed_map.png, plots/phase4_campbell.png, plots/phase4_rotor_modes.png
"""
import os, sys, json, time, numpy as np, pandas as pd, scipy.linalg as la
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# shared module (cc_rotor.py imports it), but the __main__ study below is the pure-axial rotor: its results live under axial/
AXROOT = os.path.join(ROOT, "axial")
sys.path.insert(0, HERE)
import rotor_model as rm
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

K_HARD, K_SOFT, K_SOFT_MIN, K_GUNTER_BB = 1.9e7, 1.75e6, 6.0e5, 4.4e7
IDLE, MCS_F, SM_ABOVE, SM_BELOW = 0.35, 1.05, 0.26, 0.16
RPM2RAD = np.pi / 30


class Lateral:
    """Lateral eigen-solver on ROSS's assembled matrices (M, K, G), restricted to the lateral DOFs
    (x, y, alpha, beta); axial/torsional DOFs are uncoupled in this linear model. Undamped (C = 0).
    Whirl direction: forward if |X + iY| > |X - iY| (orbit decomposed into co- and counter-rotating
    circles). Checked against ROSS run_modal (frequencies and whirl labels identical) in
    rotordynamics_verify.py, case (d)."""
    def __init__(self, rot, info=None):
        lat = np.array([i for i in range(rot.ndof) if i % 6 in (0, 1, 3, 4)])
        M, K, G = np.asarray(rot.M()), np.asarray(rot.K(0.0)), np.asarray(rot.G())
        self.n = len(lat); self.Kr = K[np.ix_(lat, lat)]; self.Gr = G[np.ix_(lat, lat)]
        self.Minv = np.linalg.inv(M[np.ix_(lat, lat)]); self.info = info

    def modes(self, speed):
        n = self.n
        A = np.block([[np.zeros((n, n)), np.eye(n)], [-self.Minv @ self.Kr, -self.Minv @ (speed * self.Gr)]])
        lam, V = la.eig(A); keep = lam.imag > 1.0
        lam, V = lam[keep], V[:n, keep]; o = np.argsort(lam.imag); lam, V = lam[o], V[:, o]
        X, Y = V[0::4], V[1::4]
        fw = [np.linalg.norm(X[:, j] + 1j * Y[:, j]) > np.linalg.norm(X[:, j] - 1j * Y[:, j]) for j in range(V.shape[1])]
        return [(float(lam[j].imag), "Forward" if fw[j] else "Backward", V[:, j]) for j in range(len(lam))]


def lateral_modes(rot, speed):
    if not hasattr(rot, "_lat"): rot._lat = Lateral(rot)
    return rot._lat.modes(speed)


def bearing_energy_share(rot, info, v):
    if not hasattr(rot, "_lat"): rot._lat = Lateral(rot)
    L = rot._lat
    v = v * np.exp(-1j * np.angle(v[np.argmax(np.abs(v))]))
    E_tot = float(np.real(np.conj(v) @ L.Kr @ v))
    E_b = sum(info["k"] * (abs(v[4 * n]) ** 2 + abs(v[4 * n + 1]) ** 2) for n in (info["node_front"], info["node_rear"]))
    return E_b / E_tot if E_tot > 0 else np.nan


def campbell(rot, rpm_max, n=26):
    sp = np.linspace(0.01, rpm_max, n) * RPM2RAD
    fw, bw = [], []
    for s in sp:
        m = lateral_modes(rot, s)
        fw.append([w for w, d, _ in m if d.lower().startswith("f")][:5]); bw.append([w for w, d, _ in m if d.lower().startswith("b")][:5])
    L = lambda a: np.array([r + [np.nan] * (5 - len(r)) for r in a])
    return sp, L(fw), L(bw)


def forward_criticals(sp, fw):
    crit = []
    for i in range(fw.shape[1]):
        g = fw[:, i] - sp
        idx = np.where(np.isfinite(g[:-1]) & np.isfinite(g[1:]) & (np.sign(g[:-1]) != np.sign(g[1:])))[0]
        if len(idx):
            j = idx[0]; crit.append(float(sp[j] - g[j] * (sp[j + 1] - sp[j]) / (g[j + 1] - g[j])))
    return sorted(crit)


def classify(rot, info):
    m = lateral_modes(rot, 0.01)
    res, seen = [], []
    for w, d, v in m:
        if any(abs(w - s) / s < 1e-3 for s in seen): continue                # x/y pair
        seen.append(w); res.append(dict(f0_rpm=w / RPM2RAD, bearing_energy=bearing_energy_share(rot, info, v)))
        if len(res) == 4: break
    return res


def crit_types(rot, info, crits_rad):
    """bearing strain-energy share of the forward mode at each critical speed (>0.5: rigid-body)."""
    out = []
    for c in crits_rad:
        m = [(w, v) for w, d, v in lateral_modes(rot, c) if d == "Forward"]
        w, v = min(m, key=lambda t: abs(t[0] - c))
        out.append(bearing_energy_share(rot, info, v))
    return out


def verdict(crits_rpm, rpm):
    mcs, idle = MCS_F * rpm, IDLE * rpm
    rows = []
    for c in crits_rpm:
        if c >= mcs: sm = c / mcs - 1; ok = sm >= SM_ABOVE; where = "above MCS"
        elif c <= idle: sm = 1 - c / idle; ok = sm >= SM_BELOW; where = "below idle"
        else: sm = -min(c / idle - 1, 1 - c / mcs); ok = False; where = "INSIDE operating range"
        rows.append(dict(crit_rpm=c, pct_design=100 * c / rpm, where=where, margin=sm, ok=ok))
    return rows


def main(trade=None):
    t0 = time.time()
    geo = rm.geometry(trade); rpm = geo["rpm"]; rpm_max = 1.6 * rpm
    out = dict(trade=geo["trade"], rpm=rpm, idle_rpm=IDLE * rpm, mcs_rpm=MCS_F * rpm, criteria=dict(sm_above=SM_ABOVE, sm_below=SM_BELOW,
               source="API Publication 684 (2003) tutorial of API 617 lateral criteria: AF<2.5 no margin; 2.5-3.55 15 % above MCS / 5 % below min speed; "
                      "AF>3.55 SM = 126 - 6/(AF-3) - 100 % above MCS (cap 26 %), 100 - (84 + 6/(AF-3)) % below min speed (cap 16 %)"),
               k_hard=K_HARD, k_soft=K_SOFT, k_soft_min=K_SOFT_MIN, geometry={k: v for k, v in geo.items()})
    # --- mass properties per layout
    out["mass"] = {}
    for lay in "AB":
        rot, info = rm.build(geo, lay, K_HARD)
        mp = rm.mass_props(rot, geo, info)
        mp["gyro_bearing_load_N_per_radps"] = mp["Ip_kgm2"] * rpm * RPM2RAD / info["span"]     # couple Ip*Omega*q reacted over the span
        out["mass"][lay] = dict(**mp, **{k: v for k, v in info.items() if k != "x_nodes"})
    # --- critical speed map
    rows = []
    for lay in "AB":
        for drum in (True, False):
            for k in np.logspace(6, 9, 13):
                rot, info = rm.build(geo, lay, float(k), drum=drum)
                sp, fw, bw = campbell(rot, rpm_max, n=22)
                c = forward_criticals(sp, fw)
                rows.append(dict(layout=lay, drum=drum, k=float(k), **{f"crit{i+1}_rpm": (c[i] / RPM2RAD if i < len(c) else np.nan) for i in range(3)}))
            print(f"  crit map {lay} drum={drum} done ({time.time()-t0:.0f} s)", flush=True)
    cm = pd.DataFrame(rows); cm.to_csv(os.path.join(AXROOT, "data", "phase4_rotordynamics_critmap.csv"), index=False)
    # --- baseline Campbell, classification, verdicts
    out["cases"] = {}
    for lay in "AB":
        for kname, k in (("hard", K_HARD), ("soft", K_SOFT), ("softmin", K_SOFT_MIN)):
            rot, info = rm.build(geo, lay, k)
            sp, fw, bw = campbell(rot, rpm_max, n=33)
            cr = forward_criticals(sp, fw); c = [x / RPM2RAD for x in cr]
            cls = classify(rot, info); ty = crit_types(rot, info, cr)
            out["cases"][f"{lay}_{kname}"] = dict(k=k, crit_fwd_rpm=c, crit_bearing_energy=ty, verdict=verdict(c[:3], rpm), modes0=cls,
                                                  campbell=dict(rpm=(sp / RPM2RAD).tolist(), fwd_rpm=(fw / RPM2RAD).tolist(), bwd_rpm=(bw / RPM2RAD).tolist()))
            print(f"  {lay}_{kname}: crit {[round(x) for x in c[:4]]} rpm; modes0 {[(round(m['f0_rpm']), round(m['bearing_energy'], 2)) for m in cls]}", flush=True)
    # --- hot-material and through-shaft sensitivities at k_hard, layout A
    sens = {}
    for tag, kw in (("E_minus10pct", dict(E_scale=0.9)), ("through_shaft", dict(drum=False)), ("mesh_5mm", dict(dx=0.005))):
        rot, info = rm.build(geo, "A", K_HARD, **kw); sp, fw, bw = campbell(rot, rpm_max, n=22)
        sens[tag] = [x / RPM2RAD for x in forward_criticals(sp, fw)][:3]
    out["sensitivity_A_hard"] = sens
    # --- shaft OD sweep (layout A and B, k_hard and 1e8)
    sweep = []
    for lay in "AB":
        for k in (K_HARD, 1e8, 1e9):
            for od in (0.016, 0.020, 0.024, 0.028, 0.032, 0.036, 0.040):
                rot, info = rm.build(geo, lay, k, shaft_od=od, shaft_id=0.5 * od)
                sp, fw, bw = campbell(rot, 2.2 * rpm, n=24)
                cr = forward_criticals(sp, fw); c = [x / RPM2RAD for x in cr]
                ty = crit_types(rot, info, cr)
                bend = [x for x, e in zip(c, ty) if e < 0.5]
                mp = rm.mass_props(rot, geo, info)
                sweep.append(dict(layout=lay, k=k, shaft_od_mm=od * 1e3, crits_rpm=c[:3], crit_bearing_energy=ty[:3], first_bending_crit_rpm=bend[0] if bend else np.nan,
                                  DN_mm_rpm=od * 1e3 * rpm, m_rotor=mp["m_rotor_kg"], Ip=mp["Ip_kgm2"]))
        print(f"  OD sweep {lay} done ({time.time()-t0:.0f} s)", flush=True)
    out["shaft_od_sweep"] = sweep
    json.dump(out, open(os.path.join(AXROOT, "data", "phase4_rotordynamics.json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o))
    plots(out, cm, geo)
    print(f"done in {time.time()-t0:.0f} s")


def plots(out, cm, geo):
    rpm = out["rpm"]; idle, mcs = out["idle_rpm"], out["mcs_rpm"]
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, lay in zip(axs, "AB"):
        for drum, ls in ((True, "-"), (False, "--")):
            d = cm[(cm.layout == lay) & (cm.drum == drum)]
            for i, c in enumerate(("#1f77b4", "#d62728", "#2ca02c")):
                ax.semilogx(d.k, d[f"crit{i+1}_rpm"] / 1e3, ls, color=c, label=f"critical {i+1}" + ("" if drum else " (through-shaft)") if lay == "A" else None)
        ax.axhspan(idle / 1e3, mcs / 1e3, color="0.85", label="operating range 35-105 %" if lay == "A" else None)
        ax.axhline(mcs * (1 + SM_ABOVE) / 1e3, color="k", lw=0.8, ls=":", label="MCS + 26 %" if lay == "A" else None)
        ax.axhline(idle * (1 - SM_BELOW) / 1e3, color="k", lw=0.8, ls="-.", label="idle - 16 %" if lay == "A" else None)
        for kk, nm in ((K_SOFT_MIN, "uGT suspension 6e5"), (K_SOFT, "damper cartridge 1.75e6"), (K_HARD, "ACBB 10x26 1.9e7"), (K_GUNTER_BB, "ball brg 4.4e7")):
            ax.axvline(kk, color="0.4", lw=0.8); ax.text(kk * 1.1, 2, nm, rotation=90, fontsize=7, va="bottom")
        ax.set_xlabel("bearing radial stiffness k [N/m]"); ax.set_title(f"Layout {lay}: " + ("straddled compressor, overhung turbine" if lay == "A" else "both bearings in shaft tunnel"), fontsize=9)
        ax.set_ylim(0, 1.6 * rpm / 1e3); ax.grid(alpha=0.3)
    axs[0].set_ylabel("forward synchronous critical speed [krpm]"); axs[0].legend(fontsize=7, loc="upper left")
    fig.suptitle("Phase 4 critical-speed map, pure-axial engine rotor (ROSS, undamped)", fontsize=10); fig.tight_layout()
    fig.savefig(os.path.join(AXROOT, "plots", "phase4_critical_speed_map.png"), dpi=140); plt.close(fig)
    fig, axs = plt.subplots(2, 2, figsize=(12, 8.5))
    for ax, key in zip(axs.flat, ("A_hard", "A_soft", "B_hard", "B_soft")):
        c = out["cases"][key]["campbell"]; r = np.array(c["rpm"]) / 1e3
        for i in range(5):
            ax.plot(r, np.array(c["fwd_rpm"])[:, i] / 1e3, "-", color="#1f77b4", lw=1.2, label="forward whirl" if i == 0 else None)
            ax.plot(r, np.array(c["bwd_rpm"])[:, i] / 1e3, "--", color="#ff7f0e", lw=1.0, label="backward whirl" if i == 0 else None)
        ax.plot(r, r, "k-", lw=0.8, label="1x"); ax.axvspan(idle / 1e3, mcs / 1e3, color="0.9")
        for cc in out["cases"][key]["crit_fwd_rpm"][:3]: ax.plot(cc / 1e3, cc / 1e3, "ro", ms=5)
        ax.set_xlim(0, r.max()); ax.set_ylim(0, 1.6 * rpm / 1e3 * 1.3); ax.grid(alpha=0.3)
        ax.set_title(f"Layout {key[0]}, k = {out['cases'][key]['k']:.2g} N/m", fontsize=9); ax.set_xlabel("rotor speed [krpm]"); ax.set_ylabel("whirl frequency [krpm]")
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("Campbell diagrams (red: forward synchronous critical speeds; grey: 35-105 % speed)", fontsize=10); fig.tight_layout()
    fig.savefig(os.path.join(AXROOT, "plots", "phase4_campbell.png"), dpi=140); plt.close(fig)
    # mode shapes, layout A hard
    fig, axs = plt.subplots(2, 1, figsize=(10, 6.5))
    for ax, key in zip(axs, ("A_hard", "B_hard")):
        rot, info = rm.build(geo, key[0], out["cases"][key]["k"])
        m = lateral_modes(rot, 0.01); x = np.array(info["x_nodes"]) * 1e3; seen = []
        for w, d, v in m:
            if any(abs(w - s) / s < 1e-3 for s in seen): continue
            seen.append(w)
            u = v[0::4][: len(x)]; u = np.real(u * np.exp(-1j * np.angle(u[np.argmax(np.abs(u))]))); u = u / np.max(np.abs(u))
            ax.plot(x, u, label=f"{w / RPM2RAD / 1e3:.1f} krpm (zero speed)")
            if len(seen) == 3: break
        for dd in geo["discs"] + [geo["turbine"]]: ax.axvline(dd["x"] * 1e3, color="0.7", lw=0.8)
        for xb in (info["x_front"], info["x_rear"]): ax.plot(xb * 1e3, 0, "k^", ms=10)
        ax.set_title(f"Layout {key[0]} mode shapes, k = {out['cases'][key]['k']:.2g} N/m (triangles: bearings; grey: discs)", fontsize=9)
        ax.set_xlabel("axial position from compressor front [mm]"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(AXROOT, "plots", "phase4_rotor_modes.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
