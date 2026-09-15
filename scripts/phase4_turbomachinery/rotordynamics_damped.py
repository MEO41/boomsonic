"""Damped critical speeds and API amplification-factor check for soft, damped bearing supports.

rotordynamics.py / rotordynamics_stiffening.py show (undamped) that no combination of bearing stiffness,
shaft OD and drum wall puts every critical outside the 35-105 % range with the worst-case (AF unknown)
margins: on hard supports the rigid-body modes sit in the range, on soft supports the rotor's first
free-free bending mode does (the ~0.4 m rotor is long for the ~28 mm shaft the combustor hub allows).
The API rules exempt a critical whose amplification factor AF < 2.5 ("critically damped"). With rolling
bearings the damping must come from the support: squeeze-film / O-ring damper cartridges (San Andres,
TAMU ME626 Notes 13, 2010: SFDs in aircraft engines supply the damping that rolling bearings lack, the
bearing being elastically supported; Gunter 2023: ball-bearing turbocharger damper cartridge, support
stiffness 10 000 +- 3 000 lb/in = 1.75e6 N/m, damping Cd = 5 lb s/in = 876 N s/m in his stable case).
Method: ROSS matrices (M, K, G, C with the bearing damping c), lateral DOFs, damped eigenvalues vs speed;
a forward mode's damped critical is where omega_d = Omega; its damping ratio zeta there gives
AF = 1 / (2 zeta) (half-power bandwidth of a single mode, the API 684 definition AF = Nc / (N2 - N1)).
Overdamped modes (no oscillatory root) have no critical. Required separation margin (API 684 / 617):
  AF < 2.5: none; 2.5 <= AF <= 3.55: 15 % above MCS, 5 % below minimum operating speed;
  AF > 3.55: above MCS: min(126 - 6/(AF - 3) - 100, 26) %; below minimum speed: min(100 - 84 - 6/(AF - 3), 16) %.
MCS = 105 % of design speed; minimum operating speed = idle 35 %. A critical inside the range with AF >= 2.5 fails.
Output: data/phase4_rotordynamics_damped.csv, plots/phase4_rotor_damped_AF.png  (plot only: python rotordynamics_damped.py --plot)
"""
import os, sys, time, numpy as np, pandas as pd, scipy.linalg as la
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# shared module (cc_rotor.py imports it), but the __main__ study below is the pure-axial rotor: its results live under axial/
AXROOT = os.path.join(ROOT, "axial")
sys.path.insert(0, HERE)
import rotor_model as rm, rotordynamics as rd


class Damped:
    def __init__(self, rot):
        lat = np.array([i for i in range(rot.ndof) if i % 6 in (0, 1, 3, 4)])
        M, K, G, C = (np.asarray(a) for a in (rot.M(), rot.K(0.0), rot.G(), rot.C(0.0)))
        self.Mi = np.linalg.inv(M[np.ix_(lat, lat)]); self.K = K[np.ix_(lat, lat)]; self.G = G[np.ix_(lat, lat)]; self.C = C[np.ix_(lat, lat)]
        self.n = len(lat)

    def forward(self, speed):
        n = self.n
        A = np.block([[np.zeros((n, n)), np.eye(n)], [-self.Mi @ self.K, -self.Mi @ (self.C + speed * self.G)]])
        lam, V = la.eig(A); keep = lam.imag > 1.0
        lam, V = lam[keep], V[:n, keep]; o = np.argsort(lam.imag); lam, V = lam[o], V[:, o]
        X, Y = V[0::4], V[1::4]
        fw = [np.linalg.norm(X[:, j] + 1j * Y[:, j]) > np.linalg.norm(X[:, j] - 1j * Y[:, j]) for j in range(V.shape[1])]
        return [(float(lam[j].imag), float(-lam[j].real / abs(lam[j]))) for j in range(len(lam)) if fw[j]]


def required_sm(AF, above):
    if AF < 2.5: return 0.0
    if AF <= 3.55: return 0.15 if above else 0.05
    return min(126 - 6 / (AF - 3) - 100, 26) / 100 if above else min(100 - 84 - 6 / (AF - 3), 16) / 100


def damped_criticals(rot, rpm_max, n=40):
    d = Damped(rot); sp = np.linspace(0.01, rpm_max, n) * rd.RPM2RAD
    W = np.full((n, 6), np.nan); Z = np.full((n, 6), np.nan)
    for i, s in enumerate(sp):
        f = d.forward(s)[:6]
        for j, (w, z) in enumerate(f): W[i, j], Z[i, j] = w, z
    out = []
    for j in range(6):
        g = W[:, j] - sp
        idx = np.where(np.isfinite(g[:-1]) & np.isfinite(g[1:]) & (np.sign(g[:-1]) != np.sign(g[1:])))[0]
        if len(idx):
            i = idx[0]; a = g[i] / (g[i] - g[i + 1])
            out.append((float(sp[i] + a * (sp[i + 1] - sp[i])), float(Z[i, j] + a * (Z[i + 1, j] - Z[i, j]))))
    return sorted(out)


