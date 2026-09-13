"""Phase 3: compile the architecture trade (all OPR runs), apply the mass-model validation calibration,
and produce the side-by-side comparison. Outputs data/phase3_arch_trade_summary.csv,
plots/phase3_arch_trade.png

Mass calibration (validate_mass_model.py): the bottom-up model under-predicts JetCat P400-PRO by
14 % (incl. its integrated ECU/pump) and AMT Nike by 24 % (engine only) -> calibrated dry mass =
bottom-up x 1.24 (range x1.16 .. x1.31). Length: x1.22 (both engines under-predicted by 18 %).
Diameter: not calibrated (145 vs 148 mm and 203 vs 201 mm).
TOGW = calibrated engine + accessories 1.60 kg (Phase 2, AMT system data) + airframe/systems with
15 % growth (Phase 2 bottom-up re-evaluated at the new fuselage diameter) + sortie fuel.
"""
import glob, os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
K_M, K_M_LO, K_M_HI, K_L = 1.24, 1.16, 1.31, 1.22
frames = []
for f in glob.glob(os.path.join(ROOT, "data", "phase3_arch_trade_opr*_t*.csv")):
    import re
    mm = re.search(r"_opr([\d.]+)_t(\d+)(_cap)?\.csv", os.path.basename(f))
    d = pd.read_csv(f); d["OPR"] = float(mm.group(1)); d["T4"] = float(mm.group(2)); d["turbine_cap"] = bool(mm.group(3))
    d = d[d.get("note").isna()] if "note" in d.columns else d
    frames.append(d)
df = pd.concat(frames, ignore_index=True)
df["dry_mass_cal"] = df.dry_mass_kg * K_M; df["dry_mass_cal_lo"] = df.dry_mass_kg * K_M_LO; df["dry_mass_cal_hi"] = df.dry_mass_kg * K_M_HI
df["L_engine_cal"] = df.L_engine_mm * K_L
df["TOGW_cal"] = df.TOGW - df.dry_mass_kg + df.dry_mass_cal
df["TOGW_cal_hi"] = df.TOGW - df.dry_mass_kg + df.dry_mass_cal_hi
df["margin_nom_ok"] = df.margin_nom >= 0.25; df["margin_hi_ok"] = df.margin_hi >= 0.25
df["label"] = df.apply(lambda r: f"{'CENTRIF' if r.arch == 'centrifugal' else 'AXIAL'} OPR {r.OPR:g} {int(r.rpm/1000)}k{' capT' if r.turbine_cap else ''}", axis=1)
df = df.sort_values(["level", "arch", "OPR", "rpm", "turbine_cap"])
cols = ["label", "level", "eta_c", "eta_t", "W", "TSFC_dash", "D_engine_mm", "D_comp", "D_comb", "D_turb", "D_engine_comb_hi_mm", "L_engine_cal",
        "dry_mass_kg", "dry_mass_cal", "dry_mass_cal_hi", "CDS_nom", "CDS_hi", "drag_nom", "drag_hi", "margin_nom", "margin_hi", "TOGW_cal", "TOGW_cal_hi"]
df[cols].to_csv(os.path.join(ROOT, "data", "phase3_arch_trade_summary.csv"), index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
print(df[cols].round(3).to_string(index=False))

fig, ax = plt.subplots(1, 4, figsize=(18, 4.8))
for a, (col, lab) in zip(ax, [("D_engine_mm", "engine OD [mm]"), ("dry_mass_cal", "engine dry mass, calibrated [kg]"),
                              ("margin_nom", "dash thrust margin, nominal drag"), ("margin_hi", "dash thrust margin, pessimistic drag")]):
    for i, (lvl, g) in enumerate(df.groupby("level")):
        x = np.arange(len(g)) + (i - 0.5) * 0.38
        a.bar(x, g[col] * (100 if "margin" in col else 1), width=0.38, label=lvl, color="tab:blue" if lvl == "tool" else "tab:red", alpha=.8)
        if col == "dry_mass_cal":
            a.errorbar(x, g[col], yerr=[g[col] - g.dry_mass_cal_lo, g.dry_mass_cal_hi - g[col]], fmt="none", ecolor="k", capsize=2)
        labels = list(g.label)
    a.set_xticks(np.arange(len(labels))); a.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    a.set_ylabel(lab + (" [%]" if "margin" in col else "")); a.grid(alpha=.3, axis="y")
    if "margin" in col: a.axhline(25, c="k", ls="--", lw=1)
ax[0].legend(fontsize=8)
fig.suptitle("Phase 3 architecture trade at the dash (Fn 500 N, M1.02 / 5 km, T4 1150 K): tool-predicted vs fielded component efficiency", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase3_arch_trade.png"), dpi=130)
print("saved")
