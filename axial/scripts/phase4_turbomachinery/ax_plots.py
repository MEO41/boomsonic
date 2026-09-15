"""Phase 4A plots of the refreshed axial (run in .venv).
  plots/phase4a_operability.png : SLS and dash steady lines of the final variable-geometry configuration
  plots/phase4a_blade_campbell.png : blade 1F / 2F vs speed with the low engine orders (ax_rotor_stress.py)
Usage: python ax_plots.py <tag>
"""
import os, sys, json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
TAG = sys.argv[1]; OUT = os.path.join(AXROOT, "data", "phase4ax"); PL = os.path.join(AXROOT, "plots")

d = pd.read_csv(os.path.join(OUT, f"operability_{TAG}_final.csv")); d = d[d.conv.astype(str) == "True"]
fig, ax = plt.subplots(2, 2, figsize=(11, 7.5), sharex=True)
for case, col, lab in (("final_SLS", "C0", "SLS"), ("final_dash", "C3", "M 1.02 / 5 km")):
    q = d[d.case == case].sort_values("N_pct"); ok = q[q.ok.astype(str) == "True"]
    for a, k, sc in ((ax[0, 0], "Fn_N", 1), (ax[0, 1], "Tt4_K", 1), (ax[1, 0], "SM_peak", 100), (ax[1, 1], "stall_index", 1)):
        a.plot(q.N_pct, q[k] * sc, "-", color=col, alpha=0.5, label=lab); a.plot(ok.N_pct, ok[k] * sc, "o", color=col, ms=4)
ax[0, 0].set_ylabel("net thrust [N]"); ax[0, 1].set_ylabel("T4 [K]"); ax[1, 0].set_ylabel("SM to stacking peak line [%]"); ax[1, 1].set_ylabel("max row stall index [-]")
ax[0, 1].axhline(1150, color="k", ls="--", lw=0.8); ax[1, 0].axhline(10, color="k", ls="--", lw=0.8); ax[1, 1].axhline(1.0, color="k", ls="--", lw=0.8)
for a in ax.ravel():
    a.axvline(77.5, color="g", ls=":", lw=1); a.grid(alpha=0.3)
for a in ax[1]: a.set_xlabel("mechanical speed [% of 80 000 rpm]")
ax[0, 0].legend(title="filled = acceptable")
fig.suptitle("Phase 4A axial: final variable geometry (VIGV 15 deg closure, 10 % bleed after stage 3 below 95 %, nozzle to 2.0 x A8 by 80 %)\n"
             "idle 77.5 % (green); stacking model unvalidated (R4.1)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(PL, "phase4a_operability.png"), dpi=130); plt.close(fig)

rs = json.load(open(os.path.join(OUT, f"rotor_stress_{TAG}.json")))
# 1F against speed: Southwell form f^2 = f0^2 + K (N)^2 through the FE static and 100 % values (the FE itself is only
# stored at those two speeds; the crossings quoted in the report are the FE values, this curve is within ~0.5 pt of them)
bl = rs["blades"]; fig, a = plt.subplots(figsize=(9, 6)); N = np.linspace(0, 1.05, 80); rpm = rs["rpm"]
for b in bl:
    f0, f1 = b["f1_static_Hz"], b["f1_100_Hz"]
    a.plot(100 * N, np.sqrt(f0**2 + (f1**2 - f0**2) * N**2), color=f"C{b['stage']-1}", label=f"stage {b['stage']} 1F")
for E in (1, 2, 3, 4):
    a.plot(100 * N, E * N * rpm / 60, "k-", lw=0.7); a.text(105.5, E * 1.05 * rpm / 60, f"{E}E", fontsize=8, va="center")
a.axvspan(77.5, 100, color="g", alpha=0.08); a.set_xlabel("speed [% of 80 000 rpm]"); a.set_ylabel("frequency [Hz]"); a.set_ylim(0, None); a.set_xlim(0, 108)
a.grid(alpha=0.3); a.legend(fontsize=8, ncol=2)
a.set_title("Phase 4A axial compressor blades: first flap mode vs low engine orders (shaded = idle 77.5 % to 100 %)\n"
            "Southwell interpolation of the verified rotating-beam FE (static and 100 %); no damping / forced response", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(PL, "phase4a_blade_campbell.png"), dpi=130); plt.close(fig)
print("written plots/phase4a_operability.png, plots/phase4a_blade_campbell.png")
