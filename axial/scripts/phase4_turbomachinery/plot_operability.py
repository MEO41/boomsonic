"""Plots for the Phase 4 operability study: stacking map with peak (surge surrogate) and Howell first-row stall
lines, running lines (SLS / dash, remedies, AXI5 bracket) and surge margin vs speed."""
import os, json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
AXROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
TAG = "ax0_opr5_t1150_cap_blk"
L = json.load(open(os.path.join(AXROOT, "data", "phase4", f"comp_lines_{TAG}_nw1.json")))
Wd, PRd = 1.0597, 5.03
rl = pd.read_csv(os.path.join(AXROOT, "data", f"phase4_running_line_{TAG}_nw1.csv"))
nz = pd.concat([pd.read_csv(os.path.join(AXROOT, "data", f)) for f in (f"phase4_nozzle_sweep_{TAG}.csv", f"phase4_nozzle_sweep_{TAG}_1.3-1.6-2.0.csv")])
bl = pd.concat([pd.read_csv(os.path.join(AXROOT, "data", f)) for f in (f"phase4_bleed_sweep_{TAG}.csv", f"phase4_bleed_sweep_{TAG}_0.2-0.3.csv")])
bl = bl[~((bl.case.isin(["SLS_bleed20", "SLS_bleed30"])) & (bl.index < 0))]
ax5 = pd.read_csv(os.path.join(AXROOT, "data", f"phase4_running_line_axi5_{TAG}.csv"))
fig, ax = plt.subplots(1, 2, figsize=(15, 6.2))
a = ax[0]
for l in L:
    W = np.array(l["W"]) / Wd; PR = np.array(l["PR"]); m = (W >= l["W_peak"] / Wd * 0.999)
    a.plot(W[m], PR[m], color="0.6", lw=0.8); a.text(W[m][0], PR[m][0], f"{l['N']:.2f}", fontsize=7, color="0.4")
a.plot([l["W_peak"] / Wd for l in L], [l["PR_peak"] for l in L], "k-", lw=2, label="peak-PR line (surge surrogate)")
hw = [(l["W_howell"] / Wd, l["PR_howell"]) for l in L if np.isfinite(l["W_howell"]) and l["PR_howell"] > 1]
a.plot(*zip(*hw), "r--", lw=1.5, label="first row at Howell stalling deflection")
def rline(df, case, **kw):
    d = df[(df.case == case) & (df.conv)]
    a.plot(d.W_stack / Wd, d.PR_stack, **kw)
rline(rl, "SLS", color="C0", marker="o", ms=3, label="SLS, fixed geometry")
rline(rl, "dash", color="C2", marker="s", ms=3, label="dash M1.02 / 5 km, fixed geometry")
rline(rl, "SLS_VIGV2", color="C4", marker="^", ms=3, label="SLS, variable IGV")
rline(bl, "SLS_bleed30", color="C1", marker="v", ms=3, label="SLS, 30 % bleed after stage 3 (N <= 90 %)")
rline(nz, "SLS_A8x2", color="C5", marker="d", ms=3, label="SLS, nozzle area x2")
a.plot([1.0], [PRd], "k*", ms=12, label="design point (dash)")
a.set_xlabel("corrected flow / design"); a.set_ylabel("compressor pressure ratio"); a.set_xlim(0.1, 1.15); a.set_ylim(1, 6.3)
a.set_title("6-stage axial, stage-stacking map (baseline; remedy lines drawn on it for reference)"); a.legend(fontsize=7, loc="upper left"); a.grid(alpha=0.3)
b = ax[1]
def sm(df, case, col="SM_peak", **kw):
    d = df[(df.case == case) & (df.conv)]
    b.plot(d.N_pct, 100 * d[col], **kw)
sm(rl, "SLS", color="C0", marker="o", label="SLS fixed geometry")
sm(rl, "dash", color="C2", marker="s", label="dash fixed geometry")
sm(rl, "SLS_VIGV2", color="C4", marker="^", label="SLS variable IGV")
sm(bl, "SLS_bleed20", color="C1", marker="v", ls=":", label="SLS 20 % bleed")
sm(bl, "SLS_bleed30", color="C1", marker="v", label="SLS 30 % bleed")
sm(nz, "SLS_A8x1.3", color="C5", marker="d", ls=":", label="SLS nozzle x1.3")
sm(nz, "SLS_A8x2", color="C5", marker="d", label="SLS nozzle x2")
d = ax5[ax5.conv]; b.plot(d.N_pct, d.SMN, "k--", marker="x", label="SLS with NPSS AXI5 map (bracket)")
b.axhline(20, color="r", lw=1); b.text(36, 21, "~20 % recommended (HP compressor)", color="r", fontsize=8)
b.axhline(0, color="k", lw=0.8)
b.set_xlabel("mechanical speed, % of 80 000 rpm"); b.set_ylabel("surge margin at constant corrected speed, %")
b.set_title("Surge margin on the steady running line (points only where a steady match exists)"); b.legend(fontsize=7); b.grid(alpha=0.3); b.set_xlim(30, 102)
fig.tight_layout(); fig.savefig(os.path.join(AXROOT, "plots", "phase4_operability.png"), dpi=130)
print("saved")
