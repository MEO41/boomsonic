"""Phase 6A: flow-path AREA / capacity check of the axial engine as drawn (run in .venv).

A packaging model is an area model: once every annulus is drawn at its real radii, the flow each station can pass
is fixed. This script walks the drawn flow path station by station and compares the required mass flow with the
station's choked capacity at the cycle's own total conditions:

    W_choke = A p0 sqrt(gamma / (R T0)) (2 / (gamma + 1)) ^ ((gamma + 1) / (2 (gamma - 1)))

Areas come from the Phase 6A parameter sheet (the same radii the CAD is built from), total conditions from the
fielded cycle. Blade blockage is reported but NOT subtracted from the capacity (so the capacity is optimistic).

Output: data/phase6a/flowpath_check.json
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
OUT = os.path.join(AXROOT, "data", "phase6a")
E = json.load(open(os.path.join(OUT, "axial_params.json")))
v = lambda sec, k: E[sec][k]["value"]

R_AIR, G_AIR = 287.05, 1.4
G_HOT = 1.3300288720728621                                   # cycle t_out_gamma
CP_HOT = 1165.309428384867                                   # cycle t_out_Cp
R_HOT = CP_HOT * (G_HOT - 1) / G_HOT

def w_choke(A, p0, T0, gam, R):
    return A * p0 * math.sqrt(gam / (R * T0)) * (2 / (gam + 1)) ** ((gam + 1) / (2 * (gam - 1)))

W = v("cycle", "W"); FAR = 0.015400346999660065               # cycle FAR (axt fielded)
W_hot = W * (1 + FAR)
Pt2, Tt2 = v("cycle", "Pt2"), v("cycle", "Tt2")
Pt5, Tt5 = v("cycle", "Pt5"), v("cycle", "Tt5")

rows = []
# ---- compressor rows: total conditions from the cumulative stage pressure ratios
pt, tt = Pt2, Tt2
for st in E["compressor"]["stages"]:
    for kind in ("rotor", "stator"):
        b = st[kind]
        A = math.pi * (b["r_tip"] ** 2 - b["r_hub"] ** 2)
        blockage = b["Z"] * b["t_max"] * (b["r_tip"] - b["r_hub"]) / A      # blade metal fraction at max thickness
        rows.append(dict(station=f"stage {st['stage']} {kind}", x=b["x_le"], A_m2=A, A_cm2=A * 1e4,
                         blade_blockage=blockage, p0=pt, T0=tt, W_req=W,
                         W_choke=w_choke(A, pt, tt, G_AIR, R_AIR)))
    pt *= st["PR"]; tt = tt * st["PR"] ** ((G_AIR - 1) / G_AIR / 0.87)      # approx, for the capacity reference only

# ---- turbine exit annulus (the area the drawn engine actually has) and the nozzle throat
A_turb = math.pi * (v("turbine", "r_tip") ** 2 - v("turbine", "r_hub") ** 2)
A8 = v("cycle", "A8")
rows.append(dict(station="turbine exit annulus", x=v("turbine", "x_rotor_le") + v("turbine", "c_rotor"),
                 A_m2=A_turb, A_cm2=A_turb * 1e4, blade_blockage=None, p0=Pt5, T0=Tt5, W_req=W_hot,
                 W_choke=w_choke(A_turb, Pt5, Tt5, G_HOT, R_HOT)))
rows.append(dict(station="nozzle throat A8 (x1.0)", x=v("nozzle", "x_exit"), A_m2=A8, A_cm2=A8 * 1e4,
                 blade_blockage=None, p0=Pt5, T0=Tt5, W_req=W_hot, W_choke=w_choke(A8, Pt5, Tt5, G_HOT, R_HOT)))
A8_max = A8 * v("nozzle", "a8_max")
rows.append(dict(station=f"nozzle throat A8 (x{v('nozzle', 'a8_max'):.1f})", x=v("nozzle", "x_exit"), A_m2=A8_max,
                 A_cm2=A8_max * 1e4, blade_blockage=None, p0=Pt5, T0=Tt5, W_req=W_hot,
                 W_choke=w_choke(A8_max, Pt5, Tt5, G_HOT, R_HOT)))

for r in rows:
    r["margin"] = r["W_choke"] / r["W_req"] - 1.0
    r["chokes"] = bool(r["W_choke"] < r["W_req"])

# ---- the specific question: where is the minimum area of the hot end, and is A8 really the throat?
min_hot = min((A_turb, "turbine exit annulus"), (A8, "nozzle throat at A8 x1.0"))
res = dict(
    note=("Phase 6A flow-path area check of the axial engine AS DRAWN. Exploratory: this is a consequence of the "
          "frozen geometry, not a new design. Nothing here is fixed or re-sized."),
    W_inlet=W, W_hot=W_hot, FAR=FAR,
    A_turbine_exit_cm2=A_turb * 1e4, A8_cm2=A8 * 1e4, A8_max_cm2=A8_max * 1e4,
    A8_over_A_turbine_exit=A8 / A_turb,
    minimum_hot_area=min_hot[1],
    turbine_exit_capacity_kgps=w_choke(A_turb, Pt5, Tt5, G_HOT, R_HOT),
    turbine_exit_shortfall=W_hot / w_choke(A_turb, Pt5, Tt5, G_HOT, R_HOT) - 1.0,
    turboflow_exit_velocity_mps=408.30294269206115,
    turboflow_exit_flow_angle_deg=-19.470037138026424,
    turboflow_Pt_out_Pa=485191.01416324056 / 2.6370474864632323,
    cycle_Pt5_Pa=Pt5,
    turb_pout_assumed_exit_M=0.45,
    stations=rows)
json.dump(res, open(os.path.join(OUT, "flowpath_check.json"), "w"), indent=1, default=float)

print("Phase 6A flow-path area check (engine as drawn)\n")
print(f"{'station':<26}{'A [cm2]':>10}{'W_req':>8}{'W_choke':>9}{'margin':>9}  ")
for r in rows:
    flag = "  <-- CHOKES" if r["chokes"] else ""
    print(f"{r['station']:<26}{r['A_cm2']:>10.2f}{r['W_req']:>8.3f}{r['W_choke']:>9.3f}{r['margin'] * 100:>8.1f}%{flag}")
print(f"\nA8 / A_turbine_exit = {A8 / A_turb:.3f}  -> the minimum hot-end area is the {min_hot[1]}")
print(f"turbine exit capacity at the fielded Pt5 {Pt5 / 1e3:.1f} kPa: {res['turbine_exit_capacity_kgps']:.3f} kg/s "
      f"vs {W_hot:.3f} required ({res['turbine_exit_shortfall'] * 100:+.1f} %)")
print(f"TurboFlow's own exit: {res['turboflow_exit_velocity_mps']:.0f} m/s at {res['turboflow_exit_flow_angle_deg']:.1f} deg, "
      f"Pt_out {res['turboflow_Pt_out_Pa'] / 1e3:.1f} kPa; arch_trade.turb_pout assumed exit M {res['turb_pout_assumed_exit_M']}")
