"""Phase 3R figures (run in .venv):
  plots/phase3r_backsweep.png : why the exit backsweep is -15 deg (OPR 4, 75 000 rpm, fielded level)
     (a) TurboFlow 100 % speed lines of the 0 / -10 / -15 / -20 deg impellers (normalised to the design point):
         backsweep makes the pressure-ratio characteristic fall with flow, which moves its peak (the surge surrogate)
         to lower flow
     (b) design-point surge margin and pessimistic dash thrust margin vs backsweep, with the two criteria
     (c) surge margin along the sea-level-static running line
  plots/phase3r_mission.png   : max-thrust deck, SLS running line and the sortie of the recommended engine
Usage: python plot_phase3r.py [recommended tag]
"""
import os, sys, json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MAPS = os.path.join(ROOT, "data", "phase3r", "maps")
REC = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"
BETAS = (0, 10, 15, 20)
COL = {0: "tab:grey", 10: "tab:orange", 15: "tab:green", 20: "tab:blue"}

def line(tag, N=1.0):
    m = json.load(open(os.path.join(MAPS, f"centrifugal_map_{tag}.json"))); Wd = m["design"]["mdot"]
    q = sorted([p for p in m["points"] if p.get("success") and abs(p["N"] - N) < 1e-6 and not p.get("choked")], key=lambda p: p["mdot"])
    W = np.array([p["mdot"] for p in q]); PR = np.array([p["PR"] for p in q])
    PRd = float(np.interp(Wd, W, PR)); i = int(np.argmax(PR))
    return W / Wd, PR / PRd, 100 * ((PR[i] / W[i]) / (PRd / Wd) - 1)

tr = pd.read_csv(os.path.join(ROOT, "data", "phase3r_cc_trade.csv")); tr = tr[(tr.level == "fielded") & (tr.OPR == 4.0) & (tr.rpm == 75000)]
fig, ax = plt.subplots(1, 3, figsize=(17, 4.8))
smn = {}
for b in BETAS:
    tag = f"ce75000_opr4_t1150_b{b}_cap"
    if not os.path.exists(os.path.join(MAPS, f"centrifugal_map_{tag}.json")): continue
    x, y, s = line(tag); smn[b] = s
    ax[0].plot(x, y, "-o", ms=3, c=COL[b], label=f"{b} deg backsweep: design SMN {s:.0f} %")
    i = int(np.argmax(y)); ax[0].plot(x[i], y[i], "*", ms=12, c=COL[b])
    f = os.path.join(ROOT, "data", f"phase3r_mission_{tag}_running_lines.csv")
    if os.path.exists(f):
        rl = pd.read_csv(f); rl = rl[(rl.case == "SLS") & rl.conv]
        ax[2].plot(rl.N_pct, 100 * rl.SMN, "-o", ms=3, c=COL[b], label=f"{b} deg")
    else:
        j = os.path.join(ROOT, "data", f"phase3r_mission_{tag}_lines.json")
ax[0].axvline(1.0, c="k", lw=0.8, ls=":"); ax[0].set_xlabel("W / W_design (100 % speed)"); ax[0].set_ylabel("PR / PR_design")
ax[0].set_title("(a) 100 % speed line; star = peak (surge surrogate)", fontsize=9); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
bs = sorted(smn); ax[1].plot(bs, [smn[b] for b in bs], "-o", c="tab:purple", label="design-point surge margin SMN")
t = tr.sort_values("beta2b"); ax[1].plot(-t.beta2b, 100 * t.margin_hi, "-s", c="tab:red", label="dash thrust margin, pessimistic drag")
ax[1].plot(-t.beta2b, 100 * t.worst_corner, "--s", c="tab:red", alpha=.5, label="thrust margin, worst corner")
ax[1].axhline(20, c="tab:purple", ls=":", lw=1); ax[1].axhline(25, c="tab:red", ls=":", lw=1)
ax[1].axvspan(10.5, 19, color="tab:green", alpha=.12, label="window: SMN >= 20 % and margin >= 25 %")
ax[1].set_xlabel("exit backsweep [deg]"); ax[1].set_ylabel("[%]"); ax[1].set_title("(b) stability vs thrust margin (OPR 4, 75k, fielded)", fontsize=9)
ax[1].legend(fontsize=7); ax[1].grid(alpha=.3)
ax[2].axhline(20, c="k", ls=":", lw=1); ax[2].set_xlabel("mechanical speed [%]"); ax[2].set_ylabel("surge margin SMN [%]")
ax[2].set_title("(c) sea-level-static running line", fontsize=9); ax[2].legend(fontsize=8); ax[2].grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase3r_backsweep.png"), dpi=130)

mf = os.path.join(ROOT, "data", f"phase3r_mission_{REC}.json")
if os.path.exists(mf):
    dk = pd.read_csv(os.path.join(ROOT, "data", f"phase3r_mission_{REC}_deck.csv"))
    rl = pd.read_csv(os.path.join(ROOT, "data", f"phase3r_mission_{REC}_running_lines.csv"))
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.8))
    for h, g in dk.groupby("alt_m"):
        ax[0].plot(g.MN, g.Fn_N, "-o", ms=3, label=f"{h/1000:g} km")
    ax[0].set_xlabel("Mach"); ax[0].set_ylabel("max thrust [N] (min of 100 % speed, T4 1150 K)"); ax[0].legend(fontsize=7, ncol=2); ax[0].grid(alpha=.3)
    ax[0].set_title("(a) max-thrust deck, real maps", fontsize=9)
    s = rl[(rl.case == "SLS") & rl.conv]
    ax[1].plot(s.N_pct, s.Fn_N, "-o", ms=3, c="k", label="thrust [N]"); a2 = ax[1].twinx()
    a2.plot(s.N_pct, s.Tt4_K, "-s", ms=3, c="tab:red", label="T4 [K]"); a2.plot(s.N_pct, s.Tt5_K - 273.15, "-^", ms=3, c="tab:orange", label="EGT [C]")
    ax[1].set_xlabel("mechanical speed [%]"); ax[1].set_ylabel("SLS thrust [N]"); a2.set_ylabel("T4 [K] / EGT [C]")
    ax[1].set_title("(b) sea-level-static running line", fontsize=9); ax[1].grid(alpha=.3); a2.legend(fontsize=7, loc="center right")
    seg = pd.read_csv(os.path.join(ROOT, "data", f"phase3r_mission_{REC}_segments_nom.csv"))
    ax[2].barh(seg.segment, seg.time_s, color="tab:blue", alpha=.7); ax[2].set_xlabel("time [s]")
    for i, r in enumerate(seg.itertuples()):
        ax[2].text(r.time_s, i, f" {r.fuel_kg:.2f} kg" + (f", min excess {r.excess_min_N:.0f} N" if np.isfinite(r.excess_min_N) else ""), va="center", fontsize=7)
    ax[2].set_title("(c) sortie, nominal wave drag", fontsize=9); ax[2].invert_yaxis()
    fig.suptitle(f"Phase 3R recommended engine {REC}: off-design with the TurboFlow compressor and turbine maps", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase3r_mission.png"), dpi=130)
print("saved")
