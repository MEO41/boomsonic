"""What rotor stiffness and support stiffness make the pure-axial rotor dynamically acceptable?

rotordynamics.py shows that the rotor as sized for mass in Phase 3 (16/8 mm steel shaft, compressor drum
wall 0.32 mm = engine_mass's 10 % tie allowance smeared into a shell) has shaft-bending critical speeds
inside the 35-105 % operating range at any bearing stiffness. This sweep (layout A: front bearing at the
compressor inlet hub, rear bearing under the NGV, turbine overhung) varies
  support stiffness k: 6e5, 1.75e6 (soft, damped supports - sources in rotordynamics.py), 1.9e7 N/m (hard)
  compressor drum wall t: 0.32 (mass model), 1.0, 2.0, 3.0 mm (Ti-6Al-4V)
  main shaft OD: 16, 20, 24, 28, 32 mm (4340, ID/OD 0.5), bearing journals kept at 16 mm OD (DN 1.28e6)
and applies the rotordynamics.py criteria (API 684 worst-case margins, AF unknown):
  first bending (bearing strain energy < 50 %) forward critical >= 1.26 x MCS;
  every rigid-body critical (bearing energy >= 50 %) <= 0.84 x idle, or >= 1.26 x MCS.
Output: data/phase4_rotordynamics_stiffening.csv, plots/phase4_rotor_stiffening.png
"""
import os, sys, time, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import rotor_model as rm, rotordynamics as rd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt


def evaluate(geo, k, t, od, layout="A", journal=0.016):
    rpm = geo["rpm"]; mcs, idle = rd.MCS_F * rpm, rd.IDLE * rpm
    rot, info = rm.build(geo, layout, k, t_drum=t, shaft_od=od, shaft_id=0.5 * od, journal_od=journal)
    sp, fw, bw = rd.campbell(rot, 2.0 * rpm, n=30)
    cr = rd.forward_criticals(sp, fw); ty = rd.crit_types(rot, info, cr)
    c = [x / rd.RPM2RAD for x in cr]
    rigid = [x for x, e in zip(c, ty) if e >= 0.5]; bend = [x for x, e in zip(c, ty) if e < 0.5]
    b1 = bend[0] if bend else np.inf                                   # > 2 x design speed if none found
    rigid_ok = all(x <= (1 - rd.SM_BELOW) * idle or x >= (1 + rd.SM_ABOVE) * mcs for x in rigid)
    bend_ok = b1 >= (1 + rd.SM_ABOVE) * mcs
    mp = rm.mass_props(rot, geo, info)
    return dict(layout=layout, k=k, t_drum_mm=t * 1e3, shaft_od_mm=od * 1e3, journal_od_mm=journal * 1e3, crits_rpm=[round(x) for x in c[:4]],
                bearing_energy=[round(e, 2) for e in ty[:4]], rigid_rpm=[round(x) for x in rigid], first_bending_rpm=b1,
                rigid_ok=rigid_ok, bending_ok=bend_ok, ok=rigid_ok and bend_ok, m_rotor_kg=mp["m_rotor_kg"], Ip_kgm2=mp["Ip_kgm2"],
                R_front_N_1g=mp["R_front_N_1g"], R_rear_N_1g=mp["R_rear_N_1g"], span_m=info["span"],
                gyro_bearing_load_N_per_radps=mp["Ip_kgm2"] * rpm * rd.RPM2RAD / info["span"])


def main(trade=None):
    t0 = time.time(); geo = rm.geometry(trade); rows = []
    t_mass = rm.build(geo, "A", 1e7)[1]["t_drum_mass_model_mm"] / 1e3
    for k in (rd.K_SOFT_MIN, rd.K_SOFT, rd.K_HARD):
        for t in (t_mass, 1.0e-3, 2.0e-3, 3.0e-3):
            for od in (0.016, 0.020, 0.024, 0.028, 0.032):
                rows.append(evaluate(geo, k, t, od))
        print(f"  k {k:.3g} done ({time.time()-t0:.0f} s)", flush=True)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase4_rotordynamics_stiffening.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(df[["k", "t_drum_mm", "shaft_od_mm", "crits_rpm", "bearing_energy", "first_bending_rpm", "rigid_ok", "bending_ok", "m_rotor_kg", "Ip_kgm2"]].round(4).to_string(index=False))
    rpm = geo["rpm"]
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
    for ax, k in zip(axs, (rd.K_SOFT_MIN, rd.K_SOFT, rd.K_HARD)):
        for t, c in zip(sorted(df.t_drum_mm.unique()), ("#999999", "#1f77b4", "#2ca02c", "#d62728")):
            d = df[(df.k == k) & (df.t_drum_mm == t)]
            y = np.minimum(d.first_bending_rpm.replace(np.inf, 2.0 * rpm), 2.0 * rpm) / 1e3
            ax.plot(d.shaft_od_mm, y, "o-", color=c, label=f"drum wall {t:.2f} mm")
            for _, r in d[d.ok].iterrows(): ax.plot(r.shaft_od_mm, min(r.first_bending_rpm, 2 * rpm) / 1e3, "k*", ms=12)
        ax.axhline((1 + rd.SM_ABOVE) * rd.MCS_F * rpm / 1e3, color="k", ls=":", lw=0.9, label="1.26 x MCS")
        ax.axhspan(rd.IDLE * rpm / 1e3, rd.MCS_F * rpm / 1e3, color="0.9", label="operating range")
        ax.set_title(f"support stiffness {k:.3g} N/m", fontsize=9); ax.set_xlabel("main shaft OD [mm] (journals 16 mm)"); ax.grid(alpha=0.3)
    axs[0].set_ylabel("first bending forward critical [krpm] (capped at 2 x design)"); axs[0].legend(fontsize=7)
    fig.suptitle("Layout A: first bending critical vs shaft OD and drum wall (star: all API worst-case margins met)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase4_rotor_stiffening.png"), dpi=140); plt.close(fig)
    print(f"done in {time.time()-t0:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
