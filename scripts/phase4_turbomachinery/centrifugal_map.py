"""Option B check 2 (part): off-design map of a Phase 3 TurboFlow centrifugal stage (run in .venv-np1).

  .venv-np1/Scripts/python scripts/phase4_turbomachinery/centrifugal_map.py <cc_out.json> <map_out.json> [N list]

Same TurboFlow configuration as the design (centrifugal_design.py: Oh losses, Wiesner slip, algebraic vaneless
diffuser, 'custom' vaned-diffuser loss, throat choke check, LHS heuristic initial guess), same geometry. Inlet T0/p0
fixed at the design eye values; the map is swept in rotational speed (fraction of design) and mass flow.
Each point is solved independently (the LHS heuristic guess), failures recorded. Verification: the design point
must reproduce the design run's PR and efficiency.
"""
import sys, json, copy, numpy as np
import turboflow as tf
d = json.load(open(sys.argv[1])); out_file = sys.argv[2]
Ns = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1.0, 1.05, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5, 0.4]
inp = d["input"]; T01, P01, mdot_d = inp["T01"], inp["P01"], inp["mdot"]; omega_d = inp["rpm"] * np.pi / 30
base = dict(turbomachinery="centrifugal_compressor",
            operation_points=dict(fluid_name="air", T0_in=T01, p0_in=P01, mass_flow_rate=mdot_d, omega=omega_d, alpha_in=0.0),
            simulation_options=dict(slip_model="wiesner",
                                    loss_model=dict(impeller=dict(model="oh", loss_coefficient="static_enthalpy_loss"),
                                                    vaneless_diffuser=dict(model="oh", loss_coefficient="static_enthalpy_loss"),
                                                    vaned_diffuser=dict(model="custom", loss_coefficient="static_enthalpy_loss")),
                                    vaneless_diffuser_model="algebraic", rel_step_fd=1e-4,
                                    factors=dict(skin_friction=0.02, wall_heat_flux=0.0, wake_width=0.366),
                                    choking_criterion="evaluate_throat"),
            performance_analysis=dict(performance_map=dict(fluid_name="air", T0_in=T01, p0_in=P01, mass_flow_rate=mdot_d, omega=omega_d, alpha_in=0.0),
                                      solver_options=dict(method="hybr", tolerance=1e-8, max_iterations=100, derivative_method="2-point",
                                                          derivative_abs_step=1e-6, plot_convergence=False, print_convergence=False),
                                      initial_guess=dict(efficiency_impeller=[0.70, 0.95], phi_impeller=[0.15, 0.45], Ma_vaned_diffuser=[0.10, 0.50], n_samples=30)))
base["geometry"] = d["geometry"]
import os
if "CC_ATR" in os.environ:        # sensitivity: impeller throat area ratio (Phase 3 opened it only until the design point was unchoked)
    base["geometry"]["impeller"]["area_throat_ratio"] = float(os.environ["CC_ATR"])
cfg0 = tf.convert_configuration_options(copy.deepcopy(base)) if hasattr(tf, "convert_configuration_options") else copy.deepcopy(base)

def run(Nf, mdot):
    cfg = copy.deepcopy(cfg0)
    op = dict(fluid_name="air", T0_in=T01, p0_in=P01, mass_flow_rate=float(mdot), omega=float(omega_d * Nf), alpha_in=0.0)
    try:
        s = tf.centrifugal_compressor.compute_performance(cfg, op, export_results=False, stop_on_failure=True)[0]
        r = s.problem.results
        ok = bool(getattr(s, "success", True))
        ch = r["impeller"]["throat_plane"].get("choked", None)
        return dict(N=Nf, mdot=float(mdot), PR=float(r["overall"]["PR_tt"]), eta=float(r["overall"]["efficiency_tt"]) / 100,
                    choked=bool(np.ravel(ch)[0]) if ch is not None else None, success=ok)
    except Exception as e:
        return dict(N=Nf, mdot=float(mdot), success=False, err=str(e)[:160])

dp = run(1.0, mdot_d)
print("DESIGN CHECK:", dp, "| design run PR", round(d["turboflow"]["PR"], 4), "eta", round(d["turboflow"]["eta"], 4), flush=True)
pts = []
def dump():
    json.dump(dict(design=dict(T01=T01, P01=P01, mdot=mdot_d, omega=omega_d, rpm=inp["rpm"], check=dp, PR=d["turboflow"]["PR"], eta=d["turboflow"]["eta"]), points=pts),
              open(out_file, "w"), indent=1, default=float)
for Nf in Ns:
    # flow range scales ~ with speed; sweep from high (choke) to low (surge side)
    for f in np.linspace(1.35, 0.35, 21):
        r = run(Nf, mdot_d * Nf * f)
        pts.append(r)
    ok = [p for p in pts if p["N"] == Nf and p.get("success")]
    print(f"N {Nf:.2f}: {len(ok)}/21 converged; " + (f"mdot {min(p['mdot'] for p in ok):.3f}-{max(p['mdot'] for p in ok):.3f}, PR max {max(p['PR'] for p in ok):.3f}" if ok else ""), flush=True)
    dump()
