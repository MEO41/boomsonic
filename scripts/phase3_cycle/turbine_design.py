"""Phase 3 single-stage axial turbine design (run in .venv-np1: TurboFlow 0.1.18 design optimisation).

  .venv-np1/Scripts/python scripts/phase3_cycle/turbine_design.py <in.json> <out.json>

Starts from TurboFlow's own one-stage example (Kofskey/NASA-type stage) and re-targets it:
inlet T0/p0 = T4/P4 from the cycle, exit static pressure from the cycle's turbine pressure
ratio, rotational speed FIXED at the compressor's spool speed, mass-flow equality constraint =
cycle turbine flow. SLSQP maximises total-to-static efficiency over specific speed, blade-jet
ratio (-> mean radius), hub/tip ratios, aspect ratios, pitch/chord, angles (TurboFlow design
variables, same bounds as the example except where stated). Loss model: Benner (as example).
Working fluid: CoolProp 'air' (TurboFlow requires a CoolProp fluid; combustion products at
FAR 0.017 have gamma 1.313 vs air ~1.34 at 1150 K -> noted as a limitation, turbine eta is
reported, the cycle keeps pyCycle's real-gas products).
Tip clearance: rotor 0.30 mm (stator 0). Outputs eta_tt, eta_ts, geometry, radii -> diameter.
STRUCTURAL CONSTRAINT (added; TurboFlow's optimiser has none): rotor blade root stress of a
tapered blade sigma = k rho w^2 (r_t^2 - r_h^2) / 2, k = 0.6, IN-713LC rho 7910, limited to
sigma_allow (default 350 MPa: cast IN-713LC near 780 C metal, ~100-h rupture strength / 1.5 -
conceptual value, to be confirmed with material data in Phase 4). With the example's hub/tip lower
bound 0.6 this becomes a tip-radius constraint r_tip <= sqrt(2 sigma / (k rho w^2 (1 - 0.6^2))).
"""
import sys, os, json, copy, numpy as np
import turboflow as tf

inp = json.load(open(sys.argv[1]))
HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "phase0_tools", "vendor", "turboflow_examples", "one-stage_config.yaml")
cfg = tf.load_config(EX, print_summary=False)
omega = inp["rpm"] * np.pi / 30
op = dict(fluid_name="air", T0_in=float(inp["T04"]), p0_in=float(inp["P04"]), p_out=float(inp["p_out"]), omega=float(omega), alpha_in=0.0)
cfg["operation_points"] = op
cfg["performance_analysis"]["performance_map"] = dict(op)
d = cfg["design_optimization"]
cons = [c for c in d["constraints"] if c["variable"] != "overall.mass_flow_rate"]
cons.append(dict(variable="overall.mass_flow_rate", type="=", value=float(inp["mdot"]), normalize=True))
sig = inp.get("sigma_allow", 350e6); k_t = 0.6; rho_b = 7910.0; ht_min = inp.get("hub_tip_lower", 0.6)
r_tmax = float(np.sqrt(2 * sig / (k_t * rho_b * omega ** 2 * (1 - ht_min ** 2))))
r_stress = r_tmax
if inp.get("r_tip_cap"):                       # optional envelope cap: keep the turbine inside the compressor/combustor casing
    r_tmax = min(r_tmax, float(inp["r_tip_cap"]))
# TurboFlow derives omega from the specific-speed design variable (it does NOT keep the operating-point
# omega), so the shaft speed must be imposed as an equality constraint:
cons.append(dict(variable="overall.angular_speed", type="=", value=float(omega), normalize=True))
for v in ("geometry.radius_tip_in", "geometry.radius_tip_out"):
    cons.append(dict(variable=v, type="<", value=r_tmax, normalize=True))
d["constraints"] = cons
d["variables"]["tip_clearance"]["value"] = [0.0, inp.get("tip_clearance", 0.30e-3)]
# widen specific-speed bounds: at fixed omega the mass-flow constraint pins Ns
d["variables"]["specific_speed"]["lower_bound"] = 0.2; d["variables"]["specific_speed"]["upper_bound"] = 2.0
d["variables"]["blade_jet_ratio"]["lower_bound"] = 0.25; d["variables"]["blade_jet_ratio"]["upper_bound"] = 0.8
if "hub_tip_lower" in inp:
    d["variables"]["hub_tip_ratio_in"]["lower_bound"] = [inp["hub_tip_lower"]] * 2
    d["variables"]["hub_tip_ratio_out"]["lower_bound"] = [inp["hub_tip_lower"]] * 2
cfg = tf.convert_configuration_options(cfg) if hasattr(tf, "convert_configuration_options") else cfg
solver = tf.compute_optimal_turbine(cfg, export_results=False)
r = solver.problem.results; g = solver.problem.geometry
ov = {k: float(np.ravel(v)[0]) for k, v in r["overall"].items() if np.size(v) >= 1 and not isinstance(v, str)}
geo = {k: (np.asarray(v, float).tolist() if not isinstance(v, (str, list)) or isinstance(v, list) else v) for k, v in g.items()
       if k not in ("cascade_type",)}
out = dict(input=inp, r_tip_limit=r_tmax, r_tip_stress_limit=r_stress, success=bool(getattr(solver, "success", True)), overall=ov, geometry=geo,
           r_tip_max=float(np.max(np.concatenate([np.ravel(g["radius_tip_in"]), np.ravel(g["radius_tip_out"])]))),
           r_hub_min=float(np.min(np.concatenate([np.ravel(g["radius_hub_in"]), np.ravel(g["radius_hub_out"])]))),
           r_mean=float(np.ravel(g["radius_mean_in"])[0]))
json.dump(out, open(sys.argv[2], "w"), indent=1, default=lambda o: np.asarray(o).tolist())
print(json.dumps(dict(success=out["success"], eta_tt=ov.get("efficiency_tt"), eta_ts=ov.get("efficiency_ts"), PR_ts=ov.get("PR_ts"),
                      mdot=ov.get("mass_flow_rate"), power_kW=ov.get("power", 0) / 1e3, omega=ov.get("angular_speed"),
                      r_tip_mm=out["r_tip_max"] * 1e3, r_tip_limit_mm=r_tmax * 1e3, r_hub_mm=out["r_hub_min"] * 1e3, r_mean_mm=out["r_mean"] * 1e3), indent=0))
