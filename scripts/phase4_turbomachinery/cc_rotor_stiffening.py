"""Phase 4 (centrifugal baseline): what moves the rotor's first bending critical out of the operating range?

cc_rotor.py shows the first shaft-bending mode (bearing strain energy ~4 %, so support dampers cannot reach it) at
38-57 krpm for solid-ish shafts of 16-28 mm (ID/OD 0.5), inside the 35-105 % range (26-79 krpm) with AF 5-20.
Levers swept here, all on damped soft supports (k 1.75e6 N/m, c 876 N s/m, Gunter 2023) with the API AF rules:
  * shaft tube OD 24 / 28 / 32 mm (the combustor inner radius, 20.9 mm, bounds the tunnel), ID/OD 0.5 / 0.8
    (a thin-walled tube has more EI per unit mass);
  * bearing journals 12 / 15 mm (DN at MCS 0.95e6 / 1.18e6);
  * impeller back-face boss A/r2 0.3 (lowest stress) / 0.1 (lighter, shorter overhang) -> its disc stress is reported;
  * combustor liner length x 1.0 / 0.85 / 0.7 of the Phase 3 rule (3 x annulus height), i.e. the bearing span.
Output: data/phase4r_rotor_stiffening.csv
"""
import os, sys, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
tag = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"; sys.argv = [sys.argv[0], tag]
import cc_rotor as cr, rotordynamics as rd, rotordynamics_damped as rdd

rows = []
geos = {(A, lf): cr.geometry(tag, A_over_r2=A, liner_factor=lf) for A in (0.3, 0.1) for lf in (1.0, 0.85, 0.7)}
for (A, lf), geo in geos.items():
    rpm = geo["rpm"]
    for od, idr, jod in itertools.product((0.024, 0.028, 0.032), (0.5, 0.8), (0.012, 0.015)):
        rot, info = cr.build(geo, cr.K_SOFT, c=cr.C_GUNTER, shaft_od=od, id_ratio=idr, journal_od=jod)
        crit = rdd.damped_criticals(rot, 1.8 * rpm, n=45); res, ok = rdd.assess(crit, rpm)
        rot0, info0 = cr.build(geo, cr.K_SOFT, shaft_od=od, id_ratio=idr, journal_od=jod)
        sp, fw, bw = rd.campbell(rot0, 2.2 * rpm, n=30); cu = rd.forward_criticals(sp, fw)
        ty = [rd.bearing_energy_share(rot0, info0, min([(w, v) for w, d_, v in rd.lateral_modes(rot0, c) if d_ == "Forward"], key=lambda t: abs(t[0] - c))[1]) for c in cu]
        bend = [c / rd.RPM2RAD for c, e in zip(cu, ty) if e < 0.5]
        mp = cr.mass_props(rot0, geo, info0)
        rows.append(dict(A_over_r2=A, liner_factor=lf, span_mm=info["span"] * 1e3, shaft_od_mm=od * 1e3, id_ratio=idr, journal_mm=jod * 1e3,
                         DN_MCS=jod * 1e3 * rpm * rd.MCS_F, bend1_undamped_rpm=bend[0] if bend else np.nan, bend1_over_MCS=(bend[0] / (rd.MCS_F * rpm)) if bend else np.nan,
                         damped_crits=[(r["crit_rpm"], r["AF"]) for r in res], api_ok=ok, m_rotor=mp["m_rotor_kg"], Ip=mp["Ip_kgm2"],
                         imp_mass=geo["imp"]["m"], imp_disc_vm_MCS=geo["impeller_hub_stress"]["vm_mech_MCS_MPa"], imp_burst_MCS=geo["impeller_hub_stress"]["burst_MCS"]))
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items() if k not in ("damped_crits",)}, rows[-1]["damped_crits"], flush=True)
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase4r_rotor_stiffening.csv"), index=False)
pd.set_option("display.width", 250); print(df.drop(columns=["damped_crits"]).round(3).to_string(index=False))
