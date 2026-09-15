"""Phase 7 step 1: afterburner design-point study at the frozen dash point (M 1.02 / 5 km).

The core is held exactly at its frozen fielded operating point (design_freeze.md section 1.1)
and only the afterburner and the nozzle throat move.  Three questions:

  1. How hot?          T7 sweep -> thrust, TSFC, required A8, and where the FAR runs out.
  2. How fast a duct?  AB-duct Mach sweep -> duct diameter against Rayleigh loss and against
                       THERMAL CHOKING, which is a hard limit, not a preference.
  3. How much of it is the AB combustion-efficiency assumption?  eta_AB sensitivity.

Outputs: data/phase7/ab_design_point.csv, ab_duct_mach.csv, ab_eta_sensitivity.csv,
         ab_design_point.json, plots/phase7_ab_design_point.png
Usage:   .venv\\Scripts\\python scripts\\phase7_afterburner\\ab_design_point.py
"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("OPENMDAO_REPORTS", "0")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ab_common as ac

ac.ensure_dirs()
fz = ac.frozen_cycle()
GAM = ac.GAMMA_AB


def duct_geometry(T7, M_in):
    """AB duct area and diameter at the AB face (before heat addition), and at the AB exit."""
    W5 = fz["W_kgps"] * (1 + fz["FAR"])
    Pt5, Tt5 = fz["Pt5_kPa"] * 1e3, fz["Tt5_K"]
    R = 287.8                                    # J/kg/K for the vitiated stream, tabular value at station 5
    A_in = ac.duct_area(W5, Tt5, Pt5, M_in, GAM, R)
    return dict(A_in_cm2=A_in * 1e4, D_in_mm=np.sqrt(4 * A_in / np.pi) * 1e3)


def sweep_T7():
    rows = []
    dry = ac.design_point(T7=None)
    rows.append(dict(T7_K=dry["Tt5_K"], ab=False, **_row(dry, dry)))
    for T7 in [1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200]:
        r = ac.design_point(T7=T7)
        rows.append(dict(T7_K=T7, ab=True, **_row(r, dry)))
    return pd.DataFrame(rows), dry


def _row(r, dry):
    return dict(FAR_ab=r.get("FAR_ab", 0.0), FAR_total=r.get("FAR_total", r["FAR"]),
                over_table=bool(r.get("FAR_total", r["FAR"]) > ac.FAR_TABLE_MAX),
                phi_total=r.get("FAR_total", r["FAR"]) / ac.FAR_STOICH_JETA,
                dPqP=r["loss"]["dPqP"], dPqP_rayleigh=r["loss"]["rayleigh"],
                Pt7_kPa=r.get("Pt7_kPa", r["Pt5_kPa"]), NPR=r["NPR"], Vj_mps=r["Vj_mps"],
                Fn_N=r["Fn_N"], Fn_ratio=r["Fn_N"] / dry["Fn_N"], Fg_N=r["Fg_N"],
                Wf_kgps=r["Wf_kgps"], Wf_ab_kgps=r.get("Wf_ab_kgps", 0.0),
                TSFC_kgpNh=r["TSFC_kgpNh"], TSFC_ratio=r["TSFC_kgpNh"] / dry["TSFC_kgpNh"],
                A8_cm2=r["A8_cm2"], A8_ratio=r["A8_cm2"] / dry["A8_cm2"],
                D8_mm=np.sqrt(4 * r["A8_cm2"] * 1e-4 / np.pi) * 1e3, res=r["res"])


def sweep_duct_mach():
    """Thermal choking is the constraint that decides the AB duct Mach, and it is computed."""
    rows = []
    for M in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.375, 0.40, 0.45]:
        loss = ac.ab_dPqP(ac.T7_DESIGN, M, Tt_in=fz["Tt5_K"])
        tau_max = 1.0 / ac.rayleigh_T0_ratio(M, GAM)       # Tt ratio that drives the duct to M = 1
        geo = duct_geometry(ac.T7_DESIGN, M)
        row = dict(M_ab=M, tau_required=loss["tau"], tau_choke=tau_max,
                   T7_choke_K=tau_max * fz["Tt5_K"], choke_margin=tau_max / loss["tau"] - 1,
                   thermally_choked=loss["thermally_choked"],
                   dPqP_rayleigh=loss["rayleigh"], dPqP_total=loss["dPqP"], M_out=loss["M_out"], **geo)
        if not loss["thermally_choked"]:
            r = ac.design_point(T7=ac.T7_DESIGN, ab_MN=M)
            row.update(Fn_N=r["Fn_N"], TSFC_kgpNh=r["TSFC_kgpNh"], A8_cm2=r["A8_cm2"], Pt7_kPa=r["Pt7_kPa"])
        else:
            row.update(Fn_N=np.nan, TSFC_kgpNh=np.nan, A8_cm2=np.nan, Pt7_kPa=np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


def sweep_eta_ab():
    rows = []
    for eta in (0.75, 0.80, 0.85, 0.90, 0.95):
        r = ac.design_point(T7=ac.T7_DESIGN, eta_ab=eta)
        rows.append(dict(eta_ab=eta, Fn_N=r["Fn_N"], Wf_kgps=r["Wf_kgps"], Wf_ab_kgps=r["Wf_ab_kgps"],
                         TSFC_kgpNh=r["TSFC_kgpNh"]))
    return pd.DataFrame(rows)


def plot(df, dm, dry):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    w = df[df.ab]
    fig, ax = plt.subplots(2, 2, figsize=(11.5, 8.2))

    a = ax[0, 0]
    ok = w[~w.over_table]; bad = w[w.over_table]
    a.plot(ok.T7_K, ok.Fn_N, "o-", color="tab:red", label="net thrust")
    a.plot(bad.T7_K, bad.Fn_N, "o--", color="tab:red", mfc="none", label="beyond the thermo table")
    a.axhline(dry["Fn_N"], ls=":", color="k", label="dry, 500 N")
    a.axvline(ac.T7_DESIGN, ls="-.", color="tab:blue", lw=1, label="chosen T7 %.0f K" % ac.T7_DESIGN)
    a.set_xlabel("afterburner exit total temperature $T_{t7}$ [K]"); a.set_ylabel("net thrust [N]")
    a.set_title("Thrust at the dash point (core frozen, A8 free)", fontsize=9)
    a.legend(fontsize=7); a.grid(alpha=.3)

    a = ax[0, 1]
    a.plot(ok.Fn_N, ok.TSFC_kgpNh, "o-", color="tab:purple")
    a.plot(bad.Fn_N, bad.TSFC_kgpNh, "o--", color="tab:purple", mfc="none")
    a.plot([dry["Fn_N"]], [dry["TSFC_kgpNh"]], "ks", label="dry")
    for _, r in w.iterrows():
        if int(r.T7_K) % 200 == 0:
            a.annotate("%.0f K" % r.T7_K, (r.Fn_N, r.TSFC_kgpNh), fontsize=6, xytext=(3, -8), textcoords="offset points")
    a.set_xlabel("net thrust [N]"); a.set_ylabel("TSFC [kg/(N h)]")
    a.set_title("What the thrust costs", fontsize=9); a.legend(fontsize=7); a.grid(alpha=.3)

    a = ax[1, 0]
    a.plot(w.T7_K, w.A8_ratio, "o-", color="tab:green")
    a.axhline(1.0, ls=":", color="k")
    a.axvline(ac.T7_DESIGN, ls="-.", color="tab:blue", lw=1)
    a2 = a.twinx(); a2.plot(w.T7_K, w.D8_mm, "s--", color="tab:olive", ms=3)
    a2.set_ylabel("throat diameter $D_8$ [mm]", color="tab:olive")
    a.set_xlabel("$T_{t7}$ [K]"); a.set_ylabel("$A_8 / A_{8,dry}$", color="tab:green")
    a.set_title("The nozzle has to open by this much", fontsize=9); a.grid(alpha=.3)

    a = ax[1, 1]
    good = dm[~dm.thermally_choked]
    a.plot(dm.M_ab, dm.T7_choke_K, "o-", color="tab:red", label="thermal-choking limit on $T_{t7}$")
    a.axhline(ac.T7_DESIGN, ls="-.", color="tab:blue", lw=1, label="required $T_{t7}$ %.0f K" % ac.T7_DESIGN)
    a.fill_between(dm.M_ab, ac.T7_DESIGN, dm.T7_choke_K, where=dm.T7_choke_K < ac.T7_DESIGN,
                   color="tab:red", alpha=.15)
    a3 = a.twinx(); a3.plot(good.M_ab, 100 * good.dPqP_rayleigh, "s--", color="tab:gray", ms=3)
    a3.set_ylabel("Rayleigh loss [% of $P_t$]", color="tab:gray")
    a.set_xlabel("afterburner-duct Mach number"); a.set_ylabel("$T_{t7}$ [K]")
    a.set_title("Duct Mach: thermal choking sets the ceiling", fontsize=9)
    a.legend(fontsize=7); a.grid(alpha=.3)

    fig.suptitle("Phase 7 afterburner design point: frozen centrifugal core, M 1.02 / 5 km ISA "
                 "($\\eta_{AB}$ %.2f, dry loss %.0f %%, Rayleigh computed)" % (ac.ETA_AB, 100 * ac.AB_DRY_DPQP), fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(ac.PLOTS, "phase7_ab_design_point.png")
    fig.savefig(out, dpi=150); print("wrote", out)


if __name__ == "__main__":
    df, dry = sweep_T7()
    dm = sweep_duct_mach()
    de = sweep_eta_ab()

    pd.set_option("display.width", 200, "display.max_columns", 50)
    print("=" * 120)
    print("1. AB exit temperature sweep (AB duct Mach %.2f, eta_AB %.2f)" % (ac.AB_MN, ac.ETA_AB))
    print("=" * 120)
    print(df[["T7_K", "FAR_ab", "FAR_total", "phi_total", "over_table", "dPqP", "Pt7_kPa", "Vj_mps",
              "Fn_N", "Fn_ratio", "Wf_kgps", "TSFC_kgpNh", "TSFC_ratio", "A8_cm2", "A8_ratio", "D8_mm"]]
          .to_string(index=False, float_format=lambda v: "%.4f" % v))

    print()
    print("=" * 120)
    print("2. AB duct Mach: thermal choking, Rayleigh loss and duct size at T7 = %.0f K" % ac.T7_DESIGN)
    print("=" * 120)
    print(dm[["M_ab", "D_in_mm", "A_in_cm2", "tau_required", "tau_choke", "T7_choke_K", "choke_margin",
              "dPqP_rayleigh", "dPqP_total", "M_out", "Fn_N", "TSFC_kgpNh"]]
          .to_string(index=False, float_format=lambda v: "%.4f" % v))

    print()
    print("=" * 120)
    print("3. Sensitivity to the AB combustion-efficiency assumption at T7 = %.0f K" % ac.T7_DESIGN)
    print("=" * 120)
    print(de.to_string(index=False, float_format=lambda v: "%.4f" % v))

    df.to_csv(os.path.join(ac.D7, "ab_design_point.csv"), index=False)
    dm.to_csv(os.path.join(ac.D7, "ab_duct_mach.csv"), index=False)
    de.to_csv(os.path.join(ac.D7, "ab_eta_sensitivity.csv"), index=False)

    chosen = df[(df.ab) & (df.T7_K == ac.T7_DESIGN)].iloc[0].to_dict()
    geo = duct_geometry(ac.T7_DESIGN, ac.AB_MN)
    summary = dict(tag=ac.TAG, T7_design_K=ac.T7_DESIGN, ab_MN=ac.AB_MN, eta_ab=ac.ETA_AB,
                   dry_dPqP=ac.AB_DRY_DPQP, dry=dict(Fn_N=dry["Fn_N"], TSFC_kgpNh=dry["TSFC_kgpNh"],
                                                     A8_cm2=dry["A8_cm2"], Tt5_K=dry["Tt5_K"], Pt5_kPa=dry["Pt5_kPa"]),
                   wet={k: (float(v) if isinstance(v, (int, float, np.floating)) else bool(v)) for k, v in chosen.items()},
                   duct=geo, far_table_max=ac.FAR_TABLE_MAX, far_stoich=ac.FAR_STOICH_JETA)
    json.dump(summary, open(os.path.join(ac.D7, "ab_design_point.json"), "w"), indent=1)

    print()
    print("AB duct at Mach %.2f: face area %.1f cm2, diameter %.1f mm  (engine OD %.1f mm, turbine OD %.1f mm)"
          % (ac.AB_MN, geo["A_in_cm2"], geo["D_in_mm"], ac.frozen_engine()["D_engine_mm"],
             ac.frozen_engine()["D_breakdown"]["turbine"]))
    plot(df, dm, dry)
