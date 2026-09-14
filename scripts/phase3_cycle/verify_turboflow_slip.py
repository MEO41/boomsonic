"""Evidence for the TurboFlow Wiesner-slip unit defect and verification of the fix (run in .venv-np1).

  .venv-np1/Scripts/python scripts/phase3_cycle/verify_turboflow_slip.py

For a converged TurboFlow solution the slip factor actually imposed is recovered from the exit triangle:
    sigma_TF = 1 - (U2 + Cm2 tan(beta2b) - Ct2) / U2          (flow_model.py slip-velocity residual)
and compared with Wiesner written correctly (degrees -> radians) and as coded (cos of the degree value).
Cases: the Phase 3 centrifugal design (data/phase3/ce85000_opr4_t1150_cc_out.json) at beta2b -30 deg, the same geometry
at -10 / -20 deg, and the upstream TurboFlow example's -24.5 deg.
"""
import os, sys, json, copy, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import turboflow as tf
import turboflow_fixes as fix

d = json.load(open(os.path.join(ROOT, "data", "phase3", "ce85000_opr4_t1150_cc_out.json")))
inp = d["input"]; omega = inp["rpm"] * np.pi / 30

def config(geo):
    return dict(turbomachinery="centrifugal_compressor",
                operation_points=dict(fluid_name="air", T0_in=inp["T01"], p0_in=inp["P01"], mass_flow_rate=inp["mdot"], omega=omega, alpha_in=0.0),
                simulation_options=dict(slip_model="wiesner",
                                        loss_model=dict(impeller=dict(model="oh", loss_coefficient="static_enthalpy_loss"),
                                                        vaneless_diffuser=dict(model="oh", loss_coefficient="static_enthalpy_loss"),
                                                        vaned_diffuser=dict(model="custom", loss_coefficient="static_enthalpy_loss")),
                                        vaneless_diffuser_model="algebraic", rel_step_fd=1e-4,
                                        factors=dict(skin_friction=0.02, wall_heat_flux=0.0, wake_width=0.366), choking_criterion="evaluate_throat"),
                performance_analysis=dict(performance_map=dict(fluid_name="air", T0_in=inp["T01"], p0_in=inp["P01"], mass_flow_rate=inp["mdot"], omega=omega, alpha_in=0.0),
                                          solver_options=dict(method="hybr", tolerance=1e-8, max_iterations=100, derivative_method="2-point",
                                                              derivative_abs_step=1e-6, plot_convergence=False, print_convergence=False),
                                          initial_guess=dict(efficiency_impeller=[0.70, 0.95], phi_impeller=[0.15, 0.45], Ma_vaned_diffuser=[0.10, 0.50], n_samples=30)),
                geometry=copy.deepcopy(geo))

def solve(beta2b):
    geo = copy.deepcopy(d["geometry"]); geo["impeller"]["trailing_edge_angle"] = beta2b
    cfg = config(geo); cfg = tf.convert_configuration_options(cfg)
    try:
        s = tf.centrifugal_compressor.compute_performance(cfg, cfg["operation_points"], export_results=False, stop_on_failure=True)[0]
    except Exception as e:
        return dict(beta2b=beta2b, ok=False, err=str(e)[:120])
    r = s.problem.results; ex = r["impeller"]["exit_plane"]
    U, Cm, Ct = float(ex["blade_speed"]), float(ex["v_m"]), float(ex["v_t"])
    sig = 1 - (U + Cm * np.tan(np.radians(beta2b)) - Ct) / U
    Z = geo["impeller"]["number_of_blades"]
    return dict(beta2b=beta2b, ok=bool(getattr(s, "success", True)), sigma_TF=sig,
                sigma_wiesner=1 - np.sqrt(np.cos(np.radians(beta2b))) / Z ** 0.7,
                sigma_as_coded=1 - np.sqrt(np.cos(beta2b) + 0j).real / Z ** 0.7 if np.cos(beta2b) >= 0 else np.nan,
                PR=float(r["overall"]["PR_tt"]), eta=float(r["overall"]["efficiency_tt"]) / 100)

rows = []
for label, patched in (("stock TurboFlow", False), ("with turboflow_fixes", True)):
    fix.apply() if patched else fix.revert()
    for b in (-30.0, -24.5, -20.0, -10.0):
        r = solve(b); r["run"] = label; rows.append(r)
        if r["ok"]:
            print(f"{label:22s} beta2b {b:6.1f}: sigma solved {r['sigma_TF']:.4f} | Wiesner (deg) {r['sigma_wiesner']:.4f} | as coded {r['sigma_as_coded']:.4f}"
                  f" | PR {r['PR']:.3f} eta {r['eta']:.4f}", flush=True)
        else:
            print(f"{label:22s} beta2b {b:6.1f}: no solution ({r.get('err', 'solver did not converge')})", flush=True)
json.dump(rows, open(os.path.join(ROOT, "data", "phase3r_turboflow_slip_check.json"), "w"), indent=1, default=float)
