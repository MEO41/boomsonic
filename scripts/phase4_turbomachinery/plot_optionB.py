"""Surge margin on the SLS / dash steady running lines: pure axial (option A), axial-centrifugal (option B, 2 and 1 axial
stages, base and larger-throat impeller) and the method benchmark on the JetCat P400 model."""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = lambda f: pd.read_csv(os.path.join(ROOT, "data", f))
fig, ax = plt.subplots(1, 2, figsize=(14, 5.5))
for a, case in zip(ax, ("SLS", "dash")):
    def pl(df, lab, **kw):
        d = df[(df.case == case) & (df.conv)] if "case" in df else df[df.conv]
        a.plot(d.N_pct, 100 * d.SM_peak, label=lab, **kw)
    pl(D("phase4_running_line_ax0_opr5_t1150_cap_blk_nw1.csv"), "A: pure axial 6 st OPR 5", color="C0", marker="o")
    pl(D("phase4_running_line_ax90000_opr4_t1150_ax2_pa2_cap_blk.csv"), "B: 2 ax + cc (as designed)", color="C1", marker="s")
    pl(D("phase4_running_line_ax90000_opr4_t1150_ax2_pa2_cap_blk_cc_atr080.csv"), "B: 2 ax + cc, impeller throat 0.80", color="C1", marker="s", ls="--")
    pl(D("phase4_running_line_ax90000_opr4_t1150_ax1_pa1.5_cap_blk.csv"), "B: 1 ax + cc (as designed)", color="C3", marker="^")
    if case == "SLS":
        b = D("phase4_benchmark_P400.csv"); b = b[b.conv]
        a.plot(b.N_pct, 100 * b.SM_peak, "k-", marker="x", label="benchmark: JetCat P400 model (idles at 31 %)")
        a.axvline(31, color="k", ls=":", lw=1); a.text(31.5, 2, "P400 published idle", fontsize=8)
    a.axhline(20, color="r", lw=1); a.axhline(0, color="k", lw=0.8)
    a.set_xlim(28, 102); a.set_ylim(-2, 56); a.grid(alpha=0.3)
    a.set_xlabel("mechanical speed, % of design"); a.set_ylabel("surge margin to peak-PR line, % (constant speed)")
    a.set_title(f"{case} steady running line (points only where a steady match exists)", fontsize=10)
ax[0].legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase4_optionB_operability.png"), dpi=130); print("saved")
