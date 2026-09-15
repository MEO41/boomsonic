"""Phase 4A: rotor dynamics of the refreshed pure axial (run in .venv; ROSS via ross_shim, verified in Phase 4).

The Phase 4 rotor study (docs/phase4_rotordynamics.md, D4.R2) was done on the Phase 3 geometry; it needs soft damped
supports plus a stiffened rotor (layout A, 2 mm Ti drum, 24 / 12 mm shaft, 16 mm journals). This re-runs the same
verified model (rotor_model.py + rotordynamics_damped.py, unchanged) on the 3A-R geometry:
  * the refreshed design is written as a Phase-3-style trade file (case.comp / case.turb / case.cycle = the fielded
    blading, turbine and cycle, so rotor_model's sqrt(W) scale is exactly 1; eval = the fielded evaluation);
  * minimum operating speed = the axial idle from the operability study (argument, % of design speed) instead of 35 %;
  * a sweep of drum wall, shaft OD, journal OD and damper damping over the Phase 4 ranges; bearing DN reported
    (Phase 4 risk R4.R2: 16 mm journals at 80 krpm = 1.28e6 against the ~1e6 micro gas turbine reference).
Usage: python ax_rotor.py <tag> <idle_pct>      output data/phase4ax/rotor_<tag>.csv / .json
"""
import os, sys, json, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE)
TAG = sys.argv[1]; IDLE = float(sys.argv[2]) / 100
AX = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"axt_{TAG}.json"))); F = AX["levels"]["fielded"]
turb = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"{TAG}_ttf_out.json")))
case = dict(kind="axial", rpm=F["comp"]["input"]["rpm"], comp=F["comp"], turb=turb, cycle=F["eval"]["cycle"])
trade_file = os.path.join(AXROOT, "data", "phase4ax", f"trade_like_{TAG}.json"); os.makedirs(os.path.dirname(trade_file), exist_ok=True)
json.dump(dict(case=case, eval=F["eval"]), open(trade_file, "w"), default=float)
import rotor_model as rm, rotordynamics as rd, rotordynamics_damped as rdd
rd.IDLE = IDLE
geo = rm.geometry(trade_file); rpm = geo["rpm"]
rows = []
for (t_drum, od, jd), k, c in itertools.product([(None, 0.016, None), (2e-3, 0.024, 0.016), (2e-3, 0.024, 0.012), (2e-3, 0.028, 0.016), (3e-3, 0.024, 0.016)],
                                                (rd.K_SOFT_MIN, rd.K_SOFT, 5e6), (876.0, 2000.0)):
    rot, info = rm.build(geo, "A", k, t_drum=t_drum, shaft_od=od, shaft_id=0.5 * od, journal_od=jd, cxx=c)
    cr = rdd.damped_criticals(rot, 1.6 * rpm); res, ok = rdd.assess(cr, rpm); mp = rm.mass_props(rot, geo, info)
    j = jd if jd else od
    rows.append(dict(t_drum_mm=(t_drum or info["t_drum_mass_model_mm"] / 1e3) * 1e3, shaft_od_mm=od * 1e3, journal_mm=j * 1e3, k=k, c=c, ok=ok,
                     DN_MCS=j * 1e3 * rpm * rd.MCS_F, span_mm=info["span"] * 1e3, overhang_turb_mm=info["overhang_turbine"] * 1e3,
                     crits=";".join(f"{r['crit_rpm']}@AF{r['AF']}" + ("" if r["ok"] else "(X)") for r in res), m_rotor_kg=mp["m_rotor_kg"], Ip_kgm2=mp["Ip_kgm2"],
                     R_front_N=mp["R_front_N_1g"], R_rear_N=mp["R_rear_N_1g"]))
    print({kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in rows[-1].items()}, flush=True)
df = pd.DataFrame(rows); df.to_csv(os.path.join(AXROOT, "data", "phase4ax", f"rotor_{TAG}.csv"), index=False)
rot0, info0 = rm.build(geo, "A", rd.K_SOFT); base = rm.mass_props(rot0, geo, info0)
json.dump(dict(tag=TAG, rpm=rpm, idle=IDLE, mcs=rd.MCS_F, geometry_check=geo["mass_check"], phase3_rotor=base,
               passing=df[df.ok].to_dict("records")), open(os.path.join(AXROOT, "data", "phase4ax", f"rotor_{TAG}.json"), "w"), indent=1, default=float)
print(f"{int(df.ok.sum())} of {len(df)} configurations pass (idle {100*IDLE:.0f} %, MCS {100*rd.MCS_F:.0f} %)")