def assess(crits, rpm):
    mcs, idle = rd.MCS_F * rpm, rd.IDLE * rpm; rows, ok = [], True
    for c, z in crits:
        c_rpm = c / rd.RPM2RAD; AF = 1 / (2 * max(z, 1e-6))
        if c_rpm >= mcs: sm = c_rpm / mcs - 1; req = required_sm(AF, True); p = sm >= req
        elif c_rpm <= idle: sm = 1 - c_rpm / idle; req = required_sm(AF, False); p = sm >= req
        else: sm = np.nan; req = 0.0 if AF < 2.5 else np.inf; p = AF < 2.5
        ok &= p
        rows.append(dict(crit_rpm=round(c_rpm), zeta=round(z, 3), AF=round(AF, 2), sm=sm, sm_req=req, ok=p))
    return rows, ok


def main(trade=None):
    t0 = time.time(); geo = rm.geometry(trade); rpm = geo["rpm"]; res = []
    t_mass = rm.build(geo, "A", 1e7)[1]["t_drum_mass_model_mm"] / 1e3
    designs = [("Phase 3 rotor (16/8 shaft, drum 0.32 mm)", None, 0.016, None), ("drum 2 mm, shaft 24/12", 2e-3, 0.024, 0.016),
               ("drum 2 mm, shaft 28/14", 2e-3, 0.028, 0.016)]
    for lay in ("A", "B"):
        for name, t, od, j in designs:
            for k in (rd.K_SOFT_MIN, rd.K_SOFT, 5e6, rd.K_HARD):
                for c in (0.0, 300.0, 876.0, 2000.0):
                    rot, info = rm.build(geo, lay, k, t_drum=t, shaft_od=od, shaft_id=0.5 * od, journal_od=j, cxx=c)
                    cr = damped_criticals(rot, 1.6 * rpm)
                    rows, ok = assess(cr, rpm)
                    mp = rm.mass_props(rot, geo, info)
                    res.append(dict(layout=lay, design=name, t_drum_mm=(t or t_mass) * 1e3, shaft_od_mm=od * 1e3, k=k, c=c, ok=ok,
                                    crits=";".join(f"{r['crit_rpm']}@AF{r['AF']}" + ("" if r["ok"] else "(X)") for r in rows),
                                    m_rotor_kg=mp["m_rotor_kg"], Ip_kgm2=mp["Ip_kgm2"]))
                    print({kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in res[-1].items()}, flush=True)
        print(f"  layout {lay} done ({time.time()-t0:.0f} s)", flush=True)
    df = pd.DataFrame(res); df.to_csv(os.path.join(AXROOT, "data", "phase4_rotordynamics_damped.csv"), index=False)
    print(f"done in {time.time()-t0:.0f} s")


def plot(rpm=None):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    rpm = rpm or rm.geometry()["rpm"]; mcs, idle = rd.MCS_F * rpm, rd.IDLE * rpm
    df = pd.read_csv(os.path.join(AXROOT, "data", "phase4_rotordynamics_damped.csv"))
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, lay in zip(axs, "AB"):
        for (name, c_), mk in zip([(n, cc) for n in df.design.unique() for cc in (876.0, 2000.0)], ("o", "s", "^", "v", "D", "P")):
            r = df[(df.layout == lay) & (df.design == name) & (df.k == rd.K_SOFT) & (df.c == c_)]
            if r.empty: continue
            pts = [(float(x.split("@AF")[0]), float(x.split("@AF")[1].replace("(X)", ""))) for x in r.crits.iloc[0].split(";")]
            ax.semilogy([p[0] / 1e3 for p in pts], [p[1] for p in pts], mk, ms=7, label=f"{name}, c = {c_:.0f} N s/m" + ("  PASS" if r.ok.iloc[0] else "  fail"))
        ax.axvspan(idle / 1e3, mcs / 1e3, color="0.9", label="operating range 35-105 %")
        ax.axhline(2.5, color="k", ls=":", lw=0.9, label="AF 2.5 (critically damped below)")
        ax.axvline((1 + rd.SM_ABOVE) * mcs / 1e3, color="k", ls="--", lw=0.8, label="MCS + 26 %")
        ax.set_xlabel("damped forward critical speed [krpm]"); ax.set_xlim(0, 1.6 * rpm / 1e3); ax.set_ylim(0.3, 100); ax.grid(alpha=0.3)
        ax.set_title(f"Layout {lay}, support k = {rd.K_SOFT:.3g} N/m", fontsize=9)
    axs[0].set_ylabel("amplification factor AF = 1 / (2 zeta)"); axs[0].legend(fontsize=6.5, loc="upper left")
    fig.suptitle("Damped critical speeds with squeeze-film / O-ring damper supports (API 684 AF rules)", fontsize=10); fig.tight_layout()
    fig.savefig(os.path.join(AXROOT, "plots", "phase4_rotor_damped_AF.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if "--plot" in sys.argv: plot()
    else: main(sys.argv[1] if len(sys.argv) > 1 else None); plot()
